"""
Generatore di video audiogram
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Optional
from moviepy import VideoClip, AudioFileClip
import urllib.request
import ssl
import re
import unicodedata
import shutil

# Traccia i segmenti audio già salvati per evitare copie multiple per lo stesso soundbite
_SAVED_SEGMENTS = set()

# Formati video per social media
FORMATS = {
    # Verticale 9:16 - Instagram Reels/Stories, YouTube Shorts, TikTok, Twitter
    'vertical': (1080, 1920),
    # Quadrato 1:1 - Instagram Post, Twitter, Mastodon, LinkedIn
    'square': (1080, 1080),
    # Orizzontale 16:9 - YouTube, Twitter orizzontale
    'horizontal': (1920, 1080)
}

# Colori Pensieri in Codice
COLOR_ORANGE = (242, 101, 34)
COLOR_BEIGE = (235, 213, 197)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (50, 50, 50)

# Spaziatura tra le righe del titolo episodio (header)
# Aumentata per migliorare la leggibilità nelle intestazioni multi‑riga
HEADER_LINE_SPACING = 1.45


def _subtitle_default_style(colors):
    """Ritorna lo stile predefinito per i sottotitoli (trascrizione)."""
    # Colori con alpha per sfondo
    bg = tuple(colors.get('transcript_bg', COLOR_BLACK))
    bg_with_alpha = bg + (190,) if len(bg) == 3 else bg
    return {
        'text_color': tuple(colors.get('text', COLOR_WHITE)),
        'bg_color': bg_with_alpha,      # RGBA
        'padding': 18,                  # px
        'radius': 18,                   # px angoli arrotondati
        'line_spacing': 2,              # moltiplicatore altezza riga
        'shadow': True,                 # ombra soft al box
        'shadow_offset': (0, 4),        # dx, dy
        'shadow_blur': 10,              # raggio blur
        'max_lines': 5,                 # righe massime visualizzate
        'width_ratio': 0.88             # % della larghezza massima
    }


def _strip_punctuation(text: str) -> str:
    """Rimuove la punteggiatura (Unicode) dal testo dei sottotitoli e normalizza gli spazi.
    Esempi rimossi: . , ; : ! ? … – — - ( ) [ ] { } « » “ ” ' " ecc.
    """
    if not text:
        return text
    # Rimuovi tutti i caratteri la cui categoria Unicode inizia con 'P' (punctuation)
    no_punct = ''.join((ch if unicodedata.category(ch)[0] != 'P' else ' ') for ch in text)
    # Collassa spazi multipli e trim
    return re.sub(r"\s+", " ", no_punct).strip()


def _draw_rounded_box_with_shadow(base_img, box, fill, radius=16, shadow=True, shadow_offset=(0, 3), shadow_blur=8):
    """Disegna un rettangolo arrotondato semi-trasparente con ombra su un overlay RGBA e lo compone su base_img.
    box: (x1, y1, x2, y2)
    Ritorna l'immagine risultante (stessa istanza o nuova se necessario).
    """
    # Assicurati che la base sia RGBA per alpha_composite
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
        shadow_overlay = shadow_overlay.filter(ImageFilter.GaussianBlur(shadow_blur))
        base_img = Image.alpha_composite(base_img, shadow_overlay)

    odraw.rounded_rectangle([box[:2], box[2:]], radius=radius, fill=fill)
    base_img = Image.alpha_composite(base_img, overlay)
    return base_img


def _render_subtitle_lines(img, draw, text, font, start_y, max_width, style):
    """Esegue il word wrap e disegna le righe di sottotitoli più gradevoli.
    Ritorna (img, total_height_disegnata).

    Nota: la spaziatura verticale tra le righe usa un'altezza di riga costante
    basata sulle metriche del font, così da evitare differenze dovute ai glifi
    presenti nelle singole righe (ascendenti/descendenti).
    """
    # Word wrap manuale
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

    # Limiti orizzontali per il centraggio
    inner_left = 0 + padding
    inner_right = img.width - padding
    area_width = max(1, inner_right - inner_left)

    # Calcola altezza di riga costante basata sul font
    try:
        ascent, descent = font.getmetrics()
        constant_line_height = ascent + descent
    except Exception:
        # Fallback: usa l'altezza del bbox di una stringa campione
        sample_bbox = draw.textbbox((0, 0), "Hg", font=font)
        constant_line_height = (sample_bbox[3] - sample_bbox[1])

    total_height = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        # Centra entro l'area definita (già ridotta del padding)
        line_x = inner_left + (area_width - lw) // 2
        line_y = start_y + int(total_height)

        box = (line_x - padding, line_y - padding, line_x + lw + padding, line_y + lh + padding)
        img = _draw_rounded_box_with_shadow(
            img,
            box,
            style['bg_color'],
            radius=style['radius'],
            shadow=style['shadow'],
            shadow_offset=style['shadow_offset'],
            shadow_blur=style['shadow_blur']
        )

        # Dopo compositing, ricrea draw su eventuale immagine RGBA
        draw = ImageDraw.Draw(img)
        draw.text((line_x, line_y), line, fill=style['text_color'], font=font)

        # Avanzamento verticale costante, indipendente dai glifi della riga
        line_advance = int(constant_line_height * style['line_spacing'])
        total_height += line_advance

    return img, int(total_height)


def _draw_text_with_stroke(draw, position, text, font, fill, stroke_width=2, stroke_fill=(30, 30, 30)):
    """Disegna testo con un sottile contorno per aumentare il contrasto.
    Usa i parametri stroke nativi di PIL se disponibili.
    """
    try:
        draw.text(position, text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
    except TypeError:
        # Fallback per versioni PIL molto vecchie: disegna il contorno manuale
        x, y = position
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]:
            draw.text((x+dx, y+dy), text, font=font, fill=stroke_fill)
        draw.text(position, text, font=font, fill=fill)


def _draw_pill_with_text(img, draw, text, font, center_x, y, padding_x=24, padding_y=12,
                         pill_color=(255, 255, 255, 230), radius=22, shadow=True,
                         text_color=(0, 0, 0), stroke_width=0, stroke_fill=(30, 30, 30)):
    """Disegna una 'pill' arrotondata con ombra e testo centrato.
    Ritorna (img, text_x, text_y) per eventuali usi successivi.
    """
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]

    x1 = int(center_x - (tw // 2) - padding_x)
    y1 = int(y - padding_y)
    x2 = int(center_x + (tw // 2) + padding_x)
    y2 = int(y + th + padding_y)

    # Disegna pill con ombra su overlay
    img = _draw_rounded_box_with_shadow(img, (x1, y1, x2, y2), pill_color, radius=radius, shadow=shadow, shadow_offset=(0, 4), shadow_blur=10)
    draw = ImageDraw.Draw(img)

    text_x = int(center_x - tw // 2)
    text_y = int(y)
    if stroke_width > 0:
        _draw_text_with_stroke(draw, (text_x, text_y), text, font, text_color, stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:
        draw.text((text_x, text_y), text, font=font, fill=text_color)
    return img, text_x, text_y


def download_image(url, output_path):
    """Scarica un'immagine da URL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, context=ssl_context) as response:
        with open(output_path, 'wb') as f:
            f.write(response.read())


