# Use a modern, supported base image containing both Node.js 20 LTS and Python 3.11
FROM nikolaik/python-nodejs:python3.11-nodejs20-slim

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Node dependencies (root and portfolio)
COPY package*.json ./
COPY portfolio/package*.json ./portfolio/
WORKDIR /app/portfolio
RUN npm install --omit=dev

# Copy all codebase files
WORKDIR /app
COPY . .

# Set permissions recursively for app directories to ensure write access across environments
RUN mkdir -p /app/isa_memory /app/logs && chmod -R 777 /app && chmod +x /app/start.sh

# Expose ports (7860 for Hugging Face Spaces, 10000 for Render)
VOLUME /app/isa_memory
EXPOSE 7860
EXPOSE 10000

# Set environment variables
ENV PORT=10000
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Run start script that launches both Discord bot & Web Portfolio
WORKDIR /app
CMD ["bash", "start.sh"]
