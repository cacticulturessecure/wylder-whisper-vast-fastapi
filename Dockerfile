# Use the official PyTorch image with CUDA 11.8 support
FROM pytorch/pytorch:2.0.1-cuda11.8-cudnn8-runtime

# Set the working directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the project files into the container
COPY . /workspace

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Set the default command
CMD ["/bin/bash"]

