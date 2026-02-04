"""
Example script demonstrating lift shaft sketch generation.

Run from the repository root:
    python -m prototypes.sketch_generator.generate_samples

Or from within the prototypes/sketch_generator directory:
    python generate_samples.py

Options:
    --machine-type mrl      Generate MRL (Machine Room Less) samples (default)
    --machine-type mra      Generate MRA (Machine Room Above) samples
    --view plan             Generate plan view sketches only
    --view section-mrl      Generate MRL section view sketches only
    --view section-mra      Generate MRA section view sketches only
    --view all              Generate both plan and section views (default)
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path if running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from prototypes.sketch_generator import LiftShaftSketch, LiftConfig, LiftSectionSketch, SectionConfig


def generate_mrl_samples(output_dir: Path) -> None:
    """Generate MRL (Machine Room Less) sample lift shaft sketches."""
    print("Generating MRL lift shaft sketches...")

    # =========================================================================
    # SIMPLE API EXAMPLES (Backward Compatible)
    # =========================================================================

    print("\n" + "=" * 60)
    print("SIMPLE API EXAMPLES (Backward Compatible)")
    print("=" * 60)

    # Example 1: Single lift with default parameters
    print("\n1. Single lift (default parameters)...")
    sketch1 = LiftShaftSketch()
    path1 = sketch1.generate(
        output_dir / "01_single_lift_default.png",
        title="SINGLE LIFT SHAFT PLAN",
    )
    print(f"   Saved: {path1}")

    # Example 2: Single lift with custom dimensions
    print("\n2. Single lift (custom dimensions)...")
    sketch2 = LiftShaftSketch(
        shaft_width=2500,
        shaft_depth=2000,
        wall_thickness=250,
        structural_opening_width=1200,
    )
    path2 = sketch2.generate(
        output_dir / "02_single_lift_custom.png",
        title="SINGLE LIFT SHAFT PLAN",
    )
    print(f"   Saved: {path2}")

    # Example 3: 2-lift bank (simple API)
    print("\n3. Two-lift bank (simple API)...")
    sketch3 = LiftShaftSketch(
        shaft_width=2600,
        shaft_depth=2100,
        num_lifts=2,
    )
    path3 = sketch3.generate(
        output_dir / "03_two_lift_bank_simple.png",
        title="TWO-LIFT BANK PLAN",
    )
    print(f"   Saved: {path3}")

    # Example 4: 3-lift bank
    print("\n4. Three-lift bank...")
    sketch4 = LiftShaftSketch(
        shaft_width=2400,
        shaft_depth=1900,
        wall_thickness=200,
        shared_wall_thickness=150,
        structural_opening_width=1100,
        num_lifts=3,
    )
    path4 = sketch4.generate(
        output_dir / "04_three_lift_bank.png",
        title="THREE-LIFT BANK PLAN",
    )
    print(f"   Saved: {path4}")

    # =========================================================================
    # ENHANCED API EXAMPLES (New Features)
    # =========================================================================

    print("\n" + "=" * 60)
    print("ENHANCED API EXAMPLES (New Features)")
    print("=" * 60)

    # Example 5: Single lift with car interior details
    print("\n5. Single lift with car interior (enhanced API)...")
    lift5 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        counterweight_bracket_width=625,
        car_bracket_width=375,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch5 = LiftShaftSketch(
        lifts=[lift5],
        shaft_depth=2300,
        wall_thickness=200,
    )
    path5 = sketch5.generate(
        output_dir / "05_single_lift_enhanced.png",
        title="LIFT SHAFT PLAN - ENHANCED",
        show_car_interior=True,
        show_brackets=True,
        show_capacity=False,
        show_accessibility=False,
    )
    print(f"   Calculated shaft width: {lift5.shaft_width}mm")
    print(f"   (625 CW + {lift5.unfinished_car_width} car + 375 bracket)")
    print(f"   Saved: {path5}")

    # Example 6: Two passenger lifts in common shaft (steel beam separator)
    print("\n6. Two passenger lifts - common shaft (steel beam separator)...")
    lift6a = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    lift6b = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    sketch6 = LiftShaftSketch(
        lifts=[lift6a, lift6b],
        is_common_shaft=True,  # This triggers steel beam separator
        shaft_depth=2300,
        wall_thickness=200,
    )
    path6 = sketch6.generate(
        output_dir / "06_two_passenger_common_shaft.png",
        title="TWO-LIFT BANK - COMMON SHAFT",
    )
    print(f"   Separator type: {sketch6._separator_type}")
    print(f"   Saved: {path6}")

    # Example 7: Fire + Passenger lift in common shaft (RCC wall separator)
    # Fire lift MUST be at position 0 (first position) and use valid cabin size
    print("\n7. Fire + Passenger lift - common shaft (RCC wall separator, dual boundary)...")
    lift7a = LiftConfig(
        lift_type="fire",
        lift_capacity=1800,
        finished_car_width=1500,  # Valid fire lift size: 1500x2300
        finished_car_depth=2300,
        counterweight_bracket_width=625,
        car_bracket_width=375,
        door_width=1100,
        structural_opening_width=1300,
    )
    lift7b = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,  # Shallower than fire lift
        counterweight_bracket_width=625,
        car_bracket_width=375,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch7 = LiftShaftSketch(
        lifts=[lift7a, lift7b],  # Fire at position 0
        is_common_shaft=True,  # Fire lift triggers RCC wall (200mm)
        wall_thickness=200,
    )
    path7 = sketch7.generate(
        output_dir / "07_fire_passenger_dual_boundary.png",
        title="FIRE + PASSENGER LIFT (DUAL BOUNDARY)",
    )
    print(f"   Separator type: {sketch7._separator_type}")
    print(f"   Fire lift shaft depth: {sketch7._shaft_depths[0]}mm")
    print(f"   Passenger lift shaft depth: {sketch7._shaft_depths[1]}mm")
    print(f"   Max shaft depth (envelope): {sketch7._max_shaft_depth}mm")
    print(f"   Saved: {path7}")

    # Example 8: Fire lift + Two passenger lifts (fire at position 0)
    print("\n8. Fire + Two passenger lifts (fire at position 0)...")
    lift8a = LiftConfig(
        lift_type="fire",
        lift_capacity=1800,
        finished_car_width=1550,  # Valid fire lift size: 1550x2200
        finished_car_depth=2200,
        counterweight_bracket_width=625,
        car_bracket_width=375,
    )
    lift8b = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    lift8c = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    sketch8 = LiftShaftSketch(
        lifts=[lift8a, lift8b, lift8c],  # Fire at position 0
        is_common_shaft=True,
        wall_thickness=200,
    )
    path8 = sketch8.generate(
        output_dir / "08_fire_two_passenger.png",
        title="FIRE + TWO PASSENGER LIFTS",
    )
    print(f"   Separator type: {sketch8._separator_type}")
    print(f"   Shaft depths: {[int(d) for d in sketch8._shaft_depths]}mm")
    print(f"   Saved: {path8}")

    # Example 9: Different capacities in same bank
    print("\n9. Different capacity lifts in same bank...")
    lift9a = LiftConfig(
        lift_type="passenger",
        lift_capacity=1000,
        finished_car_width=1600,
        finished_car_depth=1400,
        counterweight_bracket_width=550,
        car_bracket_width=350,
    )
    lift9b = LiftConfig(
        lift_type="passenger",
        lift_capacity=1600,
        finished_car_width=2100,
        finished_car_depth=1800,
        counterweight_bracket_width=700,
        car_bracket_width=400,
    )
    sketch9 = LiftShaftSketch(
        lifts=[lift9a, lift9b],
        is_common_shaft=True,
        shaft_depth=2400,
        wall_thickness=200,
    )
    path9 = sketch9.generate(
        output_dir / "09_different_capacities.png",
        title="MIXED CAPACITY LIFT BANK",
    )
    print(f"   Lift 1 shaft width: {lift9a.shaft_width}mm")
    print(f"   Lift 2 shaft width: {lift9b.shaft_width}mm")
    print(f"   Saved: {path9}")

    # =========================================================================
    # FIRE LIFT EXAMPLES
    # =========================================================================

    print("\n" + "=" * 60)
    print("FIRE LIFT EXAMPLES (Fixed Cabin Sizes)")
    print("=" * 60)

    # Example 10: Single fire lift (1400x2400)
    print("\n10. Single fire lift (1400x2400 - largest depth)...")
    lift10 = LiftConfig(
        lift_type="fire",
        lift_capacity=1800,
        finished_car_width=1400,  # Valid fire lift size: 1400x2400
        finished_car_depth=2400,
        counterweight_bracket_width=625,
        car_bracket_width=375,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch10 = LiftShaftSketch(
        lifts=[lift10],
        wall_thickness=200,
    )
    path10 = sketch10.generate(
        output_dir / "10_single_fire_lift.png",
        title="FIRE LIFT SHAFT PLAN",
    )
    print(f"   Cabin size: {int(lift10.finished_car_width)}x{int(lift10.finished_car_depth)}mm")
    print(f"   Shaft width: {int(lift10.shaft_width)}mm")
    print(f"   Shaft depth: {int(sketch10.shaft_depth)}mm")
    print(f"   Saved: {path10}")

    # Example 11: Single fire lift (1550x2200)
    print("\n11. Single fire lift (1550x2200 - widest option)...")
    lift11 = LiftConfig(
        lift_type="fire",
        lift_capacity=1800,
        finished_car_width=1550,  # Valid fire lift size: 1550x2200
        finished_car_depth=2200,
        counterweight_bracket_width=625,
        car_bracket_width=375,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch11 = LiftShaftSketch(
        lifts=[lift11],
        wall_thickness=200,
    )
    path11 = sketch11.generate(
        output_dir / "11_fire_lift_1550x2200.png",
        title="FIRE LIFT SHAFT PLAN (1550x2200)",
    )
    print(f"   Cabin size: {int(lift11.finished_car_width)}x{int(lift11.finished_car_depth)}mm")
    print(f"   Shaft width: {int(lift11.shaft_width)}mm")
    print(f"   Shaft depth: {int(sketch11.shaft_depth)}mm")
    print(f"   Saved: {path11}")

    # =========================================================================
    # FACING BANKS EXAMPLES (Dual Bank Configuration)
    # =========================================================================

    print("\n" + "=" * 60)
    print("FACING BANKS EXAMPLES (Two Banks Facing Each Other)")
    print("=" * 60)

    # Example 12: Two banks facing - 2+2 symmetric configuration
    print("\n12. Two banks facing (2+2 symmetric)...")
    bank1_lift1 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank1_lift2 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank2_lift1 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank2_lift2 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch12 = LiftShaftSketch(
        lifts=[bank1_lift1, bank1_lift2],
        lifts_bank2=[bank2_lift1, bank2_lift2],
        lobby_width=4000,
        is_common_shaft=True,
        wall_thickness=200,
    )
    path12 = sketch12.generate(
        output_dir / "12_facing_banks_2x2.png",
        title="LIFT LOBBY - 2+2 FACING",
    )
    print(f"   Bank 1: {sketch12.num_lifts} lifts")
    print(f"   Bank 2: {sketch12.num_lifts_bank2} lifts")
    print(f"   Lobby width: {sketch12.lobby_width}mm")
    print(f"   Total depth: {sketch12.total_depth}mm")
    print(f"   Saved: {path12}")

    # Example 13: Two banks facing - 3+2 asymmetric (Fire + 2 passenger vs 2 passenger)
    print("\n13. Two banks facing (3+2 asymmetric with fire lift)...")
    bank1_fire = LiftConfig(
        lift_type="fire",
        lift_capacity=1800,
        finished_car_width=1500,  # Valid fire lift size
        finished_car_depth=2300,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank1_pass1 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank1_pass2 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank2_pass1 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    bank2_pass2 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch13 = LiftShaftSketch(
        lifts=[bank1_fire, bank1_pass1, bank1_pass2],  # Fire at position 0
        lifts_bank2=[bank2_pass1, bank2_pass2],
        lobby_width=4500,
        is_common_shaft=True,
        wall_thickness=200,
    )
    path13 = sketch13.generate(
        output_dir / "13_facing_banks_3x2_fire.png",
        title="LIFT LOBBY - FIRE + 2 PASSENGER vs 2 PASSENGER",
    )
    print(f"   Bank 1: {sketch13.num_lifts} lifts (fire + 2 passenger)")
    print(f"   Bank 2: {sketch13.num_lifts_bank2} lifts")
    print(f"   Bank 1 max depth: {sketch13._max_shaft_depth}mm")
    print(f"   Bank 2 max depth: {sketch13._max_shaft_depth_bank2}mm")
    print(f"   Saved: {path13}")

    # Example 14: Two banks facing - 4+4 max configuration
    print("\n14. Two banks facing (4+4 max configuration)...")
    max_lifts = [
        LiftConfig(lift_type="passenger", lift_capacity=1350, finished_car_width=1900, finished_car_depth=1600)
        for _ in range(4)
    ]
    max_lifts_bank2 = [
        LiftConfig(lift_type="passenger", lift_capacity=1350, finished_car_width=1900, finished_car_depth=1600)
        for _ in range(4)
    ]
    sketch14 = LiftShaftSketch(
        lifts=max_lifts,
        lifts_bank2=max_lifts_bank2,
        lobby_width=5000,
        is_common_shaft=True,
        wall_thickness=200,
    )
    path14 = sketch14.generate(
        output_dir / "14_facing_banks_4x4_max.png",
        title="LIFT LOBBY - 4+4 MAX CONFIGURATION",
    )
    print(f"   Bank 1: {sketch14.num_lifts} lifts")
    print(f"   Bank 2: {sketch14.num_lifts_bank2} lifts")
    print(f"   Total lifts: {sketch14.num_lifts + sketch14.num_lifts_bank2}")
    print(f"   Total width: {sketch14.total_width}mm")
    print(f"   Total depth: {sketch14.total_depth}mm")
    print(f"   Saved: {path14}")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    print("\n" + "=" * 60)
    print(f"All MRL samples generated in: {output_dir.absolute()}")
    print("=" * 60)

    # Print LiftConfig calculations summary
    print("\nMRL LiftConfig Calculation Reference:")
    print("-" * 40)
    sample_lift = LiftConfig(
        finished_car_width=1900,
        finished_car_depth=1600,
        counterweight_bracket_width=625,
        car_bracket_width=375,
    )
    print(f"  Finished car: {sample_lift.finished_car_width}mm x {sample_lift.finished_car_depth}mm")
    print(f"  Unfinished car: {sample_lift.unfinished_car_width}mm x {sample_lift.unfinished_car_depth}mm")
    print(f"  Shaft width = CW({sample_lift.counterweight_bracket_width}) + Car({sample_lift.unfinished_car_width}) + Bracket({sample_lift.car_bracket_width})")
    print(f"             = {sample_lift.shaft_width}mm")

    # Print fire lift cabin sizes
    print("\nFire Lift Cabin Sizes (Width x Depth):")
    print("-" * 40)
    from prototypes.sketch_generator import FIRE_LIFT_CABIN_SIZES
    for w, d in FIRE_LIFT_CABIN_SIZES:
        print(f"  {w}mm x {d}mm")

    # Print facing banks summary
    print("\nFacing Banks Configuration:")
    print("-" * 40)
    print("  Max 4 lifts per bank")
    print("  Max 8 lifts total (4+4)")
    print("  Default lobby width: 4000mm")


def generate_mra_samples(output_dir: Path) -> None:
    """Generate MRA (Machine Room Above) sample lift shaft sketches."""
    print("Generating MRA lift shaft sketches...")

    # =========================================================================
    # MRA SINGLE LIFT EXAMPLES
    # =========================================================================

    print("\n" + "=" * 60)
    print("MRA (Machine Room Above) EXAMPLES")
    print("=" * 60)

    # Example 1: Single MRA lift with default parameters
    print("\n1. Single MRA lift (default parameters)...")
    lift1 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch1 = LiftShaftSketch(
        lifts=[lift1],
        wall_thickness=200,
    )
    path1 = sketch1.generate(
        output_dir / "01_single_lift_mra.png",
        title="MRA LIFT SHAFT PLAN",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
        show_accessibility=False,
    )
    print(f"   Calculated shaft width: {lift1.shaft_width}mm")
    print(f"   (2 × {lift1.mra_car_bracket_width} car brackets + {lift1.unfinished_car_width} car)")
    print(f"   Calculated shaft depth: {sketch1.shaft_depth}mm")
    print(f"   Saved: {path1}")

    # Example 2: Single MRA lift with custom car bracket width
    print("\n2. Single MRA lift (custom car brackets)...")
    lift2 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1600,
        finished_car_width=2100,
        finished_car_depth=1800,
        mra_car_bracket_width=300,  # Custom car bracket width
        mra_cw_bracket_depth=600,   # Custom CW bracket depth
        door_width=1200,
        structural_opening_width=1400,
    )
    sketch2 = LiftShaftSketch(
        lifts=[lift2],
        wall_thickness=200,
    )
    path2 = sketch2.generate(
        output_dir / "02_single_lift_mra_custom.png",
        title="MRA LIFT SHAFT PLAN - CUSTOM",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
    )
    print(f"   Calculated shaft width: {lift2.shaft_width}mm")
    print(f"   Calculated shaft depth: {sketch2.shaft_depth}mm")
    print(f"   Saved: {path2}")

    # Example 3: Two MRA lifts in common shaft
    print("\n3. Two MRA lifts - common shaft (steel beam separator)...")
    lift3a = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    lift3b = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch3 = LiftShaftSketch(
        lifts=[lift3a, lift3b],
        is_common_shaft=True,
        wall_thickness=200,
        steel_beam_width=150,
    )
    path3 = sketch3.generate(
        output_dir / "03_two_lift_mra_bank.png",
        title="TWO MRA LIFT BANK",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
    )
    print(f"   Separator type: {sketch3._separator_type}")
    print(f"   Total width: {sketch3.total_width}mm")
    print(f"   Saved: {path3}")

    # Example 4: Single MRA fire lift
    print("\n4. Single MRA fire lift...")
    lift4 = LiftConfig(
        lift_machine_type="mra",
        lift_type="fire",
        finished_car_width=1400,
        finished_car_depth=2400,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch4 = LiftShaftSketch(
        lifts=[lift4],
        wall_thickness=200,
    )
    path4 = sketch4.generate(
        output_dir / "04_single_fire_lift_mra.png",
        title="MRA FIRE LIFT SHAFT PLAN",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
    )
    print(f"   Shaft width: {lift4.shaft_width}mm")
    print(f"   Saved: {path4}")

    # Example 5: MRA fire + passenger lifts in common shaft
    print("\n5. MRA fire + passenger lifts (common shaft)...")
    lift5a = LiftConfig(
        lift_machine_type="mra",
        lift_type="fire",
        finished_car_width=1400,
        finished_car_depth=2400,
        door_width=1100,
        structural_opening_width=1300,
    )
    lift5b = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
    )
    sketch5 = LiftShaftSketch(
        lifts=[lift5a, lift5b],
        is_common_shaft=True,
        wall_thickness=200,
        shared_wall_thickness=200,  # RCC wall for fire lift separation
    )
    path5 = sketch5.generate(
        output_dir / "05_fire_passenger_mra_bank.png",
        title="MRA FIRE + PASSENGER BANK",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
    )
    print(f"   Separator type: {sketch5._separator_type}")
    print(f"   Saved: {path5}")

    # Example 6: MRA facing banks (2+2 symmetric)
    print("\n6. MRA facing banks (2+2 symmetric)...")
    bank1_lifts = [
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
    ]
    bank2_lifts = [
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
    ]
    sketch6 = LiftShaftSketch(
        lifts=bank1_lifts,
        lifts_bank2=bank2_lifts,
        is_common_shaft=True,
        wall_thickness=200,
        steel_beam_width=150,
        lobby_width=4000,
    )
    path6 = sketch6.generate(
        output_dir / "06_facing_banks_mra_2x2.png",
        title="MRA FACING BANKS (2+2)",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
    )
    print(f"   Bank 1: {len(bank1_lifts)} lifts")
    print(f"   Bank 2: {len(bank2_lifts)} lifts")
    print(f"   Lobby depth: {sketch6.lobby_width}mm")
    print(f"   Saved: {path6}")

    # Example 7: MRA facing banks with fire lift (3+2 asymmetric)
    print("\n7. MRA facing banks with fire lift (3+2 asymmetric)...")
    bank1_lifts_fire = [
        LiftConfig(
            lift_machine_type="mra",
            lift_type="fire",
            finished_car_width=1400,
            finished_car_depth=2400,
            door_width=1100,
            structural_opening_width=1300,
        ),
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
    ]
    bank2_lifts_fire = [
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
        LiftConfig(
            lift_machine_type="mra",
            lift_type="passenger",
            lift_capacity=1350,
            finished_car_width=1900,
            finished_car_depth=1600,
            door_width=1100,
            structural_opening_width=1300,
        ),
    ]
    sketch7 = LiftShaftSketch(
        lifts=bank1_lifts_fire,
        lifts_bank2=bank2_lifts_fire,
        is_common_shaft=True,
        wall_thickness=200,
        shared_wall_thickness=200,
        lobby_width=4000,
    )
    path7 = sketch7.generate(
        output_dir / "07_facing_banks_mra_fire_3x2.png",
        title="MRA FACING BANKS - FIRE + PASSENGER (3+2)",
        show_car_interior=True,
        show_brackets=True,
        show_lift_doors=True,
        show_capacity=False,
    )
    print(f"   Bank 1: {len(bank1_lifts_fire)} lifts (fire + 2 passenger)")
    print(f"   Bank 2: {len(bank2_lifts_fire)} lifts")
    print(f"   Saved: {path7}")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    print("\n" + "=" * 60)
    print(f"All MRA samples generated in: {output_dir.absolute()}")
    print("=" * 60)

    # Print MRA LiftConfig calculations summary
    print("\nMRA LiftConfig Calculation Reference:")
    print("-" * 40)
    sample_lift = LiftConfig(
        lift_machine_type="mra",
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    print(f"  Finished car: {sample_lift.finished_car_width}mm x {sample_lift.finished_car_depth}mm")
    print(f"  Unfinished car: {sample_lift.unfinished_car_width}mm x {sample_lift.unfinished_car_depth}mm")
    print(f"  Shaft width = 2 × CarBracket({sample_lift.mra_car_bracket_width}) + Car({sample_lift.unfinished_car_width})")
    print(f"             = {sample_lift.shaft_width}mm")
    print(f"  CW bracket depth: {sample_lift.mra_cw_bracket_depth}mm (at top of shaft)")


def generate_section_mrl_samples(output_dir: Path) -> None:
    """Generate MRL section view lift shaft sketches."""
    print("Generating MRL SECTION VIEW lift shaft sketches...")

    # =========================================================================
    # MRL SECTION VIEW EXAMPLES
    # =========================================================================

    print("\n" + "=" * 60)
    print("MRL SECTION VIEW EXAMPLES (Cross-sectional view from door side)")
    print("=" * 60)

    # Example 1: Basic section with default parameters
    print("\n1. Basic section view (default parameters)...")
    section1 = LiftSectionSketch()
    path1 = section1.generate(
        output_dir / "section_01_basic.png",
        title="LIFT SHAFT SECTION",
    )
    print(f"   Saved: {path1}")

    # Example 2: Section view using LiftConfig for dimensional consistency
    print("\n2. Section view with LiftConfig (consistent with plan view)...")
    lift2 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        counterweight_bracket_width=625,
        car_bracket_width=375,
        door_width=1100,
        structural_opening_width=1300,
        structural_opening_height=2200,
    )
    section2 = LiftSectionSketch(
        lift_config=lift2,
        wall_thickness=200,
    )
    path2 = section2.generate(
        output_dir / "section_02_with_lift_config.png",
        title="LIFT SHAFT SECTION - 1350 KG",
    )
    print(f"   Shaft width from LiftConfig: {lift2.shaft_width}mm")
    print(f"   Saved: {path2}")

    # Example 3: Custom section configuration
    print("\n3. Section view with custom SectionConfig...")
    section_cfg = SectionConfig(
        pit_depth=1500,
        overhead_clearance=4500,
        travel_height=45000,  # 45m travel
        floor_height=3500,
        car_interior_height=2600,
    )
    lift3 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1600,
        finished_car_width=2100,
        finished_car_depth=1800,
        door_width=1200,
        structural_opening_width=1400,
        structural_opening_height=2300,
    )
    section3 = LiftSectionSketch(
        lift_config=lift3,
        section_config=section_cfg,
        wall_thickness=250,
    )
    path3 = section3.generate(
        output_dir / "section_03_custom_config.png",
        title="LIFT SHAFT SECTION - HIGH RISE",
        subtitle=f"Travel: {section_cfg.travel_height/1000:.0f}m | Pit: {section_cfg.pit_depth}mm",
    )
    print(f"   Travel height: {section_cfg.travel_height}mm")
    print(f"   Pit depth: {section_cfg.pit_depth}mm")
    print(f"   Saved: {path3}")

    # Example 4: Section without break lines (shows full detail)
    print("\n4. Section view without break lines...")
    section4 = LiftSectionSketch(
        shaft_width=2600,
        wall_thickness=200,
    )
    path4 = section4.generate(
        output_dir / "section_04_no_break_lines.png",
        title="LIFT SHAFT SECTION - FULL VIEW",
        show_break_lines=False,
    )
    print(f"   Saved: {path4}")

    # Example 5: Schematic section (minimal details)
    print("\n5. Schematic section view (minimal details)...")
    section5 = LiftSectionSketch(
        shaft_width=2400,
        wall_thickness=200,
    )
    path5 = section5.generate(
        output_dir / "section_05_schematic.png",
        title="LIFT SHAFT SECTION - SCHEMATIC",
        show_hatching=False,
    )
    print(f"   Saved: {path5}")

    # Example 6: Section with all features enabled
    print("\n6. Section view with all features...")
    lift6 = LiftConfig(
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
        structural_opening_height=2200,
    )
    section6 = LiftSectionSketch(
        lift_config=lift6,
        section_config=SectionConfig(
            pit_depth=1200,
            overhead_clearance=4200,
        ),
        wall_thickness=200,
    )
    path6 = section6.generate(
        output_dir / "section_06_full_features.png",
        title="LIFT SHAFT SECTION - COMPLETE",
        show_hatching=True,
        show_dimensions=True,
        show_pit=True,
        show_break_lines=True,
    )
    print(f"   Saved: {path6}")

    # Example 7: High DPI section for print
    print("\n7. High DPI section (300 dpi for print)...")
    section7 = LiftSectionSketch(
        lift_config=lift6,
        wall_thickness=200,
    )
    path7 = section7.generate(
        output_dir / "section_07_high_dpi.png",
        title="LIFT SHAFT SECTION",
        dpi=300,
    )
    print(f"   Saved: {path7}")

    # Example 8: Section as bytes (API usage)
    print("\n8. Section view as bytes (API usage)...")
    section8 = LiftSectionSketch(
        shaft_width=2600,
        wall_thickness=200,
    )
    png_bytes = section8.to_bytes(
        title="LIFT SHAFT SECTION",
    )
    bytes_path = output_dir / "section_08_from_bytes.png"
    with open(bytes_path, "wb") as f:
        f.write(png_bytes)
    print(f"   Generated {len(png_bytes):,} bytes, saved: {bytes_path}")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    print("\n" + "=" * 60)
    print(f"All MRL section view samples generated in: {output_dir.absolute()}")
    print("=" * 60)

    # Print SectionConfig reference
    print("\nSectionConfig Reference:")
    print("-" * 40)
    default_section = SectionConfig()
    print(f"  Pit depth: {default_section.pit_depth}mm")
    print(f"  Overhead clearance: {default_section.overhead_clearance}mm")
    print(f"  Travel height: {default_section.travel_height}mm")
    print(f"  Floor height: {default_section.floor_height}mm")
    print(f"  Car interior height: {default_section.car_interior_height}mm")
    print(f"  Total shaft height: {default_section.total_shaft_height}mm")


def generate_section_mra_samples(output_dir: Path) -> None:
    """Generate MRA (Machine Room Above) section view lift shaft sketches."""
    print("Generating MRA SECTION VIEW lift shaft sketches...")

    # =========================================================================
    # MRA SECTION VIEW EXAMPLES
    # =========================================================================

    print("\n" + "=" * 60)
    print("MRA SECTION VIEW EXAMPLES (Cross-sectional view with machine room)")
    print("=" * 60)

    # Example 1: Basic MRA section with default parameters
    print("\n1. Basic MRA section view (default parameters)...")
    lift1 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
        structural_opening_height=2200,
    )
    section1 = LiftSectionSketch(
        lift_config=lift1,
        wall_thickness=200,
    )
    path1 = section1.generate(
        output_dir / "section_mra_01_basic.png",
        title="MRA LIFT SHAFT SECTION",
    )
    print(f"   Machine room height: {section1.machine_room_height}mm")
    print(f"   Saved: {path1}")

    # Example 2: MRA section with custom machine room height
    print("\n2. MRA section view with custom machine room height...")
    lift2 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1600,
        finished_car_width=2100,
        finished_car_depth=1800,
        door_width=1200,
        structural_opening_width=1400,
        structural_opening_height=2300,
    )
    section_cfg2 = SectionConfig(
        pit_depth=1500,
        overhead_clearance=4500,
        travel_height=45000,  # 45m travel
        machine_room_height=3500,  # Custom machine room height
    )
    section2 = LiftSectionSketch(
        lift_config=lift2,
        section_config=section_cfg2,
        wall_thickness=250,
    )
    path2 = section2.generate(
        output_dir / "section_mra_02_custom.png",
        title="MRA LIFT SHAFT SECTION - HIGH RISE",
        subtitle=f"Travel: {section_cfg2.travel_height/1000:.0f}m | Machine Room: {section_cfg2.machine_room_height}mm",
    )
    print(f"   Machine room height: {section2.machine_room_height}mm")
    print(f"   Saved: {path2}")

    # Example 3: MRA section without break lines
    print("\n3. MRA section view without break lines...")
    lift3 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    section3 = LiftSectionSketch(
        lift_config=lift3,
        wall_thickness=200,
    )
    path3 = section3.generate(
        output_dir / "section_mra_03_no_break_lines.png",
        title="MRA LIFT SHAFT SECTION - FULL VIEW",
        show_break_lines=False,
    )
    print(f"   Saved: {path3}")

    # Example 4: MRA schematic section (minimal details)
    print("\n4. MRA schematic section view (minimal details)...")
    lift4 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    section4 = LiftSectionSketch(
        lift_config=lift4,
        wall_thickness=200,
    )
    path4 = section4.generate(
        output_dir / "section_mra_04_schematic.png",
        title="MRA LIFT SHAFT SECTION - SCHEMATIC",
        show_hatching=False,
    )
    print(f"   Saved: {path4}")

    # Example 5: MRA section with all features
    print("\n5. MRA section view with all features...")
    lift5 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
        door_width=1100,
        structural_opening_width=1300,
        structural_opening_height=2200,
    )
    section5 = LiftSectionSketch(
        lift_config=lift5,
        section_config=SectionConfig(
            pit_depth=1200,
            overhead_clearance=4200,
            machine_room_height=3000,
        ),
        wall_thickness=200,
    )
    path5 = section5.generate(
        output_dir / "section_mra_05_full_features.png",
        title="MRA LIFT SHAFT SECTION - COMPLETE",
        show_hatching=True,
        show_dimensions=True,
        show_pit=True,
        show_break_lines=True,
    )
    print(f"   Saved: {path5}")

    # Example 6: MRA section as bytes (API usage)
    print("\n6. MRA section view as bytes (API usage)...")
    lift6 = LiftConfig(
        lift_machine_type="mra",
        lift_type="passenger",
        lift_capacity=1350,
        finished_car_width=1900,
        finished_car_depth=1600,
    )
    section6 = LiftSectionSketch(
        lift_config=lift6,
        wall_thickness=200,
    )
    png_bytes = section6.to_bytes(
        title="MRA LIFT SHAFT SECTION",
    )
    bytes_path = output_dir / "section_mra_06_from_bytes.png"
    with open(bytes_path, "wb") as f:
        f.write(png_bytes)
    print(f"   Generated {len(png_bytes):,} bytes, saved: {bytes_path}")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    print("\n" + "=" * 60)
    print(f"All MRA section view samples generated in: {output_dir.absolute()}")
    print("=" * 60)

    # Print MRA SectionConfig reference
    print("\nMRA SectionConfig Reference:")
    print("-" * 40)
    default_section = SectionConfig()
    print(f"  Pit depth: {default_section.pit_depth}mm")
    print(f"  Overhead clearance: {default_section.overhead_clearance}mm")
    print(f"  Travel height: {default_section.travel_height}mm")
    print(f"  Machine room height: {default_section.machine_room_height}mm (MRA specific)")
    print(f"  Total shaft height: {default_section.total_shaft_height}mm")


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Generate lift shaft sketch samples.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_samples.py                              # Generate MRL plan samples (default)
  python generate_samples.py --machine-type mrl
  python generate_samples.py --machine-type mra
  python generate_samples.py --machine-type all
  python generate_samples.py --view section-mrl           # Generate MRL section view samples
  python generate_samples.py --view section-mra           # Generate MRA section view samples
  python generate_samples.py --view all                   # Generate all views (plan + section)
  python generate_samples.py --machine-type mrl --view all
        """
    )
    parser.add_argument(
        "--machine-type",
        choices=["mrl", "mra", "all"],
        default="mrl",
        help="Lift machine type: mrl (Machine Room Less), mra (Machine Room Above), or all"
    )
    parser.add_argument(
        "--view",
        choices=["plan", "section-mrl", "section-mra", "all"],
        default="plan",
        help="View type: plan (top-down), section-mrl (MRL cross-sectional), section-mra (MRA cross-sectional), or all"
    )
    args = parser.parse_args()

    # Create output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Generate samples based on view type and machine type
    if args.view == "section-mrl":
        generate_section_mrl_samples(output_dir)
    elif args.view == "section-mra":
        generate_section_mra_samples(output_dir)
    elif args.view == "all":
        # Generate plan views first
        if args.machine_type == "mrl":
            generate_mrl_samples(output_dir)
        elif args.machine_type == "mra":
            generate_mra_samples(output_dir)
        else:  # all machine types
            generate_mrl_samples(output_dir)
            print("\n" + "=" * 60 + "\n")
            generate_mra_samples(output_dir)
        # Then generate section views (both MRL and MRA)
        print("\n" + "=" * 60 + "\n")
        generate_section_mrl_samples(output_dir)
        print("\n" + "=" * 60 + "\n")
        generate_section_mra_samples(output_dir)
    else:  # plan view only
        if args.machine_type == "mrl":
            generate_mrl_samples(output_dir)
        elif args.machine_type == "mra":
            generate_mra_samples(output_dir)
        else:  # all
            generate_mrl_samples(output_dir)
            print("\n" + "=" * 60 + "\n")
            generate_mra_samples(output_dir)


if __name__ == "__main__":
    main()
