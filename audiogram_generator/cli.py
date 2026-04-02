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

    for episode_num in selected_episode_numbers:
        selected = None
        for ep in episodes:
            if ep['number'] == episode_num:
                selected = ep
                break
        if selected is None:
            logger.warning("Episode %d not found in the feed. Skipping.", episode_num)
            continue

        process_one_episode(
            selected=selected,
            podcast_info=podcast_info,
            colors=colors,
            formats_config=formats_config,
            config_hashtags=config_hashtags,
            show_subtitles=show_subtitles,
            output_dir=output_dir,
            temp_dir_base=temp_dir_base,
            soundbites_choice=soundbites_choice,
            dry_run=dry_run,
            use_episode_cover=use_episode_cover,
            header_title_source=header_title_source,
            fonts=fonts,
            verify_ssl=verify_ssl,
            full_episode=full_episode,
            cta=cta,
        )


if __name__ == "__main__":
    main()
