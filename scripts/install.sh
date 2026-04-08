#!/bin/bash
# BMOCompanion Installation Script
# For Jetson Orin Nano

set -e

echo "🤖 BMOCompanion Installation"
echo "=============================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for errors
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: $1${NC}"
        exit 1
    fi
}

# Check if running on Jetson
is_jetson() {
    if [ -f /etc/nv_tegra_release ]; then
        return 0
    else
        return 1
    fi
}

echo -e "${YELLOW}Step 1: System dependencies${NC}"
sudo apt-get update
check_error "Failed to update apt"
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    libopenblas-dev \
    libsndfile1 \
    portaudio19-dev \
    libasound2-dev \
    i2c-tools \
    git
check_error "Failed to install system packages"

echo -e "${YELLOW}Step 2: Python virtual environment${NC}"
if [ -d "venv" ]; then
    echo "Virtual environment exists, removing..."
    rm -rf venv
fi
python3 -m venv venv
source venv/bin/activate
check_error "Failed to create virtual environment"

pip install --upgrade pip
check_error "Failed to upgrade pip"

echo -e "${YELLOW}Step 3: Python packages${NC}"
pip install \
    numpy \
    pyaudio \
    smbus2 \
    RPi.GPIO || echo "RPi.GPIO not needed on Jetson"
check_error "Failed to install basic Python packages"

# llama-cpp-python (GPU support for Jetson)
echo -e "${YELLOW}Installing llama-cpp-python with GPU support...${NC}"
CMAKE_ARGS="-DLLAMA_CUBLAS=ON" pip install \
    llama-cpp-python \
    --force-reinstall \
    --no-cache-dir
check_error "Failed to install llama-cpp-python"

# Coqui STT
echo -e "${YELLOW}Installing Coqui STT...${NC}"
pip install \
    coqui-stt \
    coqui-stt-model-manager \
    --no-cache-dir || echo "Coqui STT installation may have warnings"
check_error "Failed to install Coqui STT"

# Piper TTS
echo -e "${YELLOW}Installing Piper TTS...${NC}"
pip install \
    piper-tts \
    piper-download \
    --no-cache-dir
check_error "Failed to install Piper TTS"

# Development dependencies
echo -e "${YELLOW}Installing development dependencies${NC}"
pip install \
    pytest \
    pytest-cov \
    black \
    flake8 \
    mypy
check_error "Failed to install dev dependencies"

echo -e "${YELLOW}Step 4: Download AI models${NC}"

# Create models directory
mkdir -p models voices
check_error "Failed to create models directory"

# Download Piper voice
echo -e "${YELLOW}Downloading Piper English voice...${NC}"
if command -v piper-download &> /dev/null; then
    piper-download en_US-lessac-medium voices/
else
    echo "Warning: piper-download not found. Install voice manually:"
    echo "  piper-download en_US-lessac-medium voices/"
fi

# Note about Nemotron
echo -e "${YELLOW}Note about Nemotron model:${NC}"
echo "Due to model size, please download manually:"
echo "  1. Visit: https://huggingface.co/NousResearch/Meta-Llama-3-8B-Instruct"
echo "  2. Download the GGUF quantized version"
echo "  3. Place in models/ directory"
echo "  4. Update config.json with path"

# Create default config
echo -e "${YELLOW}Step 5: Configuration${NC}"
if [ ! -f "config.json" ]; then
    cat > config.json << 'EOF'
{
    "i2c_bus": 1,
    "display_address": 60,
    "audio_device": 0,
    "nemotron_model_path": "models/ggml-model.gguf",
    "parakeet_model_path": null,
    "piper_model_path": "voices/en_US-lessac-medium.onnx",
    "piper_voice": "en_US-lessac-medium",
    "piper_noise_scale": 0.667,
    "piper_length_scale": 1.0,
    "nemotron_temperature": 0.7,
    "nemotron_max_tokens": 512,
    "meeting_storage_dir": "meetings",
    "wake_word": "hey bmo",
    "debug_mode": false,
    "log_level": "INFO"
}
EOF
    echo "Created config.json with defaults"
fi

# Create meetings directory
mkdir -p meetings

echo ""
echo -e "${GREEN}=============================="
echo "✅ Installation complete!"
echo "==============================${NC}"
echo ""
echo "Next steps:"
echo "  1. Download Nemotron model to models/"
echo "  2. Activate venv: source venv/bin/activate"
echo "  3. Test display: python -m bmo.main --test-face"
echo "  4. Test audio: python -m bmo.main --test-audio"
echo "  5. Run BMO: python -m bmo.main"
echo ""
echo "For full documentation, see docs/"
