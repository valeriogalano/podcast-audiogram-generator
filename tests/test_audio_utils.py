"""
Tests for audio_utils: load_audio and extract_audio_segment.
"""
import unittest
from unittest.mock import patch, MagicMock, call


class TestLoadAudio(unittest.TestCase):
    def test_load_audio_calls_from_file(self):
        """load_audio delegates to AudioSegment.from_file and returns its result."""
        from audiogram_generator.audio_utils import load_audio

        mock_segment = MagicMock()
        with patch("pydub.AudioSegment.from_file", return_value=mock_segment) as mock_ff:
            result = load_audio("/fake/audio.mp3")

        mock_ff.assert_called_once_with("/fake/audio.mp3")
        self.assertIs(result, mock_segment)

    def test_load_audio_propagates_exception(self):
        """load_audio lets exceptions from AudioSegment.from_file propagate."""
        from audiogram_generator.audio_utils import load_audio

        with patch("pydub.AudioSegment.from_file", side_effect=FileNotFoundError("no such file")):
            with self.assertRaises(FileNotFoundError):
                load_audio("/missing.mp3")


class TestExtractAudioSegment(unittest.TestCase):
    def _make_mock_segment(self):
        """Return a mock AudioSegment that supports slicing and export."""
        seg = MagicMock()
        seg.__getitem__ = MagicMock(return_value=MagicMock())
        return seg

    def test_uses_provided_audio_without_reading_file(self):
        """When audio= is provided, from_file must NOT be called."""
        from audiogram_generator.audio_utils import extract_audio_segment

        pre_loaded = self._make_mock_segment()
        sliced = MagicMock()
        pre_loaded.__getitem__ = MagicMock(return_value=sliced)

        with patch("pydub.AudioSegment.from_file") as mock_ff:
            extract_audio_segment("/fake/full.mp3", 10, 5, "/fake/out.mp3", audio=pre_loaded)
            mock_ff.assert_not_called()

        sliced.export.assert_called_once_with("/fake/out.mp3", format="mp3")

    def test_loads_file_when_audio_is_none(self):
        """When audio=None, from_file must be called to read from disk."""
        from audiogram_generator.audio_utils import extract_audio_segment

        loaded = self._make_mock_segment()
        sliced = MagicMock()
        loaded.__getitem__ = MagicMock(return_value=sliced)

        with patch("pydub.AudioSegment.from_file", return_value=loaded) as mock_ff:
            extract_audio_segment("/fake/full.mp3", 10, 5, "/fake/out.mp3", audio=None)

        mock_ff.assert_called_once_with("/fake/full.mp3")
        sliced.export.assert_called_once_with("/fake/out.mp3", format="mp3")

    def test_correct_slice_times(self):
        """Slice boundaries are computed from start_time and duration in milliseconds."""
        from audiogram_generator.audio_utils import extract_audio_segment

        pre_loaded = MagicMock()
        sliced = MagicMock()
        pre_loaded.__getitem__ = MagicMock(return_value=sliced)

        with patch("pydub.AudioSegment.from_file"):
            extract_audio_segment("/fake/full.mp3", 2.5, 3.0, "/fake/out.mp3", audio=pre_loaded)

        # start_ms=2500, end_ms=5500
        pre_loaded.__getitem__.assert_called_once_with(slice(2500, 5500))

    def test_returns_output_path(self):
        """extract_audio_segment returns the output path."""
        from audiogram_generator.audio_utils import extract_audio_segment

        pre_loaded = self._make_mock_segment()
        sliced = MagicMock()
        pre_loaded.__getitem__ = MagicMock(return_value=sliced)

        with patch("pydub.AudioSegment.from_file"):
            result = extract_audio_segment("/fake/full.mp3", 0, 1, "/out/seg.mp3", audio=pre_loaded)

        self.assertEqual(result, "/out/seg.mp3")


if __name__ == "__main__":
    unittest.main()
