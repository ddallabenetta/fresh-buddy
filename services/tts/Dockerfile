FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py audio_utils.py entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p /app/voices

ENV PIPER_VOICE=it_IT-riccardo-x_low
ENV LOG_LEVEL=INFO

EXPOSE 5002

ENTRYPOINT ["./entrypoint.sh"]
