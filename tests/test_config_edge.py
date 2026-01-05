"""
Additional tests for Config: CLI>YAML>default precedence, deep-merge and edge cases.
"""
import tempfile
import os
import unittest
import yaml

from audiogram_generator.config import Config


class TestConfigEdge(unittest.TestCase):
    """Edge cases on configuration loading and merging"""

    def test_update_from_args_does_not_override_with_none(self):
        # Initial YAML
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'feed_url': 'https://example.com/feed.xml',
                            'output_dir': './from_yaml'}, f)
            path = f.name
        try:
            cfg = Config(path)
            # Apply args where one is None → should not override
            cfg.update_from_args({'feed_url': None, 'output_dir': './from_args'})
            self.assertEqual(cfg.get('feed_url'), 'https://example.com/feed.xml')
            self.assertEqual(cfg.get('output_dir'), './from_args')
        finally:
            os.unlink(path)

    def test_deep_merge_formats_partial_override(self):
        # YAML that disables only the square format
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'formats': {'square': {'enabled': False}}}, f)
            path = f.name
        try:
            cfg = Config(path)
            formats = cfg.get('formats')
            # width/height of square should remain from defaults
            self.assertIn('width', formats['square'])
            self.assertIn('height', formats['square'])
            self.assertIs(formats['square']['enabled'], False)
            # vertical untouched, still enabled True by default
            self.assertIs(formats['vertical']['enabled'], True)
        finally:
            os.unlink(path)

    def test_unknown_keys_are_preserved(self):
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'unknown_key': 123}, f)
            path = f.name
        try:
            cfg = Config(path)
            self.assertEqual(cfg.get('unknown_key'), 123)
        finally:
            os.unlink(path)

    def test_yaml_crlf_and_null_values(self):
        # Content with CRLF and null values
        content = 'feed_url: https://example.com\r\nepisode: null\r\n'
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            cfg = Config(path)
            self.assertEqual(cfg.get('feed_url'), 'https://example.com')
            # null value remains None and doesn't break defaults
            self.assertIsNone(cfg.get('episode'))
            self.assertEqual(cfg.get('output_dir'), './output')
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
