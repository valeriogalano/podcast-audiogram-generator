"""
Tests for transcription functions and caption generation in cli.py
"""
import io
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from audiogram_generator import cli


FAKE_SRT = """
1
00:00:00,000 --> 00:00:02,000
Fuori dal range

2
00:00:05,000 --> 00:00:07,000
Dentro l'intervallo uno

3
00:00:07,000 --> 00:00:09,000
Dentro l'intervallo due

4
00:00:09,500 --> 00:00:10,000
Parzialmente dentro (da escludere)
""".strip()


class TestTranscriptAndCaptions(unittest.TestCase):
    """Test SRT parsing and caption file generation"""

    def _mock_urlopen(self):
        # Returns an object similar to HTTPResponse with read() -> bytes
        mm = MagicMock()
        mm.read.return_value = FAKE_SRT.encode("utf-8")
        # Context for with ... as response
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mm
        mock_ctx.__exit__.return_value = False
        return mock_ctx

    @patch("urllib.request.urlopen")
    def test_get_transcript_text_range(self, mock_urlopen):
        """Extracts only SRT blocks entirely contained in the range"""
        mock_urlopen.return_value = self._mock_urlopen()
        # Range: start=5s, duration=4s -> [5,9]
        text = cli.get_transcript_text("http://example/srt", 5, 4)
        # Should include blocks 2 and 3, but not 1 (outside) nor 4 (partial)
        self.assertIsNotNone(text)
        self.assertIn("Dentro l'intervallo uno", text)
        self.assertIn("Dentro l'intervallo due", text)
        self.assertNotIn("Fuori", text)
        self.assertNotIn("Parzialmente", text)

    @patch("urllib.request.urlopen")
    def test_get_transcript_text_no_matches(self, mock_urlopen):
        """Returns None if no block is entirely contained"""
        mock_urlopen.return_value = self._mock_urlopen()
        text = cli.get_transcript_text("http://example/srt", 20, 3)
        self.assertIsNone(text)

    @patch("urllib.request.urlopen")
    def test_get_transcript_chunks_relative_timing(self, mock_urlopen):
        """Chunks have relative timing to the soundbite and respect boundaries"""
        mock_urlopen.return_value = self._mock_urlopen()
        chunks = cli.get_transcript_chunks("http://example/srt", 5, 4)
        self.assertEqual(len(chunks), 2)
        # First chunk: [5,7] -> relative [0,2]
        self.assertAlmostEqual(chunks[0]['start'], 0)
        self.assertAlmostEqual(chunks[0]['end'], 2)
        self.assertIn("intervallo uno", chunks[0]['text'])
        # Second chunk: [7,9] -> relative [2,4]
        self.assertAlmostEqual(chunks[1]['start'], 2)
        self.assertAlmostEqual(chunks[1]['end'], 4)

    def test_generate_caption_file_hashtags_and_defaults(self):
        """Generates file with normalized and default hashtags when absent"""
        with tempfile.NamedTemporaryFile("r+", suffix=".txt", delete=True) as tmp:
            cli.generate_caption_file(
                output_path=tmp.name,
                episode_number=42,
                episode_title="Title",
                episode_link="https://example/ep",
                soundbite_title="SB",
                transcript_text="Text",
                podcast_keywords="AI, coding, #Podcast",
                episode_keywords="AI,   Dev Ops",
                config_hashtags=["Podcast", "python"]
            )
            tmp.seek(0)
            content = tmp.read()
            # Header and body
            self.assertIn("Episode 42: Title", content)
            self.assertIn("SB", content)
            self.assertIn("Text", content)
            self.assertIn("Listen to the full episode: https://example/ep", content)
            # Hashtags: normalized, unique, with # and in lowercase, no spaces
            self.assertIn("#ai", content)
            self.assertIn("#coding", content)
            self.assertIn("#podcast", content)
            self.assertIn("#devops", content)
            self.assertIn("#python", content)

        # Nessun hashtag disponibile -> usa default #podcast
        with tempfile.NamedTemporaryFile("r+", suffix=".txt", delete=True) as tmp2:
            cli.generate_caption_file(
                output_path=tmp2.name,
                episode_number=1,
                episode_title="x",
                episode_link="y",
                soundbite_title="z",
                transcript_text="t",
                podcast_keywords=None,
                episode_keywords=None,
                config_hashtags=None
            )
            tmp2.seek(0)
            content2 = tmp2.read()
            self.assertIn("#podcast", content2)


if __name__ == "__main__":
    unittest.main()
