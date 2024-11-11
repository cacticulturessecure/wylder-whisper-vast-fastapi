#!/usr/bin/env python3

import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv('HF_TOKEN')
WORKSPACE_DIR = os.getenv('WORKSPACE_DIR', '/workspace/audio')
