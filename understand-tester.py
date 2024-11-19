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
        # Base directories - using data/audio from current working directory
        self.workspace_dir = Path("data/audio")
        
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
        """Find the single WAV/JSON pair in each subfolder"""
        audio_pairs = []
        try:
            # Ensure workspace directory exists
            if not self.workspace_dir.exists():
                logging.warning(f"Workspace directory {self.workspace_dir} does not exist")
                return audio_pairs

            # Log the contents of the workspace directory for debugging
            logging.info(f"Scanning directory: {self.workspace_dir}")
            
            # Look for subdirectories
            for subdir in self.workspace_dir.iterdir():
                if subdir.is_dir() and not subdir.name == 'logs':
                    # Find all WAV and JSON files in this directory
                    wav_files = list(subdir.glob("*.wav"))
                    json_files = list(subdir.glob("*.json"))
                    
                    # Check if we have exactly one of each
                    if len(wav_files) == 1 and len(json_files) == 1:
                        audio_pairs.append((wav_files[0], json_files[0]))
                        logging.info(f"Found pair in {subdir.name}:")
                        logging.info(f"  WAV: {wav_files[0].name}")
                        logging.info(f"  JSON: {json_files[0].name}")
                    else:
                        logging.warning(f"Skipping directory {subdir.name}: " +
                                      f"Found {len(wav_files)} WAV files and {len(json_files)} JSON files")

            return audio_pairs
        except Exception as e:
            logging.error(f"Error in find_audio_pairs: {e}")
            return audio_pairs

    def process_audio_file(self, audio_path: Path, json_path: Path):
        """Process a single audio file with WhisperX"""
        print(f"\n{Fore.CYAN}=== Processing Audio File ==={Style.RESET_ALL}")
        print(f"🎤 File: {audio_path.name}")
        print(f"📂 Directory: {audio_path.parent.name}")
        print(f"📄 Metadata: {json_path.name}")

        # Load metadata
        metadata, metadata_location = self.load_metadata(json_path)
        
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

            # Transcribe with Whisper
            print(f"{Fore.YELLOW}Transcribing with Whisper...{Style.RESET_ALL}")
            model = whisperx.load_model(
                "large-v2",
                self.device,
                compute_type=self.compute_type,
                language='en'
            )

            with tqdm(total=100, desc="Transcribing") as pbar:
                result = model.transcribe(
                    audio,
                    batch_size=16,
                    language='en'
                )
                pbar.update(100)

            # Align transcript
            print(f"\n{Fore.YELLOW}Aligning transcript...{Style.RESET_ALL}")
            model_a, metadata = whisperx.load_align_model(
                language_code="en",
                device=self.device
            )

            with tqdm(total=100, desc="Aligning") as pbar:
                result = whisperx.align(
                    result["segments"],
                    model_a,
                    metadata,
                    audio,
                    self.device
                )
                pbar.update(100)

            # Clear GPU memory
            del model
            del model_a
            gc.collect()
            torch.cuda.empty_cache()

            # Diarize
            print(f"\n{Fore.YELLOW}Diarizing with {speaker_count} speakers...{Style.RESET_ALL}")
            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=self.hf_token,
                device=self.device
            )

            with tqdm(total=100, desc="Diarizing") as pbar:
                diarize_segments = diarize_model(
                    audio,
                    min_speakers=speaker_count,
                    max_speakers=speaker_count
                )
                pbar.update(100)

            result = whisperx.assign_word_speakers(diarize_segments, result)

            # Save results
            self.save_results(result, audio_path, audio_path.parent, metadata)

            print(f"\n{Fore.GREEN}✓ Processing completed successfully!{Style.RESET_ALL}")
            return True

        except Exception as e:
            logging.error(f"Error processing {audio_path}: {e}", exc_info=True)
            print(f"\n{Fore.RED}❌ Error processing file: {str(e)}{Style.RESET_ALL}")
            return False

    def load_metadata(self, json_path: Path) -> Tuple[Optional[Dict], str]:
        """Load metadata from JSON file"""
        try:
            print(f"\n{Fore.CYAN}Loading metadata from: {json_path}{Style.RESET_ALL}")
            
            try:
                with open(json_path, 'r') as f:
                    metadata = json.load(f)
                    # Check for either speaker_count or explicit speakers field
                    if 'speaker_count' in metadata or 'speakers' in metadata:
                        speaker_count = metadata.get('speaker_count', len(metadata.get('speakers', [])))
                        logging.info(f"Found valid metadata at {json_path}")
                        print(f"\n{Fore.GREEN}✓ Found metadata file")
                        print(f"Speaker count: {speaker_count}")
                        
                        # Log full metadata content for debugging
                        print(f"\nMetadata contents:")
                        print(json.dumps(metadata, indent=2))
                        
                        return metadata, str(json_path)
                    else:
                        print(f"{Fore.YELLOW}Missing speaker information in metadata{Style.RESET_ALL}")
            except json.JSONDecodeError:
                print(f"{Fore.RED}Invalid JSON in file: {json_path}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error reading file: {json_path} - {str(e)}{Style.RESET_ALL}")

            return None, ""

        except Exception as e:
            logging.error(f"Error in load_metadata for {json_path}: {e}", exc_info=True)
            print(f"\n{Fore.RED}Error while loading metadata: {str(e)}{Style.RESET_ALL}")
            return None, ""

    def save_results(self, result: Dict, audio_path: Path, output_dir: Path, metadata: Optional[Dict]):
        """Save processing results with speaker mapping"""
        base_name = audio_path.stem
        
        # Create speaker mapping if metadata exists
        speaker_mapping = {}
        if metadata and 'attendees' in metadata:
            for i, attendee in enumerate(metadata['attendees'], 1):
                speaker_mapping[f'SPEAKER_{i}'] = attendee['name']
                
        # Log speaker mapping for debugging
        logging.info(f"Using speaker mapping: {speaker_mapping}")

        # Save detailed transcript with speaker mapping
        transcript_path = output_dir / f"{base_name}.json"
        self.save_transcript(result, transcript_path, speaker_mapping)

        # Save conversation format
        conversation_path = output_dir / f"{base_name}_conversation.json"
        self.save_conversation(result, conversation_path, speaker_mapping)

        # Save text format
        text_path = output_dir / f"{base_name}.txt"
        self.save_text_format(result, text_path, speaker_mapping)

        print(f"\n{Fore.GREEN}Results saved:")
        print(f"  📝 Transcript: {transcript_path}")
        print(f"  💭 Conversation: {conversation_path}")
        print(f"  📄 Text: {text_path}{Style.RESET_ALL}")

    def save_transcript(self, result: Dict, output_file: Path, speaker_mapping: Dict):
        """Save detailed transcript as JSON"""
        segments = result["segments"]
        for segment in segments:
            if 'speaker' in segment:
                segment['speaker'] = speaker_mapping.get(segment['speaker'], segment['speaker'])

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved detailed transcript to {output_file}")

    def save_conversation(self, result: Dict, output_file: Path, speaker_mapping: Dict):
        """Save conversation format as JSON"""
        conversation = []
        current_speaker = None
        current_text = ''

        for segment in result["segments"]:
            speaker = segment.get('speaker', 'Unknown')
            speaker = speaker_mapping.get(speaker, speaker)
            text = segment['text'].strip()

            if speaker != current_speaker:
                if current_speaker is not None:
                    conversation.append({
                        'speaker': current_speaker,
                        'text': current_text.strip()
                    })
                current_speaker = speaker
                current_text = text + ' '
            else:
                current_text += text + ' '

        if current_speaker is not None and current_text:
            conversation.append({
                'speaker': current_speaker,
                'text': current_text.strip()
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved conversation format to {output_file}")

    def save_text_format(self, result: Dict, output_file: Path, speaker_mapping: Dict):
        """Save transcript in readable text format"""
        with open(output_file, 'w', encoding='utf-8') as f:
            for segment in result["segments"]:
                speaker = segment.get('speaker', 'Unknown')
                speaker = speaker_mapping.get(speaker, speaker)
                text = segment['text'].strip()
                f.write(f"{speaker}: {text}\n")
        logging.info(f"Saved text format to {output_file}")

    def process_directory(self):
        """Process WAV/JSON pairs found in subdirectories"""
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
            print(f"  • {wav_file.parent.name}/")
            print(f"    ├── {wav_file.name}")
            print(f"    └── {json_file.name}")

        successful = 0
        failed = 0

        for i, (wav_path, json_path) in enumerate(audio_pairs, 1):
            print(f"\n{Fore.CYAN}[Pair {i}/{len(audio_pairs)} - {wav_path.parent.name}]{Style.RESET_ALL}")
            print("=" * 50)

            try:
                logging.info(f"Processing folder {i}/{len(audio_pairs)}: {wav_path.parent.name}")

                if self.process_audio_file(wav_path, json_path):
                    successful += 1
                    logging.info(f"Successfully processed: {wav_path.parent.name}")
                else:
                    failed += 1
                    logging.error(f"Failed to process: {wav_path.parent.name}")

            except Exception as e:
                logging.error(f"Error processing {wav_path.parent.name}: {e}", exc_info=True)
                failed += 1
                print(f"\n{Fore.RED}Error processing {wav_path.parent.name}: {str(e)}{Style.RESET_ALL}")
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

