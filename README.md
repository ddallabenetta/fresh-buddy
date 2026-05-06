# Fresh Buddy 🤖

**Private AI Companion — Docker-Deployable on Jetson Orin Nano**

Fresh Buddy è un assistente AI vocale privato con viso OLED animato. L'architettura è containerizzata: il servizio LLM (llama.cpp) è separato dall'applicazione principale, permettendo deploy flessibili su GPU dedicata o in cloud.

## 🎯 Features

- **Decoupled LLM**: OpenAI-compatible API, deployabile separatamente
- **Voice Interaction**: Parakeet STT + Piper TTS (locali)
- **Expressive Face**: OLED display with dynamic expressions
- **Meeting Assistant**: Records, transcribes, and summarizes meetings
- **Privacy First**: Everything runs locally, no cloud dependencies
- **Docker-Ready**: Full stack deployable with docker-compose

## 🖥️ Hardware Requirements

- NVIDIA Jetson Orin Nano (8GB recommended)
- SSD Storage (256GB+ recommended for models)
- OLED display (I2C/SPI compatible, e.g. Waveshare 1.3")
- I2S microphone array or USB mic
- Speakers or headphone output

## 🚀 Docker Deployment (Consigliato)

```bash
git clone https://github.com/ddallabenetta/fresh-buddy.git
cd fresh-buddy

# Configura
cp .env.example .env
mkdir -p models
# Copia il tuo modello GGUF in models/model.gguf

# Build e avvio
docker compose build
docker compose up -d
```

## 📦 Development Setup

```bash
# Clone the repository
git clone https://github.com/ddallabenetta/fresh-buddy.git
cd fresh-buddy

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure (point to your LLM server)
cp .env.example .env
# Edit .env with your LLM endpoint

# Run
python -m bmo.main
```

## 🏗️ Architecture

```
fresh-buddy/
├── src/bmo/              # Fresh Buddy application
│   ├── main.py           # Entry point
│   ├── face/             # OLED display and expression rendering
│   ├── audio/            # Parakeet STT and Piper TTS
│   └── ai/               # LLM client (OpenAI-compatible API)
├── server/               # LLM Server (llama.cpp)
│   ├── Dockerfile        # GPU-enabled LLM server image
│   └── models/           # GGUF model files
├── docs/                 # Documentation
├── tests/                # Unit and integration tests
├── docker-compose.yml    # Full stack orchestration
├── Dockerfile.client     # Fresh Buddy container
└── .env.example          # Environment configuration
```

## 🎨 Expression System

Fresh Buddy's face changes based on:
- **Speech**: Mouth animation synced with TTS output
- **Emotion**: Happy, sad, confused, excited, sleeping, listening
- **Activity**: Recording indicator, processing spinner, thinking dots
- **80s Robot Animation**: CRT scanlines, glow bloom, pupil radar reticles, eyelid sweeps, cheek LEDs, voice equalizer bars, recording scan beams

### Development Preview

Run the app in simulation mode to open the 800×480 dev console:

```bash
PYTHONPATH=src PREVIEW_PORT=8088 python3 -c "from bmo.face.display import OLEDDisplay; from bmo.face.expressions import ExpressionEngine; from bmo.face.preview_server import configure; import time; d=OLEDDisplay(); e=ExpressionEngine(d); configure(expressions=e); e.show_expression('neutral'); time.sleep(3600)"
```

Then open `http://localhost:8088/`. The console includes expression buttons, theme selector, transition speed, animation speed, scanline toggle, glow toggle, and glitch trigger.

## 📝 Meeting Mode

1. Say "Hey Buddy, start meeting" to begin recording
2. Fresh Buddy displays red recording indicator
3. All speech is transcribed in real-time
4. Say "Hey Buddy, end meeting" to stop
5. Fresh Buddy generates a structured summary automatically

## 📄 Documentation

- [Deployment Guide](docs/deployment.md) — Docker stack setup
- [Hardware Setup](docs/hardware.md)
- [Software Installation](docs/setup.md)
- [Usage Guide](docs/usage.md)
- [Architecture](docs/architecture.md)

## ⚙️ Supported Models

| Component | Model | Notes |
|-----------|-------|-------|
| LLM | Any OpenAI-compatible model (e.g. Llama, Nemotron, Qwen) | Quantized for Jetson |
| STT | Parakeet | Distilled variant |
| TTS | Piper | Medium quality voice |

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your settings
# Example: SYSTEM_PROMPT=Sei un assistente minimalista.
# Example: FIRST_MESSAGE=Ciao! Sono Fresh Buddy. Come posso aiutarti?
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
