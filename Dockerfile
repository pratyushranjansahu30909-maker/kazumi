# Use a lightweight base image containing both Node.js and Python
FROM nikolaik/python-nodejs:python3.10-nodejs18-slim

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Node dependencies
COPY portfolio/package.json ./portfolio/
WORKDIR /app/portfolio
RUN npm install --omit=dev

# Copy all codebase files
WORKDIR /app
COPY . .

# Set permissions recursively for app directories to ensure write access on Hugging Face (non-root user 1000)
RUN mkdir -p /app/isa_memory && chmod -R 777 /app

# Expose port (Hugging Face Spaces use 7860 by default)
VOLUME /app/isa_memory
EXPOSE 7860

# Set environment variables
ENV PORT=7860
ENV NODE_ENV=production

# Run Node server from portfolio directory
WORKDIR /app/portfolio
CMD ["npm", "start"]
