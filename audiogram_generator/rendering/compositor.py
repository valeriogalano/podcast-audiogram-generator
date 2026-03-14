"""Low-level PIL drawing primitives and color/font defaults."""
import re
import sys
import unicodedata
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# Default font path resolved per platform; overridable via config.yaml
_PLATFORM_DEFAULT_FONTS = {
    "darwin": "/System/Library/Fonts/Helvetica.ttc",
    "linux":  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "win32":  "C:/Windows/Fonts/Arial.ttf",
}
DEFAULT_FONT_PATH = _PLATFORM_DEFAULT_FONTS.get(sys.platform, "")

# Default brand colors
COLOR_ORANGE = (242, 101, 34)
COLOR_BEIGE = (235, 213, 197)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (50, 50, 50)


def _subtitle_default_style(colors):
    """Returns the default style for subtitles (transcription)."""
    bg = tuple(colors.get('transcript_bg', COLOR_BLACK))
    bg_with_alpha = bg + (190,) if len(bg) == 3 else bg
    return {
        'text_color': tuple(colors.get('text', COLOR_WHITE)),
        'bg_color': bg_with_alpha,
        'padding': 18,
        'radius': 18,
        'line_spacing': 2,
        'shadow': True,
        'shadow_offset': (0, 4),
        'shadow_blur': 10,
        'max_lines': 5,
        'width_ratio': 0.88
    }


def _strip_punctuation(text: str) -> str:
    """Removes Unicode punctuation from subtitle text and normalizes spaces."""
    if not text:
        return text
    no_punct = ''.join((ch if unicodedata.category(ch)[0] != 'P' else ' ') for ch in text)
    return re.sub(r"\s+", " ", no_punct).strip()


def _draw_rounded_box_with_shadow(base_img, box, fill, radius=16, shadow=True,
                                   shadow_offset=(0, 3), shadow_blur=8):
    """Draws a semi-transparent rounded rectangle with optional shadow.

    Composites the result onto ``base_img`` and returns the resulting image.
    ``box`` is (x1, y1, x2, y2).
    """
    if base_img.mode != 'RGBA':
        base_img = base_img.convert('RGBA')

    overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    if shadow:
        sx = box[0] + shadow_offset[0]
        sy = box[1] + shadow_offset[1]
        ex = box[2] + shadow_offset[0]
        ey = box[3] + shadow_offset[1]
        shadow_overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_overlay)
        sdraw.rounded_rectangle([(sx, sy), (ex, ey)], radius=radius, fill=(0, 0, 0, 140))
        blurred = shadow_overlay.filter(ImageFilter.GaussianBlur(shadow_blur))
        shadow_overlay.close()
        composited = Image.alpha_composite(base_img, blurred)
        blurred.close()
        base_img = composited

    odraw.rounded_rectangle([box[:2], box[2:]], radius=radius, fill=fill)
    result = Image.alpha_composite(base_img, overlay)
    overlay.close()
    return result


def _render_subtitle_lines(img, draw, text, font, start_y, max_width, style):
    """Word-wrap and draw subtitle lines with backgrounds.

    Returns (img, total_height_drawn).
    """
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + w + " ").strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test + " " if not test.endswith(" ") else test
        else:
            if current.strip():
                lines.append(current.strip())
            current = w + " "
    if current.strip():
        lines.append(current.strip())

    lines = lines[: style.get('max_lines', 5)]

    padding = int(style.get('padding', 0))
    inner_left = 0 + padding
    inner_right = img.width - padding
    area_width = max(1, inner_right - inner_left)

    try:
        ascent, descent = font.getmetrics()
        constant_line_height = ascent + descent
    except Exception:
        sample_bbox = draw.textbbox((0, 0), "Hg", font=font)
        constant_line_height = (sample_bbox[3] - sample_bbox[1])

    total_height = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        line_x = inner_left + (area_width - lw) // 2
        line_y = start_y + int(total_height)

        box = (line_x - padding, line_y - padding, line_x + lw + padding, line_y + lh + padding)
        img = _draw_rounded_box_with_shadow(
            img, box, style['bg_color'],
            radius=style['radius'],
            shadow=style['shadow'],
            shadow_offset=style['shadow_offset'],
            shadow_blur=style['shadow_blur'],
        )
        draw = ImageDraw.Draw(img)
        draw.text((line_x, line_y), line, fill=style['text_color'], font=font)

        line_advance = int(constant_line_height * style['line_spacing'])
        total_height += line_advance

    return img, int(total_height)


def _draw_text_with_stroke(draw, position, text, font, fill, stroke_width=2,
                            stroke_fill=(30, 30, 30)):
    """Draws text with a thin outline to increase contrast."""
    try:
        draw.text(position, text, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
    except TypeError:
        x, y = position
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=stroke_fill)
        draw.text(position, text, font=font, fill=fill)


def _draw_pill_with_text(img, draw, text, font, center_x, y, padding_x=24, padding_y=12,
                          pill_color=(255, 255, 255, 230), radius=22, shadow=True,
                          text_color=(0, 0, 0), stroke_width=0, stroke_fill=(30, 30, 30)):
    """Draws a rounded pill with shadow and centered text.

    Returns (img, text_x, text_y).
    """
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]

    x1 = int(center_x - (tw // 2) - padding_x)
    y1 = int(y - padding_y)
    x2 = int(center_x + (tw // 2) + padding_x)
    y2 = int(y + th + padding_y)

    img = _draw_rounded_box_with_shadow(img, (x1, y1, x2, y2), pill_color,
                                         radius=radius, shadow=shadow,
                                         shadow_offset=(0, 4), shadow_blur=10)
    draw = ImageDraw.Draw(img)

    text_x = int(center_x - tw // 2)
    text_y = int(y)
    if stroke_width > 0:
        _draw_text_with_stroke(draw, (text_x, text_y), text, font, text_color,
                                stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:
        draw.text((text_x, text_y), text, font=font, fill=text_color)
    return img, text_x, text_y
