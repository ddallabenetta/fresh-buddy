"""STT microservice — wraps faster-whisper."""

import logging
import os
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Fresh Buddy STT Service")

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "tiny")
LANGUAGE = os.environ.get("STT_LANGUAGE", "it")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
BEAM_SIZE = int(os.environ.get("WHISPER_BEAM_SIZE", "1"))
BEST_OF = int(os.environ.get("WHISPER_BEST_OF", "1"))
TEMPERATURE = float(os.environ.get("WHISPER_TEMPERATURE", "0.0"))
VAD_FILTER = os.environ.get("WHISPER_VAD_FILTER", "true").lower() in {"1", "true", "yes"}
CONDITION_ON_PREVIOUS_TEXT = (
    os.environ.get("WHISPER_CONDITION_ON_PREVIOUS_TEXT", "false").lower()
    in {"1", "true", "yes"}
)

_model = None


@app.on_event("startup")
async def load_model():
    global _model
    from faster_whisper import WhisperModel

    logger.info(f"Loading Whisper model '{MODEL_SIZE}' ...")
    _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    logger.info("Whisper model ready")


@app.get("/health")
def health():
    return {"status": "ok" if _model is not None else "loading", "model": MODEL_SIZE}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if _model is None:
        raise HTTPException(503, "Model not ready")

    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio file")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(data)
        tmp_path = f.name

    try:
        segments, info = _model.transcribe(
            tmp_path,
            language=LANGUAGE,
            beam_size=BEAM_SIZE,
            best_of=BEST_OF,
            temperature=TEMPERATURE,
            vad_filter=VAD_FILTER,
            condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        logger.info(f"Transcribed ({info.language}): {text!r}")
        return {"text": text, "language": info.language}
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(500, "Transcription failed")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
