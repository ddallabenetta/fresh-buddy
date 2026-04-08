# Software Setup Guide

## Prerequisites

- NVIDIA Jetson Orin Nano with JetPack 5.x+ installed
- Python 3.8+ installed
- Git installed
- CUDA available on system

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/bmocompano.git
cd bmocompano
```

### 2. Run Installation Script

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

The script will:
- Create a Python virtual environment
- Install system dependencies
- Install Python dependencies
- Download required AI models

### 3. Manual Installation (Alternative)

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    libopenblas-dev \
    libsndfile1 \
    portaudio19-dev

# Install Python packages
pip install \
    numpy \
    pyaudio \
    smbus2 \
    llama-cpp-python \
    coqui-stt \
    coqui-stt-model-manager

# Install Piper TTS
pip install piper-tts
pip install piper-download  # For downloading voices
```

### 4. Download AI Models

#### Nemotron 3 4B (LLM)

Download the Nemotron model from HuggingFace:

```bash
# Using huggingface-cli
huggingface-cli download --local-dir models/nemotron-3-4b \
   NousResearch/Meta-Llama-3-8B-Instruct

# Or manually download from:
# https://huggingface.co/NousResearch/Meta-Llama-3-8B-Instruct
```

Note: For Jetson Orin Nano, use the quantized GGUF version for better performance.

#### Parakeet STT Model

```bash
coqui-stt-model-manager download驿
coqui-stt-model-manager use普通话 
```

Or download manually from Coqui model hub.

#### Piper TTS Voice

```bash
piper-download en_US-lessac-medium
```

### 5. Configuration

Create `config.json` in the project root:

```json
{
    "nemotron_model_path": "models/nemotron-3-4b/ggml-model.gguf",
    "parakeet_model_path": "models/parakeet/model",
    "piper_model_path": "voices/en_US-lessac-medium.onnx",
    "i2c_bus": 1,
    "debug_mode": false
}
```

Or copy from example:
```bash
cp config.json.example config.json
```

## Running BMO

### Normal Mode (with display and audio)
```bash
python -m bmo.main
```

### Headless Mode (no display/audio, testing)
```bash
python -m bmo.main --query "Hello BMO"
```

### Test Display
```bash
python -m bmo.main --test-face
```

### Test Audio
```bash
python -m bmo.main --test-audio
```

## Virtual Environment

Always activate the venv before running:
```bash
source venv/bin/activate
```

## Updating

Pull latest changes and reinstall:
```bash
git pull
pip install -r requirements.txt
```

## Docker Support (Optional)

For containerized deployment:

```bash
# Build image
docker build -t bmocompano .

# Run container
docker run --device /dev/i2c-1 --device /dev/snd \
    -v $(pwd)/config.json:/app/config.json \
    bmocompano
```

## Performance Optimization

### For Jetson Orin Nano 8GB:
- Use 4-bit quantization for Nemotron
- Set `n_gpu_layers=32` in llama-cpp config
- Enable Jetson power mode: `sudo nvpmodel -m 1`

### Memory Optimization:
- Reduce context window if running out of memory
- Use swap file: `sudo fallocate -l 8G /swapfile`
