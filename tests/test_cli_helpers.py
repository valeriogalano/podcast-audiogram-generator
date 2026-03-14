"""
Tests for CLI module helper functions (without external I/O)
"""
import unittest
import unittest.mock
from unittest.mock import patch, MagicMock
from audiogram_generator import cli


class TestCliHelpers(unittest.TestCase):
    """Tests for pure and parsing functions"""

    def test_format_seconds(self):
        """Test formatting seconds into HH:MM:SS.mmm string"""
        self.assertEqual(cli.format_seconds(0), "00:00:00.000")
        self.assertEqual(cli.format_seconds(10.5), "00:00:10.500")
        self.assertEqual(cli.format_seconds(3661.007), "01:01:01.007")
        self.assertEqual(cli.format_seconds(-0.1), "-00:00:00.100")

    def test_parse_episode_selection_variants(self):
        """Test variants for episode selection"""
        # None -> empty list
        self.assertEqual(cli.parse_episode_selection(None, 5), [])
        # Valid integer
        self.assertEqual(cli.parse_episode_selection(3, 5), [3])
        # List with spaces and duplicates (preserves order and removes duplicates)
        self.assertEqual(cli.parse_episode_selection("1, 2, 2, 3", 5), [1, 2, 3])
        # all/a case-insensitive
        self.assertEqual(cli.parse_episode_selection("ALL", 3), [1, 2, 3])
        self.assertEqual(cli.parse_episode_selection(" a ", 2), [1, 2])
        # last
        self.assertEqual(cli.parse_episode_selection("last", 7), [7])

    def test_parse_episode_selection_invalid(self):
        """Errors on invalid values for episodes"""
        with self.assertRaises(ValueError):
            cli.parse_episode_selection(0, 5)
        with self.assertRaises(ValueError):
            cli.parse_episode_selection("0", 5)
        with self.assertRaises(ValueError):
            cli.parse_episode_selection("abc", 5)
        with self.assertRaises(ValueError):
            cli.parse_episode_selection("", 5)

    def test_parse_soundbite_selection_variants(self):
        """Test variants for soundbite selection"""
        # None -> all
        self.assertEqual(cli.parse_soundbite_selection(None, 3), [1, 2, 3])
        # Valid integer
        self.assertEqual(cli.parse_soundbite_selection(2, 3), [2])
        # String list with spaces and duplicates
        self.assertEqual(cli.parse_soundbite_selection("1, 1, 3", 3), [1, 3])
        # all/a case-insensitive
        self.assertEqual(cli.parse_soundbite_selection("ALL", 4), [1, 2, 3, 4])

    def test_parse_soundbite_selection_invalid(self):
        """Errors on invalid values for soundbite"""
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection(0, 3)
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection("0", 3)
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection("x,y", 3)
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection("", 3)


class TestProcessSingleSoundbitePassesLoadedAudio(unittest.TestCase):
    """T11 — _process_single_soundbite passes loaded_audio to extract_audio_segment."""

    def _make_soundbite(self):
        return {'start': 10, 'duration': 5, 'title': 'Test SB', 'text': 'hello'}

    def _make_selected(self):
        return {
            'number': 1,
            'title': 'Episode',
            'link': 'https://example.com/ep1',
            'audio_url': 'https://example.com/audio.mp3',
            'transcript_url': None,
            'soundbites': [self._make_soundbite()],
            'keywords': '',
            'image_url': None,
        }

    @patch('audiogram_generator.cli.generate_audiogram')
    @patch('audiogram_generator.cli.extract_audio_segment', return_value='/tmp/seg.mp3')
    @patch('os.path.exists', return_value=True)
    def test_loaded_audio_forwarded_to_extract(self, mock_exists, mock_extract, mock_gen):
        """loaded_audio kwarg must be forwarded to extract_audio_segment."""
        import tempfile, os
        pre_loaded = unittest.mock.MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            cli._process_single_soundbite(
                soundbite=self._make_soundbite(),
                soundbite_num=1,
                total_soundbites=1,
                selected=self._make_selected(),
                podcast_info={'title': 'Podcast', 'image_url': None},
                temp_dir=tmp,
                logo_path=os.path.join(tmp, 'logo.png'),
                srt_content=None,
                full_audio_path='/fake/full.mp3',
                output_dir=tmp,
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                show_subtitles=False,
                config_hashtags=None,
                loaded_audio=pre_loaded,
            )

        # extract_audio_segment must have been called with audio=pre_loaded
        mock_extract.assert_called_once()
        _, kwargs = mock_extract.call_args
        self.assertIs(kwargs.get('audio'), pre_loaded)

    @patch('audiogram_generator.cli.generate_audiogram')
    @patch('audiogram_generator.cli.extract_audio_segment', return_value='/tmp/seg.mp3')
    @patch('os.path.exists', return_value=True)
    def test_none_loaded_audio_still_calls_extract(self, mock_exists, mock_extract, mock_gen):
        """When loaded_audio=None, extract_audio_segment is still called (fallback)."""
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmp:
            cli._process_single_soundbite(
                soundbite=self._make_soundbite(),
                soundbite_num=1,
                total_soundbites=1,
                selected=self._make_selected(),
                podcast_info={'title': 'Podcast', 'image_url': None},
                temp_dir=tmp,
                logo_path=os.path.join(tmp, 'logo.png'),
                srt_content=None,
                full_audio_path='/fake/full.mp3',
                output_dir=tmp,
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                show_subtitles=False,
                config_hashtags=None,
                loaded_audio=None,
            )

        mock_extract.assert_called_once()
        _, kwargs = mock_extract.call_args
        self.assertIsNone(kwargs.get('audio'))


if __name__ == "__main__":
    unittest.main()
