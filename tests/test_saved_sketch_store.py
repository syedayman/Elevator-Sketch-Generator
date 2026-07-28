from types import SimpleNamespace

import pytest

import saved_sketch_store as store_mod
import saved_sketches as saved
import sketch_state as ss


USER_ID = "974c9abb-7e82-4b73-a6fc-f522bf5ebc3d"
SKETCH_ID = "2f99134d-aebb-4018-8d7c-f1e53f79c074"
CREATED_AT = "2026-07-27T12:00:00Z"
UPDATED_AT = "2026-07-28T08:30:00Z"


def _snapshot(name="Hotel Core A"):
    return saved.build_snapshot(
        name,
        ss.make_default_config(),
        saved.make_view_state(),
    )


def _row(name="Hotel Core A"):
    snapshot = _snapshot(name)
    return {
        "id": SKETCH_ID,
        "user_id": USER_ID,
        "app_scope": saved.APP_SCOPE,
        "summary": saved.config_summary(snapshot["config"]),
        **snapshot,
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
    }


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.calls = []

    def _call(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return self

    def select(self, *args, **kwargs):
        return self._call("select", *args, **kwargs)

    def insert(self, *args, **kwargs):
        return self._call("insert", *args, **kwargs)

    def update(self, *args, **kwargs):
        return self._call("update", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._call("delete", *args, **kwargs)

    def eq(self, *args, **kwargs):
        return self._call("eq", *args, **kwargs)

    def order(self, *args, **kwargs):
        return self._call("order", *args, **kwargs)

    def limit(self, *args, **kwargs):
        return self._call("limit", *args, **kwargs)

    def execute(self):
        self.client.queries.append(self)
        response = self.client.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(data=response)


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.queries = []

    def table(self, name):
        return FakeQuery(self, name)


def _store(client):
    return store_mod.SavedSketchStore(client, USER_ID)


def _eq_filters(query):
    return {args[0]: args[1] for method, args, _ in query.calls if method == "eq"}


def test_list_is_scoped_and_returns_metadata():
    row = _row()
    metadata = {
        key: row[key]
        for key in (
            "id",
            "name",
            "schema_version",
            "summary",
            "created_at",
            "updated_at",
        )
    }
    client = FakeClient([metadata])

    result = _store(client).list_sketches()

    assert result == [metadata]
    assert _eq_filters(client.queries[0]) == {
        "user_id": USER_ID,
        "app_scope": saved.APP_SCOPE,
    }


def test_create_adds_owner_scope_and_summary():
    client = FakeClient([_row()])

    result = _store(client).create_sketch(_snapshot())

    assert result["id"] == SKETCH_ID
    insert_payload = next(
        args[0] for method, args, _ in client.queries[0].calls if method == "insert"
    )
    assert insert_payload["user_id"] == USER_ID
    assert insert_payload["app_scope"] == saved.APP_SCOPE
    assert insert_payload["summary"] == "MRL · 1 core · 1 lift"


def test_get_and_delete_are_both_owner_scoped():
    client = FakeClient([_row()], [{"id": SKETCH_ID}])
    sketch_store = _store(client)

    record = sketch_store.get_sketch(SKETCH_ID)
    sketch_store.delete_sketch(SKETCH_ID)

    assert record["name"] == "Hotel Core A"
    for query in client.queries:
        assert _eq_filters(query) == {
            "id": SKETCH_ID,
            "user_id": USER_ID,
            "app_scope": saved.APP_SCOPE,
        }


def test_delete_reports_a_missing_sketch():
    client = FakeClient([])

    with pytest.raises(store_mod.SketchNotFoundError, match="not found"):
        _store(client).delete_sketch(SKETCH_ID)


def test_update_uses_optimistic_timestamp_guard():
    client = FakeClient([_row("Renamed")])

    result = _store(client).update_sketch(
        SKETCH_ID,
        _snapshot("Renamed"),
        expected_updated_at=CREATED_AT,
    )

    assert result["name"] == "Renamed"
    assert _eq_filters(client.queries[0])["updated_at"] == CREATED_AT


def test_duplicate_name_error_is_user_friendly():
    error = RuntimeError("duplicate key value violates unique constraint (23505)")
    client = FakeClient(error)

    with pytest.raises(
        store_mod.DuplicateSketchNameError,
        match="already exists",
    ):
        _store(client).create_sketch(_snapshot())


def test_invalid_gate_user_id_is_rejected_before_network():
    with pytest.raises(store_mod.SketchStoreError, match="UUID"):
        store_mod.SavedSketchStore(FakeClient(), "shared-team")
