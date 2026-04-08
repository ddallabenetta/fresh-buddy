"""BMO Companion - Main Entry Point"""

import argparse
import logging
import signal
import sys
from pathlib import Path

from bmo.config import Config
from bmo.face.display import OLEDDisplay
from bmo.face.expressions import ExpressionEngine
from bmo.audio.stt import ParakeetSTT
from bmo.audio.tts import PiperTTS
from bmo.ai.nemotron import NemotronLLM
from bmo.ai.meeting import MeetingAssistant

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BMOCompanion:
    """Main BMO Companion application."""

    def __init__(self, config: Config = None):
        self.config = config or Config.load()
        self.running = False

        # Initialize components
        logger.info("Initializing BMO Companion...")
        self.display = OLEDDisplay(self.config)
        self.expressions = ExpressionEngine(self.display)
        self.stt = ParakeetSTT(self.config)
        self.tts = PiperTTS(self.config)
        self.llm = NemotronLLM(self.config)
        self.meeting = MeetingAssistant(self.llm, self.stt, self.tts)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received...")
        self.running = False
        self.shutdown()

    def startup(self):
        """Show startup animation."""
        logger.info("BMO starting up...")
        self.expressions.show_expression("happy")
        self.tts.speak("Hello! I'm BMO. How can I help you today?")

    def shutdown(self):
        """Clean shutdown sequence."""
        logger.info("Shutting down BMO...")
        self.expressions.show_expression("sleeping")
        if hasattr(self.stt, 'stop'):
            self.stt.stop()
        if hasattr(self.tts, 'cleanup'):
            self.tts.cleanup()
        logger.info("BMO shutdown complete.")

    def run(self):
        """Main interaction loop."""
        self.startup()
        self.running = True

        logger.info("BMO is ready! Listening for commands...")

        while self.running:
            try:
                # Listen for wake word or direct command
                audio_data = self.stt.listen(timeout=30)

                if audio_data:
                    text = self.stt.transcribe(audio_data)
                    logger.info(f" Heard: {text}")

                    if self._is_wake_word(text):
                        self._handle_wake(text)
                    elif self.meeting.is_recording:
                        self.meeting.process_speech(text)
                    else:
                        self._handle_command(text)

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                self.expressions.show_expression("confused")

    def _is_wake_word(self, text: str) -> bool:
        """Check if text contains wake word."""
        wake_words = ["hey bmo", "bm0", "b m o"]
        text_lower = text.lower().strip()
        return any(w in text_lower for w in wake_words)

    def _handle_wake(self, text: str):
        """Handle wake word detection."""
        self.expressions.show_expression("happy")
        self.tts.speak("Yes?")

        # Listen for command after wake
        audio_data = self.stt.listen(timeout=10)
        if audio_data:
            command = self.stt.transcribe(audio_data)
            self._handle_command(command)

    def _handle_command(self, text: str):
        """Route and execute commands."""
        text_lower = text.lower()

        # Meeting commands
        if "start meeting" in text_lower or "inizia riunione" in text_lower:
            self.meeting.start_recording()
            return

        if "end meeting" in text_lower or "fine riunione" in text_lower:
            self.meeting.stop_recording()
            return

        if "summarize meeting" in text_lower or "riassumi" in text_lower:
            summary = self.meeting.get_summary()
            self.tts.speak(summary)
            return

        # General AI query
        self.expressions.show_expression("thinking")
        response = self.llm.generate(text)

        # Determine emotion from response
        emotion = self._detect_emotion(response)
        self.expressions.show_expression(emotion)

        self.tts.speak(response)

    def _detect_emotion(self, text: str) -> str:
        """Detect emotion from text response."""
        positive = ["happy", "great", "wonderful", "excellent", "good"]
        negative = ["sad", "sorry", "unfortunately", "regret"]
        excited = ["amazing", "wow", "incredible", "fantastic"]

        text_lower = text.lower()

        if any(w in text_lower for w in excited):
            return "excited"
        if any(w in text_lower for w in positive):
            return "happy"
        if any(w in text_lower for w in negative):
            return "sad"
        return "neutral"

    def run_headless(self, query: str) -> str:
        """Run a single query without voice (for testing)."""
        return self.llm.generate(query)


def main():
    parser = argparse.ArgumentParser(description="BMO Companion - Local AI Assistant")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--query", type=str, help="Run single query (headless mode)")
    parser.add_argument("--test-face", action="store_true", help="Test face display")
    parser.add_argument("--test-audio", action="store_true", help="Test audio pipeline")
    args = parser.parse_args()

    if args.query:
        # Headless single query mode
        config = Config.load(args.config) if args.config else Config.load()
        bmo = BMOCompanion(config)
        response = bmo.run_headless(args.query)
        print(response)
    elif args.test_face:
        # Test display only
        config = Config.load(args.config) if args.config else Config.load()
        display = OLEDDisplay(config)
        expressions = ExpressionEngine(display)
        expressions.test_all()
    elif args.test_audio:
        # Test audio only
        config = Config.load(args.config) if args.config else Config.load()
        stt = ParakeetSTT(config)
        tts = PiperTTS(config)
        print("Testing TTS...")
        tts.speak("Hello, I am BMO!")
        print("Testing STT... Speak now:")
        audio = stt.listen(timeout=5)
        if audio:
            text = stt.transcribe(audio)
            print(f"You said: {text}")
    else:
        # Normal interactive mode
        config = Config.load(args.config) if args.config else Config.load()
        bmo = BMOCompanion(config)
        bmo.run()


if __name__ == "__main__":
    main()
