"""
Provider constants loader.

This module loads provider constants from the JSON file (single source of truth).
All constants are now stored in provider_constants.json.
"""

import json
import os


def get_provider_constants():
    """Load and return provider constants from JSON file."""
    json_path = os.path.join(os.path.dirname(__file__), 'provider_constants.json')
    with open(json_path, 'r') as f:
        return json.load(f)