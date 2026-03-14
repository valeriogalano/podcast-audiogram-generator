"""Waveform data extraction from audio files."""
import numpy as np


def get_waveform_data(audio_path, fps=24):
    """
    Extracts waveform data from audio sampled per frame.

    Args:
        audio_path: Path to the audio file
        fps: Video frames per second

    Returns:
        Array of amplitudes for each video frame
    """
    # Lazy import to avoid importing heavy dependencies at module import time
    # which can break unit tests in constrained environments
    from pydub import AudioSegment  # type: ignore

    audio = AudioSegment.from_file(audio_path)
    samples = np.array(audio.get_array_of_samples())

    # Normalize
    if len(samples) > 0:
        samples = samples.astype(float)
        samples = samples / np.max(np.abs(samples))

    # Calculate audio samples per video frame
    duration_seconds = len(audio) / 1000.0
    total_frames = int(duration_seconds * fps)
    samples_per_frame = len(samples) // total_frames if total_frames > 0 else len(samples)

    # Vectorized: trim samples to exact multiple of samples_per_frame, reshape and mean per frame
    n_complete = (len(samples) // samples_per_frame) * samples_per_frame
    trimmed = np.abs(samples[:n_complete]).reshape(-1, samples_per_frame)
    frame_amplitudes = trimmed.mean(axis=1)

    # Trim or pad to exactly total_frames
    frame_amplitudes = frame_amplitudes[:total_frames]

    return frame_amplitudes