def get_waveform_data(audio_path, fps=24):
    """
    Estrae dati waveform dall'audio campionati per frame

    Args:
        audio_path: Percorso del file audio
        fps: Frame per secondo del video

    Returns:
        Array di ampiezze per ogni frame del video
    """
    # Lazy import to avoid importing heavy dependencies at module import time
    # which can break unit tests in constrained environments
    from pydub import AudioSegment  # type: ignore

    audio = AudioSegment.from_file(audio_path)
    samples = np.array(audio.get_array_of_samples())

    # Normalizza
    if len(samples) > 0:
        samples = samples.astype(float)
        samples = samples / np.max(np.abs(samples))

    # Calcola quanti campioni audio per frame video
    sample_rate = audio.frame_rate
    duration_seconds = len(audio) / 1000.0
    total_frames = int(duration_seconds * fps)
    samples_per_frame = len(samples) // total_frames if total_frames > 0 else len(samples)

    # Estrai ampiezza media per ogni frame
    frame_amplitudes = []
    for i in range(total_frames):
        start = i * samples_per_frame
        end = min(start + samples_per_frame, len(samples))
        if start < len(samples):
            chunk = samples[start:end]
            frame_amplitudes.append(np.abs(chunk).mean())

    return np.array(frame_amplitudes)


