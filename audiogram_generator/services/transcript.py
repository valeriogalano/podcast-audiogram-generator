"""Transcript fetching and parsing services.

Split between network I/O (fetch_srt) and pure parsing helpers that operate on
SRT text. Designed to be testable offline by supplying SRT strings directly.
"""
from __future__ import annotations

from typing import List, Dict
import re
import urllib.request
import logging

from audiogram_generator.core import parse_srt_time
from .errors import SrtFetchError
from ._http import make_ssl_context

logger = logging.getLogger(__name__)


def fetch_srt(url: str, timeout: int = 10, verify_ssl: bool = False) -> str:
    """Fetch SRT text from a URL using a UA header.

    Returns the decoded UTF‑8 text. Raises exceptions on network errors.
    """
    logger.info("Fetching SRT: %s", url)
    ssl_context = make_ssl_context(verify=verify_ssl)

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, context=ssl_context, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            logger.debug("Fetched SRT with %d chars", len(text))
            return text
    except Exception as e:
        logger.error("Failed to fetch SRT from %s: %s", url, e)
        raise SrtFetchError(str(e))


def parse_srt_to_chunks(srt_text: str, start_time: float, duration: float) -> List[Dict]:
    """Parse SRT text and return chunks overlapping the interval, clipped.

    Inclusion rule change:
    - Previous behavior: include only blocks fully contained in [start, end].
    - New behavior: include any block that overlaps the interval and clip
      its timing to the interval boundaries.

    Chunks contain timing relative to the start of the interval: keys
    ``start``, ``end``, and ``text``.
    """
    start_time_sec = float(start_time)
    end_time_sec = start_time_sec + float(duration)

    entries = re.split(r"\n\n+", srt_text.strip()) if srt_text else []

    transcript_chunks: List[Dict] = []
    for entry in entries:
        lines = entry.strip().split('\n')
        if len(lines) >= 3:
            timestamp_line = lines[1]
            if '-->' in timestamp_line:
                time_parts = timestamp_line.split('-->')
                entry_start = parse_srt_time(time_parts[0].strip())
                entry_end = parse_srt_time(time_parts[1].strip())

                # Include blocks that overlap the interval and clip to bounds
                if (entry_end > start_time_sec) and (entry_start < end_time_sec):
                    clipped_start_abs = max(entry_start, start_time_sec)
                    clipped_end_abs = min(entry_end, end_time_sec)
                    # Guard against pathological zero/negative after clipping
                    if clipped_end_abs > clipped_start_abs:
                        text = ' '.join(lines[2:])
                        transcript_chunks.append({
                            'start': clipped_start_abs - start_time_sec,
                            'end': clipped_end_abs - start_time_sec,
                            'text': text,
                        })

    return transcript_chunks


def get_transcript_text_from_srt(srt_text: str, start_time: float, duration: float) -> str | None:
    """Return concatenated transcript text restricted to the interval.

    Uses overlapping-and-clipping semantics from ``parse_srt_to_chunks``.
    Returns None if no matching blocks are found.
    """
    chunks = parse_srt_to_chunks(srt_text, start_time, duration)
    if not chunks:
        return None
    return ' '.join(c['text'] for c in chunks if c.get('text')) or None
