"""
Tests for exit-code propagation on config, feed and rendering errors.

Before this fix, config/feed errors and rendering exceptions were logged and
swallowed: main() always returned None (exit code 0), so a failed CI run
looked green. These tests assert the process now reports failure.
"""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from audiogram_generator import cli, pipeline


def _mock_config(overrides=None):
    values = {
        'feed_url': 'https://example.com/feed.xml',
        'episode': '1',
        'soundbites': 'all',
        'colors': {},
        'formats': {'vertical': {'width': 64, 'height': 64, 'enabled': True}},
        'hashtags': [],
        'show_subtitles': True,
        'dry_run': False,
        'use_episode_cover': False,
        'header_title_source': 'auto',
        'fonts': {},
        'verify_ssl': True,
        'full_episode': False,
        'cta': None,
        'force': False,
        'limit': None,
        'caption_labels': {},
        'caption_transcript': 'inline',
        'manual_soundbites': {},
        'output_dir': './output',
        'temp_dir': './temp',
    }
    if overrides:
        values.update(overrides)

    mock = MagicMock()
    mock.get.side_effect = lambda key, default=None: values.get(key, default)
    return mock


class TestMainExitCodeOnConfigFeedErrors(unittest.TestCase):
    @patch('sys.argv', ['audiogram-generator'])
    @patch('audiogram_generator.cli.Config')
    def test_missing_feed_url_returns_1(self, mock_config_cls):
        mock_config_cls.return_value = _mock_config({'feed_url': None})
        self.assertEqual(cli.main(), 1)

    @patch('sys.argv', ['audiogram-generator'])
    @patch('audiogram_generator.cli.get_podcast_episodes', return_value=([], {}))
    @patch('audiogram_generator.cli.Config')
    def test_no_episodes_in_feed_returns_1(self, mock_config_cls, _get_episodes):
        mock_config_cls.return_value = _mock_config()
        self.assertEqual(cli.main(), 1)

    @patch('sys.argv', ['audiogram-generator'])
    @patch('audiogram_generator.cli.get_podcast_episodes',
           return_value=([{'number': 1, 'title': 'Ep1'}], {'title': 'Podcast'}))
    @patch('audiogram_generator.cli.Config')
    def test_missing_episode_selection_returns_1(self, mock_config_cls, _get_episodes):
        mock_config_cls.return_value = _mock_config({'episode': None})
        self.assertEqual(cli.main(), 1)

    @patch('sys.argv', ['audiogram-generator'])
    @patch('audiogram_generator.cli.get_podcast_episodes',
           return_value=([{'number': 1, 'title': 'Ep1'}], {'title': 'Podcast'}))
    @patch('audiogram_generator.cli.Config')
    def test_missing_soundbites_selection_returns_1(self, mock_config_cls, _get_episodes):
        mock_config_cls.return_value = _mock_config({'soundbites': None})
        self.assertEqual(cli.main(), 1)


class TestMainExitCodeOnRenderingErrors(unittest.TestCase):
    @patch('sys.argv', ['audiogram-generator'])
    @patch('audiogram_generator.cli.process_one_episode', return_value=False)
    @patch('audiogram_generator.cli.get_podcast_episodes',
           return_value=([{'number': 1, 'title': 'Ep1'}], {'title': 'Podcast'}))
    @patch('audiogram_generator.cli.Config')
    def test_failed_episode_generation_returns_1(self, mock_config_cls, _get_episodes, _process):
        mock_config_cls.return_value = _mock_config()
        self.assertEqual(cli.main(), 1)

    @patch('sys.argv', ['audiogram-generator'])
    @patch('audiogram_generator.cli.process_one_episode', return_value=True)
    @patch('audiogram_generator.cli.get_podcast_episodes',
           return_value=([{'number': 1, 'title': 'Ep1'}], {'title': 'Podcast'}))
    @patch('audiogram_generator.cli.Config')
    def test_successful_run_returns_0(self, mock_config_cls, _get_episodes, _process):
        mock_config_cls.return_value = _mock_config()
        self.assertEqual(cli.main(), 0)


