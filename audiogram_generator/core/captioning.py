"""Pure caption text generation and hashtag normalization.

This module contains side‑effect‑free helpers to build the caption text for
social posts and to normalize/merge hashtag sources.
"""
from __future__ import annotations
from typing import Iterable, List, Optional
import re


def normalize_hashtags(*sources: Optional[Iterable[str]]) -> List[str]:
    """Normalize and merge hashtag sources.

    - Accepts multiple iterables of strings (may be None)
    - Trims whitespace, removes an optional leading '#'
    - Lowercases and removes inner spaces
    - Deduplicates while preserving order

    Returns a list like ``["ai", "devops", "python"]`` (without '#').
    """
    flat: List[str] = []
    for src in sources:
        if not src:
            continue
        for item in src:
            if item is None:
                continue
            t = str(item).strip()
            if t.startswith('#'):
                t = t[1:]
            # remove spaces and lowercase
            t = re.sub(r"\s+", "", t).lower()
            if t:
                flat.append(t)

    seen = set()
    result: List[str] = []
    for t in flat:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def build_caption_text(
    episode_number: int,
    episode_title: str,
    episode_link: str,
    soundbite_title: str,
    transcript_text: str,
    podcast_keywords: Optional[str] = None,
    episode_keywords: Optional[str] = None,
    config_hashtags: Optional[Iterable[str]] = None,
    *,
    episode_prefix: str = "Episode",
    listen_full_prefix: str = "Listen to the full episode",
) -> str:
    """Build the full caption text content.

    Keyword sources are combined as follows:
    - ``podcast_keywords``: comma‑separated string from the feed
    - ``episode_keywords``: comma‑separated string from the feed
    - ``config_hashtags``: list of extra hashtags from config

    When no hashtags are available, defaults to ``#podcast``.
    """
    # Split comma‑separated inputs into lists
    podcast_tags = [t.strip() for t in podcast_keywords.split(',')] if podcast_keywords else []
    episode_tags = [t.strip() for t in episode_keywords.split(',')] if episode_keywords else []

    normalized = normalize_hashtags(podcast_tags, episode_tags, config_hashtags or [])
    hashtag_string = ' '.join(f"#{t}" for t in normalized) if normalized else '#podcast'

    caption = (
        f"{episode_prefix} {episode_number}: {episode_title}\n\n"
        f"{soundbite_title}\n\n"
        f"{transcript_text}\n\n"
        f"{listen_full_prefix}: {episode_link}\n\n"
        f"{hashtag_string}\n"
    )
    return caption


def format_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    import math
    s = abs(seconds)
    hours = int(s // 3600)
    minutes = int((s % 3600) // 60)
    secs = int(s % 60)
    millis = int(round((s - math.floor(s)) * 1000))
    # Correct possible overflow from rounding
    if millis == 1000:
        millis = 0
        secs += 1
        if secs == 60:
            secs = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_content(chunks: List[dict]) -> str:
    """Generate SRT content from transcript chunks.

    Chunks must be a list of dicts with 'start', 'end', and 'text' keys.
    """
    lines = []
    for i, chunk in enumerate(chunks, 1):
        start = format_srt_time(chunk['start'])
        end = format_srt_time(chunk['end'])
        text = chunk['text'].strip()
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(f"{text}\n")
    return "\n".join(lines)
