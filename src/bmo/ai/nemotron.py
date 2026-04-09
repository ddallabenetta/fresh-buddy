"""Nemotron LLM Integration"""

import logging
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class NemotronLLM:
    """Interface to Nemotron 3 4B running locally."""

    def __init__(self, config=None):
        """
        Initialize Nemotron LLM.

        Args:
            config: Configuration object
        """
        self.config = config
        self.model_path = getattr(self.config, 'nemotron_model_path', None)
        self.model = None
        self.tokenizer = None
        self._initialized = False

        # Generation settings
        self.temperature = getattr(self.config, 'nemotron_temperature', 0.7)
        self.max_tokens = getattr(self.config, 'nemotron_max_tokens', 512)
        self.top_p = getattr(self.config, 'nemotron_top_p', 0.9)

        self._init_model()

    def _init_model(self):
        """Initialize the Nemotron model."""
        try:
            # Try llama-cpp-python first (supports Nemotron)
            from llama_cpp import Llama

            if self.model_path and Path(self.model_path).exists():
                logger.info(f"Loading Nemotron from {self.model_path}")
                self.model = Llama(
                    model_path=str(self.model_path),
                    n_ctx=4096,  # Context window
                    n_gpu_layers=32,  # Layers for Jetson Orin
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    verbose=False
                )
                self._initialized = True
                logger.info("Nemotron model loaded successfully")
            else:
                logger.warning(f"Nemotron model not found at {self.model_path}")
                logger.info("Set nemotron_model_path in config or download model")

        except ImportError:
            logger.warning("llama-cpp-python not available")
            logger.info("Install: pip install llama-cpp-python")
            self._init_mock_mode()
        except Exception as e:
            logger.error(f"Failed to load Nemotron: {e}")
            self._init_mock_mode()

    def _init_mock_mode(self):
        """Initialize mock mode for testing without GPU."""
        logger.info("Running in MOCK mode - responses will be simulated")
        self._initialized = False

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate a response from the model.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text response
        """
        if not self._initialized:
            return self._mock_generate(prompt, system_prompt)

        try:
            # Build messages format for chat completion
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Generate response
            response = self.model.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
            )

            return response['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return self._mock_generate(prompt, system_prompt)

    def _mock_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Mock generation for testing."""
        mock_responses = [
            "I understand. Let me help you with that.",
            "That's an interesting question. Here's what I think...",
            "I've noted that. Is there anything specific you'd like me to do?",
            "Got it! I'm here to help with your meeting notes.",
        ]
        # Simple hash to get consistent response for same input
        response_idx = hash(prompt) % len(mock_responses)
        return mock_responses[response_idx]

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Continue a chat conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Assistant response
        """
        if not self._initialized:
            return self._mock_generate(str(messages))

        try:
            response = self.model.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "I'm having trouble processing that right now."

    def summarize(self, text: str, max_length: int = 200) -> str:
        """
        Summarize a long text.

        Args:
            text: Text to summarize
            max_length: Maximum summary length in words

        Returns:
            Summary text
        """
        system_prompt = f"""Sei Fresh Buddy, un assistente AI gentile e utile. Riassumi il seguente testo 
        in modo conciso in non più di {max_length} parole. Concentrati sui punti chiave e azioni da fare."""

        return self.generate(f"Summarize this:\n\n{text}", system_prompt)

    def extract_action_items(self, text: str) -> List[str]:
        """
        Extract action items from meeting notes.

        Args:
            text: Meeting transcript or notes

        Returns:
            List of action items
        """
        system_prompt = """Sei Fresh Buddy. Estrai tutti i task e le azioni dal seguente testo.
        Ritorna una lista JSON di azioni, ognuna con:
        - task: descrizione del task
        - assignee: chi dovrebbe farlo (se menzionato)
        - deadline: quando dovrebbe essere completato (se menzionato)

        Ritorna SOLO la lista JSON, nient'altro."""

        response = self.generate(text, system_prompt)

        try:
            # Try to parse as JSON
            action_items = json.loads(response)
            return action_items
        except json.JSONDecodeError:
            logger.warning("Failed to parse action items as JSON")
            return [{"task": response, "assignee": None, "deadline": None}]

    def set_temperature(self, temperature: float):
        """Adjust generation temperature."""
        self.temperature = max(0.0, min(2.0, temperature))

    def set_max_tokens(self, max_tokens: int):
        """Set maximum tokens for generation."""
        self.max_tokens = max_tokens

    def is_initialized(self) -> bool:
        """Check if model is loaded and ready."""
        return self._initialized
