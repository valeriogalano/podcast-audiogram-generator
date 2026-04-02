"""Rendering facade wrapping the legacy video generator.

This module exposes a small, stable API that the CLI can call without knowing
implementation details of the underlying rendering engine. It simply delegates
to ``video_generator.generate_audiogram``.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from audiogram_generator import video_generator


def generate_audiogram(
    audio_path: str,
    output_path: str,
    format_name: str,
    logo_path: str,
    podcast_title: str,
    episode_title: str,
    transcript_chunks: List[Dict],
    duration: float,
    formats: Optional[Dict],
    colors: Optional[Dict],
    show_subtitles: bool = True,
    *,
    header_title_source: Optional[str] = None,
    header_soundbite_title: Optional[str] = None,
    fonts: Optional[Dict] = None,
    cta: Optional[Dict] = None,
) -> None:
    """Legacy-compatible wrapper used by the CLI and tests.

    This keeps the existing call sites unchanged while allowing the CLI to
    import the function from the rendering layer instead of the monolithic
    video module.
    """
    video_generator.generate_audiogram(
        audio_path,
        output_path,
        format_name,
        logo_path,
        podcast_title,
        episode_title,
        transcript_chunks,
        duration,
        formats,
        colors,
        show_subtitles,
        header_title_source=header_title_source,
        header_soundbite_title=header_soundbite_title,
        fonts=fonts,
        cta=cta,
    )
