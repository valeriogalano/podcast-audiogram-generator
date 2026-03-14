"""
Tests for video_generator: pure functions that don't require FFmpeg or real fonts.
"""
import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from PIL import Image

from audiogram_generator.video_generator import (
    _resolve_header_text,
    _precompute_header,
    _precompute_transcript,
    _render_logo,
    get_waveform_data,
    create_audiogram_frame,
    LAYOUT_CONFIGS,
)


class TestResolveHeaderText(unittest.TestCase):
    """T4 — _resolve_header_text: all header_title_source values."""

    def test_none_source_returns_none(self):
        result = _resolve_header_text("Podcast", "Episode", "none", "Soundbite")
        self.assertIsNone(result)

    def test_podcast_source(self):
        result = _resolve_header_text("My Podcast", "Episode", "podcast", None)
        self.assertEqual(result, "My Podcast")

    def test_episode_source(self):
        result = _resolve_header_text("My Podcast", "My Episode", "episode", None)
        self.assertEqual(result, "My Episode")

    def test_soundbite_source_uses_soundbite_title(self):
        result = _resolve_header_text("Podcast", "Episode", "soundbite", "Soundbite Title")
        self.assertEqual(result, "Soundbite Title")

    def test_soundbite_source_falls_back_to_episode(self):
        result = _resolve_header_text("Podcast", "Episode Title", "soundbite", "")
        self.assertEqual(result, "Episode Title")

    def test_soundbite_source_falls_back_to_podcast_when_no_episode(self):
        result = _resolve_header_text("My Podcast", "", "soundbite", "")
        self.assertEqual(result, "My Podcast")

    def test_auto_prefers_episode(self):
        result = _resolve_header_text("Podcast", "Episode", "auto", None)
        self.assertEqual(result, "Episode")

    def test_auto_falls_back_to_podcast(self):
        result = _resolve_header_text("My Podcast", "", "auto", None)
        self.assertEqual(result, "My Podcast")

    def test_auto_returns_none_when_both_empty(self):
        result = _resolve_header_text("", "", "auto", None)
        self.assertIsNone(result)

    def test_unknown_source_treated_as_auto(self):
        result = _resolve_header_text("Podcast", "Episode", "unknown_value", None)
        self.assertEqual(result, "Episode")


def _mock_draw():
    """Return a mock ImageDraw whose textbbox always returns a realistic int tuple."""
    draw = MagicMock()
    draw.textbbox.return_value = (0, 0, 100, 20)
    return draw


class TestPrecomputeHeader(unittest.TestCase):
    """T5 — _precompute_header: returns coherent cache dict."""

    def _mock_font(self):
        font = MagicMock()
        font.getmetrics.return_value = (12, 3)
        return font

    @patch("audiogram_generator.video_generator.ImageDraw.Draw", return_value=_mock_draw())
    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    @patch("audiogram_generator.video_generator.ImageFont.load_default")
    def test_returns_required_keys(self, mock_default, mock_truetype, mock_draw_cls):
        mock_truetype.return_value = self._mock_font()
        layout = LAYOUT_CONFIGS['vertical']
        cache = _precompute_header(1080, 1920, layout, None, "Podcast", "Episode")
        for key in ('header_height', 'lines', 'font', 'base_h', 'total_text_h', 'pad_x', 'pad_y'):
            self.assertIn(key, cache)

    def test_no_text_when_source_is_none(self):
        layout = LAYOUT_CONFIGS['vertical']
        cache = _precompute_header(1080, 1920, layout, None, "Podcast", "Episode",
                                   header_title_source="none")
        self.assertEqual(cache['lines'], [])
        self.assertIsNone(cache['font'])

    @patch("audiogram_generator.video_generator.ImageDraw.Draw", return_value=_mock_draw())
    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    def test_header_height_matches_layout(self, mock_truetype, mock_draw_cls):
        mock_truetype.return_value = self._mock_font()
        layout = LAYOUT_CONFIGS['square']
        cache = _precompute_header(1080, 1080, layout, None, "Podcast", "Episode")
        expected = int(1080 * layout['header_ratio'])
        self.assertEqual(cache['header_height'], expected)

    @patch("audiogram_generator.video_generator.ImageDraw.Draw", return_value=_mock_draw())
    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    def test_falls_back_to_default_font_on_error(self, mock_truetype, mock_draw_cls):
        mock_truetype.side_effect = OSError("font not found")
        layout = LAYOUT_CONFIGS['vertical']
        with patch("audiogram_generator.video_generator.ImageFont.load_default") as mock_default:
            mock_default.return_value = self._mock_font()
            cache = _precompute_header(1080, 1920, layout, None, "Podcast", "Episode")
        mock_default.assert_called()
        self.assertIsNotNone(cache)


