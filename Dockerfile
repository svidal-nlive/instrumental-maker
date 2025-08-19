FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install CPU-only Torch stack (pin for reproducibility) before large demucs deps
ARG TORCH_VERSION=2.3.1
ARG TORCHAUDIO_VERSION=2.3.1
RUN pip install torch==${TORCH_VERSION} torchaudio==${TORCHAUDIO_VERSION} --index-url https://download.pytorch.org/whl/cpu

# audio + io libs (excluding torch/torchaudio already installed)
RUN pip install --no-cache-dir demucs==4.0.0 librosa==0.10.2.post1 \
    soundfile==0.12.1 numpy==1.26.4 mutagen==1.47.0 pydub==0.25.1 \
    watchdog==4.0.1 pyyaml==6.0.2 python-dotenv==1.0.1 \
    minio==7.2.9 && \
    find /root/.cache -type f -delete 2>/dev/null || true

# Final minimal sanity + cleanup: show versions then remove build tools
RUN python -c "import torch,demucs,librosa;print('ENV OK: torch',torch.__version__,'cpu_only?',not torch.cuda.is_available());print('demucs',demucs.__version__,'librosa',librosa.__version__)" \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

WORKDIR /app
COPY app /app/app
