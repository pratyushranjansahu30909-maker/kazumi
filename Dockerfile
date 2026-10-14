# 🌸 Kazumi Discord AI Companion — Cloud Production Dockerfile
# Fully compatible with Hugging Face Spaces (24/7 Free CPU), Render, Koyeb, and Cloud VPS
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app

# Install system dependencies (ffmpeg for audio, libopus for voice encoding, ca-certificates, git)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus-dev \
    libopus0 \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Sanitize start.sh line endings, grant execution permissions, and set up storage directories
RUN sed -i 's/\r$//' /app/start.sh && \
    chmod +x /app/start.sh && \
    mkdir -p /app/isa_memory /app/logs && \
    chmod -R 777 /app/isa_memory /app/logs

# Persistent storage volume for memory database
VOLUME /app/isa_memory

# Expose HTTP ports for cloud health monitoring (7860 for Hugging Face Spaces, 10000 for Render)
EXPOSE 7860
EXPOSE 10000

CMD ["bash", "start.sh"]
