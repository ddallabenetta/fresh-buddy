# Usage Guide

## Starting BMO

```bash
source venv/bin/activate
python -m bmo.main
```

BMO will:
1. Initialize all hardware components
2. Show startup animation on OLED
3. Greet you with voice: "Hello! I'm BMO. How can I help you today?"
4. Listen for voice commands

## Voice Commands

### Basic Interaction
- Say "Hey BMO" to get BMO's attention
- After the wake word, speak your question or command
- BMO will respond with voice and expression changes

### Meeting Commands

| Command | Description |
|---------|-------------|
| "Hey BMO, start meeting" | Begin recording meeting |
| "Hey BMO, end meeting" | Stop recording and generate summary |
| "Hey BMO, summarize meeting" | Get summary of last meeting |

### Examples

**Starting a meeting:**
```
You: "Hey BMO, start meeting"
BMO: "Meeting recording started."
(Recording indicator shows on display)
```

**Having a conversation:**
```
You: "Hey BMO, what is the capital of France?"
BMO: (thinking expression)
BMO: "The capital of France is Paris."
```

**Ending a meeting:**
```
You: "Hey BMO, end meeting"
BMO: "Meeting recording stopped. Generating summary..."
BMO: (reads summary aloud)
```

## Display Expressions

BMO shows different expressions:

| Expression | When |
|-----------|------|
| 😊 Happy | Positive responses |
| 😢 Sad | Apologetic or sad news |
| 🤔 Thinking | Processing complex queries |
| 😮 Excited | Very positive or surprising info |
| 😕 Confused | Unclear or misunderstood input |
| 😴 Sleeping | Idle/inactive state |
| 🔴 Recording | Meeting is being recorded |
| 👂 Listening | Active listening mode |

## Meetings

### Meeting Flow

1. **Start**: "Hey BMO, start meeting"
2. **During**: All spoken content is transcribed
3. **End**: "Hey BMO, end meeting"
4. **Summary**: BMO generates and reads summary

### Saved Meeting Data

Meetings are saved to `meetings/` directory:

```
meetings/
├── 20260408_143000_minutes.json  # Structured summary
└── 20260408_143000_transcript.txt # Full transcript
```

### Meeting Minutes Format

```json
{
    "meeting_id": "20260408_143000",
    "date": "2026-04-08T14:30:00",
    "duration_seconds": 1800,
    "summary": "Team discussed Q2 roadmap...",
    "action_items": [
        {"task": "Review PR #123", "assignee": "Alice", "deadline": "Friday"}
    ],
    "decisions": ["Approved budget increase"],
    "participants": ["Alice", "Bob", "Charlie"]
}
```

## Configuration

Edit `config.json` to customize:

### Voice Settings
```json
{
    "piper_voice": "en_US-lessac-medium",
    "piper_speaker": null,
    "piper_length_scale": 1.0
}
```

### LLM Settings
```json
{
    "nemotron_temperature": 0.7,
    "nemotron_max_tokens": 512
}
```

### Wake Word
```json
{
    "wake_word": "hey bmo",
    "wake_word_sensitivity": 0.5
}
```

## Troubleshooting

### BMO doesn't respond to wake word
- Check microphone is working: `python -m bmo.main --test-audio`
- Lower wake word sensitivity in config
- Speak closer to microphone

### Responses are slow
- Nemotron model may need quantization
- Check Jetson thermal throttling
- Reduce `nemotron_max_tokens`

### Audio quality is poor
- Use higher quality microphone
- Adjust audio input gain in system settings
- Try USB microphone instead of I2S

## API Usage

BMO can be used programmatically:

```python
from bmo.main import BMOCompanion
from bmo.config import Config

# Load config
config = Config.load()

# Create BMO instance
bmo = BMOCompanion(config)

# Query without voice
response = bmo.run_headless("What time is it?")
print(response)

# Get meeting summary
summary = bmo.meeting.get_summary()
print(summary)
```