class TestRenderingFailurePropagation(unittest.TestCase):
    """Rendering exceptions must propagate as a failure signal, not be swallowed."""

    def _make_selected(self, n_soundbites=2):
        return {
            'number': 20,
            'title': 'Episode 20',
            'link': 'https://example.com/ep20',
            'audio_url': 'https://example.com/ep20.mp3',
            'transcript_url': None,
            'soundbites': [
                {'start': i * 10, 'duration': 5, 'title': f'SB{i}', 'text': f'text{i}'}
                for i in range(1, n_soundbites + 1)
            ],
            'keywords': '',
            'image_url': None,
        }

    @patch('audiogram_generator.pipeline.generate_audiogram', side_effect=RuntimeError("boom"))
    @patch('audiogram_generator.pipeline.extract_audio_segment', return_value='/tmp/seg.mp3')
    @patch('os.path.exists', return_value=True)
    def test_process_single_soundbite_raises_on_render_failure(self, _exists, _extract, _gen):
        selected = self._make_selected(n_soundbites=1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                pipeline._process_single_soundbite(
                    soundbite=selected['soundbites'][0],
                    soundbite_num=1,
                    total_soundbites=None,
                    selected=selected,
                    podcast_info={'title': 'Podcast', 'image_url': None},
                    temp_dir=tmp,
                    logo_path=os.path.join(tmp, 'logo.png'),
                    srt_content=None,
                    full_audio_path='/fake/full.mp3',
                    output_dir=tmp,
                    formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                    colors={},
                    show_subtitles=False,
                    config_hashtags=None,
                    force=True,
                )

    @patch('audiogram_generator.pipeline.generate_audiogram')
    @patch('audiogram_generator.pipeline.shutil.copy2')
    @patch('audiogram_generator.pipeline.extract_audio_segment', return_value='/tmp/seg.mp3')
    @patch('os.path.exists', return_value=True)
    def test_process_single_soundbite_skips_video_when_no_formats_enabled(
            self, _exists, _extract, _copy, mock_generate):
        selected = self._make_selected(n_soundbites=1)
        with tempfile.TemporaryDirectory() as tmp:
            result = pipeline._process_single_soundbite(
                soundbite=selected['soundbites'][0],
                soundbite_num=1,
                total_soundbites=None,
                selected=selected,
                podcast_info={'title': 'Podcast', 'image_url': None},
                temp_dir=tmp,
                logo_path=os.path.join(tmp, 'logo.png'),
                srt_content=None,
                full_audio_path='/fake/full.mp3',
                output_dir=tmp,
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': False}},
                colors={},
                show_subtitles=False,
                config_hashtags=None,
                force=True,
            )

        self.assertEqual(result, {})
        mock_generate.assert_not_called()

    @patch('audiogram_generator.pipeline._process_single_soundbite')
    def test_render_soundbites_batch_continues_after_one_failure(self, mock_process):
        """One soundbite failing must not stop the others, but must mark the batch failed."""
        mock_process.side_effect = [RuntimeError("format failed"), {'vertical': 'Vertical'}]
        selected = self._make_selected(n_soundbites=2)

        with tempfile.TemporaryDirectory() as tmp:
            success = pipeline._render_soundbites_batch(
                soundbite_nums=[1, 2],
                selected=selected,
                podcast_info={'title': 'Podcast', 'image_url': None},
                artwork_url=None,
                srt_content=None,
                full_audio_path='/fake/full.mp3',
                output_dir=tmp,
                temp_dir_base=tmp,
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                colors={},
                show_subtitles=False,
                config_hashtags=None,
            )

        self.assertFalse(success)
        self.assertEqual(mock_process.call_count, 2)

    @patch('audiogram_generator.pipeline._process_single_soundbite')
    def test_render_soundbites_batch_succeeds_when_no_errors(self, mock_process):
        mock_process.return_value = {'vertical': 'Vertical'}
        selected = self._make_selected(n_soundbites=2)

        with tempfile.TemporaryDirectory() as tmp:
            success = pipeline._render_soundbites_batch(
                soundbite_nums=[1, 2],
                selected=selected,
                podcast_info={'title': 'Podcast', 'image_url': None},
                artwork_url=None,
                srt_content=None,
                full_audio_path='/fake/full.mp3',
                output_dir=tmp,
                temp_dir_base=tmp,
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                colors={},
                show_subtitles=False,
                config_hashtags=None,
            )

        self.assertTrue(success)


class TestFullEpisodeExitCode(unittest.TestCase):
    @patch('audiogram_generator.pipeline.generate_audiogram', side_effect=RuntimeError("boom"))
    @patch('audiogram_generator.pipeline.download_image')
    @patch('audiogram_generator.pipeline.load_audio')
    @patch('os.path.exists', return_value=True)
    def test_returns_false_on_render_failure(self, _exists, mock_load_audio, _dl_image, _gen):
        mock_load_audio.return_value.__len__.return_value = 10000
        selected = {'number': 5, 'title': 'Ep5'}

        with tempfile.TemporaryDirectory() as tmp:
            success = pipeline._process_full_episode(
                selected=selected,
                podcast_info={'title': 'Podcast'},
                full_audio_path='/fake/full.mp3',
                srt_content=None,
                artwork_url=None,
                output_dir=tmp,
                temp_dir_base=tmp,
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                colors={},
                show_subtitles=False,
                force=True,
            )

        self.assertFalse(success)

    def test_returns_false_when_audio_missing(self):
        success = pipeline._process_full_episode(
            selected={'number': 5, 'title': 'Ep5'},
            podcast_info={'title': 'Podcast'},
            full_audio_path=None,
            srt_content=None,
            artwork_url=None,
            output_dir='./output',
            temp_dir_base='./temp',
            formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
            colors={},
            show_subtitles=False,
        )
        self.assertFalse(success)

    @patch('os.path.exists', return_value=True)
    def test_returns_true_when_output_already_exists(self, _exists):
        success = pipeline._process_full_episode(
            selected={'number': 5, 'title': 'Ep5'},
            podcast_info={'title': 'Podcast'},
            full_audio_path='/fake/full.mp3',
            srt_content=None,
            artwork_url=None,
            output_dir='./output',
            temp_dir_base='./temp',
            formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
            colors={},
            show_subtitles=False,
            force=False,
        )
        self.assertTrue(success)

    @patch('audiogram_generator.pipeline.generate_audiogram')
    @patch('audiogram_generator.pipeline.load_audio')
    @patch('os.path.exists', return_value=True)
    def test_returns_true_when_no_formats_enabled(self, _exists, mock_load_audio, mock_generate):
        mock_load_audio.return_value.__len__.return_value = 10000
        success = pipeline._process_full_episode(
            selected={'number': 5, 'title': 'Ep5'},
            podcast_info={'title': 'Podcast'},
            full_audio_path='/fake/full.mp3',
            srt_content=None,
            artwork_url=None,
            output_dir='./output',
            temp_dir_base='./temp',
            formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': False}},
            colors={},
            show_subtitles=False,
            force=True,
        )
        self.assertTrue(success)
        mock_generate.assert_not_called()


class TestProcessOneEpisodePropagatesSuccess(unittest.TestCase):
    def _make_selected(self):
        return {
            'number': 30,
            'title': 'Episode 30',
            'link': 'https://example.com/ep30',
            'audio_url': 'https://example.com/ep30.mp3',
            'transcript_url': None,
            'soundbites': [{'start': 0, 'duration': 5, 'title': 'SB1', 'text': 'hello'}],
            'keywords': '',
            'image_url': None,
        }

    def test_dry_run_returns_true(self):
        success = cli.process_one_episode(
            selected=self._make_selected(),
            podcast_info={'title': 'Podcast', 'image_url': None},
            colors={},
            formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
            config_hashtags=None,
            show_subtitles=True,
            output_dir='./output',
            temp_dir_base='./temp',
            soundbites_choice='1',
            dry_run=True,
        )
        self.assertTrue(success)

    @patch('audiogram_generator.pipeline._render_soundbites_batch', return_value=False)
    @patch('os.path.exists', return_value=False)
    def test_returns_false_when_batch_fails(self, _exists, _mock_batch):
        with tempfile.TemporaryDirectory() as tmp:
            success = cli.process_one_episode(
                selected=self._make_selected(),
                podcast_info={'title': 'Podcast', 'image_url': None},
                colors={},
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                config_hashtags=None,
                show_subtitles=True,
                output_dir=tmp,
                temp_dir_base=tmp,
                soundbites_choice='all',
                dry_run=False,
            )
        self.assertFalse(success)

    @patch('audiogram_generator.pipeline._render_soundbites_batch', return_value=True)
    @patch('os.path.exists', return_value=False)
    def test_returns_true_when_batch_succeeds(self, _exists, _mock_batch):
        with tempfile.TemporaryDirectory() as tmp:
            success = cli.process_one_episode(
                selected=self._make_selected(),
                podcast_info={'title': 'Podcast', 'image_url': None},
                colors={},
                formats_config={'vertical': {'width': 64, 'height': 64, 'enabled': True}},
                config_hashtags=None,
                show_subtitles=True,
                output_dir=tmp,
                temp_dir_base=tmp,
                soundbites_choice='all',
                dry_run=False,
            )
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
