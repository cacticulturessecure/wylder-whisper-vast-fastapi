import whisperx
import torch
import gc
import os
import json
from pathlib import Path
from datetime import datetime
import logging
from colorama import init, Fore, Style
from tqdm import tqdm
import soundfile as sf
from typing import Dict, List, Optional, Tuple
import time

# Initialize colorama
init()

class WhisperXProcessor:
    def __init__(self):
        # Base directories
        self.workspace_dir = Path("/data/audio")
        
        self.setup_logging()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "float32"
        self.hf_token = "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"

        # Disable TF32 for consistency
        if self.device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            logging.info("TF32 disabled for consistency")

    def setup_logging(self):
        """Configure logging system"""
        log_dir = self.workspace_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'whisperx_processing.log'),
                logging.StreamHandler()
            ]
        )

    def find_audio_pairs(self):
        """Find WAV files and their corresponding JSON files in the data directory"""
        audio_pairs = []
        try:
            # Ensure base directory exists
            if not self.workspace_dir.exists():
                logging.warning(f"Base directory {self.workspace_dir} does not exist")
                return audio_pairs

            # Log the contents of the base directory for debugging
            logging.info(f"Scanning directory: {self.workspace_dir}")
            logging.info(f"Directory contents: {[str(p) for p in self.workspace_dir.iterdir()]}")

            # Look for subdirectories
            for subdir in self.workspace_dir.iterdir():
                if subdir.is_dir() and not subdir.name == 'logs':
                    # Look for WAV and JSON files in each subdirectory
                    wav_files = list(subdir.glob("*.wav"))
                    
                    for wav_file in wav_files:
                        # Look for corresponding JSON file
                        json_file = wav_file.with_suffix('.json')
                        
                        if json_file.exists():
                            audio_pairs.append((wav_file, json_file))
                            logging.info(f"Found pair: {wav_file.name} - {json_file.name}")
                        else:
                            logging.warning(f"No JSON file found for {wav_file}")

            return audio_pairs
        except Exception as e:
            logging.error(f"Error in find_audio_pairs: {e}")
            return audio_pairs

    def load_metadata(self, json_file: Path) -> Tuple[Optional[Dict], str]:
        """Load metadata from JSON file"""
        try:
            print(f"\n{Fore.CYAN}Loading metadata from: {json_file}{Style.RESET_ALL}")
            
            if json_file.exists():
                try:
                    with open(json_file, 'r') as f:
                        metadata = json.load(f)
                        # Check for either speaker_count or explicit speakers field
                        if 'speaker_count' in metadata or 'speakers' in metadata:
                            speaker_count = metadata.get('speaker_count', len(metadata.get('speakers', [])))
                            logging.info(f"Found valid metadata at {json_file}")
                            print(f"\n{Fore.GREEN}✓ Found metadata file: {json_file}")
                            print(f"Speaker count: {speaker_count}")
                            
                            # Log full metadata content for debugging
                            print(f"\nMetadata contents:")
                            print(json.dumps(metadata, indent=2))
                            
                            return metadata, str(json_file)
                        else:
                            print(f"{Fore.YELLOW}Missing speaker information in metadata{Style.RESET_ALL}")
                except json.JSONDecodeError:
                    print(f"{Fore.RED}Invalid JSON in file: {json_file}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error reading file: {json_file} - {str(e)}{Style.RESET_ALL}")

            print(f"\n{Fore.YELLOW}⚠ No valid metadata found at {json_file}{Style.RESET_ALL}")
            return None, ""

        except Exception as e:
            logging.error(f"Error in load_metadata for {json_file}: {e}", exc_info=True)
            print(f"\n{Fore.RED}Error while loading metadata: {str(e)}{Style.RESET_ALL}")
            return None, ""

    def process_audio_file(self, audio_path: Path, metadata_path: Path):
        """Process a single audio file with WhisperX"""
        print(f"\n{Fore.CYAN}=== Processing Audio File ==={Style.RESET_ALL}")
        print(f"🎤 File: {audio_path.name}")
        print(f"📂 Output directory: {audio_path.parent}")

        # Load metadata
        metadata, metadata_location = self.load_metadata(metadata_path)
        
        if metadata and 'speaker_count' in metadata:
            speaker_count = metadata['speaker_count']
            print(f"\n{Fore.GREEN}✓ Using metadata from: {metadata_location}")
            print(f"👥 Number of speakers: {speaker_count}")
            if 'attendees' in metadata:
                print("Attendees:")
                for attendee in metadata['attendees']:
                    print(f"  • {attendee['name']}")
        else:
            speaker_count = 2  # Default fallback
            print(f"\n{Fore.YELLOW}⚠ No metadata found, defaulting to {speaker_count} speakers{Style.RESET_ALL}")

        try:
            # Load audio
            print(f"\n{Fore.YELLOW}Loading audio...{Style.RESET_ALL}")
            audio = whisperx.load_audio(str(audio_path))

            # Rest of the processing remains the same...
            # [Previous transcription, alignment, and diarization code remains unchanged]

            # Save results
            self.save_results(result, audio_path, audio_path.parent, metadata)

            print(f"\n{Fore.GREEN}✓ Processing completed successfully!{Style.RESET_ALL}")
            return True

        except Exception as e:
            logging.error(f"Error processing {audio_path}: {e}", exc_info=True)
            print(f"\n{Fore.RED}❌ Error processing file: {str(e)}{Style.RESET_ALL}")
            return False

    # [save_results, save_transcript, save_conversation, and save_text_format methods remain unchanged]

    def process_directory(self):
        """Process WAV files and their corresponding JSON files"""
        print(f"\n{Fore.CYAN}=== WhisperX Audio Processing ==={Style.RESET_ALL}")
        print(f"📂 Scanning directory: {self.workspace_dir}")

        # Find WAV and JSON file pairs
        audio_pairs = self.find_audio_pairs()
        
        if not audio_pairs:
            print(f"\n{Fore.YELLOW}No WAV/JSON pairs found in the directory!{Style.RESET_ALL}")
            return

        print(f"\nFound {len(audio_pairs)} audio pairs to process")
        print("\nFiles to process:")
        for wav_file, json_file in audio_pairs:
            print(f"  • {wav_file.relative_to(self.workspace_dir)} - {json_file.relative_to(self.workspace_dir)}")

        successful = 0
        failed = 0

        for i, (wav_path, json_path) in enumerate(audio_pairs, 1):
            print(f"\n{Fore.CYAN}[Pair {i}/{len(audio_pairs)}]{Style.RESET_ALL}")
            print("=" * 50)

            try:
                logging.info(f"Processing pair {i}/{len(audio_pairs)}: {wav_path} - {json_path}")

                if self.process_audio_file(wav_path, json_path):
                    successful += 1
                    logging.info(f"Successfully processed: {wav_path}")
                else:
                    failed += 1
                    logging.error(f"Failed to process: {wav_path}")

            except Exception as e:
                logging.error(f"Error processing {wav_path}: {e}", exc_info=True)
                failed += 1
                print(f"\n{Fore.RED}Error processing {wav_path.name}: {str(e)}{Style.RESET_ALL}")
                continue

        # Print summary
        summary = f"""
{Fore.CYAN}=== Processing Summary ==={Style.RESET_ALL}
✓ Successfully processed: {successful}
❌ Failed: {failed}
📊 Success rate: {(successful/len(audio_pairs))*100:.1f}%
"""
        print(summary)
        logging.info(f"Processing complete. Success: {successful}, Failed: {failed}")

def main():
    try:
        processor = WhisperXProcessor()
        processor.process_directory()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Processing interrupted by user.{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"\n{Fore.RED}An unexpected error occurred. Check logs for details.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
