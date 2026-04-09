#!/bin/bash
set -e

VOICE="${PIPER_VOICE:-it_IT-riccardo-x_low}"
VOICES_DIR="/app/voices"

mkdir -p "$VOICES_DIR"

if [ ! -f "$VOICES_DIR/${VOICE}.onnx" ]; then
    echo "[tts] Downloading Piper voice: $VOICE ..."

    # Parse voice name: {lang}_{REGION}-{speaker}-{quality}
    # e.g. it_IT-riccardo-x_low → lang=it, region=it_IT, speaker=riccardo, quality=x_low
    LANG=$(echo "$VOICE" | cut -d'_' -f1)
    LANG_REGION=$(echo "$VOICE" | cut -d'-' -f1)
    SPEAKER=$(echo "$VOICE" | cut -d'-' -f2)
    QUALITY=$(echo "$VOICE" | cut -d'-' -f3-)

    BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
    FILE_URL="${BASE_URL}/${LANG}/${LANG_REGION}/${SPEAKER}/${QUALITY}/${VOICE}"

    wget -q --show-progress -O "$VOICES_DIR/${VOICE}.onnx"      "${FILE_URL}.onnx"
    wget -q --show-progress -O "$VOICES_DIR/${VOICE}.onnx.json" "${FILE_URL}.onnx.json"

    echo "[tts] Voice downloaded: $VOICE"
else
    echo "[tts] Voice already present: $VOICE"
fi

export PIPER_MODEL_PATH="${VOICES_DIR}/${VOICE}.onnx"

exec uvicorn server:app --host 0.0.0.0 --port 5002
