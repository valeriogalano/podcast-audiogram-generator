"""
Utilities to download and process audio
"""
import os
import ssl
import urllib.request


def download_audio(url, output_path):
    """Download an audio file from a URL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

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


def extract_audio_segment(audio_path, start_time, duration, output_path):
    """
    Extracts an audio segment from a file.

    Args:
        audio_path: Path to the full audio file
        start_time: Start time in seconds
        duration: Segment duration in seconds
        output_path: Output file path
    """
    # Lazy import to avoid importing heavy dependencies at module import time
    # and to keep unit tests independent from optional binary deps.
    from pydub import AudioSegment  # type: ignore

    audio = AudioSegment.from_file(audio_path)

    start_ms = int(float(start_time) * 1000)
    end_ms = start_ms + int(float(duration) * 1000)

    segment = audio[start_ms:end_ms]
    segment.export(output_path, format="mp3")

    return output_path
