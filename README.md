# BMOCompano 🤖

**Local AI Companion on Jetson Orin Nano with Virtual BMO Face**

A private, fully-local AI assistant featuring a animated face inspired by Adventure Time's BMO, running on NVIDIA Jetson Orin Nano with Nemotron 3 4B, Parakeet STT, and Piper TTS.

## 🎯 Features

- **Local AI**: Nemotron 3 4B running fully on-device
- **Voice Interaction**: Parakeet STT + Piper TTS pipeline
- **Expressive Face**: OLED display showing BMO-like character with dynamic expressions
- **Meeting Assistant**: Records, transcribes, and summarizes meetings
- **Privacy First**: Everything runs locally, no cloud dependencies

## 🖥️ Hardware Requirements

- NVIDIA Jetson Orin Nano (8GB recommended)
- SSD Storage (256GB+ recommended for models)
- Small CRT monitor with integrated OLED display
- I2S microphone array
- Speakers or headphone output

## 📦 Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/bmocompano.git
cd bmocompano

# Run installation
chmod +x scripts/install.sh
./scripts/install.sh

# Start BMO
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

BMO's face changes based on:
- **Speech**: Mouth animation synced with TTS output
- **Emotion**: Happy, sad, confused, excited, sleeping, listening
- **Activity**: Recording indicator, processing spinner, thinking dots

## 📝 Meeting Mode

1. Say "BMO, start meeting" to begin recording
2. BMO displays red recording indicator
3. All speech is transcribed in real-time
4. Say "BMO, end meeting" to stop
5. BMO generates a structured summary automatically

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
