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

_model = None


@app.on_event("startup")
async def load_model():
    global _model
    from faster_whisper import WhisperModel

    logger.info(f"Loading Whisper model '{MODEL_SIZE}' ...")
    _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
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
        segments, info = _model.transcribe(tmp_path, language=LANGUAGE)
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
