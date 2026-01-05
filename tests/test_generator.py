"""
Tests for the audiogram generator modules
"""
import unittest
from audiogram_generator import cli


class TestCliModule(unittest.TestCase):
    """Tests for the CLI module"""

    def test_parse_srt_time(self):
        """Test conversion of SRT timestamp to seconds"""
        # Format test: 00:00:10,500 -> 10.5 seconds
        self.assertEqual(cli.parse_srt_time("00:00:10,500"), 10.5)
        self.assertEqual(cli.parse_srt_time("00:01:00,000"), 60.0)
        self.assertEqual(cli.parse_srt_time("01:00:00,000"), 3600.0)
        self.assertEqual(cli.parse_srt_time("00:00:00,500"), 0.5)
        self.assertEqual(cli.parse_srt_time("00:05:30,250"), 330.25)

    def test_parse_srt_time_edge_cases(self):
        """Test edge cases for SRT timestamp conversion"""
        # Zero timestamp
        self.assertEqual(cli.parse_srt_time("00:00:00,000"), 0.0)

        # Timestamp with milliseconds
        self.assertEqual(cli.parse_srt_time("00:00:01,123"), 1.123)

    def test_parse_episode_selection_last(self):
        """Test episode selection with 'last' value"""
        # max_episode=150 -> 'last' should return [150]
        self.assertEqual(cli.parse_episode_selection('last', 150), [150])
        # Case-insensitive and with spaces
        self.assertEqual(cli.parse_episode_selection('  LAST  ', 12), [12])


if __name__ == "__main__":
    unittest.main()
