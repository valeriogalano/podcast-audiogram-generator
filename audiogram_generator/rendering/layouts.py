"""Layout definitions and per-frame rendering functions."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Optional

from .compositor import (
    DEFAULT_FONT_PATH,
    COLOR_ORANGE, COLOR_BEIGE, COLOR_WHITE, COLOR_BLACK,
    _subtitle_default_style,
    _strip_punctuation,
    _draw_rounded_box_with_shadow,
    _render_subtitle_lines,
    _draw_text_with_stroke,
)

# Social media video formats: (width, height)
FORMATS = {
    'vertical': (1080, 1920),
    'square': (1080, 1080),
    'horizontal': (1920, 1080),
}

# Line spacing multiplier for multi-line headers
HEADER_LINE_SPACING = 1.45

# Per-format layout ratios and parameters
LAYOUT_CONFIGS = {
    'vertical': {
        'header_ratio': 0.17,
        'central_ratio': 0.54,
        'footer_ratio': 0.27,
        'logo_size_ratio': 0.6,
        'transcript_font_size': 0.028,
        'transcript_y_offset': 0.84,
        'max_lines': 5,
    },
    'square': {
        'header_ratio': 0.12,
        'central_ratio': 0.66,
        'footer_ratio': 0.20,
        'logo_size_ratio': 0.5,
        'transcript_font_size': 0.030,
        'transcript_y_offset': 0.15,
        'max_lines': 3,
    },
    'horizontal': {
        'header_ratio': 0.15,
        'central_ratio': 0.68,
        'footer_ratio': 0.15,
        'logo_size_ratio': 0.6,
        'logo_width_ratio': 0.3,
        'transcript_font_size': 0.030,
        'transcript_y_offset': 0.12,
        'max_lines': 2,
    },
}


def _resolve_header_text(podcast_title, episode_title, header_title_source, header_soundbite_title):
    """Resolve which text to show in the header based on source config."""
    src = (header_title_source or 'auto').lower()
    if src == 'none':
        return None
    if src == 'podcast':
        return (podcast_title or '').strip() or None
    if src == 'episode':
        return (episode_title or '').strip() or None
    if src == 'soundbite':
        text = (header_soundbite_title or '').strip()
        return text or (episode_title or podcast_title or '').strip() or None
    # auto
    if episode_title and str(episode_title).strip():
        return str(episode_title).strip()
    if podcast_title and str(podcast_title).strip():
        return str(podcast_title).strip()
    return None


def _precompute_header(width, height, layout_config, fonts, podcast_title, episode_title,
                        header_title_source=None, header_soundbite_title=None):
    """Run font size-negotiation once and return a cache dict for _render_header.

    Returns None if there is no text to display.
    """
    header_height = int(height * layout_config['header_ratio'])
    header_text = _resolve_header_text(podcast_title, episode_title,
                                        header_title_source, header_soundbite_title)
    if not header_text:
        return {'header_height': header_height, 'lines': [], 'font': None,
                'base_h': 0, 'total_text_h': 0, 'pad_x': 0, 'pad_y': 0}

    pad_x = int(width * 0.04)
    pad_y = int(header_height * 0.10)
    max_width = width - 2 * pad_x
    max_height = header_height - 2 * pad_y

    tmp_img = Image.new('RGB', (width, header_height))
    tmp_draw = ImageDraw.Draw(tmp_img)

    header_font_path = DEFAULT_FONT_PATH
    if fonts and fonts.get('header'):
        header_font_path = fonts['header']

    size = max(16, int(header_height * 0.15))
    min_size = 12
    font_header = ImageFont.load_default()
    lines: list = []
    base_h = 0
    total_text_h = 0

    while size >= min_size:
        try:
            try:
                font_header = ImageFont.truetype(header_font_path, size=size, index=1)
            except Exception:
                font_header = ImageFont.truetype(header_font_path, size=size)
        except Exception:
            font_header = ImageFont.load_default()

        words = header_text.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + (" " if cur else "") + w)
            bbox = tmp_draw.textbbox((0, 0), test, font=font_header)
            if (bbox[2] - bbox[0]) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
            if len(lines) >= 3:
                break
        if cur and len(lines) < 3:
            lines.append(cur)

        if lines:
            lines = lines[:3]

            def ellipsize(text_line: str) -> str:
                if not text_line:
                    return text_line
                ell = "…"
                while True:
                    b = tmp_draw.textbbox((0, 0), text_line, font=font_header)
                    if (b[2] - b[0]) <= max_width or len(text_line) <= 1:
                        return text_line
                    text_line = text_line[:-2] + ell if len(text_line) > 2 else ell

            lines[-1] = ellipsize(lines[-1])

            line_heights = []
            for ln in lines:
                b = tmp_draw.textbbox((0, 0), ln, font=font_header)
                line_heights.append(b[3] - b[1])
            base_h = max(line_heights) if line_heights else 0
            total_text_h = sum(
                base_h if i == 0 else int(base_h * HEADER_LINE_SPACING)
                for i in range(len(line_heights))
            )
        else:
            base_h = 0
            total_text_h = 0

        if total_text_h <= max_height:
            break
        size -= 2

    tmp_img.close()
    return {
        'header_height': header_height,
        'lines': lines,
        'font': font_header,
        'base_h': base_h,
        'total_text_h': total_text_h,
        'pad_x': pad_x,
        'pad_y': pad_y,
    }


def _render_header(draw, width, height, layout_config, colors, podcast_title, episode_title,
                    header_title_source=None, header_soundbite_title=None, fonts=None,
                    header_cache=None):
    """Render the header bar with title text.

    If ``header_cache`` is provided the font size-negotiation is skipped.
    Returns header_height in pixels.
    """
    header_height = int(height * layout_config['header_ratio'])
    draw.rectangle([(0, 0), (width, header_height)], fill=colors['primary'])

    if header_cache is not None:
        lines = header_cache['lines']
        font_header = header_cache['font']
        base_h = header_cache['base_h']
        total_text_h = header_cache['total_text_h']
        pad_x = header_cache['pad_x']
        pad_y = header_cache['pad_y']
    else:
        cache = _precompute_header(width, height, layout_config, fonts,
                                    podcast_title, episode_title,
                                    header_title_source, header_soundbite_title)
        lines = cache['lines']
        font_header = cache['font']
        base_h = cache['base_h']
        total_text_h = cache['total_text_h']
        pad_x = cache['pad_x']
        pad_y = cache['pad_y']

    if lines:
        start_y = header_height - pad_y - total_text_h
        text_fill = tuple(colors.get('text', COLOR_WHITE))
        cy = start_y
        for i, ln in enumerate(lines):
            bbox = draw.textbbox((0, 0), ln, font=font_header)
            lw = bbox[2] - bbox[0]
            text_x = (width - lw) // 2
            _draw_text_with_stroke(draw, (text_x, cy), ln, font_header, text_fill,
                                   stroke_width=2, stroke_fill=(30, 30, 30))
            cy += (base_h if i == 0 else int(base_h * HEADER_LINE_SPACING))

    return header_height


def _render_waveform(draw, width, central_top, central_height, waveform_data,
                      current_time, audio_duration, colors, sensitivities=None):
    """Render the waveform visualizer in the central area."""
    if waveform_data is None or len(waveform_data) == 0:
        return

    bar_spacing = 3
    bar_width = 12
    total_bar_width = bar_width + bar_spacing

    num_bars = width // total_bar_width
    if num_bars % 2 != 0:
        num_bars -= 1

    if num_bars < 2:
        return

    frame_idx = (int((current_time / audio_duration) * len(waveform_data))
                 if audio_duration > 0 else 0)
    frame_idx = min(frame_idx, len(waveform_data) - 1)
    current_amplitude = waveform_data[frame_idx]

    if sensitivities is None or len(sensitivities) != num_bars:
        rng = np.random.default_rng(42)
        half = rng.uniform(0.6, 1.4, num_bars // 2)
        sensitivities = np.concatenate([half, half[::-1]])

    for i in range(num_bars):
        x = i * total_bar_width
        center_idx = num_bars // 2
        distance_from_center = abs(i - center_idx)
        center_boost = (1.0 + (1.0 - distance_from_center / center_idx) * 0.4
                        if center_idx > 0 else 1.0)
        bar_amplitude = current_amplitude * sensitivities[i] * center_boost

        min_height = int(central_height * 0.03)
        max_height = int(central_height * 0.70)
        bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
        bar_height = max(min_height, min(bar_height, max_height))

        y_center = central_top + central_height // 2
        y_top = y_center - bar_height // 2
        y_bottom = y_center + bar_height // 2

        draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])


def _render_logo(img, width, central_top, central_height, logo_img):
    """Render the podcast logo (pre-loaded) in the central area."""
    if logo_img is None:
        return
    logo_size = logo_img.width
    logo_x = (width - logo_size) // 2
    logo_y = central_top + (central_height - logo_size) // 2
    img.paste(logo_img, (logo_x, logo_y), logo_img if logo_img.mode == 'RGBA' else None)


def _render_footer(draw, width, height, central_bottom, colors):
    """Render the footer bar."""
    draw.rectangle([(0, central_bottom), (width, height)], fill=colors['primary'])


def _precompute_transcript(width, height, layout_config, colors, fonts=None):
    """Pre-compute all static transcript rendering data (font, style, position).

    Returns a cache dict to be passed to _render_transcript every frame.
    """
    try:
        transcript_font_path = DEFAULT_FONT_PATH
        if fonts and fonts.get('transcript'):
            transcript_font_path = fonts['transcript']
        font_transcript = ImageFont.truetype(
            transcript_font_path,
            size=int(height * layout_config['transcript_font_size']),
        )
    except Exception:
        font_transcript = ImageFont.load_default()

    style = _subtitle_default_style(colors)
    style['max_lines'] = min(style.get('max_lines', 5), layout_config['max_lines'])
    max_width = int(width * style['width_ratio'])

    header_height = int(height * layout_config['header_ratio'])
    central_height = int(height * layout_config['central_ratio'])
    central_top = header_height
    central_bottom = central_top + central_height

    if layout_config['transcript_y_offset'] < 0.5:
        transcript_y = central_bottom - int(central_height * layout_config['transcript_y_offset'])
    else:
        transcript_y = central_top + int(central_height * layout_config['transcript_y_offset'])

    return {
        'font': font_transcript,
        'style': style,
        'max_width': max_width,
        'transcript_y': transcript_y,
    }


def _render_transcript(img, draw, width, height, central_top, central_height, central_bottom,
                        transcript_chunks, current_time, layout_config, colors, fonts=None,
                        transcript_cache=None):
    """Render the transcript/subtitle text.

    Returns updated (img, draw).
    """
    if not transcript_chunks:
        return img, draw

    current_text = ""
    for chunk in transcript_chunks:
        if chunk['start'] <= current_time < chunk['end']:
            current_text = chunk['text']
            break

    if not current_text:
        return img, draw

    current_text = _strip_punctuation(current_text)

    if transcript_cache is not None:
        font_transcript = transcript_cache['font']
        style = transcript_cache['style']
        max_width = transcript_cache['max_width']
        transcript_y = transcript_cache['transcript_y']
    else:
        cache = _precompute_transcript(width, height, layout_config, colors, fonts)
        font_transcript = cache['font']
        style = cache['style']
        max_width = cache['max_width']
        transcript_y = cache['transcript_y']

    img, _ = _render_subtitle_lines(img, draw, current_text, font_transcript,
                                     transcript_y, max_width, style)
    draw = ImageDraw.Draw(img)
    return img, draw


def _create_unified_layout(img, draw, width, height, logo_img, podcast_title, episode_title,
                             waveform_data, current_time, transcript_chunks, audio_duration,
                             colors, layout_config,
                             header_title_source: Optional[str] = None,
                             header_soundbite_title: Optional[str] = None,
                             fonts=None, waveform_sensitivities=None,
                             header_cache=None, transcript_cache=None):
    """Unified layout for all video formats."""
    header_height = _render_header(
        draw, width, height, layout_config, colors,
        podcast_title, episode_title,
        header_title_source, header_soundbite_title, fonts,
        header_cache=header_cache,
    )

    central_top = header_height
    central_height = int(height * layout_config['central_ratio'])
    central_bottom = central_top + central_height

    _render_waveform(draw, width, central_top, central_height, waveform_data,
                      current_time, audio_duration, colors,
                      sensitivities=waveform_sensitivities)
    _render_logo(img, width, central_top, central_height, logo_img)
    _render_footer(draw, width, height, central_bottom, colors)

    img, draw = _render_transcript(
        img, draw, width, height, central_top, central_height, central_bottom,
        transcript_chunks, current_time, layout_config, colors, fonts,
        transcript_cache=transcript_cache,
    )

    return img


def create_layout(img, draw, width, height, logo_img, podcast_title, episode_title,
                   waveform_data, current_time, transcript_chunks, audio_duration,
                   colors, format_name='vertical',
                   header_title_source: Optional[str] = None,
                   header_soundbite_title: Optional[str] = None,
                   fonts=None, waveform_sensitivities=None,
                   header_cache=None, transcript_cache=None):
    """Creates the layout for the specified format.

    Supported formats: 'vertical', 'square', 'horizontal'.
    """
    layout_config = LAYOUT_CONFIGS.get(format_name, LAYOUT_CONFIGS['vertical'])
    return _create_unified_layout(
        img, draw, width, height, logo_img, podcast_title, episode_title,
        waveform_data, current_time, transcript_chunks, audio_duration, colors,
        layout_config, header_title_source, header_soundbite_title,
        fonts=fonts, waveform_sensitivities=waveform_sensitivities,
        header_cache=header_cache, transcript_cache=transcript_cache,
    )


def create_audiogram_frame(width, height, logo_img, podcast_title, episode_title,
                            waveform_data, current_time, transcript_chunks, audio_duration,
                            colors_tuples, format_name='vertical',
                            header_title_source: Optional[str] = None,
                            header_soundbite_title: Optional[str] = None,
                            fonts=None, waveform_sensitivities=None,
                            header_cache=None, transcript_cache=None):
    """Creates a single audiogram frame as a numpy RGB array."""
    import numpy as np

    img = Image.new('RGB', (width, height), colors_tuples['background'])
    draw = ImageDraw.Draw(img)

    img = create_layout(
        img, draw, width, height, logo_img, podcast_title, episode_title,
        waveform_data, current_time, transcript_chunks, audio_duration,
        colors_tuples, format_name, header_title_source, header_soundbite_title,
        fonts=fonts, waveform_sensitivities=waveform_sensitivities,
        header_cache=header_cache, transcript_cache=transcript_cache,
    )

    if img.mode != 'RGB':
        img = img.convert('RGB')
    return np.array(img)
