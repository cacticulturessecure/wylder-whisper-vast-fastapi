FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

RUN apt-get update -y && \
  apt-get install -y git ffmpeg software-properties-common && \
  add-apt-repository -y ppa:deadsnakes/ppa && \
  apt-get install -y python3.10 python3-pip && \
  pip3 install setuptools-rust && \
  pip3 install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118 && \
  pip3 install git+https://github.com/m-bain/whisperx.git && \
  git clone https://github.com/m-bain/whisperX.git /whisperx && \
  pip3 install -e /whisperx && \
  pip3 install colorama ctranslate2==3.24.0 rich pydantic && \
  mkdir /app && \
  cd /app && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/whisperx"]
