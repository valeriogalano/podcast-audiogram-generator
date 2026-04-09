"""
Command-line interface for the audiogram generator.

This module handles argument parsing and configuration loading.
All business logic is delegated to ``pipeline``.

Configuration is driven by config.yaml; CLI flags provide lightweight
overrides for episode/soundbite selection and debugging.
"""
import logging
import os
import argparse

from .config import Config
from .core import (  # noqa: F401 – re-exported for tests
    parse_srt_time,
    format_seconds,
    parse_episode_selection,
    parse_soundbite_selection,
)
from .pipeline import (
    _warn_if_no_ffmpeg,
    get_transcript_text,
    get_transcript_chunks,
    generate_caption_file,
    generate_srt_file,
    _prepare_episode_resources,
    _dry_run_episode,
    _process_single_soundbite,
    process_one_episode,
    generate_audiogram,
    CAPTION_LABEL_EPISODE_PREFIX,
    CAPTION_LABEL_LISTEN_PREFIX,
)
from .rendering.facade import generate_audiogram  # noqa: F811 – keep facade reference for API guard test
from .services import rss as rss_svc


logger = logging.getLogger(__name__)


def get_podcast_episodes(feed_url, manual_soundbites=None, verify_ssl: bool = False):
    """Fetch the list of episodes from the RSS feed."""
    return rss_svc.get_podcast_episodes(feed_url, manual_soundbites=manual_soundbites,
                                         verify_ssl=verify_ssl)


