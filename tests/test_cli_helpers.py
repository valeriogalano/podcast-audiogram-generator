"""
Tests for CLI module helper functions (without external I/O)
"""
import unittest
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


if __name__ == "__main__":
    unittest.main()
