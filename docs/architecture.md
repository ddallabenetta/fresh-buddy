# Architecture Documentation

## System Overview

BMOCompanion is a local AI assistant that combines:
- **Voice I/O**: Speech-to-text and text-to-speech
- **LLM**: Local language model for reasoning
- **Display**: Animated face for visual feedback
- **Meeting Assistant**: Automated transcription and summarization

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      User                               │
└─────────────────────┬───────────────────────────────────┘
                      │ Voice / Display
┌─────────────────────▼───────────────────────────────────┐
│                      BMOCompanion                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Face/Display │  │  Audio(STT) │  │  Audio(TTS)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         └─────────────────┼─────────────────┘           │
│                           │                             │
│  ┌────────────────────────▼────────────────────────┐    │
│  │               ExpressionEngine                  │    │
│  └────────────────────────┬────────────────────────┘    │
│                           │                             │
│  ┌────────────────────────▼────────────────────────┐    │
│  │                    LLM (Nemotron)               │    │
│  └────────────────────────┬────────────────────────┘    │
│                           │                             │
│  ┌────────────────────────▼────────────────────────┐    │
│  │              MeetingAssistant                    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Module Descriptions

### bmo.main (Main Entry Point)

The `BMOCompanion` class orchestrates all components:
- Initializes all subsystems on startup
- Handles wake word detection
- Routes voice commands to appropriate handlers
- Manages main interaction loop

### bmo.face

#### OLEDDisplay
- Low-level driver for SSD1306 128x64 OLED
- I2C communication via smbus2
- Framebuffer management
- Drawing primitives (pixels, rectangles, text)

#### ExpressionEngine
- Manages BMO facial expressions
- Expression types: happy, sad, confused, excited, etc.
- Idle animations (sleeping Z's, thinking dots)
- Mouth animation for speaking

### bmo.audio

#### ParakeetSTT
- Speech-to-text using Coqui/STT (Parakeet model)
- Audio capture via PyAudio
- Real-time streaming transcription support
- Configurable sample rate (default 16kHz)

#### PiperTTS
- Text-to-speech using Piper
- Multiple voice support
- Speaker ID for multi-voice models
- Audio playback via PyAudio

### bmo.ai

#### NemotronLLM
- Interface to local Nemotron 3 4B model
- Uses llama-cpp-python for inference
- Chat completion API
- Summarization and action item extraction
- Mock mode for testing without GPU

#### MeetingAssistant
- Meeting lifecycle management
- Real-time transcription collection
- Summary generation via LLM
- Action item extraction
- Meeting storage (JSON + TXT)

### bmo.config

- Configuration management via dataclass
- JSON file loading/saving
- Environment variable override
- Default values for all settings

## Data Flow

### Voice Command Flow
```
Microphone → PyAudio → ParakeetSTT.listen() → ParakeetSTT.transcribe()
     ↓
BMOCompanion._handle_command()
     ↓
NemotronLLM.generate()
     ↓
PiperTTS.speak()
     ↓
Speaker
```

### Meeting Flow
```
Microphone → STT → MeetingAssistant.process_speech()
     ↓
(transcript stored)
     ↓
MeetingAssistant.stop_recording()
     ↓
MeetingAssistant.get_summary() → LLM.summarize()
     ↓
TTS.speak(summary)
```

## Expression State Machine

```
                    ┌─────────┐
                    │ NEUTRAL │
                    └────┬────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
     ┌─────────┐   ┌───────────┐   ┌─────────┐
     │  HAPPY  │   │ CONFUSED  │   │   SAD   │
     └────┬────┘   └───────────┘   └─────────┘
          │              │              │
          ▼              ▼              ▼
     ┌─────────┐   ┌───────────┐   ┌─────────┐
     │EXCITED  │   │  IDLE     │   │  IDLE   │
     └─────────┘   └───────────┘   └─────────┘

     ┌─────────────────────────────────────┐
     │          SPEAKING                    │
     │ (mouth animates during TTS output)    │
     └─────────────────────────────────────┘

     ┌─────────────────────────────────────┐
     │          RECORDING                   │
     │  (red dot + listening expression)   │
     └─────────────────────────────────────┘
```

## File Structure

```
bmocompano/
├── src/bmo/
│   ├── __init__.py
│   ├── main.py           # BMOCompanion class
│   ├── config.py         # Configuration
│   ├── face/
│   │   ├── display.py    # OLED driver
│   │   └── expressions.py # Expression engine
│   ├── audio/
│   │   ├── stt.py        # Parakeet STT
│   │   └── tts.py        # Piper TTS
│   └── ai/
│       ├── nemotron.py   # LLM interface
│       └── meeting.py    # Meeting assistant
├── tests/
│   ├── test_face.py
│   ├── test_audio.py
│   └── test_ai.py
├── docs/
│   ├── hardware.md
│   ├── setup.md
│   ├── usage.md
│   └── architecture.md
├── scripts/
│   └── install.sh
├── assets/
│   ├── stl/              # 3D printable files
│   └── fonts/            # Display fonts
├── config.json.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Performance Considerations

### Memory Management
- Streaming transcription to avoid memory buildup
- Context window limit on LLM
- Framebuffer is 1KB (fixed)

### GPU Utilization
- llama-cpp-python manages GPU layers
- Jetson Orin: use `n_gpu_layers=32`
- Monitor with `tegrastats`

### Latency
- STT latency: ~500ms for short phrases
- TTS latency: ~200ms for short phrases
- LLM latency: Depends on model size and quantization
