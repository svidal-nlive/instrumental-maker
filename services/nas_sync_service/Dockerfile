FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (rsync, ssh for SCP)
RUN apt-get update && apt-get install -y \
    rsync \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

# Create required directories
RUN mkdir -p /data/logs /data/outputs

# Set executable
RUN chmod +x main.py

# Default: run in daemon mode
CMD ["python", "main.py", "--daemon"]
