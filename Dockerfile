# Use NVIDIA CUDA base image with CUDA 11.8 and cuDNN 8
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set the working directory
WORKDIR /workspace

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Install a compatible version of NumPy
RUN pip3 install --no-cache-dir numpy==1.24.4

# Install PyTorch with CUDA 11.8 support
RUN pip3 install --no-cache-dir \
    torch==2.0.0+cu118 \
    torchvision==0.15.0+cu118 \
    torchaudio==2.0.0 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# Install compatible versions of packages
RUN pip3 install --no-cache-dir \
    tqdm \
    pyannote.audio==2.1.1 \
    pyannote.pipeline==2.4 \
    torchmetrics==0.11.4

# Install WhisperX and dependencies
RUN pip3 install --no-cache-dir git+https://github.com/m-bain/whisperx.git

# Install any additional Python packages you need
RUN pip3 install --no-cache-dir \
    pydantic==1.10.2 \
    colorama==0.4.6

# Set the default command
CMD ["/bin/bash"]
