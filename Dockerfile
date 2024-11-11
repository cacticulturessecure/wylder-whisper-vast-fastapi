# Use NVIDIA CUDA base image with CUDA 11.8 and cuDNN 8
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set the working directory
WORKDIR /workspace

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Copy requirements.txt into the image
COPY requirements.txt /workspace/

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.10.6-1~22.04.2 \
    python3-pip=22.0.2+dfsg-1ubuntu0.2 \
    ffmpeg=7:4.4.2-0ubuntu0.22.04.1 \
    git=1:2.34.1-1ubuntu1.9 \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu118 \
    && pip3 install --no-cache-dir git+https://github.com/m-bain/whisperx.git

# Set the default command
CMD ["/bin/bash"]

