import whisperx
import torch
import gc
import json
from pathlib import Path
import logging
from colorama import init, Fore, Style
from tqdm import tqdm
from typing import Dict, Optional, Tuple

# Initialize colorama
init()

class WhisperXProcessor:
    def __init__(self):
        # Base directory is where the script is run
        self.base_dir = Path("data/audio")
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
        log_dir = self.base_dir.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'whisperx_processing.log'),
                logging.StreamHandler()
            ]
        )

    def find_wav_files(self) -> list:
        """Find WAV files in event directories"""
        wav_files = []
        try:
            # Look for directories containing wav files
            for event_dir in self.base_dir.iterdir():
                if event_dir.is_dir():
                    wav_files.extend(list(event_dir.glob("*.wav")))
                    logging.info(f"Found {len(wav_files)} WAV files in {event_dir}")
            return wav_files
        except Exception as e:
            logging.error(f"Error in find_wav_files: {e}")
            return wav_files

    def load_metadata(self, wav_file: Path) -> Tuple[Optional[Dict], str]:
        """Load metadata from the same directory as the WAV file"""
        try:
            event_dir = wav_file.parent
            json_files = list(event_dir.glob("*.json"))
            
            print(f"\n{Fore.CYAN}Looking for metadata in: {event_dir}{Style.RESET_ALL}")
            
            if not json_files:
                print(f"{Fore.YELLOW}No metadata file found in {event_dir}{Style.RESET_ALL}")
                return None, ""

            # Use the first JSON file found
            metadata_file = json_files[0]
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if 'speaker_count' in metadata or 'speakers' in metadata:
                        speaker_count = metadata.get('speaker_count', len(metadata.get('speakers', [])))
                        print(f"{Fore.GREEN}✓ Found metadata: {metadata_file}")
                        print(f"Speaker count: {speaker_count}{Style.RESET_ALL}")
                        return metadata, str(metadata_file)
            except Exception as e:
                print(f"{Fore.RED}Error reading metadata: {str(e)}{Style.RESET_ALL}")
                return None, ""

            return None, ""
        except Exception as e:
            logging.error(f"Error in load_metadata: {e}")
            return None, ""

    def process_audio_file(self, audio_path: Path):
        """Process a single audio file with WhisperX"""
        print(f"\n{Fore.CYAN}=== Processing Audio File ==={Style.RESET_ALL}")
        print(f"🎤 File: {audio_path}")

        output_dir = audio_path.parent
        metadata, metadata_location = self.load_metadata(audio_path)
        
        if metadata and 'speaker_count' in metadata:
            speaker_count = metadata['speaker_count']
        else:
            speaker_count = 2  # Default fallback
            print(f"{Fore.YELLOW}⚠ No metadata found, defaulting to {speaker_count} speakers{Style.RESET_ALL}")

        try:
            # Load and process audio
            print(f"\n{Fore.YELLOW}Loading audio...{Style.RESET_ALL}")
            audio = whisperx.load_audio(str(audio_path))

            # Transcribe
            print(f"{Fore.YELLOW}Transcribing...{Style.RESET_ALL}")
            model = whisperx.load_model("large-v2", self.device, compute_type=self.compute_type)
            result = model.transcribe(audio, batch_size=16)

            # Align
            print(f"{Fore.YELLOW}Aligning...{Style.RESET_ALL}")
            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=self.device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, self.device)

            # Clear GPU memory
            del model
            del model_a
            gc.collect()
            torch.cuda.empty_cache()

            # Diarize
            print(f"{Fore.YELLOW}Diarizing...{Style.RESET_ALL}")
            diarize_model = whisperx.DiarizationPipeline(use_auth_token=self.hf_token, device=self.device)
            diarize_segments = diarize_model(audio, min_speakers=speaker_count, max_speakers=speaker_count)
            result = whisperx.assign_word_speakers(diarize_segments, result)

            # Save results
            self.save_results(result, audio_path, output_dir, metadata)
            return True

        except Exception as e:
            logging.error(f"Error processing {audio_path}: {e}")
            print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
            return False

    def save_results(self, result: Dict, audio_path: Path, output_dir: Path, metadata: Optional[Dict]):
        """Save processing results"""
        base_name = audio_path.stem
        
        # Create output files
        transcript_path = output_dir / f"{base_name}_transcript.json"
        conversation_path = output_dir / f"{base_name}_conversation.txt"
        
        # Save detailed JSON transcript
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(result["segments"], f, indent=4, ensure_ascii=False)

        # Save conversation format
        with open(conversation_path, 'w', encoding='utf-8') as f:
            for segment in result["segments"]:
                speaker = segment.get('speaker', 'Unknown')
                text = segment['text'].strip()
                f.write(f"{speaker}: {text}\n")

        print(f"\n{Fore.GREEN}Results saved:")
        print(f"📝 Transcript: {transcript_path}")
        print(f"💭 Conversation: {conversation_path}{Style.RESET_ALL}")

    def process_directory(self):
        """Process all WAV files found in event directories"""
        wav_files = self.find_wav_files()
        
        if not wav_files:
            print(f"{Fore.YELLOW}No WAV files found!{Style.RESET_ALL}")
            return

        print(f"\nFound {len(wav_files)} files to process:")
        for wav_file in wav_files:
            print(f"  • {wav_file}")

        successful = 0
        failed = 0

        for i, wav_path in enumerate(wav_files, 1):
            print(f"\n{Fore.CYAN}[File {i}/{len(wav_files)}]{Style.RESET_ALL}")
            if self.process_audio_file(wav_path):
                successful += 1
            else:
                failed += 1

        print(f"\n{Fore.CYAN}=== Processing Summary ===")
        print(f"✓ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Success rate: {(successful/len(wav_files))*100:.1f}%{Style.RESET_ALL}")

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
