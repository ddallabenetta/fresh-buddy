# Fresh Buddy 🤖

**Private, Fully-Local AI Companion on Jetson Orin Nano**

A private, fully-local AI assistant with an animated OLED face, running on NVIDIA Jetson Orin Nano with Nemotron 3 4B, Parakeet STT, and Piper TTS.

## 🎯 Features

- **Local AI**: Nemotron 3 4B running fully on-device
- **Voice Interaction**: Parakeet STT + Piper TTS pipeline
- **Expressive Face**: OLED display showing dynamic expressions
- **Meeting Assistant**: Records, transcribes, and summarizes meetings
- **Privacy First**: Everything runs locally, no cloud dependencies

## 🖥️ Hardware Requirements

- NVIDIA Jetson Orin Nano (8GB recommended)
- SSD Storage (256GB+ recommended for models)
- OLED display (I2C/SPI compatible, e.g. Waveshare 1.3")
- I2S microphone array or USB mic
- Speakers or headphone output

## 📦 Quick Start

```bash
# Clone the repository
git clone https://github.com/ddallabenetta/fresh-buddy.git
cd bmocompano

# Run installation
chmod +x scripts/install.sh
./scripts/install.sh

# Start Fresh Buddy
python -m bmo.main
```

## 🏗️ Architecture

```
bmocompano/
├── src/bmo/
│   ├── main.py           # Entry point
│   ├── face/            # OLED display and expression rendering
│   ├── audio/           # Parakeet STT and Piper TTS
│   └── ai/              # Nemotron integration and meeting utils
├── docs/                # Documentation
├── tests/               # Unit and integration tests
└── scripts/             # Installation and setup scripts
```

## 🎨 Expression System

Fresh Buddy's face changes based on:
- **Speech**: Mouth animation synced with TTS output
- **Emotion**: Happy, sad, confused, excited, sleeping, listening
- **Activity**: Recording indicator, processing spinner, thinking dots

## 📝 Meeting Mode

1. Say "Hey Buddy, start meeting" to begin recording
2. Fresh Buddy displays red recording indicator
3. All speech is transcribed in real-time
4. Say "Hey Buddy, end meeting" to stop
5. Fresh Buddy generates a structured summary automatically

## 📄 Documentation

- [Hardware Setup](docs/hardware.md)
- [Software Installation](docs/setup.md)
- [Usage Guide](docs/usage.md)
- [Architecture](docs/architecture.md)

## ⚙️ Supported Models

| Component | Model | Notes |
|-----------|-------|-------|
| LLM | Nemotron 3 4B | Quantized for Jetson |
| STT | Parakeet | Distilled variant |
| TTS | Piper | Medium quality voice |

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run specific test suite
pytest tests/test_face.py
pytest tests/test_audio.py
pytest tests/test_ai.py
```

## 📄 License

MIT License - See LICENSE file

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md first.
