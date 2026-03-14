"""Business logic layer for audiogram generation.

This module contains the orchestration functions that turn episode/soundbite
data into output files (audio, video, captions, SRT). It has no dependency on
argparse, stdin, or any interactive I/O — all choices are passed as parameters.

The CLI (cli.py) handles user interaction and delegates to these functions.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from .audio_utils import download_audio, extract_audio_segment, load_audio
from .core import format_seconds, parse_soundbite_selection
from .core.captioning import build_caption_text, generate_srt_content
from .rendering.facade import generate_audiogram
from .services import transcript as transcript_svc
from .services.assets import download_image

logger = logging.getLogger(__name__)


def _warn_if_no_ffmpeg():
    """Log a one-time warning if FFmpeg is not available on PATH.

    Non-fatal: only informs the user; rendering may still fail later if required.
    Logged at most once per process (state stored as a function attribute).
    """
    if _warn_if_no_ffmpeg.warned:  # type: ignore[attr-defined]
        return
    try:
        if shutil.which('ffmpeg') is None:
            logger.warning(
                "FFmpeg not found on PATH. Rendering may fail. "
                "See README for install instructions."
            )
        _warn_if_no_ffmpeg.warned = True  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("FFmpeg check failed: %s", e)
        _warn_if_no_ffmpeg.warned = True  # type: ignore[attr-defined]


_warn_if_no_ffmpeg.warned = False  # type: ignore[attr-defined]

# Caption label defaults; overridable via config in the CLI layer
CAPTION_LABEL_EPISODE_PREFIX = "Episode"
CAPTION_LABEL_LISTEN_PREFIX = "Listen to the full episode"


def get_transcript_text(transcript_url, start_time, duration, srt_content=None,
                         verify_ssl: bool = False):
    """Fetch (if needed) and extract transcript text for a time window."""
    try:
        if srt_content is None and transcript_url:
            srt_content = transcript_svc.fetch_srt(transcript_url, verify_ssl=verify_ssl)
        if srt_content:
            return transcript_svc.get_transcript_text_from_srt(srt_content, start_time, duration)
    except Exception as e:
        logging.warning("Could not load transcript text: %s", e)
    return None


def get_transcript_chunks(transcript_url, start_time, duration, srt_content=None,
                           verify_ssl: bool = False):
    """Fetch (if needed) and return timed transcript chunks for a soundbite window."""
    try:
        if srt_content is None and transcript_url:
            srt_content = transcript_svc.fetch_srt(transcript_url, verify_ssl=verify_ssl)
        if srt_content:
            return transcript_svc.parse_srt_to_chunks(srt_content, float(start_time), float(duration))
    except Exception as e:
        logging.warning("Could not load transcript chunks: %s", e)
    return []


def generate_caption_file(output_path, episode_number, episode_title, episode_link,
                           soundbite_title, transcript_text, podcast_keywords=None,
                           episode_keywords=None, config_hashtags=None,
                           *, episode_prefix: Optional[str] = None,
                           listen_full_prefix: Optional[str] = None):
    """Generate a plain-text caption file for social posts."""
    ep_prefix = episode_prefix if episode_prefix is not None else CAPTION_LABEL_EPISODE_PREFIX
    listen_prefix = listen_full_prefix if listen_full_prefix is not None else CAPTION_LABEL_LISTEN_PREFIX

    caption = build_caption_text(
        episode_number=episode_number,
        episode_title=episode_title,
        episode_link=episode_link,
        soundbite_title=soundbite_title,
        transcript_text=transcript_text,
        podcast_keywords=podcast_keywords,
        episode_keywords=episode_keywords,
        config_hashtags=config_hashtags,
        episode_prefix=ep_prefix,
        listen_full_prefix=listen_prefix,
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(caption)


def generate_srt_file(output_path, transcript_chunks):
    """Generate a .srt subtitle file from transcript chunks."""
    if not transcript_chunks:
        return
    content = generate_srt_content(transcript_chunks)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)


def _prepare_episode_resources(selected, output_dir, verify_ssl: bool = False):
    """Download full audio and transcript for an episode.

    Returns:
        Tuple of (full_audio_path, srt_content)
    """
    full_audio_path = None
    srt_content = None

    if selected['audio_url']:
        full_audio_path = os.path.join(output_dir, f"ep{selected['number']}.mp3")

        try:
            if os.path.exists(full_audio_path) and os.path.getsize(full_audio_path) == 0:
                logger.warning("Existing audio file %s is empty. Removing it.", full_audio_path)
                os.remove(full_audio_path)
        except OSError:
            pass

        if not os.path.exists(full_audio_path):
            logger.info("\nDownloading full audio: %s", selected['audio_url'])
            try:
                download_audio(selected['audio_url'], full_audio_path, verify_ssl=verify_ssl)
                logger.info("✓ Full audio: %s", full_audio_path)
            except Exception as e:
                logger.warning("Could not download full audio: %s", e)
                full_audio_path = None
        else:
            logger.info("\nFull audio already exists: %s", full_audio_path)

    if selected.get('transcript_url'):
        logger.info("Processing full transcript...")
        try:
            srt_content = transcript_svc.fetch_srt(selected['transcript_url'], verify_ssl=verify_ssl)
            if srt_content:
                full_srt_path = os.path.join(output_dir, f"ep{selected['number']}.srt")
                with open(full_srt_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                logger.info("✓ Full SRT: %s", full_srt_path)
        except Exception as e:
            logger.warning("Could not fetch or save full transcript: %s", e)

    return full_audio_path, srt_content


def _dry_run_episode(selected, soundbites_choice, verify_ssl: bool = False):
    """Print soundbite intervals and subtitles without generating any files."""
    sbs = selected.get('soundbites') or []
    logger.info("\nFound soundbites (%d):", len(sbs))
    if not sbs:
        logger.info("No soundbites available for this episode.")
        return

    try:
        nums = parse_soundbite_selection(soundbites_choice, len(sbs))
    except ValueError as e:
        logger.warning("Soundbite selection error: %s", e)
        return

    logger.info("\n%s", "=" * 60)
    logger.info("Dry-run: print start/end time and subtitle text")
    logger.info("%s", "=" * 60)

    srt_content = None
    if selected.get('transcript_url'):
        try:
            srt_content = transcript_svc.fetch_srt(selected['transcript_url'], verify_ssl=verify_ssl)
        except Exception as e:
            logging.warning("Could not fetch SRT for dry-run preview: %s", e)

    for idx in nums:
        sb = sbs[idx - 1]
        try:
            start_s = float(sb['start'])
            dur_s = float(sb['duration'])
        except Exception:
            logger.warning("Soundbite %d: invalid timing values (start=%s, duration=%s)",
                           idx, sb.get('start'), sb.get('duration'))
            continue
        end_s = start_s + dur_s

        transcript_text = get_transcript_text(
            selected.get('transcript_url'),
            sb['start'],
            sb['duration'],
            srt_content=srt_content,
            verify_ssl=verify_ssl,
        )
        text = (transcript_text or sb.get('text') or sb.get('title') or '').strip()

        logger.info("\nSoundbite %d", idx)
        logger.info("- Start: %.3fs (%s)", start_s, format_seconds(start_s))
        logger.info("- Duration: %.3fs (%s)", dur_s, format_seconds(dur_s))
        logger.info("- End:   %.3fs (%s)", end_s, format_seconds(end_s))
        logger.info("- Subtitle text:")
        logger.info("%s", text if text else "[Not available]")


def _process_single_soundbite(
    soundbite,
    soundbite_num,
    total_soundbites,
    selected,
    podcast_info,
    temp_dir,
    logo_path,
    srt_content,
    full_audio_path,
    output_dir,
    formats_config,
    colors,
    show_subtitles,
    config_hashtags,
    header_title_source=None,
    fonts=None,
    loaded_audio=None,
    verify_ssl: bool = False,
):
    """Process a single soundbite: extract audio, generate audiograms, caption and SRT."""
    if total_soundbites:
        logger.info("\n%s", "=" * 60)
        logger.info("Soundbite %d/%d: %s", soundbite_num, total_soundbites,
                    soundbite.get('text') or soundbite.get('title'))
        logger.info("%s", "=" * 60)
    else:
        logger.info("\n%s", "=" * 60)
        logger.info("Soundbite %d: %s", soundbite_num,
                    soundbite.get('text') or soundbite.get('title'))
        logger.info("%s", "=" * 60)

    if full_audio_path and os.path.exists(full_audio_path):
        logger.info("Extracting audio segment...")
        segment_path = os.path.join(temp_dir, f"segment_{soundbite_num}.mp3")
        extract_audio_segment(
            full_audio_path,
            soundbite['start'],
            soundbite['duration'],
            segment_path,
            audio=loaded_audio,
        )
    else:
        logger.warning("Skipping audio extraction because full audio file is missing or invalid.")
        segment_path = None

    logger.info("Processing transcript...")
    transcript_chunks: List = []
    transcript_text = ""
    if srt_content:
        transcript_chunks = get_transcript_chunks(
            selected.get('transcript_url'),
            soundbite['start'],
            soundbite['duration'],
            srt_content=srt_content,
            verify_ssl=verify_ssl,
        )
        transcript_text = get_transcript_text(
            selected.get('transcript_url'),
            soundbite['start'],
            soundbite['duration'],
            srt_content=srt_content,
            verify_ssl=verify_ssl,
        ) or (soundbite.get('text') or soundbite.get('title'))
    else:
        transcript_text = soundbite.get('text') or soundbite.get('title')

    mp3_output_path = os.path.join(output_dir, f"ep{selected['number']}_sb{soundbite_num}.mp3")
    if segment_path and os.path.exists(segment_path):
        try:
            shutil.copy2(segment_path, mp3_output_path)
            logger.info("✓ Audio: %s", mp3_output_path)
        except Exception as e:
            logger.warning("Could not save audio file: %s", e)
    else:
        logger.warning("Audio segment was not generated, skipping MP3 output.")

    formats_info = {}
    for fmt_name, fmt_config in formats_config.items():
        if fmt_config.get('enabled', True):
            formats_info[fmt_name] = fmt_config.get('description', fmt_name)

    if not segment_path or not os.path.exists(segment_path):
        logger.warning("Skipping audiogram video generation because audio segment is missing.")
    else:
        nosubs_suffix = "_nosubs" if not show_subtitles else ""
        soundbite_title = soundbite.get('text') or soundbite.get('title')

        def _render_one_format(format_name):
            output_path = os.path.join(
                output_dir,
                f"ep{selected['number']}_sb{soundbite_num}{nosubs_suffix}_{format_name}.mp4"
            )
            logger.info("Generating audiogram %s...", formats_info[format_name])
            generate_audiogram(
                segment_path,
                output_path,
                format_name,
                logo_path,
                podcast_info['title'],
                selected['title'],
                transcript_chunks,
                float(soundbite['duration']),
                formats_config,
                colors,
                show_subtitles,
                header_title_source=header_title_source,
                header_soundbite_title=soundbite_title,
                fonts=fonts,
            )
            logger.info("✓ %s: %s", format_name, output_path)
            return format_name, output_path

        with ThreadPoolExecutor(max_workers=len(formats_info)) as executor:
            futures = {executor.submit(_render_one_format, fmt): fmt for fmt in formats_info}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error("Format %s rendering failed: %s", futures[future], e)

    logger.info("Generating caption file...")
    caption_path = os.path.join(output_dir, f"ep{selected['number']}_sb{soundbite_num}_caption.txt")
    generate_caption_file(
        caption_path,
        selected['number'],
        selected['title'],
        selected['link'],
        soundbite.get('text') or soundbite.get('title') or '',
        transcript_text,
        podcast_info.get('keywords'),
        selected.get('keywords'),
        config_hashtags,
    )
    logger.info("✓ Caption: %s", caption_path)

    logger.info("Generating SRT file...")
    srt_path = os.path.join(output_dir, f"ep{selected['number']}_sb{soundbite_num}.srt")
    generate_srt_file(srt_path, transcript_chunks)
    if os.path.exists(srt_path):
        logger.info("✓ SRT: %s", srt_path)

    return formats_info


def _process_full_episode(selected, podcast_info, full_audio_path, srt_content,
                           artwork_url, output_dir, temp_dir_base, formats_config, colors,
                           show_subtitles, header_title_source=None, fonts=None,
                           verify_ssl: bool = False):
    """Generate audiograms for the entire episode (no soundbite extraction).

    Uses the full audio file and all transcript chunks. Outputs are named
    ``ep{N}_full_{format}.mp4``.
    """
    if not full_audio_path or not os.path.exists(full_audio_path):
        logger.warning("Full audio file missing — cannot generate full-episode audiogram.")
        return

    # Parse transcript chunks for the full episode (no time window restriction)
    transcript_chunks: List = []
    if srt_content:
        try:
            transcript_chunks = transcript_svc.parse_srt_to_chunks(srt_content, 0.0, float('inf'))
        except Exception as e:
            logger.warning("Could not parse transcript chunks for full episode: %s", e)

    # Duration from loaded audio
    try:
        loaded = load_audio(full_audio_path)
        duration = len(loaded) / 1000.0
    except Exception as e:
        logger.warning("Could not determine episode duration: %s", e)
        return

    logger.warning(
        "Generating full-episode audiogram (duration: %.0fs). This may take a while.", duration
    )

    formats_info = {}
    for fmt_name, fmt_config in formats_config.items():
        if fmt_config.get('enabled', True):
            formats_info[fmt_name] = fmt_config.get('description', fmt_name)

    with tempfile.TemporaryDirectory(dir=temp_dir_base) as temp_dir:
        _warn_if_no_ffmpeg()

        logger.info("Downloading artwork...")
        logo_path = os.path.join(temp_dir, "logo.png")
        if artwork_url:
            download_image(artwork_url, logo_path, verify_ssl=verify_ssl)

        def _render_one_format(format_name):
            output_path = os.path.join(
                output_dir,
                f"ep{selected['number']}_full_{format_name}.mp4"
            )
            logger.info("Generating full-episode audiogram %s...", formats_info[format_name])
            generate_audiogram(
                full_audio_path,
                output_path,
                format_name,
                logo_path,
                podcast_info['title'],
                selected['title'],
                transcript_chunks if show_subtitles else [],
                duration,
                formats_config,
                colors,
                show_subtitles,
                header_title_source=header_title_source,
                fonts=fonts,
            )
            logger.info("✓ %s: %s", format_name, output_path)
            return format_name, output_path

        with ThreadPoolExecutor(max_workers=len(formats_info)) as executor:
            futures = {executor.submit(_render_one_format, fmt): fmt for fmt in formats_info}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error("Format %s rendering failed: %s", futures[future], e)

    logger.info("\n%s", "=" * 60)
    logger.info("Full-episode audiograms generated in folder: %s", output_dir)
    logger.info("%s", "=" * 60)


def process_one_episode(selected, podcast_info, colors, formats_config, config_hashtags,
                         show_subtitles, output_dir, temp_dir_base, soundbites_choice,
                         dry_run=False, use_episode_cover=False, header_title_source=None,
                         fonts=None, verify_ssl: bool = False, full_episode: bool = False):
    """Orchestrate all steps for a single episode.

    ``soundbites_choice`` must be resolved by the caller (main() handles
    interactive stdin prompts). This function contains no input() calls.
    """
    logger.info("\nEpisode %d: %s", selected['number'], selected['title'])
    if selected['audio_url']:
        logger.info("Audio: %s", selected['audio_url'])

    artwork_url = None
    if use_episode_cover and selected.get('image_url'):
        artwork_url = selected['image_url']
    else:
        artwork_url = podcast_info.get('image_url')

    if dry_run:
        _dry_run_episode(selected, soundbites_choice, verify_ssl=verify_ssl)
        return

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir_base, exist_ok=True)

    full_audio_path, srt_content = _prepare_episode_resources(
        selected, output_dir, verify_ssl=verify_ssl
    )

    # Full-episode mode: generate audiogram for the entire episode
    if full_episode:
        _process_full_episode(
            selected=selected,
            podcast_info=podcast_info,
            full_audio_path=full_audio_path,
            srt_content=srt_content,
            artwork_url=artwork_url,
            output_dir=output_dir,
            temp_dir_base=temp_dir_base,
            formats_config=formats_config,
            colors=colors,
            show_subtitles=show_subtitles,
            header_title_source=header_title_source,
            fonts=fonts,
            verify_ssl=verify_ssl,
        )
        return

    loaded_audio = None
    if full_audio_path and os.path.exists(full_audio_path):
        try:
            logger.info("Pre-loading audio for segment extraction...")
            loaded_audio = load_audio(full_audio_path)
        except Exception as e:
            logger.warning("Could not pre-load audio, will reload per soundbite: %s", e)

    if selected['soundbites']:
        choice = str(soundbites_choice) if soundbites_choice is not None else 'n'

        if choice.lower() == 'a' or choice.lower() == 'all':
            logger.info("\nGenerating audiograms for all %d soundbites...",
                        len(selected['soundbites']))

            with tempfile.TemporaryDirectory(dir=temp_dir_base) as temp_dir:
                _warn_if_no_ffmpeg()

                logger.info("Downloading artwork...")
                logo_path = os.path.join(temp_dir, "logo.png")
                if artwork_url:
                    download_image(artwork_url, logo_path, verify_ssl=verify_ssl)

                formats_info = {}
                for soundbite_num, soundbite in enumerate(selected['soundbites'], 1):
                    formats_info = _process_single_soundbite(
                        soundbite=soundbite,
                        soundbite_num=soundbite_num,
                        total_soundbites=len(selected['soundbites']),
                        selected=selected,
                        podcast_info=podcast_info,
                        temp_dir=temp_dir,
                        logo_path=logo_path,
                        srt_content=srt_content,
                        full_audio_path=full_audio_path,
                        output_dir=output_dir,
                        formats_config=formats_config,
                        colors=colors,
                        show_subtitles=show_subtitles,
                        config_hashtags=config_hashtags,
                        header_title_source=header_title_source,
                        fonts=fonts,
                        loaded_audio=loaded_audio,
                        verify_ssl=verify_ssl,
                    )

                logger.info("\n%s", "=" * 60)
                logger.info("All audiograms generated successfully into the 'output' folder!")
                logger.info("Total: %d soundbites × %d formats = %d videos",
                            len(selected['soundbites']), len(formats_info),
                            len(selected['soundbites']) * len(formats_info))
                logger.info("%s", "=" * 60)

        elif choice.lower() != 'n':
            try:
                if ',' in choice:
                    soundbite_nums = [int(n.strip()) for n in choice.split(',')]
                else:
                    soundbite_nums = [int(choice)]

                for num in soundbite_nums:
                    if not (1 <= num <= len(selected['soundbites'])):
                        logger.error("Invalid number %d. Choose between 1 and %d",
                                     num, len(selected['soundbites']))
                        return

                logger.info("\nGenerating audiogram for %d soundbite(s)...", len(soundbite_nums))

                with tempfile.TemporaryDirectory(dir=temp_dir_base) as temp_dir:
                    _warn_if_no_ffmpeg()

                    logger.info("Downloading artwork...")
                    logo_path = os.path.join(temp_dir, "logo.png")
                    if artwork_url:
                        download_image(artwork_url, logo_path, verify_ssl=verify_ssl)

                    for soundbite_num in soundbite_nums:
                        soundbite = selected['soundbites'][soundbite_num - 1]
                        _process_single_soundbite(
                            soundbite=soundbite,
                            soundbite_num=soundbite_num,
                            total_soundbites=None,
                            selected=selected,
                            podcast_info=podcast_info,
                            temp_dir=temp_dir,
                            logo_path=logo_path,
                            srt_content=srt_content,
                            full_audio_path=full_audio_path,
                            output_dir=output_dir,
                            formats_config=formats_config,
                            colors=colors,
                            show_subtitles=show_subtitles,
                            config_hashtags=config_hashtags,
                            header_title_source=header_title_source,
                            fonts=fonts,
                            loaded_audio=loaded_audio,
                            verify_ssl=verify_ssl,
                        )

                    logger.info("\n%s", "=" * 60)
                    logger.info("Audiograms successfully generated in folder: %s", output_dir)
                    logger.info("%s", "=" * 60)
            except ValueError:
                logger.warning("Invalid input")
            except Exception as e:
                logger.error("Error during generation: %s", e)
    else:
        logger.info("\nNo soundbites found for this episode.")
