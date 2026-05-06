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
    audio_device: Optional[Any] = None
    audio_input_device: Optional[Any] = None
    audio_output_device: Optional[Any] = None

    # Model paths (for local STT/TTS)
    parakeet_model_path: Optional[str] = None
    piper_model_path: Optional[str] = None

    # Audio microservice endpoints
    stt_endpoint: str = "http://stt:5001"
    tts_endpoint: str = "http://tts:5002"

    # LLM API settings (OpenAI-compatible endpoint)
    llm_api_endpoint: Optional[str] = "http://llm-server:8080/v1"
    llm_api_key: Optional[str] = "not-needed"
    llm_model_name: Optional[str] = "model"
    system_prompt: Optional[str] = None
    first_message: Optional[str] = "Ciao! Sono Fresh Buddy. Come posso aiutarti?"

    # LLM generation settings
    llm_temperature: float = 0.7
    llm_max_tokens: int = 512
    llm_top_p: float = 0.9

    # Piper TTS settings
    piper_voice: str = "it_IT-paola-medium"
    piper_speaker: Optional[int] = None
    piper_noise_scale: float = 0.667
    piper_length_scale: float = 1.0
    tts_volume: float = 1.0
    audio_output_volume: Optional[float] = None
    audio_output_mixer: Optional[str] = None

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

        # Load variables from .env/.nev files before applying explicit env vars.
        env_paths = []
        for name in (".env", ".nev"):
            candidate = config_path.parent / name
            env_paths.append(candidate)
            cwd_candidate = Path(name)
            if cwd_candidate != candidate:
                env_paths.append(cwd_candidate)

        for env_path in env_paths:
            cls._load_env_file(env_path)

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
            "STT_ENDPOINT": "stt_endpoint",
            "TTS_ENDPOINT": "tts_endpoint",
            "PARAKEET_MODEL_PATH": "parakeet_model_path",
            "PIPER_MODEL_PATH": "piper_model_path",
            "AUDIO_DEVICE": "audio_device",
            "AUDIO_INPUT_DEVICE": "audio_input_device",
            "AUDIO_OUTPUT_DEVICE": "audio_output_device",
            "PIPER_VOICE": "piper_voice",
            "TTS_VOLUME": "tts_volume",
            "AUDIO_OUTPUT_VOLUME": "audio_output_volume",
            "AUDIO_OUTPUT_MIXER": "audio_output_mixer",
            "LLM_API_ENDPOINT": "llm_api_endpoint",
            "LLM_API_KEY": "llm_api_key",
            "LLM_MODEL_NAME": "llm_model_name",
            "SYSTEM_PROMPT": "system_prompt",
            "LLM_SYSTEM_PROMPT": "system_prompt",
            "FIRST_MESSAGE": "first_message",
            "LLM_TEMPERATURE": "llm_temperature",
            "LLM_MAX_TOKENS": "llm_max_tokens",
            "LLM_TOP_P": "llm_top_p",
            "DEBUG_MODE": "debug_mode",
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Type conversion
                if config_key in {
                    "audio_device",
                    "audio_input_device",
                    "audio_output_device",
                }:
                    value = int(value) if value.isdigit() else value
                elif isinstance(getattr(config, config_key), bool):
                    value = value.lower() in ("true", "1", "yes")
                elif isinstance(getattr(config, config_key), float):
                    value = float(value)
                elif isinstance(getattr(config, config_key), int):
                    value = int(value)
                elif config_key == "audio_output_volume":
                    value = float(value)
                setattr(config, config_key, value)

        return config

    @staticmethod
    def _load_env_file(env_path: Path) -> None:
        """Load environment variables from a .env file if present."""
        if not env_path.exists():
            return

        try:
            with open(env_path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if line.startswith("export "):
                        line = line[len("export ") :].strip()

                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if not key or key in os.environ:
                        continue

                    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                        value = value[1:-1]

                    os.environ.setdefault(key, value)

            logger.info(f"Loaded environment variables from {env_path}")
        except Exception as e:
            logger.error(f"Error loading env file {env_path}: {e}")

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
    "audio_device": null,
    "audio_input_device": null,
    "audio_output_device": null,

    "parakeet_model_path": null,
    "piper_model_path": null,

    "llm_api_endpoint": "http://llm-server:8080/v1",
    "llm_api_key": "not-needed",
    "llm_model_name": "model",
    "system_prompt": null,
    "first_message": "Ciao! Sono Fresh Buddy. Come posso aiutarti?",

    "piper_voice": "it_IT-paola-medium",
    "piper_speaker": null,
    "piper_noise_scale": 0.667,
    "piper_length_scale": 1.0,
    "tts_volume": 1.0,
    "audio_output_volume": null,
    "audio_output_mixer": null,

    "llm_temperature": 0.7,
    "llm_max_tokens": 512,
    "llm_top_p": 0.9,

    "meeting_storage_dir": "meetings",
    "meeting_summary_length": 300,

    "wake_word": "ciao buddy",
    "wake_word_sensitivity": 0.5,

    "debug_mode": false,
    "log_level": "INFO"
}
"""