def main():
    """Main CLI entry point. Configuration is loaded from config.yaml."""
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description='Audiogram generator from podcast RSS')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file')
    parser.add_argument('--episode', type=str,
                        help="Episode(s) to process: number (e.g., 5), list (e.g., 1,3,5), "
                             "'all'/'a' for all, or 'last' for the most recent episode")
    parser.add_argument('--soundbites', type=str,
                        help='Soundbites to generate: specific number, "all" for all, '
                             'or comma-separated list (e.g., 1,3,5)')
    parser.add_argument('--log-level', type=str,
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print soundbite intervals and subtitles without generating files')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing output files instead of skipping them')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='Maximum number of soundbites to generate per episode')

    args = parser.parse_args()

    if args.log_level:
        logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

    default_config_path = None
    if not args.config:
        cwd = os.getcwd()
        for candidate in [os.path.join(cwd, 'config.yml'), os.path.join(cwd, 'config.yaml')]:
            if os.path.exists(candidate):
                default_config_path = candidate
                break
    config = Config(config_file=args.config or default_config_path)

    config.update_from_args({
        'episode': args.episode,
        'soundbites': args.soundbites,
        'dry_run': args.dry_run or None,
        'force': args.force or None,
        'limit': args.limit,
    })

    feed_url = config.get('feed_url')
    if not feed_url:
        logger.error("feed_url is required. Set it in config.yaml.")
        return

    episode_input = config.get('episode')
    soundbites_choice = config.get('soundbites')
    output_dir = config.get('output_dir', os.path.join(os.getcwd(), 'output'))
    temp_dir_base = config.get('temp_dir', os.path.join(os.getcwd(), 'temp'))

    colors = config.get('colors')
    formats_config = config.get('formats')
    config_hashtags = config.get('hashtags', [])
    show_subtitles = config.get('show_subtitles', True)
    dry_run = config.get('dry_run', False)
    use_episode_cover = config.get('use_episode_cover', False)
    header_title_source = config.get('header_title_source', 'auto')
    fonts = config.get('fonts')
    verify_ssl = config.get('verify_ssl', False)
    full_episode = bool(config.get('full_episode', False))
    cta = config.get('cta')
    force = bool(config.get('force', False))
    limit = config.get('limit')

    if not verify_ssl:
        logger.warning("SSL certificate verification is disabled (verify_ssl: false). "
                       "Set verify_ssl: true in config.yaml to enable it.")

    labels = config.get('caption_labels') or {}
    import audiogram_generator.pipeline as _pipeline
    _pipeline.CAPTION_LABEL_EPISODE_PREFIX = labels.get(
        'episode_prefix', _pipeline.CAPTION_LABEL_EPISODE_PREFIX
    )
    _pipeline.CAPTION_LABEL_LISTEN_PREFIX = labels.get(
        'listen_full_prefix', _pipeline.CAPTION_LABEL_LISTEN_PREFIX
    )

    logger.info("\nFetching episodes from feed...")
    manual_sbs = config.get('manual_soundbites', {})
    episodes, podcast_info = get_podcast_episodes(feed_url, manual_soundbites=manual_sbs,
                                                   verify_ssl=verify_ssl)

    if not episodes:
        logger.warning("No episodes found in the feed.")
        return

    logger.info("\n%s", "=" * 60)
    logger.info("Podcast: %s", podcast_info.get('title', 'N/A'))
    if podcast_info.get('image_url'):
        logger.info("Artwork: %s", podcast_info['image_url'])
    logger.info("%s", "=" * 60)

    logger.info("\nFound %d episodes:\n", len(episodes))
    for episode in episodes:
        logger.info("%d. %s", episode['number'], episode['title'])

    max_episode = len(episodes)
    if not episode_input:
        logger.error("episode is required. Set it in config.yaml or pass --episode.")
        return
    try:
        selected_episode_numbers = parse_episode_selection(episode_input, max_episode)
    except ValueError as e:
        logger.error("Episode input error: %s", e)
        return

    if not soundbites_choice and not dry_run and not full_episode:
        logger.error("soundbites is required. Set it in config.yaml or pass --soundbites.")
        return

    # When --limit is set, pre-select the last N unprocessed soundbites across all
    # selected episodes (newest episode first, newest soundbite first) so that only
    # the episodes that actually have pending work are downloaded.
    episode_soundbite_overrides = {}  # ep_num -> comma-separated soundbite numbers
    effective_limit = limit  # limit to forward to process_one_episode (cleared below if pre-selected)

    if limit is not None and not dry_run and not full_episode:
        _nosubs_sfx = "" if show_subtitles else "_nosubs"
        _enabled_fmts = [
            fmt for fmt, cfg in (formats_config or {}).items()
            if cfg.get('enabled', True)
        ] if formats_config else []

        _pending = []  # [(episode_num, soundbite_num), ...]
        for _ep_num in reversed(selected_episode_numbers):
            _ep = next((e for e in episodes if e['number'] == _ep_num), None)
            if _ep is None:
                continue
            _soundbites = _ep.get('soundbites') or []
            for _sb_num in range(1, len(_soundbites) + 1):
                _already_done = False
                if _enabled_fmts and not force:
                    _sb_dir = os.path.join(output_dir, f"ep{_ep_num}", f"sb{_sb_num}")
                    _already_done = all(
                        os.path.exists(os.path.join(
                            _sb_dir, f"ep{_ep_num}_sb{_sb_num}{_nosubs_sfx}_{fmt}.mp4"
                        ))
                        for fmt in _enabled_fmts
                    )
                if not _already_done:
                    _pending.append((_ep_num, _sb_num))
                    if len(_pending) >= limit:
                        break
            if len(_pending) >= limit:
                break

        # Build per-episode soundbite overrides and restrict episode list
        _ep_sb_map = {}
        for _ep_num, _sb_num in _pending:
            _ep_sb_map.setdefault(_ep_num, []).append(_sb_num)

        selected_episode_numbers = [n for n in selected_episode_numbers if n in _ep_sb_map]
        for _ep_num, _sb_nums in _ep_sb_map.items():
            episode_soundbite_overrides[_ep_num] = ','.join(str(n) for n in _sb_nums)
        effective_limit = None  # already enforced above

    for episode_num in selected_episode_numbers:
        selected = None
        for ep in episodes:
            if ep['number'] == episode_num:
                selected = ep
                break
        if selected is None:
            logger.warning("Episode %d not found in the feed. Skipping.", episode_num)
            continue

        effective_soundbites_choice = episode_soundbite_overrides.get(episode_num, soundbites_choice)
        process_one_episode(
            selected=selected,
            podcast_info=podcast_info,
            colors=colors,
            formats_config=formats_config,
            config_hashtags=config_hashtags,
            show_subtitles=show_subtitles,
            output_dir=output_dir,
            temp_dir_base=temp_dir_base,
            soundbites_choice=effective_soundbites_choice,
            dry_run=dry_run,
            use_episode_cover=use_episode_cover,
            header_title_source=header_title_source,
            fonts=fonts,
            verify_ssl=verify_ssl,
            full_episode=full_episode,
            cta=cta,
            force=force,
            limit=effective_limit,
        )


if __name__ == "__main__":
    main()
