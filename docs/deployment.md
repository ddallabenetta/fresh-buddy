# Deployment — Fresh Buddy

Fresh Buddy è deployabile come stack Docker completo, con LLM separato dal servizio principale.

## Architettura

```
┌─────────────────────────────────────────────────┐
│              Docker Compose Stack                │
│                                                  │
│  ┌──────────────────┐    ┌───────────────────┐  │
│  │   fresh-buddy    │───▶│   llm-server      │  │
│  │   (client app)   │    │   (llama.cpp)     │  │
│  │   :5000          │    │   :8080 (API)     │  │
│  └──────────────────┘    └───────────────────┘  │
│           │                         │            │
│     ┌─────┴─────┐            ┌──────┴──────┐     │
│     │ Audio/I2C│            │ GPU / CPU   │     │
│     │ periferiche│          │ Model (GGUF)│     │
│     └───────────┘            └─────────────┘     │
└─────────────────────────────────────────────────┘
```

## Prerequisiti

- Docker e Docker Compose
- (Opzionale) GPU NVIDIA con CUDA per il server LLM

## Quick Start

### 1. Clona e configura

```bash
git clone https://github.com/ddallabenetta/fresh-buddy.git
cd fresh-buddy

# Copia env di esempio
cp .env.example .env

# Crea directory per i modelli
mkdir -p models
```

### 2. Download del modello LLM

Scarica il modello GGUF compatibile (es. Nemotron 3 4B quantizzato):

```bash
# Esempio con huggingface-cli
huggingface-cli download \
  --local-dir ./models \
  NousResearch/Meta-Llama-3-8B-Instruct \
  --local-dir-use-symlinks False

# Se usi un modello diverso, rinominalo in model.gguf
mv your-model.gguf models/model.gguf
```

### 3. Build e avvio

```bash
# Build delle immagini
docker compose build

# Avvio di tutto lo stack
docker compose up -d

# Verifica i log
docker compose logs -f
```

### 4. Accesso

- **Fresh Buddy** (app): http://localhost:5000
- **LLM API** (direct): http://localhost:8080/v1

## Configurazione

### Variabili d'ambiente (.env)

```bash
# Server LLM
LLM_PORT=8080
MODEL_NAME=model
MODEL_PATH=./models
CONTEXT_SIZE=4096
N_GPU_LAYERS=32

# API
LLM_API_KEY=not-needed
SYSTEM_PROMPT=Sei Fresh Buddy, un assistente AI amichevole...
FIRST_MESSAGE=Ciao! Sono Fresh Buddy. Come posso aiutarti?
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=512
LLM_TOP_P=0.9

# TTS
PIPER_VOICE=it_IT-riccardo-x_low
TTS_VOLUME=0.3

# STT tuning
STT_MAIN_TIMEOUT=12.0
STT_FOLLOWUP_TIMEOUT=6.0
STT_STREAM_TIMEOUT=3.0
STT_ENERGY_THRESHOLD=500
STT_END_SILENCE_TIMEOUT=0.45
STT_FOLLOWUP_END_SILENCE_TIMEOUT=0.35
STT_STREAM_END_SILENCE_TIMEOUT=0.35
STT_PRE_ROLL_CHUNKS=3

# App
APP_PORT=5000
DEBUG_MODE=false
LOG_LEVEL=INFO
```

### Configurazione manuale (config.json)

```json
{
    "llm_api_endpoint": "http://llm-server:8080/v1",
    "llm_api_key": "not-needed",
    "llm_model_name": "model",
    "llm_temperature": 0.7,
    "llm_max_tokens": 512,
    "llm_top_p": 0.9,
    "piper_voice": "it_IT-riccardo-x_low",
    "tts_volume": 0.3,
    "stt_main_timeout": 12.0,
    "stt_followup_timeout": 6.0,
    "stt_energy_threshold": 500,
    "stt_end_silence_timeout": 0.45,
    "stt_chunk_frames": 512,
    "stt_beam_size": 1,
    "stt_best_of": 1,
    "stt_temperature": 0.0,
    "stt_vad_filter": true,
    "stt_condition_on_previous_text": false,
    "wake_word": "ciao buddy"
}
```

## Deploy su Jetson Orin Nano

### Con GPU (consigliato)

```bash
# Verifica CUDA
docker run --rm --gpus all nvidia/cuda:12.4.0-ga base nvidia-smi

# Build e run
docker compose build
docker compose up -d
```

### Senza GPU (CPU only)

Modifica `docker-compose.yml` togliendo le risorse GPU per `llm-server`:

```yaml
llm-server:
  # rimuovi la sezione deploy.resources
  # il server funzionerà su CPU (più lento)
```

## Servizi Separati

### Solo LLM Server

```bash
# Avvia solo il server LLM
docker compose up -d llm-server

# Test API
curl http://localhost:8080/v1/models
```

### Solo Fresh Buddy (collegato a LLM esterno)

```bash
# Collegati a un LLM già in esecuzione altrove
export LLM_API_ENDPOINT=http://your-llm-server:8080/v1
docker compose up -d fresh-buddy
```

## Troubleshooting

### LLM server non risponde

```bash
# Verifica i log
docker compose logs llm-server

# Test manuale
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"model","messages":[{"role":"user","content":"Ciao"}]}'
```

### Fresh Buddy non si connette

```bash
# Verifica che llm-server sia healthy
docker compose ps

# Verifica endpoint configurato
docker compose exec fresh-buddy env | grep LLM_API
```

### Problemi GPU su Jetson

```bash
# Verifica accesso GPU
docker compose exec llm-server nvidia-smi

# Se non funziona, aggiungi utente al gruppo docker
sudo usermod -aG docker $USER
```

## Production Deployment

Per deployment in produzione considera:

1. **GPU dedicata** al container LLM
2. **Volume persistente** per i meeting
3. **HTTPS** con reverse proxy (nginx/traefik)
4. **Restart policy** appropriate
5. **Monitoring** con healthcheck avanzati

## Build Custom Image

```bash
# Build solo client
docker build -f Dockerfile.client -t fresh-buddy/app .

# Build solo server
docker build -f server/Dockerfile -t fresh-buddy/llm-server ./server
```