class TestPrecomputeTranscript(unittest.TestCase):
    """T6 — _precompute_transcript: font, style and transcript_y for all 3 layouts."""

    def _colors(self):
        return {'primary': (242, 101, 34), 'background': (235, 213, 197),
                'text': (255, 255, 255), 'transcript_bg': (50, 50, 50)}

    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    def test_returns_required_keys(self, mock_truetype):
        mock_truetype.return_value = MagicMock()
        layout = LAYOUT_CONFIGS['vertical']
        cache = _precompute_transcript(1080, 1920, layout, self._colors())
        for key in ('font', 'style', 'max_width', 'transcript_y'):
            self.assertIn(key, cache)

    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    def test_max_lines_capped_by_layout(self, mock_truetype):
        mock_truetype.return_value = MagicMock()
        for fmt, layout in LAYOUT_CONFIGS.items():
            with self.subTest(format=fmt):
                cache = _precompute_transcript(1080, 1080, layout, self._colors())
                self.assertLessEqual(cache['style']['max_lines'], layout['max_lines'])

    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    def test_transcript_y_is_positive(self, mock_truetype):
        mock_truetype.return_value = MagicMock()
        for fmt, layout in LAYOUT_CONFIGS.items():
            with self.subTest(format=fmt):
                cache = _precompute_transcript(1080, 1080, layout, self._colors())
                self.assertGreater(cache['transcript_y'], 0)

    @patch("audiogram_generator.video_generator.ImageFont.truetype")
    def test_falls_back_to_default_font(self, mock_truetype):
        mock_truetype.side_effect = OSError("no font")
        layout = LAYOUT_CONFIGS['vertical']
        with patch("audiogram_generator.video_generator.ImageFont.load_default") as mock_def:
            mock_def.return_value = MagicMock()
            cache = _precompute_transcript(1080, 1920, layout, self._colors())
        mock_def.assert_called()
        self.assertIsNotNone(cache['font'])


class TestRenderLogo(unittest.TestCase):
    """T8 — _render_logo: handles None logo gracefully."""

    def test_none_logo_does_not_raise(self):
        img = Image.new('RGB', (100, 100))
        _render_logo(img, 100, 0, 100, None)  # must not raise

    def test_logo_pasted_at_correct_position(self):
        img = Image.new('RGB', (200, 200))
        logo = Image.new('RGBA', (40, 40), (255, 0, 0, 255))
        pasted_positions = []
        original_paste = img.paste

        def capture_paste(im, pos, *args, **kwargs):
            pasted_positions.append(pos)
            original_paste(im, pos, *args, **kwargs)

        img.paste = capture_paste
        _render_logo(img, 200, 0, 200, logo)
        self.assertEqual(len(pasted_positions), 1)
        x, y = pasted_positions[0]
        # Logo should be horizontally centered
        self.assertEqual(x, (200 - 40) // 2)


class TestGetWaveformData(unittest.TestCase):
    """T7 — get_waveform_data: vectorized output length equals int(duration * fps)."""

    def _make_mock_audio(self, duration_ms=2000, frame_rate=44100, channels=1):
        audio = MagicMock()
        audio.frame_rate = frame_rate
        audio.channels = channels
        n_samples = int(duration_ms / 1000 * frame_rate * channels)
        audio.get_array_of_samples.return_value = [1000] * n_samples
        # len(audio) returns duration in ms for pydub AudioSegment
        audio.__len__ = MagicMock(return_value=duration_ms)
        return audio

    def test_output_length_matches_duration(self):
        fps = 24
        duration_ms = 3000
        mock_audio = self._make_mock_audio(duration_ms=duration_ms)

        with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
            result = get_waveform_data("/fake/audio.mp3", fps=fps)

        expected_frames = int((duration_ms / 1000) * fps)
        self.assertEqual(len(result), expected_frames)

    def test_output_is_numpy_array(self):
        mock_audio = self._make_mock_audio()
        with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
            result = get_waveform_data("/fake/audio.mp3", fps=24)
        self.assertIsInstance(result, np.ndarray)

    def test_amplitudes_are_non_negative(self):
        mock_audio = self._make_mock_audio()
        with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
            result = get_waveform_data("/fake/audio.mp3", fps=24)
        self.assertTrue(np.all(result >= 0))


class TestCreateAudiogramFrameSmoke(unittest.TestCase):
    """T10 — Smoke test: create_audiogram_frame returns a valid numpy RGB array."""

    def _patch_drawing(self):
        """Context managers to patch font loading and draw measurements."""
        mock_font = MagicMock()
        mock_font.getmetrics.return_value = (12, 3)
        draw_instance = MagicMock()
        draw_instance.textbbox.return_value = (0, 0, 30, 12)
        return (
            patch("audiogram_generator.video_generator.ImageFont.truetype", return_value=mock_font),
            patch("audiogram_generator.video_generator.ImageFont.load_default", return_value=mock_font),
            patch("audiogram_generator.video_generator.ImageDraw.Draw", return_value=draw_instance),
        )

    def test_returns_correct_shape(self):
        width, height = 64, 64
        colors = {'primary': (242, 101, 34), 'background': (235, 213, 197),
                  'text': (255, 255, 255), 'transcript_bg': (50, 50, 50)}
        logo = Image.new('RGBA', (10, 10), (255, 0, 0, 128))

        p1, p2, p3 = self._patch_drawing()
        with p1, p2, p3:
            frame = create_audiogram_frame(
                width, height,
                logo_img=logo,
                podcast_title="Test Podcast",
                episode_title="Test Episode",
                waveform_data=np.zeros(24),
                current_time=0.0,
                transcript_chunks=[],
                audio_duration=1.0,
                colors_tuples=colors,
                format_name='vertical',
            )

        self.assertIsInstance(frame, np.ndarray)
        self.assertEqual(frame.shape, (height, width, 3))

    def test_none_logo_does_not_crash(self):
        colors = {'primary': (242, 101, 34), 'background': (235, 213, 197),
                  'text': (255, 255, 255), 'transcript_bg': (50, 50, 50)}

        p1, p2, p3 = self._patch_drawing()
        with p1, p2, p3:
            frame = create_audiogram_frame(
                64, 64,
                logo_img=None,
                podcast_title="Podcast",
                episode_title="Episode",
                waveform_data=np.zeros(24),
                current_time=0.0,
                transcript_chunks=[],
                audio_duration=1.0,
                colors_tuples=colors,
                format_name='square',
            )
        self.assertEqual(frame.shape, (64, 64, 3))


if __name__ == "__main__":
    unittest.main()
