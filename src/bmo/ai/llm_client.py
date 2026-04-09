"""LLM Client — OpenAI-Compatible API Integration"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import openai, fallback to requests
try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    import requests


class LLMClient:
    """Interface to LLM via OpenAI-compatible API endpoint."""

    def __init__(self, config=None):
        """
        Initialize LLM API client.

        Args:
            config: Configuration object with llm_api_endpoint and optional api_key
        """
        self.config = config
        self.endpoint = (
            getattr(self.config, "llm_api_endpoint", None) or "http://localhost:8080/v1"
        )
        self.api_key = getattr(self.config, "llm_api_key", None) or "not-needed"
        self.model_name = getattr(self.config, "llm_model_name", None) or "model"

        # Generation settings
        self.temperature = getattr(self.config, "llm_temperature", 0.7)
        self.max_tokens = getattr(self.config, "llm_max_tokens", 512)
        self.top_p = getattr(self.config, "llm_top_p", 0.9)

        _base = (
            "Sei Fresh Buddy, un assistente AI amichevole integrato in un dispositivo fisico con un viso animato. "
            "Rispondi SEMPRE in italiano, in modo naturale e conciso. "
            "Non usare mai l'inglese o altre lingue, a meno che l'utente non ti scriva esplicitamente in un'altra lingua."
            "Usa frasi brevi e concise, evitando l'utilizzo di emoji."
        )
        self._system_prompt_base = _base
        # Extended version used when the backend doesn't support tool/function calling.
        self._system_prompt_with_tag = (
            _base + "\n\n"
            "Alla fine di ogni risposta aggiungi SEMPRE, su una riga separata, il tag dell'emozione appropriata:\n"
            "[EMOZIONE: <nome>]\n\n"
            "Valori validi:\n"
            "- neutral  → risposta informativa o descrittiva, tono piatto.\n"
            "- happy    → risposta positiva, incoraggiante, accordo entusiasta.\n"
            "- excited  → notizia straordinaria, entusiasmo genuino.\n"
            "- sad      → cattive notizie, scuse, impossibilità di aiutare.\n"
            "- confused → domanda ambigua, richiesta di chiarimenti."
        )

        # Tool definition for structured emotion + text output.
        # Using tool_choice="required" forces the model to always return structured data
        # instead of appending a fragile free-text tag.
        self._respond_tool = {
            "type": "function",
            "function": {
                "name": "respond",
                "description": "Deliver your reply to the user together with the emotion that best matches your tone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The full response text in Italian.",
                        },
                        "emotion": {
                            "type": "string",
                            "enum": ["neutral", "happy", "excited", "sad", "confused"],
                            "description": (
                                "neutral: informative or descriptive reply, flat tone. "
                                "happy: positive, encouraging, enthusiastic agreement. "
                                "excited: extraordinary news, genuine enthusiasm, surprising discovery. "
                                "sad: bad news, apologies, inability to help, regret. "
                                "confused: ambiguous request, need clarification, uncertain answer."
                            ),
                        },
                    },
                    "required": ["text", "emotion"],
                },
            },
        }

        self._client = None
        self._initialized = False
        self._tool_calling_supported = (
            True  # flipped to False on first failed tool call
        )
        self._init_client()

    @property
    def default_system_prompt(self) -> str:
        """Returns the appropriate system prompt depending on tool calling support."""
        if self._tool_calling_supported:
            return self._system_prompt_base
        return self._system_prompt_with_tag

    def _init_client(self):
        """Initialize the API client."""
        if not self.endpoint:
            logger.warning("No LLM API endpoint configured")
            logger.info("Set llm_api_endpoint in config or use docker-compose")
            self._init_mock_mode()
            return

        try:
            if HAS_OPENAI:
                self._client = OpenAI(
                    base_url=self.endpoint,
                    api_key=self.api_key,
                    timeout=120.0,
                )
                # Test connection
                self._client.models.list()
                self._initialized = True
                logger.info(f"LLM client connected to {self.endpoint}")
            else:
                # Test with requests
                response = requests.get(f"{self.endpoint}/models", timeout=10)
                if response.ok:
                    self._initialized = True
                    logger.info(f"LLM client connected to {self.endpoint}")
                else:
                    raise Exception(f"API returned {response.status_code}")

        except Exception as e:
            logger.warning(f"Could not connect to LLM API: {e}")
            logger.info("Running in MOCK mode - responses will be simulated")
            self._init_mock_mode()

    def _init_mock_mode(self):
        """Initialize mock mode for testing without API."""
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
            messages = []
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt or self.default_system_prompt,
                }
            )
            messages.append({"role": "user", "content": prompt})

            # Use tool calling only for conversational responses (no custom prompt)
            # and only while the backend has shown it supports function calling.
            use_tool = system_prompt is None and self._tool_calling_supported

            if HAS_OPENAI:
                kwargs = dict(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                )
                if use_tool:
                    kwargs["tools"] = [self._respond_tool]
                    kwargs["tool_choice"] = {"type": "function", "name": "respond"}

                response = self._client.chat.completions.create(**kwargs)
                choice = response.choices[0]

                if use_tool:
                    tool_calls = choice.message.tool_calls or []
                    if tool_calls:
                        args = json.loads(tool_calls[0].function.arguments)
                        text = args.get("text", "")
                        emotion = args.get("emotion", "neutral")
                        logger.info(f"Tool call OK — emotion={emotion!r}")
                        return f"{text}\n[EMOZIONE: {emotion}]"
                    else:
                        # Model didn't return a tool call despite tool_choice="required".
                        # This means the backend doesn't support function calling.
                        logger.warning(
                            "Tool call expected but not returned "
                            f"(finish_reason={choice.finish_reason!r}). "
                            "Backend may not support function calling — "
                            "falling back to tag-in-text mode."
                        )
                        self._tool_calling_supported = False

                return choice.message.content
            else:
                # Fallback to requests
                body: dict = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                if use_tool:
                    body["tools"] = [self._respond_tool]
                    body["tool_choice"] = {"type": "function", "name": "respond"}

                resp = requests.post(
                    f"{self.endpoint}/chat/completions",
                    json=body,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]

                if use_tool:
                    tool_calls = choice.get("message", {}).get("tool_calls") or []
                    if tool_calls:
                        args = json.loads(tool_calls[0]["function"]["arguments"])
                        text = args.get("text", "")
                        emotion = args.get("emotion", "neutral")
                        logger.info(f"Tool call OK — emotion={emotion!r}")
                        return f"{text}\n[EMOZIONE: {emotion}]"
                    else:
                        logger.warning(
                            "Tool call expected but not returned. "
                            "Backend may not support function calling — "
                            "falling back to tag-in-text mode."
                        )
                        self._tool_calling_supported = False

                return choice["message"]["content"]

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return self._mock_generate(prompt, system_prompt)

    def _mock_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Mock generation for testing."""
        mock_responses = [
            "Capisco. Fammi pensare... come posso aiutarti?",
            "Interessante domanda. Ecco cosa ne penso...",
            "Ho capito. C'è qualcosa di specifico che vuoi che faccia?",
            "Ricevuto! Sono qui per aiutarti con i tuoi appunti.",
        ]
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
            if HAS_OPENAI:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content
            else:
                resp = requests.post(
                    f"{self.endpoint}/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "Sto avendo problemi a elaborare la richiesta."

    def summarize(self, text: str, max_length: int = 200) -> str:
        """
        Summarize a long text.

        Args:
            text: Text to summarize
            max_length: Maximum summary length in words

        Returns:
            Summary text
        """
        system_prompt = (
            f"Sei Fresh Buddy, un assistente AI gentile e utile. "
            f"Riassumi il seguente testo in modo conciso in non più di {max_length} parole. "
            f"Concentrati sui punti chiave e azioni da fare."
        )
        return self.generate(f"Summarize this:\n\n{text}", system_prompt)

    def extract_action_items(self, text: str) -> List[str]:
        """
        Extract action items from meeting notes.

        Args:
            text: Meeting transcript or notes

        Returns:
            List of action items
        """
        system_prompt = (
            "Sei Fresh Buddy. Estrai tutti i task e le azioni dal seguente testo. "
            "Ritorna una lista JSON di azioni, ognuna con: "
            "- task: descrizione del task "
            "- assignee: chi dovrebbe farlo (se menzionato) "
            "- deadline: quando dovrebbe essere completato (se menzionato) "
            "Ritorna SOLO la lista JSON, nient'altro."
        )

        response = self.generate(text, system_prompt)

        try:
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
        """Check if API client is connected and ready."""
        return self._initialized
