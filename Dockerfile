# Use NVIDIA CUDA base image with CUDA 11.8 and cuDNN 8
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set the working directory
WORKDIR /workspace

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    nano \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --upgrade pip \
    # Install PyTorch with specific versions
    && pip3 install torch==2.0.0 torchvision==0.15.0 torchaudio==2.0.0 --index-url https://download.pytorch.org/whl/cu118 \
    # Install WhisperX
    && pip3 install --no-cache-dir git+https://github.com/m-bain/whisperx.git
    # Install colorama pydantic and specific version of
    && pip3 install colorama ctranslate2==3.24.0 pydantic

# Set environment variables to disable TF32
ENV TORCH_BACKENDS_CUDA_MATMUL_ALLOW_TF32=false
ENV TORCH_BACKENDS_CUDNN_ALLOW_TF32=false

# Set the default command
CMD ["/bin/bash"]
