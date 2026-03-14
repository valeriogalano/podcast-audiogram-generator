"""
Utilities to download and process audio
"""
import os
import urllib.request
from .services._http import make_ssl_context


def download_audio(url, output_path, verify_ssl: bool = False):
    """Download an audio file from a URL"""
    ssl_context = make_ssl_context(verify=verify_ssl)

    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(request, context=ssl_context, timeout=30) as response:
            with open(output_path, 'wb') as f:
                content = response.read()
                if not content:
                    raise ValueError("Downloaded audio content is empty")
                f.write(content)
    except Exception:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise


def load_audio(audio_path):
    """Load a full audio file into an AudioSegment object.

    Returns the AudioSegment, which can be passed to extract_audio_segment()
    to avoid reloading the file for every soundbite.
    """
    from pydub import AudioSegment
    return AudioSegment.from_file(audio_path)


def extract_audio_segment(audio_path, start_time, duration, output_path, audio=None):
    """
    Extracts an audio segment from a file.

    Args:
        audio_path: Path to the full audio file (used only when ``audio`` is None)
        start_time: Start time in seconds
        duration: Segment duration in seconds
        output_path: Output file path
        audio: Pre-loaded AudioSegment object (optional). When provided the file
               at ``audio_path`` is not read from disk, avoiding redundant I/O
               when processing multiple soundbites from the same episode.
    """
    if audio is None:
        # Lazy import to avoid importing heavy dependencies at module import time
        # and to keep unit tests independent from optional binary deps.
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)

    start_ms = int(float(start_time) * 1000)
    end_ms = start_ms + int(float(duration) * 1000)

    segment = audio[start_ms:end_ms]
    segment.export(output_path, format="mp3")

    return output_path
