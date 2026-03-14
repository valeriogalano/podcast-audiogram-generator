"""
Command-line interface for the audiogram generator.

This module handles argument parsing, configuration loading, and interactive
user prompts. All business logic is delegated to ``pipeline``.
"""
import logging
import os
import argparse

from .config import Config
from .core import (
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
    """Main CLI function"""
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description='Audiogram generator from podcast RSS')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file')
    parser.add_argument('--feed-url', type=str, help='URL of the podcast RSS feed')
    parser.add_argument('--episode', type=str,
                        help="Episode(s) to process: number (e.g., 5), list (e.g., 1,3,5), "
                             "'all'/'a' for all, or 'last' for the most recent episode")
    parser.add_argument('--soundbites', type=str,
                        help='Soundbites to generate: specific number, "all" for all, '
                             'or comma-separated list (e.g., 1,3,5)')
    parser.add_argument('--output-dir', type=str, help='Output directory for generated files')
    parser.add_argument('--temp-dir', type=str, help='Temporary directory for intermediate files')
    parser.add_argument('--log-level', type=str,
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level (default: INFO)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print only soundbite intervals and subtitles without generating files')
    parser.add_argument(
        '--header-title-source',
        type=str,
        choices=['auto', 'podcast', 'episode', 'soundbite', 'none'],
        help="Header title source: 'auto' (default), 'podcast', 'episode', 'soundbite', "
             "or 'none' to hide",
    )

    subs_group = parser.add_mutually_exclusive_group()
    subs_group.add_argument('--show-subtitles', dest='show_subtitles', action='store_true',
                             help='Enable subtitle display in the video')
    subs_group.add_argument('--no-subtitles', dest='show_subtitles', action='store_false',
                             help='Disable subtitle display in the video')
    parser.set_defaults(show_subtitles=None)

    cover_group = parser.add_mutually_exclusive_group()
    cover_group.add_argument('--use-episode-cover', dest='use_episode_cover', action='store_true',
                              help="Use episode-specific cover if available")
    cover_group.add_argument('--no-use-episode-cover', dest='use_episode_cover',
                              action='store_false',
                              help="Do not use episode cover, use podcast cover instead")
    parser.set_defaults(use_episode_cover=None)

    args = parser.parse_args()

    if args.log_level:
        level = getattr(logging, args.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(level)

    default_config_path = None
    if not args.config:
        cwd = os.getcwd()
        for candidate in [os.path.join(cwd, 'config.yml'), os.path.join(cwd, 'config.yaml')]:
            if os.path.exists(candidate):
                default_config_path = candidate
                break
    config = Config(config_file=args.config or default_config_path)

    config.update_from_args({
        'feed_url': args.feed_url,
        'episode': args.episode,
        'soundbites': args.soundbites,
        'output_dir': args.output_dir,
        'temp_dir': args.temp_dir,
        'dry_run': args.dry_run,
        'show_subtitles': args.show_subtitles,
        'use_episode_cover': args.use_episode_cover,
        'header_title_source': args.header_title_source,
    })

    feed_url = config.get('feed_url')
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
    if not verify_ssl:
        logger.warning("SSL certificate verification is disabled (verify_ssl: false). "
                       "Set verify_ssl: true in config.yaml to enable it.")

    try:
        labels = config.get('caption_labels', {}) or {}
    except Exception as e:
        logging.warning("Could not read caption_labels from config: %s", e)
        labels = {}
    import audiogram_generator.pipeline as _pipeline
    _pipeline.CAPTION_LABEL_EPISODE_PREFIX = labels.get(
        'episode_prefix', _pipeline.CAPTION_LABEL_EPISODE_PREFIX
    )
    _pipeline.CAPTION_LABEL_LISTEN_PREFIX = labels.get(
        'listen_full_prefix', _pipeline.CAPTION_LABEL_LISTEN_PREFIX
    )

    if feed_url is None:
        try:
            while True:
                user_input = input("\nEnter the podcast RSS feed URL: ").strip()
                if user_input:
                    feed_url = user_input
                    logger.info("Using feed: %s", feed_url)
                    break
                else:
                    logger.warning("The feed URL cannot be empty. Try again.")
        except KeyboardInterrupt:
            logger.info("\nOperation cancelled.")
            return

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
    try:
        selected_episode_numbers = parse_episode_selection(episode_input, max_episode)
    except ValueError as e:
        logger.error("Episode input error: %s", e)
        return

    if not selected_episode_numbers:
        while True:
            try:
                choice = input(
                    f"\nSelect episode: number (e.g. 5), list (e.g. 1,3,5), "
                    f"'all'/'a' for all, or 'last' for the last one: "
                ).strip()
                try:
                    selected_episode_numbers = parse_episode_selection(choice, max_episode)
                    break
                except ValueError as e:
                    logger.warning("Invalid input: %s", e)
            except KeyboardInterrupt:
                logger.info("\nOperation cancelled.")
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

        # Resolve soundbite choice interactively when not specified via config/CLI
        resolved_soundbites_choice = soundbites_choice
        if resolved_soundbites_choice is None and not dry_run:
            sbs = selected.get('soundbites') or []
            if sbs:
                logger.info("\nFound soundbites (%d):", len(sbs))
                for i, sb in enumerate(sbs, 1):
                    logger.info("  %d. [Start: %ss, Duration: %ss] %s",
                                i, sb['start'], sb['duration'],
                                sb.get('text') or sb.get('title') or '')
                logger.info("\n%s", "=" * 60)
                try:
                    resolved_soundbites_choice = input(
                        "\nDo you want to generate an audiogram for a soundbite? "
                        "(number, 'a' for all, or 'n' to exit): "
                    )
                except KeyboardInterrupt:
                    logger.info("\nOperation cancelled.")
                    return

        process_one_episode(
            selected=selected,
            podcast_info=podcast_info,
            colors=colors,
            formats_config=formats_config,
            config_hashtags=config_hashtags,
            show_subtitles=show_subtitles,
            output_dir=output_dir,
            temp_dir_base=temp_dir_base,
            soundbites_choice=resolved_soundbites_choice,
            dry_run=dry_run,
            use_episode_cover=use_episode_cover,
            header_title_source=header_title_source,
            fonts=fonts,
            verify_ssl=verify_ssl,
        )

    return


if __name__ == "__main__":
    main()
