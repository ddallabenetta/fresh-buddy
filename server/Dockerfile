# LLM Server - llama.cpp server with OpenAI-compatible API
# GPU support via CUDA

FROM nvidia/cuda:12.4.0-devel-ubuntu22.04

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3 \
    python3-pip \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone and build llama.cpp server
RUN git clone https://github.com/ggerganov/llama.cpp.git /llama.cpp \
    && cd /llama.cpp \
    && mkdir build \
    && cd build \
    && cmake .. -DLLAMA_SERVER_GPU_METAL=OFF -DLLAMA_CUBLAS=ON \
    && cmake --build . --config Release -j$(nproc) \
    && cp server /app/llama-server \
    && cp -r ../models /app/models_template \
    && cd / && rm -rf /llama.cpp

# Create models directory
RUN mkdir -p /models

# Environment
ENV MODEL_NAME=model
ENV CONTEXT_SIZE=4096
ENV N_GPU_LAYERS=32
ENV PORT=8080

EXPOSE 8080

# Run server - mount your GGUF model to /models
ENTRYPOINT ["/app/llama-server", "--host", "0.0.0.0", "--port", "8080"]
CMD ["--model", "/models/model.gguf", "--ctx-size", "4096", "--n-gpu-layers", "32"]
