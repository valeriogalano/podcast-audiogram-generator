"""
Configuration management module for the audiogram generator
"""
import os
import yaml
from typing import Dict, Any, Optional


class Config:
    """Class to manage application configuration"""

    DEFAULT_CONFIG = {
        'feed_url': None,
        'output_dir': './output',
        'episode': None,
        'soundbites': None,
        'dry_run': False,
        'show_subtitles': True,
        'use_episode_cover': False,
        'manual_soundbites': {},
        # Header title text source: 'auto' (episode then podcast),
        # or explicitly 'episode' | 'podcast' | 'soundbite' | 'none'
        'header_title_source': 'auto',
        'caption_labels': {
            'episode_prefix': 'Episode',
            'listen_full_prefix': 'Listen to the full episode',
        },
        'colors': {
            'primary': [242, 101, 34],      # Orange (header, footer, bars)
            'background': [235, 213, 197],  # Beige (central background)
            'text': [255, 255, 255],        # White (text)
            'transcript_bg': [0, 0, 0]      # Black (transcript background)
        },
        'fonts': {
            'header': '/System/Library/Fonts/Helvetica.ttc',
            'transcript': '/System/Library/Fonts/Helvetica.ttc'
        },
        'formats': {
            'vertical': {
                'width': 1080,
                'height': 1920,
                'enabled': True,
                'description': 'Vertical 9:16 (Reels, Stories, Shorts, TikTok)'
            },
            'square': {
                'width': 1080,
                'height': 1080,
                'enabled': True,
                'description': 'Square 1:1 (Instagram Post, Twitter, Mastodon)'
            },
            'horizontal': {
                'width': 1920,
                'height': 1080,
                'enabled': True,
                'description': 'Horizontal 16:9 (YouTube)'
            }
        }
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        Initializes the configuration.

        Args:
            config_file: Path to the YAML configuration file (optional)
        """
        # Deep copy to avoid modifying defaults
        import copy
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)

        if config_file and os.path.exists(config_file):
            self.load_from_file(config_file)

    def load_from_file(self, config_file: str) -> None:
        """
        Loads the configuration from a YAML file.

        Args:
            config_file: Path to the configuration file
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    # Deep merge for colors, formats, fonts and caption_labels
                    for key, value in file_config.items():
                        if key in ['colors', 'formats', 'fonts', 'caption_labels'] and isinstance(value, dict):
                            if key not in self.config:
                                self.config[key] = {}
                            self._deep_merge(self.config[key], value)
                        else:
                            self.config[key] = value
        except Exception as e:
            raise Exception(f"Error loading the configuration file: {e}")

    def _deep_merge(self, base: dict, update: dict) -> None:
        """
        Deep merge of nested dictionaries.

        Args:
            base: Base dictionary to update
            update: Dictionary with updates
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def update_from_args(self, args: Dict[str, Any]) -> None:
        """
        Updates the configuration with CLI arguments.
        CLI arguments take precedence over the configuration file.

        Args:
            args: Dictionary with CLI arguments
        """
        for key, value in args.items():
            if value is not None:
                self.config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a configuration value.

        Args:
            key: Configuration key
            default: Default value if the key does not exist

        Returns:
            The configuration value
        """
        return self.config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """
        Gets all configuration.

        Returns:
            Dictionary with all configuration
        """
        return self.config.copy()
