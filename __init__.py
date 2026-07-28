"""
Lift Shaft Sketch Generator

A Python module for generating parametric elevator/lift shaft diagrams as PNG images.
Supports single lifts and multi-lift banks with configurable dimensions.

Includes:
- Plan view: Top-down shaft layouts (LiftShaftSketch)
- Section view: Cross-sectional views from door side (LiftSectionSketch)

Enhanced features:
- Lift car interiors with finished/unfinished boundaries
- Counterweight and car brackets
- Steel beam separators for common shaft configurations
- Fire lift configurations with RCC walls
- Capacity labels, C.O.P markers, and accessibility symbols
- Machine room configurations (MRL/MRA)
- Break lines for multi-floor sections
"""

if __package__:
    from .shaft_sketch import (
        FIRE_LIFT_CABIN_SIZES,
        LiftConfig,
        LiftShaftSketch,
        determine_separator_types,
    )
    from .section_sketch import LiftSectionSketch, SectionConfig
    from .drawing_utils import brief_spec_row, format_brief_capacity
    from . import config
else:  # pytest may collect this folder as a top-level module
    from shaft_sketch import (
        FIRE_LIFT_CABIN_SIZES,
        LiftConfig,
        LiftShaftSketch,
        determine_separator_types,
    )
    from section_sketch import LiftSectionSketch, SectionConfig
    from drawing_utils import brief_spec_row, format_brief_capacity
    import config

__all__ = [
    "LiftShaftSketch",
    "LiftSectionSketch",
    "LiftConfig",
    "SectionConfig",
    "determine_separator_types",
    "FIRE_LIFT_CABIN_SIZES",
    "brief_spec_row",
    "format_brief_capacity",
    "config",
]
__version__ = "0.3.0"
