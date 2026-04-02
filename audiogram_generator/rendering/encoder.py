"""Video encoding: assembles audio, waveform, and frames into an MP4 audiogram."""
import logging
import os
import re
import shutil
import numpy as np
from PIL import Image
from typing import Optional
from moviepy import VideoClip, AudioFileClip

from .compositor import COLOR_ORANGE, COLOR_BEIGE, COLOR_WHITE, COLOR_BLACK
from .waveform import get_waveform_data
from .layouts import (
    FORMATS, LAYOUT_CONFIGS,
    _precompute_transcript, _precompute_header, _precompute_cta,
    create_audiogram_frame,
)

logger = logging.getLogger(__name__)


def generate_audiogram(audio_path, output_path, format_name, podcast_logo_path,
                        podcast_title, episode_title, transcript_chunks, duration,
                        formats=None, colors=None,
                        show_subtitles=True, *,
                        header_title_source: Optional[str] = None,
                        header_soundbite_title: Optional[str] = None,
                        fonts=None, cta=None):
    """Generate a complete audiogram video.

    Args:
        audio_path: Path to the audio file
        output_path: Path to the output video file
        format_name: 'vertical', 'square', or 'horizontal'
        podcast_logo_path: Path to the podcast logo image
        podcast_title: Podcast title string
        episode_title: Episode title string
        transcript_chunks: List of timed transcript chunks
        duration: Video duration in seconds
        formats: Optional dict with custom format dimensions
        colors: Optional dict with custom color values
        show_subtitles: Whether to overlay subtitle text
        header_title_source: Source key for header text ('auto', 'podcast', etc.)
        header_soundbite_title: Soundbite title used when source is 'soundbite'
        fonts: Optional dict with font paths ('header', 'transcript')
    """
    if formats is None or format_name not in formats:
        width, height = FORMATS[format_name]
    else:
        fmt = formats[format_name]
        width = fmt.get('width', FORMATS[format_name][0])
        height = fmt.get('height', FORMATS[format_name][1])

    fps = 24

    if colors is None:
        colors_tuples = {
            'primary': COLOR_ORANGE,
            'background': COLOR_BEIGE,
            'text': COLOR_WHITE,
            'transcript_bg': COLOR_BLACK,
        }
    else:
        colors_tuples = {
            'primary': tuple(colors.get('primary', COLOR_ORANGE)),
            'background': tuple(colors.get('background', COLOR_BEIGE)),
            'text': tuple(colors.get('text', COLOR_WHITE)),
            'transcript_bg': tuple(colors.get('transcript_bg', COLOR_BLACK)),
        }

    logger.info("  - Extracting waveform...")
    waveform_data = get_waveform_data(audio_path, fps=fps)

    logger.info("  - Pre-loading logo...")
    layout_config = LAYOUT_CONFIGS.get(format_name, LAYOUT_CONFIGS['vertical'])
    logo_img = None
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        central_height_px = int(height * layout_config['central_ratio'])
        if 'logo_width_ratio' in layout_config:
            logo_size = int(min(width * layout_config['logo_width_ratio'],
                                central_height_px * layout_config['logo_size_ratio']))
        else:
            logo_size = int(min(width, central_height_px) * layout_config['logo_size_ratio'])
        logo_img = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        logo.close()

    bar_spacing = 3
    bar_width = 12
    num_bars = width // (bar_width + bar_spacing)
    if num_bars % 2 != 0:
        num_bars -= 1
    waveform_sensitivities = None
    if num_bars >= 2:
        rng = np.random.default_rng(42)
        half = rng.uniform(0.6, 1.4, num_bars // 2)
        waveform_sensitivities = np.concatenate([half, half[::-1]])

    logger.info("  - Pre-computing transcript layout...")
    transcript_cache = _precompute_transcript(width, height, layout_config, colors_tuples, fonts)

    logger.info("  - Pre-computing header layout...")
    header_cache = _precompute_header(
        width, height, layout_config, fonts,
        podcast_title, episode_title,
        header_title_source, header_soundbite_title,
    )

    cta_cache = None
    if cta and cta.get('enabled'):
        logger.info("  - Pre-computing CTA layout...")
        cta_cache = _precompute_cta(height, fonts)

    logger.info("  - Video frame generation...")
    chunks_for_render = transcript_chunks if show_subtitles else []

    def make_frame(t):
        return create_audiogram_frame(
            width, height,
            logo_img,
            podcast_title,
            episode_title,
            waveform_data,
            t,
            chunks_for_render,
            duration,
            colors_tuples,
            format_name,
            header_title_source,
            header_soundbite_title,
            fonts=fonts,
            waveform_sensitivities=waveform_sensitivities,
            header_cache=header_cache,
            transcript_cache=transcript_cache,
            cta_config=cta,
            cta_cache=cta_cache,
        )

    video = VideoClip(make_frame, duration=duration)
    video.fps = fps

    logger.info("  - Adding audio...")
    audio = AudioFileClip(audio_path)
    video = video.with_audio(audio)

    logger.info("  - Rendering video...")
    video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=fps,
        threads=4,
        preset='veryfast',
    )

    try:
        base = os.path.basename(output_path)
        m = re.search(r"(ep\d+)_sb(\d+)", base)
        if m:
            ep_tag = m.group(1)
            sb_tag = m.group(2)
            dest_path = os.path.join(os.path.dirname(output_path), f"{ep_tag}_sb{sb_tag}.mp3")
            shutil.copyfile(audio_path, dest_path)
    except Exception as e:
        logger.warning("Could not save audio segment in output: %s", e)
