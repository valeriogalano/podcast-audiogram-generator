"""
Audiogram Generator for Podcast
"""
import logging
import os

__version__ = "0.1.0"

# Configure package logger once: console (INFO+) and file (DEBUG+)
_logger = logging.getLogger('audiogram_generator')
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    _console = logging.StreamHandler()
    _console.setLevel(logging.INFO)
    _console.setFormatter(logging.Formatter('%(message)s'))

    _log_path = os.path.join(os.getcwd(), 'audiogram_generator.log')
    _file = logging.FileHandler(_log_path)
    _file.setLevel(logging.DEBUG)
    _file.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

    _logger.addHandler(_console)
    _logger.addHandler(_file)
    _logger.propagate = False
