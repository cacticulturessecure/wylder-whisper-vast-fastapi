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
import tarfile
import hashlib
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import sys

class GPUController:
    def __init__(self, config_file: str = "vast_config.json"):
        self.config = self._load_config(config_file)
        self.setup_logging()
        self.max_workers = 4
        
    def setup_logging(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'gpu_controller.log'),
                logging.StreamHandler()
            ]
        )

    def _load_config(self, config_file: str) -> Dict:
        """Load vast.ai configuration"""
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file {config_file} not found. Please create it with vast.ai details.")
        
        with open(config_file, 'r') as f:
            config = json.load(f)
            required = ['host', 'port', 'remote_path']
            if not all(k in config for k in required):
                raise ValueError(f"Config file must contain: {required}")
            return config

    def verify_connection(self) -> bool:
        """Test SSH connection to vast.ai"""
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
            wav_files = glob.glob(os.path.join(input_dir, "*.wav"))
            json_files = glob.glob(os.path.join(input_dir, "*.json"))

            if len(wav_files) != 1 or len(json_files) != 1:
                logging.error(f"Expected exactly 1 WAV and 1 JSON file, found {len(wav_files)} WAV and {len(json_files)} JSON files")
                return None, None

            return wav_files[0], json_files[0]

        except Exception as e:
            logging.error(f"Error finding audio pair: {e}")
            return None, None

    def create_compressed_archive(self, files: list, archive_name: str) -> Optional[str]:
        """Create a compressed tar archive of input files"""
        try:
            print("📦 Creating compressed archive...")
            with tarfile.open(archive_name, "w:gz") as tar:
                for file_path in files:
                    tar.add(file_path, arcname=os.path.basename(file_path))
            return archive_name
        except Exception as e:
            logging.error(f"Error creating archive: {e}")
            return None

    def execute_gpu_service(self, input_dir: str, wav_file: str, json_file: str) -> Optional[str]:
        """Execute GPU service with compressed file transfer"""
        try:
            # Create work directory
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            work_dir = f"{self.config['remote_path']}/work_{timestamp}"
            
            # Create and verify archive
            archive_name = f"input_{timestamp}.tar.gz"
            archive_path = os.path.join(input_dir, archive_name)
            if not self.create_compressed_archive([wav_file, json_file], archive_path):
                raise Exception("Failed to create archive")

            # Setup remote directory
            print("🔄 Setting up remote directory...")
            setup_cmds = [
                f"mkdir -p {work_dir}",
                f"cd {work_dir}"
            ]
            subprocess.run([
                'ssh',
                '-p', str(self.config['port']),
                self.config['host'],
                " && ".join(setup_cmds)
            ], check=True)

            # Upload archive
            print("📤 Uploading files to vast.ai...")
            scp_cmd = [
                'rsync',
                '-avz',
                '--progress',
                '-e', f'ssh -p {self.config["port"]}',
                archive_path,
                f"{self.config['host']}:{work_dir}/"
            ]
            subprocess.run(scp_cmd, check=True)

            # Extract archive
            print("📂 Extracting files on vast.ai...")
            extract_cmd = f"cd {work_dir} && tar xzf {archive_name}"
            subprocess.run([
                'ssh',
                '-p', str(self.config['port']),
                self.config['host'],
                extract_cmd
            ], check=True)

            # Execute GPU service
            print("🚀 Starting GPU processing...")
            execute_cmd = (
                f"cd {work_dir} && "
                "python3 /wylder-whisper-vast-fastapi/gpu_service.py "
                f"--wav {os.path.basename(wav_file)} "
                f"--json {os.path.basename(json_file)} "
                f"--work_dir {work_dir} "
                "> process.log 2>&1 & "
                "echo $!"
            )

            result = subprocess.run([
                'ssh',
                '-p', str(self.config['port']),
                self.config['host'],
                execute_cmd
            ], capture_output=True, text=True, check=True)

            # Cleanup local archive
            os.remove(archive_path)

            return work_dir

        except Exception as e:
            logging.error(f"Error in execute_gpu_service: {e}")
            return None

    def monitor_process(self, work_dir: str) -> bool:
        """Monitor GPU process and log output"""
        try:
            print("\n📊 Monitoring process...")
            with tqdm(total=100, desc="Processing", unit="%") as pbar:
                last_progress = 0
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
                        print(f"\rStatus: {result.stdout.strip()}", end="")

                    # Check for completion
                    check_cmd = f"test -f {work_dir}/COMPLETED"
                    result = subprocess.run([
                        'ssh',
                        '-p', str(self.config['port']),
                        self.config['host'],
                        check_cmd
                    ])

                    if result.returncode == 0:
                        pbar.update(100 - last_progress)
                        logging.info("Processing completed successfully")
                        return True

                    time.sleep(5)

        except KeyboardInterrupt:
            logging.info("Monitoring interrupted by user")
            return False
        except Exception as e:
            logging.error(f"Error monitoring process: {e}")
            return False

    def retrieve_results(self, work_dir: str, local_dir: str, original_files: Tuple[str, str], max_retries: int = 3, initial_delay: int = 5) -> bool:
        """
        Retrieve processed files with retries and verification
        Args:
            work_dir: Remote working directory
            local_dir: Local directory to save results
            original_files: Tuple of (wav_file, json_file) original input files
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first attempt
        """
        try:
            print("\n📥 Retrieving results...")
            transcripts_dir = os.path.join(local_dir, 'transcripts')
            os.makedirs(transcripts_dir, exist_ok=True)

            wav_name = os.path.basename(original_files[0])
            json_name = os.path.basename(original_files[1])

            # Wait for file operations to complete
            print(f"⏳ Waiting {initial_delay} seconds for file operations to complete...")
            time.sleep(initial_delay)

            # Create archive of results on remote
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        print(f"📦 Retry attempt {attempt + 1}/{max_retries}")
                        time.sleep(attempt * 2)

                    remote_archive = "results.tar.gz"
                    create_archive_cmd = (
                        f"cd {work_dir} && "
                        "sleep 2 && "
                        f"tar czf {remote_archive} "
                        f"--exclude='{wav_name}' "
                        f"--exclude='{json_name}' "
                        "--exclude='process.log' "
                        "--exclude='COMPLETED' "
                        "--exclude='input_*.tar.gz' "
                        "--exclude='*.log' "
                        "transcript_* && "
                        f"test -s {remote_archive}"
                    )
                    
                    logging.info(f"Creating remote archive, excluding: {wav_name}, {json_name}")
                    subprocess.run([
                        'ssh',
                        '-p', str(self.config['port']),
                        self.config['host'],
                        create_archive_cmd
                    ], check=True)

                    # Download archive with progress
                    local_archive = os.path.join(transcripts_dir, remote_archive)
                    print(f"📦 Downloading results to: {transcripts_dir}")
                    rsync_cmd = [
                        'rsync',
                        '-avz',
                        '--progress',
                        '-e', f'ssh -p {self.config["port"]}',
                        f"{self.config['host']}:{work_dir}/{remote_archive}",
                        local_archive
                    ]
                    subprocess.run(rsync_cmd, check=True)

                    # Extract locally
                    print("📂 Extracting results...")
                    with tarfile.open(local_archive, "r:gz") as tar:
                        tar.extractall(path=transcripts_dir)

                    # Verify extracted files
                    expected_files = ['transcript_detailed', 'transcript_conversation', 'transcript_']
                    found_files = [
                        f for f in os.listdir(transcripts_dir)
                        if any(exp in f for exp in expected_files)
                    ]
                    
                    if not found_files:
                        raise Exception("No transcript files found in the extracted archive")
                    
                    logging.info(f"Successfully extracted files: {', '.join(found_files)}")

                    # Cleanup
                    os.remove(local_archive)
                    if not self.config.get('keep_remote', False):
                        cleanup_cmd = f"rm -rf {work_dir}"
                        subprocess.run([
                            'ssh',
                            '-p', str(self.config['port']),
                            self.config['host'],
                            cleanup_cmd
                        ], check=True)

                    return True

                except Exception as e:
                    if attempt == max_retries - 1:
                        raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
                    else:
                        logging.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        continue

        except Exception as e:
            logging.error(f"Error retrieving results: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Control GPU processing on vast.ai')
    parser.add_argument('input', help='Input directory containing WAV and JSON files')
    parser.add_argument('--config', default='vast_config.json', help='Path to config file')
    parser.add_argument('--keep-remote', action='store_true', help='Keep remote files after processing')
    args = parser.parse_args()

    try:
        # Validate input directory
        if not os.path.isdir(args.input):
            print(f"❌ Input path must be a directory: {args.input}")
            return

        controller = GPUController(args.config)

        print("\n🔄 Verifying vast.ai connection...")
        if not controller.verify_connection():
            print("❌ Failed to connect to vast.ai")
            return

        print(f"\n🔍 Checking input directory: {args.input}")
        wav_file, json_file = controller.find_audio_pair(args.input)
        if not wav_file or not json_file:
            print("❌ Could not find valid WAV/JSON pair in input directory")
            return

        print(f"\n🚀 Starting GPU processing for:")
        print(f"   WAV:  {os.path.basename(wav_file)}")
        print(f"   JSON: {os.path.basename(json_file)}")

        work_dir = controller.execute_gpu_service(args.input, wav_file, json_file)
        
        if work_dir:
            print(f"\n✅ Processing started in: {work_dir}")
            
            if controller.monitor_process(work_dir):
                print("\n✅ Processing completed successfully!")
                
                if controller.retrieve_results(work_dir, args.input, (wav_file, json_file)):
                    print("\n✅ Results retrieved successfully!")
                    print(f"📂 Results saved in: {args.input}/transcripts/")
                else:
                    print("\n❌ Failed to retrieve results")
            else:
                print("\n❌ Processing failed or was interrupted")
        else:
            print("\n❌ Failed to start GPU processing")

    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        logging.error(f"Unexpected error: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