# Configurazioni per i diversi layout
LAYOUT_CONFIGS = {
    'vertical': {
        'header_ratio': 0.17,
        'central_ratio': 0.54,
        'footer_ratio': 0.27,
        'logo_size_ratio': 0.6,
        'transcript_font_size': 0.028,
        'transcript_y_offset': 0.84,
        'max_lines': 5
    },
    'square': {
        'header_ratio': 0.12,
        'central_ratio': 0.66,
        'footer_ratio': 0.20,
        'logo_size_ratio': 0.5,
        'transcript_font_size': 0.030,
        'transcript_y_offset': 0.15,
        'max_lines': 3
    },
    'horizontal': {
        'header_ratio': 0.15,
        'central_ratio': 0.68,
        'footer_ratio': 0.15,
        'logo_size_ratio': 0.6,
        'logo_width_ratio': 0.3,
        'transcript_font_size': 0.030,
        'transcript_y_offset': 0.12,
        'max_lines': 2
    }
}


def _create_unified_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, colors, layout_config,
                           header_title_source: Optional[str] = None, header_soundbite_title: Optional[str] = None):
    """
    Layout unificato per tutti i formati video
    Utilizza configurazioni specifiche per ciascun formato passate tramite layout_config
    """
    progress_height = 0

    # Header
    header_top = progress_height
    header_height = int(height * layout_config['header_ratio'])
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])

    # Header title selection according to configuration
    src = (header_title_source or 'auto').lower()
    header_text = None
    if src == 'none':
        header_text = None
    elif src == 'podcast':
        header_text = (podcast_title or '').strip()
    elif src == 'episode':
        header_text = (episode_title or '').strip()
    elif src == 'soundbite':
        header_text = (header_soundbite_title or '').strip()
        if not header_text:
            # fallback gracefully
            header_text = (episode_title or podcast_title or '').strip()
    else:  # auto
        if episode_title and str(episode_title).strip():
            header_text = str(episode_title).strip()
        elif podcast_title and str(podcast_title).strip():
            header_text = str(podcast_title).strip()

    if header_text:
        # Font size tuned per layout height; slightly smaller than header to leave padding
        # Use a robust font fallback
        # Available width with horizontal padding
        pad_x = int(width * 0.04)
        # Lower the title closer to the bottom edge of the header bar
        # by reducing the vertical padding.
        pad_y = int(header_height * 0.04)
        max_width = width - 2 * pad_x
        max_height = header_height - 2 * pad_y

        # Start from a size proportionate to header and go down until fits
        size = max(16, int(header_height * 0.26))
        min_size = 12
        lines = []
        base_h = 0
        total_text_h = 0

        while size >= min_size:
            try:
                font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=size)
            except Exception:
                font_header = ImageFont.load_default()

            # Simple word wrap to fit within header width
            words = header_text.split()
            lines = []
            cur = ""
            for w in words:
                test = (cur + (" " if cur else "") + w)
                bbox = draw.textbbox((0, 0), test, font=font_header)
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
                # Ellipsize last line until it fits in width
                def ellipsize(text_line: str) -> str:
                    if not text_line:
                        return text_line
                    ell = "…"
                    while True:
                        bbox2 = draw.textbbox((0, 0), text_line, font=font_header)
                        if (bbox2[2] - bbox2[0]) <= max_width or len(text_line) <= 1:
                            return text_line
                        text_line = text_line[:-2] + ell if len(text_line) > 2 else ell

                lines[-1] = ellipsize(lines[-1])

                # Compute total height
                line_heights = []
                for ln in lines:
                    bbox = draw.textbbox((0, 0), ln, font=font_header)
                    line_heights.append(bbox[3] - bbox[1])
                base_h = max(line_heights) if line_heights else 0
                total_text_h = 0
                for i, _lh in enumerate(line_heights):
                    total_text_h += (base_h if i == 0 else int(base_h * HEADER_LINE_SPACING))
            else:
                base_h = 0
                total_text_h = 0

            if total_text_h <= max_height:
                break
            size -= 2

        # Draw lines if any
        if lines:
            start_y = header_top + header_height - pad_y - total_text_h
            x = pad_x
            text_fill = tuple(colors.get('text', COLOR_WHITE))
            cy = start_y
            for i, ln in enumerate(lines):
                # Draw plain text: same font as subtitles, but no background box and no shadows
                draw.text((x, cy), ln, font=font_header, fill=text_fill)
                cy += (base_h if i == 0 else int(base_h * HEADER_LINE_SPACING))

    # Area centrale
    central_top = header_top + header_height
    central_height = int(height * layout_config['central_ratio'])
    central_bottom = central_top + central_height

    # Visualizzatore waveform CENTRATO VERTICALMENTE
    if waveform_data is not None and len(waveform_data) > 0:
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        num_bars = width // total_bar_width
        if num_bars % 2 != 0:
            num_bars -= 1

        if num_bars >= 2:
            frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
            frame_idx = min(frame_idx, len(waveform_data) - 1)
            current_amplitude = waveform_data[frame_idx]

            np.random.seed(42)
            sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
            sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])

            for i in range(num_bars):
                x = i * total_bar_width

                center_idx = num_bars // 2
                distance_from_center = abs(i - center_idx)
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                min_height = int(central_height * 0.03)
                max_height = int(central_height * 0.70)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
                bar_height = max(min_height, min(bar_height, max_height))

                # CENTRATO VERTICALMENTE al 50%
                y_center = central_top + central_height // 2
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo podcast CENTRATO VERTICALMENTE
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)

        # Calcolo dimensione logo (horizontal ha logica diversa)
        if 'logo_width_ratio' in layout_config:
            logo_size = int(min(width * layout_config['logo_width_ratio'], central_height * layout_config['logo_size_ratio']))
        else:
            logo_size = int(min(width, central_height) * layout_config['logo_size_ratio'])

        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # CENTRATO VERTICALMENTE al 50%
        logo_x = (width - logo_size) // 2
        logo_y = central_top + (central_height - logo_size) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer
    footer_top = central_bottom
    footer_height = int(height * layout_config['footer_ratio'])
    draw.rectangle([(0, footer_top), (width, height)], fill=colors['primary'])

    # Trascrizione
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            current_text = _strip_punctuation(current_text)
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc",
                                                     size=int(height * layout_config['transcript_font_size']))
            except:
                font_transcript = ImageFont.load_default()

            # Posizionamento trascrizione: per square e horizontal dal basso, per vertical dall'alto
            if layout_config['transcript_y_offset'] < 0.5:
                # Dal basso (square, horizontal)
                transcript_y = central_bottom - int(central_height * layout_config['transcript_y_offset'])
            else:
                # Dall'alto (vertical)
                transcript_y = central_top + int(central_height * layout_config['transcript_y_offset'])

            style = _subtitle_default_style(colors)
            style['max_lines'] = min(style.get('max_lines', 5), layout_config['max_lines'])
            max_width = int(width * style['width_ratio'])

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style
            )
            draw = ImageDraw.Draw(img)

    return img


