"""Audiogram video generator — compatibility re-export shim.

All implementation has been split into the ``rendering`` sub-package:
  - rendering/compositor.py  — PIL drawing primitives, color/font defaults
  - rendering/waveform.py    — waveform data extraction
  - rendering/layouts.py     — layout configs and per-frame rendering
  - rendering/encoder.py     — video encoding (generate_audiogram)

This module re-exports every public symbol so existing call-sites remain
unchanged (facade.py, tests, etc.).
"""
from audiogram_generator.rendering.compositor import (  # noqa: F401
    DEFAULT_FONT_PATH,
    COLOR_ORANGE,
    COLOR_BEIGE,
    COLOR_WHITE,
    COLOR_BLACK,
    _subtitle_default_style,
    _strip_punctuation,
    _draw_rounded_box_with_shadow,
    _render_subtitle_lines,
    _draw_text_with_stroke,
    _draw_pill_with_text,
)
from audiogram_generator.rendering.waveform import get_waveform_data  # noqa: F401
from audiogram_generator.rendering.layouts import (  # noqa: F401
    FORMATS,
    HEADER_LINE_SPACING,
    LAYOUT_CONFIGS,
    _resolve_header_text,
    _precompute_header,
    _render_header,
    _render_waveform,
    _render_logo,
    _render_footer,
    _precompute_transcript,
    _render_transcript,
    _precompute_cta,
    _render_cta,
    _create_unified_layout,
    create_layout,
    create_audiogram_frame,
)
from audiogram_generator.rendering.encoder import generate_audiogram  # noqa: F401
