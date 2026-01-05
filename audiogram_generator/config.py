"""
Configuration management module for the audiogram generator
"""
import os
import yaml
from typing import Dict, Any, Optional


class Config:
    """Classe per gestire la configurazione dell'applicazione"""

    DEFAULT_CONFIG = {
        'feed_url': None,
        'output_dir': './output',
        'episode': None,
        'soundbites': None,
        'dry_run': False,
        'show_subtitles': True,
        'use_episode_cover': False,
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
        Inizializza la configurazione

        Args:
            config_file: Path al file di configurazione YAML (opzionale)
        """
        # Deep copy per evitare modifiche ai default
        import copy
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)

        if config_file and os.path.exists(config_file):
            self.load_from_file(config_file)

    def load_from_file(self, config_file: str) -> None:
        """
        Carica la configurazione da file YAML

        Args:
            config_file: Path al file di configurazione
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    # Deep merge for colors, formats and caption_labels
                    for key, value in file_config.items():
                        if key in ['colors', 'formats', 'caption_labels'] and isinstance(value, dict):
                            if key not in self.config:
                                self.config[key] = {}
                            self._deep_merge(self.config[key], value)
                        else:
                            self.config[key] = value
        except Exception as e:
            # Messaggio di errore in italiano per coerenza con i test e i messaggi del progetto
            raise Exception(f"Errore nel caricamento del file di configurazione: {e}")

    def _deep_merge(self, base: dict, update: dict) -> None:
        """
        Merge profondo di dizionari nested

        Args:
            base: Dizionario base da aggiornare
            update: Dizionario con gli aggiornamenti
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def update_from_args(self, args: Dict[str, Any]) -> None:
        """
        Aggiorna la configurazione con argomenti da CLI
        Gli argomenti CLI hanno precedenza sul file di configurazione

        Args:
            args: Dizionario con gli argomenti da CLI
        """
        for key, value in args.items():
            if value is not None:
                self.config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Ottiene un valore di configurazione

        Args:
            key: Chiave della configurazione
            default: Valore di default se la chiave non esiste

        Returns:
            Il valore della configurazione
        """
        return self.config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """
        Ottiene tutta la configurazione

        Returns:
            Dizionario con tutta la configurazione
        """
        return self.config.copy()
