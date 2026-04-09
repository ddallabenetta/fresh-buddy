"""Configuration Management for Fresh Buddy"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Fresh Buddy configuration."""

    # Hardware settings
    i2c_bus: int = 1
    display_address: int = 0x3C
    audio_device: int = 0

    # Model paths
    nemotron_model_path: Optional[str] = None
    parakeet_model_path: Optional[str] = None
    piper_model_path: Optional[str] = None

    # Piper TTS settings
    piper_voice: str = "it_IT-riccardo-medium"
    piper_speaker: Optional[int] = None
    piper_noise_scale: float = 0.667
    piper_length_scale: float = 1.0

    # Nemotron LLM settings
    nemotron_temperature: float = 0.7
    nemotron_max_tokens: int = 512
    nemotron_top_p: float = 0.9

    # Meeting settings
    meeting_storage_dir: str = "meetings"
    meeting_summary_length: int = 300

    # Wake word settings
    wake_word: str = "ciao buddy"
    wake_word_sensitivity: float = 0.5

    # Debug settings
    debug_mode: bool = False
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from file or environment.

        Args:
            config_path: Path to config JSON file

        Returns:
            Config instance
        """
        config = cls()

        # Try to load from file
        if config_path is None:
            config_path = Path("config.json")

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
                logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        # Override with environment variables
        env_mappings = {
            "NEMOTRON_MODEL_PATH": "nemotron_model_path",
            "PARAKEET_MODEL_PATH": "parakeet_model_path",
            "PIPER_MODEL_PATH": "piper_model_path",
            "PIPER_VOICE": "piper_voice",
            "NEMOTRON_TEMPERATURE": "nemotron_temperature",
            "NEMOTRON_MAX_TOKENS": "nemotron_max_tokens",
            "DEBUG_MODE": "debug_mode",
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Type conversion
                if isinstance(getattr(config, config_key), bool):
                    value = value.lower() in ("true", "1", "yes")
                elif isinstance(getattr(config, config_key), float):
                    value = float(value)
                elif isinstance(getattr(config, config_key), int):
                    value = int(value)
                setattr(config, config_key, value)

        return config

    def save(self, config_path: Path = Path("config.json")):
        """
        Save configuration to file.

        Args:
            config_path: Path to save config
        """
        try:
            with open(config_path, 'w') as f:
                json.dump(asdict(self), f, indent=2)
            logger.info(f"Config saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """
        Create Config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            Config instance
        """
        config = cls()
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config


# Default config as JSON for reference
DEFAULT_CONFIG_JSON = """
{
    "i2c_bus": 1,
    "display_address": 60,
    "audio_device": 0,

    "nemotron_model_path": null,
    "parakeet_model_path": null,
    "piper_model_path": null,

    "piper_voice": "it_IT-riccardo-medium",
    "piper_speaker": null,
    "piper_noise_scale": 0.667,
    "piper_length_scale": 1.0,

    "nemotron_temperature": 0.7,
    "nemotron_max_tokens": 512,
    "nemotron_top_p": 0.9,

    "meeting_storage_dir": "meetings",
    "meeting_summary_length": 300,

    "wake_word": "ciao buddy",
    "wake_word_sensitivity": 0.5,

    "debug_mode": false,
    "log_level": "INFO"
}
"""