def create_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                  waveform_data, current_time, transcript_chunks, audio_duration, colors, format_name='vertical',
                  header_title_source: Optional[str] = None, header_soundbite_title: Optional[str] = None):
    """
    Crea il layout per il formato specificato

    Args:
        format_name: 'vertical', 'square', o 'horizontal'

    Formati supportati:
        - vertical: 9:16 (1080x1920) - Instagram Reels, Stories, YouTube Shorts, TikTok
        - square: 1:1 (1080x1080) - Instagram Post, Twitter, Mastodon, LinkedIn
        - horizontal: 16:9 (1920x1080) - YouTube
    """
    layout_config = LAYOUT_CONFIGS.get(format_name, LAYOUT_CONFIGS['vertical'])
    return _create_unified_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                                  waveform_data, current_time, transcript_chunks, audio_duration, colors,
                                  layout_config, header_title_source, header_soundbite_title)


def create_audiogram_frame(width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, formats=None, colors=None, format_name='vertical',
                           header_title_source: Optional[str] = None, header_soundbite_title: Optional[str] = None):
    """
    Crea un singolo frame dell'audiogram delegando al layout specifico per formato

    Args:
        width, height: Dimensioni del frame
        podcast_logo_path: Percorso logo podcast
        podcast_title: Titolo del podcast
        episode_title: Titolo dell'episodio
        waveform_data: Dati della waveform
        current_time: Tempo corrente in secondi
        transcript_chunks: Lista di chunk di trascrizione con timing
        audio_duration: Durata totale dell'audio
        colors: Dizionario con i colori personalizzati (opzionale)
        format_name: Nome del formato ('vertical', 'square', 'horizontal')
    """
    # Usa colori di default o personalizzati
    if colors is None:
        colors = {
            'primary': COLOR_ORANGE,
            'background': COLOR_BEIGE,
            'text': COLOR_WHITE,
            'transcript_bg': COLOR_BLACK
        }
    else:
        # Converti liste in tuple se necessario
        colors = {
            'primary': tuple(colors.get('primary', COLOR_ORANGE)),
            'background': tuple(colors.get('background', COLOR_BEIGE)),
            'text': tuple(colors.get('text', COLOR_WHITE)),
            'transcript_bg': tuple(colors.get('transcript_bg', COLOR_BLACK))
        }

    # Crea immagine di base
    img = Image.new('RGB', (width, height), colors['background'])
    draw = ImageDraw.Draw(img)

    # Crea il layout
    img = create_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                       episode_title, waveform_data, current_time, transcript_chunks,
                       audio_duration, colors, format_name, header_title_source, header_soundbite_title)

    # Assicurati che l'array sia in RGB per MoviePy
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return np.array(img)


