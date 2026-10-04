# 🌸 Kazumi Discord AI Companion — Standalone Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

# Install system dependencies (ca-certificates, ffmpeg for voice/music playback)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
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

# Expose HTTP port for cloud health monitoring (Render / HF Spaces)
EXPOSE 10000
EXPOSE 7860

CMD ["bash", "start.sh"]
