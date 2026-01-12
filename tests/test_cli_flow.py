"""
Tests for the CLI flow in dry-run mode and verification of the _nosubs suffix in filenames (mock I/O).
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock

from audiogram_generator import cli


class TestCliFlow(unittest.TestCase):
    def _make_selected(self, with_soundbites=True, with_transcript=True, with_image=True):
        return {
            'number': 142,
            'title': 'Episode title',
            'link': 'https://example/ep142',
            'description': 'desc',
            'soundbites': (
                [
                    {'start': 5, 'duration': 4, 'title': "SB1"},
                    {'start': 12, 'duration': 3, 'title': "SB2"},
                ] if with_soundbites else []
            ),
            'transcript_url': 'https://example/srt.srt' if with_transcript else None,
            'audio_url': 'https://example/audio.mp3',
            'keywords': 'ai, coding',
            'image_url': 'https://example/ep_cover.jpg' if with_image else None,
        }

    def test_dry_run_no_soundbites_prints_message(self):
        selected = self._make_selected(with_soundbites=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice=None,
                dry_run=True,
                use_episode_cover=False,
            )
        out = buf.getvalue()
        self.assertIn("No soundbites available for this episode.", out)

    @patch('audiogram_generator.cli.get_transcript_text', return_value=None)
    def test_dry_run_fallback_to_soundbite_title_when_no_transcript(self, _):
        selected = self._make_selected(with_soundbites=True, with_transcript=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice='1',
                dry_run=True,
                use_episode_cover=False,
            )
        out = buf.getvalue()
        # Should print the SB title as fallback (when transcript=None)
        self.assertIn('SB1', out)
        # Should also print formatted times
        self.assertIn('00:00:05', out)

    def test_dry_run_invalid_selection_prints_error(self):
        selected = self._make_selected(with_soundbites=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice='0',  # invalid
                dry_run=True,
                use_episode_cover=False,
            )
        out = buf.getvalue()
        self.assertIn('Soundbite selection error', out)

    @patch('audiogram_generator.cli.generate_audiogram')
    @patch('audiogram_generator.cli.download_image', return_value='/tmp/cover.jpg')
    @patch('audiogram_generator.cli.extract_audio_segment', return_value='/tmp/seg.mp3')
    @patch('audiogram_generator.cli.download_audio', return_value='/tmp/full.mp3')
    def test_output_filenames_include_nosubs_when_disabled(self, *_mocks):
        selected = self._make_selected(with_soundbites=True, with_transcript=False)
        formats = {
            'vertical': {'width': 1080, 'height': 1920, 'enabled': True},
            'square': {'width': 1080, 'height': 1080, 'enabled': True},
        }
        # Run non-dry-run but with everything mocked; intercept calls
        with patch('audiogram_generator.cli.generate_audiogram') as gen:
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=formats,
                config_hashtags=None,
                show_subtitles=False,  # disabled → _nosubs
                output_dir='./output',
                soundbites_choice='1',
                dry_run=False,
                use_episode_cover=True,
            )
            # Verify that each call to generate_audiogram uses a path with _nosubs
            self.assertGreaterEqual(gen.call_count, 1)
            for call in gen.call_args_list:
                args, kwargs = call
                # output_path is the second positional argument
                output_path = args[1] if len(args) >= 2 else kwargs.get('output_path')
                self.assertIn('_nosubs', output_path)

    @patch('audiogram_generator.cli.transcript_svc.fetch_srt', return_value='FAKE SRT')
    @patch('audiogram_generator.cli.download_audio')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('os.path.exists', return_value=False)
    def test_always_downloads_full_mp3_and_srt(self, mock_exists, mock_open, mock_makedirs, mock_download_audio, mock_fetch_srt):
        selected = self._make_selected(with_soundbites=False) # No soundbites
        
        # Intercept output to avoid clutter
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice=None,
                dry_run=False,
                use_episode_cover=False,
            )
        
        # Verify full audio download attempt
        mock_download_audio.assert_called_once_with(selected['audio_url'], './output/ep142.mp3')
        
        # Verify full SRT fetch attempt
        mock_fetch_srt.assert_called_once_with(selected['transcript_url'])
        
        # Verify SRT file save attempt
        mock_open.assert_any_call('./output/ep142.srt', 'w', encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
