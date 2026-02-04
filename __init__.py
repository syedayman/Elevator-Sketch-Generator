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

from .shaft_sketch import (
    LiftShaftSketch,
    LiftConfig,
    determine_separator_type,
    validate_fire_lift_positions,
    FIRE_LIFT_CABIN_SIZES,
)
from .section_sketch import LiftSectionSketch, SectionConfig
from . import config

__all__ = [
    "LiftShaftSketch",
    "LiftSectionSketch",
    "LiftConfig",
    "SectionConfig",
    "determine_separator_type",
    "validate_fire_lift_positions",
    "FIRE_LIFT_CABIN_SIZES",
    "config",
]
__version__ = "0.3.0"
