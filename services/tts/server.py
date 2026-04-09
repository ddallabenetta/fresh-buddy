"""TTS microservice — wraps piper-tts."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Fresh Buddy TTS Service")

VOICE = os.environ.get("PIPER_VOICE", "it_IT-riccardo-x_low")
MODEL_PATH = os.environ.get("PIPER_MODEL_PATH", f"/app/voices/{VOICE}.onnx")


class SynthesizeRequest(BaseModel):
    text: str


@app.get("/health")
def health():
    model_exists = Path(MODEL_PATH).exists()
    return {
        "status": "ok" if model_exists else "no_model",
        "voice": VOICE,
        "model_path": MODEL_PATH,
    }


@app.post("/synthesize", response_class=Response)
def synthesize(req: SynthesizeRequest):
    if not req.text.strip():
        raise HTTPException(400, "Empty text")

    if not Path(MODEL_PATH).exists():
        raise HTTPException(503, f"Voice model not found: {MODEL_PATH}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_file = f.name

    try:
        result = subprocess.run(
            ["piper", "--model", MODEL_PATH, "--output-file", output_file],
            input=req.text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"Piper error: {result.stderr}")
            raise HTTPException(500, "Synthesis failed")

        with open(output_file, "rb") as f:
            wav_bytes = f.read()

        logger.info(f"Synthesized {len(req.text)} chars → {len(wav_bytes)} bytes WAV")
        return Response(content=wav_bytes, media_type="audio/wav")

    except subprocess.TimeoutExpired:
        logger.error("Piper synthesis timed out")
        raise HTTPException(500, "Synthesis timed out")
    finally:
        Path(output_file).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)
