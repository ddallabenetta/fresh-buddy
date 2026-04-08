"""Meeting Assistant - Record, Transcribe, and Summarize Meetings"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class MeetingAssistant:
    """Handles meeting recording, transcription, and summarization."""

    def __init__(self, llm, stt, tts):
        """
        Initialize Meeting Assistant.

        Args:
            llm: NemotronLLM instance
            stt: ParakeetSTT instance
            tts: PiperTTS instance
        """
        self.llm = llm
        self.stt = stt
        self.tts = tts

        self.is_recording = False
        self.transcript: List[Dict[str, str]] = []
        self.meeting_start_time: Optional[datetime] = None
        self.meeting_id: Optional[str] = None

        # Storage
        self.storage_dir = Path("meetings")
        self.storage_dir.mkdir(exist_ok=True)

    def start_recording(self):
        """Start a new meeting recording session."""
        if self.is_recording:
            logger.warning("Already recording a meeting")
            return

        self.is_recording = True
        self.transcript = []
        self.meeting_start_time = datetime.now()
        self.meeting_id = self.meeting_start_time.strftime("%Y%m%d_%H%M%S")

        logger.info(f"Meeting recording started: {self.meeting_id}")

        # Notify via TTS
        if self.tts:
            self.tts.speak("Meeting recording started.")

    def stop_recording(self):
        """Stop the current meeting recording."""
        if not self.is_recording:
            logger.warning("No meeting recording in progress")
            return

        self.is_recording = False
        duration = datetime.now() - self.meeting_start_time

        logger.info(f"Meeting recording stopped. Duration: {duration}")

        # Notify via TTS
        if self.tts:
            self.tts.speak("Meeting recording stopped. Generating summary...")

        # Generate and save summary
        summary = self.get_summary()

        # Save to file
        self._save_meeting()

        return summary

    def process_speech(self, text: str, speaker: str = "Participant"):
        """
        Process speech during a meeting.

        Args:
            text: Transcribed text
            speaker: Who spoke (default: Participant)
        """
        if not self.is_recording:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "speaker": speaker,
            "text": text
        }

        self.transcript.append(entry)
        logger.info(f"[{speaker}] {text}")

    def get_transcript(self) -> str:
        """
        Get full transcript as text.

        Returns:
            Formatted transcript
        """
        if not self.transcript:
            return "No transcript available."

        lines = []
        for entry in self.transcript:
            timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M")
            lines.append(f"[{timestamp}] {entry['speaker']}: {entry['text']}")

        return "\n".join(lines)

    def get_summary(self) -> str:
        """
        Generate a summary of the meeting.

        Returns:
            Meeting summary
        """
        if not self.transcript:
            return "No meeting content to summarize."

        # Combine all transcript text
        full_text = " ".join(entry["text"] for entry in self.transcript)

        # Generate summary using LLM
        summary = self.llm.summarize(full_text, max_length=300)

        return summary

    def get_minutes(self) -> Dict:
        """
        Generate structured meeting minutes.

        Returns:
            Dictionary with summary, action items, and decisions
        """
        if not self.transcript:
            return {
                "meeting_id": self.meeting_id,
                "summary": "No content recorded.",
                "action_items": [],
                "decisions": [],
                "participants": []
            }

        # Get full transcript
        full_text = " ".join(entry["text"] for entry in self.transcript)

        # Extract participants
        participants = list(set(entry["speaker"] for entry in self.transcript))

        # Get summary
        summary = self.llm.summarize(full_text, max_length=300)

        # Extract action items
        action_items = self.llm.extract_action_items(full_text)

        # Identify decisions (simplified - just find sentences with "decided", "agreed", etc.)
        decisions = []
        decision_keywords = ["decided", "agreed", "confirmed", "will", "must", "shall"]
        for entry in self.transcript:
            text_lower = entry["text"].lower()
            if any(kw in text_lower for kw in decision_keywords):
                decisions.append(entry["text"])

        return {
            "meeting_id": self.meeting_id,
            "date": self.meeting_start_time.isoformat() if self.meeting_start_time else None,
            "duration_seconds": (
                datetime.now() - self.meeting_start_time
            ).seconds if self.meeting_start_time else 0,
            "summary": summary,
            "action_items": action_items,
            "decisions": decisions[:5],  # Limit to 5 decisions
            "participants": participants,
            "transcript_count": len(self.transcript)
        }

    def _save_meeting(self):
        """Save meeting data to storage."""
        if not self.meeting_id:
            return

        # Get minutes
        minutes = self.get_minutes()

        # Save JSON
        json_path = self.storage_dir / f"{self.meeting_id}_minutes.json"
        with open(json_path, 'w') as f:
            json.dump(minutes, f, indent=2)

        # Save transcript
        transcript_path = self.storage_dir / f"{self.meeting_id}_transcript.txt"
        with open(transcript_path, 'w') as f:
            f.write(f"Meeting ID: {self.meeting_id}\n")
            f.write(f"Date: {minutes.get('date', 'Unknown')}\n")
            f.write(f"Duration: {minutes.get('duration_seconds', 0)} seconds\n")
            f.write(f"Participants: {', '.join(minutes.get('participants', []))}\n")
            f.write("\n" + "=" * 50 + "\n\n")
            f.write(self.get_transcript())

        logger.info(f"Meeting saved to {json_path}")

    def load_meeting(self, meeting_id: str) -> bool:
        """
        Load a previous meeting.

        Args:
            meeting_id: Meeting ID to load

        Returns:
            True if loaded successfully
        """
        json_path = self.storage_dir / f"{meeting_id}_minutes.json"

        if not json_path.exists():
            logger.error(f"Meeting {meeting_id} not found")
            return False

        try:
            with open(json_path, 'r') as f:
                minutes = json.load(f)

            self.meeting_id = meeting_id
            self.transcript = []  # Transcript loaded separately if needed

            logger.info(f"Loaded meeting {meeting_id}")
            return True

        except Exception as e:
            logger.error(f"Error loading meeting: {e}")
            return False

    def list_meetings(self) -> List[Dict]:
        """
        List all saved meetings.

        Returns:
            List of meeting metadata
        """
        meetings = []

        for json_file in self.storage_dir.glob("*_minutes.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    meetings.append({
                        "meeting_id": data.get("meeting_id"),
                        "date": data.get("date"),
                        "duration": data.get("duration_seconds", 0),
                        "participant_count": len(data.get("participants", [])),
                        "summary_preview": data.get("summary", "")[:100]
                    })
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")

        return sorted(meetings, key=lambda x: x["date"] or "", reverse=True)
