# Guida Installazione Software — Fresh Buddy

## Prerequisiti

- NVIDIA Jetson Orin Nano con JetPack 5.x+ installato
- Python 3.8+ installato
- Git installato
- CUDA disponibile sul sistema

## Passaggi di Installazione

### 1. Clona la Repository

```bash
git clone https://github.com/ddallabenetta/fresh-buddy.git
cd bmocompano
```

### 2. Esegui lo Script di Installazione

```bash
chmod +x scripts/install.sh
./scripts/installazione.sh
```

Lo script:
- Crea un ambiente virtuale Python
- Installa le dipendenze di sistema
- Installa le dipendenze Python
- Scarica i modelli AI necessari

### 3. Installazione Manuale (Alternativa)

```bash
# Crea ambiente virtuale
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze di sistema
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    libopenblas-dev \
    libsndfile1 \
    portaudio19-dev

# Installa pacchetti Python
pip install \
    numpy \
    pyaudio \
    smbus2 \
    llama-cpp-python \
    coqui-stt \
    coqui-stt-model-manager

# Installa Piper TTS
pip install piper-tts
pip install piper-download
```

### 4. Scarica i Modelli AI

#### Nemotron 3 4B (LLM)

```bash
huggingface-cli download --local-dir models \
   NousResearch/Meta-Llama-3-8B-Instruct
```

Per Jetson Orin Nano, usa la versione quantizzata GGUF per performance migliori.

#### Parakeet STT Model

```bash
coqui-stt-model-manager download parakeet
```

#### Piper TTS Voice (Italiano)

```bash
piper-download it_IT-riccardo-x_low
```

### 5. Configurazione

Crea `config.json` nella root del progetto:

```json
{
    "llm_model_path": "models/ggml-model.gguf",
    "parakeet_model_path": "models/parakeet/model",
    "piper_model_path": "voices/it_IT-riccardo-x_low.onnx",
    "i2c_bus": 1,
    "debug_mode": false
}
```

Oppure copia da example:
```bash
cp config.json.example config.json
```

## Avviare Fresh Buddy

### Modalità Normale (con display e audio)
```bash
python -m bmo.main
```

### Modalità Headless (senza display/audio, testing)
```bash
python -m bmo.main --query "Che ore sono?"
```

### Test Display
```bash
python -m bmo.main --test-face
```

### Test Audio
```bash
python -m bmo.main --test-audio
```

## Ambiente Virtuale

Attiva sempre il venv prima di eseguire:
```bash
source venv/bin/activate
```

## Aggiornamento

Scarica le ultime modifiche e reinstalla:
```bash
git pull
pip install -r requirements.txt
```

## Docker (Opzionale)

```bash
# Build immagine
docker build -t fresh-buddy .

# Run container
docker run --device /dev/i2c-1 --device /dev/snd \
    -v $(pwd)/config.json:/app/config.json \
    fresh-buddy
```

## Ottimizzazione Performance

### Per Jetson Orin Nano 8GB:
- Usa quantizzazione a 4-bit per Nemotron
- Imposta `n_gpu_layers=32` nella config llama-cpp
- Abilita modalità risparmio energetico: `sudo nvpmodel -m 1`

### Ottimizzazione Memoria:
- Riduci la finestra di contesto se finisci la memoria
- Usa swap file: `sudo fallocate -l 8G /swapfile`