def generate_audiogram(audio_path, output_path, format_name, podcast_logo_path,
                      podcast_title, episode_title, transcript_chunks, duration,
                      formats=None, colors=None,
                      show_subtitles=True, *,
                      header_title_source: Optional[str] = None,
                      header_soundbite_title: Optional[str] = None):
    """
    Genera un video audiogram completo

    Args:
        audio_path: Percorso del file audio
        output_path: Percorso del file video di output
        format_name: Nome del formato ('vertical', 'square', 'horizontal')
        podcast_logo_path: Percorso logo podcast
        podcast_title: Titolo del podcast
        episode_title: Titolo dell'episodio
        transcript_chunks: Lista di chunk di trascrizione con timing
        duration: Durata del video
        formats: Dizionario con i formati personalizzati (opzionale)
        colors: Dizionario con i colori personalizzati (opzionale)
    """
    # Usa formati personalizzati o di default
    if formats is None or format_name not in formats:
        width, height = FORMATS[format_name]
    else:
        format_config = formats[format_name]
        width = format_config.get('width', FORMATS[format_name][0])
        height = format_config.get('height', FORMATS[format_name][1])

    fps = 24  # Riduci da 30 a 24 fps per velocizzare

    print(f"  - Estrazione waveform...")
    # Estrai waveform una sola volta, campionata per frame
    waveform_data = get_waveform_data(audio_path, fps=fps)

    print(f"  - Pre-caricamento logo...")
    # Pre-carica e ridimensiona il logo una sola volta
    logo_img = None
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        central_height = int(height * 0.60)
        logo_size = int(min(width, central_height) * 0.4)
        logo_img = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    print(f"  - Generazione frame video...")
    # Prepara chunks sottotitoli in base al flag
    chunks_for_render = transcript_chunks if show_subtitles else []
    # Funzione per generare frame
    def make_frame(t):
        return create_audiogram_frame(
            width, height,
            podcast_logo_path,  # Passiamo il path per compatibilità
            podcast_title,
            episode_title,
            waveform_data,
            t,
            chunks_for_render,
            duration,
            formats,
            colors,
            format_name,  # Passa il formato per usare il layout corretto
            header_title_source,
            header_soundbite_title,
        )

    # Crea video clip
    video = VideoClip(make_frame, duration=duration)
    video.fps = fps

    print(f"  - Aggiunta audio...")
    # Aggiungi audio
    audio = AudioFileClip(audio_path)
    video = video.with_audio(audio)

    print(f"  - Rendering video...")
    # Esporta con threads per velocizzare
    video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=fps,
        threads=4,
        preset='veryfast'  # Velocizza la creazione per video semplici
    )

    # Salva anche il segmento audio nella cartella di output.
    # Deduce il nome da output_path (es: ep145_sb1_vertical.mp4 -> ep145_sb1.mp3)
    try:
        base = os.path.basename(output_path)
        m = re.search(r"(ep\d+)_sb(\d+)", base)
        if m:
            ep_tag = m.group(1)
            sb_tag = m.group(2)
            dest_path = os.path.join(os.path.dirname(output_path), f"{ep_tag}_sb{sb_tag}.mp3")
            # Copia sempre sovrascrivendo come da richiesta dell'utente
            shutil.copyfile(audio_path, dest_path)
    except Exception as e:
        # Non interrompere la generazione video in caso di errore di copia
        print(f"  - Avviso: impossibile salvare il segmento audio in output: {e}")
