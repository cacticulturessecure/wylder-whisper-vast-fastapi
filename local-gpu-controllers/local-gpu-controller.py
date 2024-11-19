#!/usr/bin/env python3
import os
import subprocess
import json
import time
import argparse
from pathlib import Path
import logging
from typing import Optional, Dict, Tuple
import glob

class GPUController:
    def __init__(self, config_file: str = "vast_config.json"):
        self.config = self._load_config(config_file)
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('gpu_controller.log'),
                logging.StreamHandler()
            ]
        )

    def _load_config(self, config_file: str) -> Dict:
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file {config_file} not found. Please create it with vast.ai details.")
        
        with open(config_file, 'r') as f:
            config = json.load(f)
            required = ['host', 'port', 'remote_path']
            if not all(k in config for k in required):
                raise ValueError(f"Config file must contain: {required}")
            return config

    def verify_connection(self) -> bool:
        try:
            cmd = [
                'ssh',
                '-p', str(self.config['port']),
                self.config['host'],
                'echo "Connection test"'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Connection error: {e}")
            return False

    def find_audio_pair(self, input_dir: str) -> Tuple[Optional[str], Optional[str]]:
        """Find WAV and JSON files in input directory"""
        try:
            # Find all WAV and JSON files
            wav_files = glob.glob(os.path.join(input_dir, "*.wav"))
            json_files = glob.glob(os.path.join(input_dir, "*.json"))

            if len(wav_files) != 1 or len(json_files) != 1:
                logging.error(f"Expected exactly 1 WAV and 1 JSON file, found {len(wav_files)} WAV and {len(json_files)} JSON files")
                return None, None

            return wav_files[0], json_files[0]

        except Exception as e:
            logging.error(f"Error finding audio pair: {e}")
            return None, None

    def execute_gpu_service(self, input_dir: str) -> Optional[str]:
        """Execute GPU service on vast.ai with input directory"""
        try:
            # Find WAV and JSON files
            wav_file, json_file = self.find_audio_pair(input_dir)
            if not wav_file or not json_file:
                raise ValueError("Could not find valid WAV/JSON pair in input directory")

            # Create remote work directory with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            work_dir = f"{self.config['remote_path']}/work_{timestamp}"
            
            logging.info(f"Creating work directory: {work_dir}")
            
            # Create directory on vast.ai
            setup_cmd = f"mkdir -p {work_dir}"
            subprocess.run([
                'ssh',
                '-p', str(self.config['port']),
                self.config['host'],
                setup_cmd
            ], check=True)

            # Copy files to vast.ai
            for file_path in [wav_file, json_file]:
                logging.info(f"Copying {os.path.basename(file_path)} to vast.ai...")
                scp_cmd = [
                    'scp',
                    '-P', str(self.config['port']),
                    file_path,
                    f"{self.config['host']}:{work_dir}/"
                ]
                subprocess.run(scp_cmd, check=True)

            # Execute GPU service
            execute_cmd = (
                f"cd {work_dir} && "
                "python3 /wylder-whisper-vast-fastapi/gpu_service.py "
                f"--wav {os.path.basename(wav_file)} "
                f"--json {os.path.basename(json_file)} "
                f"--work_dir {work_dir} "
                "> process.log 2>&1 & "
                "echo $!"
            )

            logging.info("Starting GPU processing...")
            result = subprocess.run([
                'ssh',
                '-p', str(self.config['port']),
                self.config['host'],
                execute_cmd
            ], capture_output=True, text=True, check=True)

            pid = result.stdout.strip()
            logging.info(f"GPU service started with PID: {pid}")

            return work_dir

        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {e.cmd}")
            logging.error(f"Output: {e.output}")
            return None
        except Exception as e:
            logging.error(f"Error executing GPU service: {e}")
            return None

    def monitor_process(self, work_dir: str) -> bool:
        """Monitor GPU process and log output"""
        try:
            while True:
                # Check log file
                log_cmd = f"tail -n 1 {work_dir}/process.log"
                result = subprocess.run([
                    'ssh',
                    '-p', str(self.config['port']),
                    self.config['host'],
                    log_cmd
                ], capture_output=True, text=True)

                if result.stdout:
                    print(f"Status: {result.stdout.strip()}")

                # Check for completion file
                check_cmd = f"test -f {work_dir}/COMPLETED"
                result = subprocess.run([
                    'ssh',
                    '-p', str(self.config['port']),
                    self.config['host'],
                    check_cmd
                ])

                if result.returncode == 0:
                    logging.info("Processing completed successfully")
                    return True

                time.sleep(5)  # Check every 5 seconds

        except KeyboardInterrupt:
            logging.info("Monitoring interrupted by user")
            return False
        except Exception as e:
            logging.error(f"Error monitoring process: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Control GPU processing on vast.ai')
    parser.add_argument('input', help='Input directory containing WAV and JSON files')
    parser.add_argument('--config', default='vast_config.json', help='Path to config file')
    args = parser.parse_args()

    try:
        # Validate input directory
        if not os.path.isdir(args.input):
            print(f"❌ Input path must be a directory: {args.input}")
            return

        controller = GPUController(args.config)

        print("🔄 Verifying vast.ai connection...")
        if not controller.verify_connection():
            print("❌ Failed to connect to vast.ai")
            return

        print(f"🔍 Checking input directory: {args.input}")
        wav_file, json_file = controller.find_audio_pair(args.input)
        if not wav_file or not json_file:
            print("❌ Could not find valid WAV/JSON pair in input directory")
            return

        print(f"🚀 Starting GPU processing for:")
        print(f"   WAV:  {os.path.basename(wav_file)}")
        print(f"   JSON: {os.path.basename(json_file)}")

        work_dir = controller.execute_gpu_service(args.input)
        
        if work_dir:
            print(f"✅ Processing started in: {work_dir}")
            print("📊 Monitoring process...")
            if controller.monitor_process(work_dir):
                print("✅ Processing completed successfully!")
            else:
                print("❌ Processing failed or was interrupted")
        else:
            print("❌ Failed to start GPU processing")

    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
