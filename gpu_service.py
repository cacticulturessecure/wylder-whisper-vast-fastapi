#!/usr/bin/env python3

import os
import json
import logging
import argparse
from pathlib import Path
import torch
import whisperx
import gc
from datetime import datetime
from tqdm import tqdm
import sys
from colorama import init, Fore, Style
import traceback

# Initialize colorama
init()

class GPUService:
    def __init__(self, work_dir: str):
        self.work_dir = Path(work_dir)
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
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.work_dir / 'process.log'),
                logging.StreamHandler()
            ]
        )

    def _debug_print_structure(self, obj, name="Object", max_depth=3, current_depth=0):
        """Helper method to print object structure for debugging"""
        indent = "  " * current_depth
        if current_depth >= max_depth:
            print(f"{indent}{name}: <max depth reached>")
            return

        if isinstance(obj, dict):
            print(f"{indent}{name} (dict with {len(obj)} keys):")
            for k, v in obj.items():
                self._debug_print_structure(v, k, max_depth, current_depth + 1)
        elif isinstance(obj, list):
            print(f"{indent}{name} (list with {len(obj)} items):")
            if obj and current_depth < max_depth - 1:
                self._debug_print_structure(obj[0], "First Item", max_depth, current_depth + 1)
        else:
            print(f"{indent}{name}: {type(obj)}")

    def load_metadata(self, json_file: str) -> dict:
        """Load and validate metadata"""
        try:
            json_path = self.work_dir / json_file
            if not json_path.exists():
                raise FileNotFoundError(f"JSON file not found: {json_path}")

            logging.info(f"Loading metadata from: {json_path}")
            print(f"\n{Fore.CYAN}Loading metadata from: {json_path}{Style.RESET_ALL}")
            
            with open(json_path, 'r') as f:
                metadata = json.load(f)

            if 'speaker_count' in metadata:
                speaker_count = metadata['speaker_count']
                print(f"{Fore.GREEN}✓ Found speaker count: {speaker_count}{Style.RESET_ALL}")
                logging.info(f"Speaker count from metadata: {speaker_count}")
            else:
                speaker_count = 2  # Default fallback
                metadata['speaker_count'] = speaker_count
                print(f"{Fore.YELLOW}⚠ No speaker count found, using default: {speaker_count}{Style.RESET_ALL}")
                logging.warning(f"Using default speaker count: {speaker_count}")

            metadata['processing_start'] = datetime.now().isoformat()
            return metadata

        except Exception as e:
            logging.error(f"Error loading metadata: {e}")
            print(f"{Fore.RED}Error loading metadata: {str(e)}{Style.RESET_ALL}")
            raise

    def process_audio(self, wav_file: str, metadata: dict) -> dict:
        """Process audio with WhisperX"""
        try:
            wav_path = self.work_dir / wav_file
            if not wav_path.exists():
                raise FileNotFoundError(f"WAV file not found: {wav_path}")

            # Load audio
            print(f"\n{Fore.YELLOW}Loading audio...{Style.RESET_ALL}")
            audio = whisperx.load_audio(str(wav_path))
            logging.info("Audio loaded successfully")

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
                logging.info("Transcription completed")

            # Debug print transcription result structure
            print("\nTranscription Result Structure:")
            self._debug_print_structure(result, "Transcription")

            # Align transcript
            print(f"\n{Fore.YELLOW}Aligning transcript...{Style.RESET_ALL}")
            model_a, align_metadata = whisperx.load_align_model(
                language_code="en",
                device=self.device
            )

            with tqdm(total=100, desc="Aligning") as pbar:
                try:
                    result = whisperx.align(
                        result["segments"],
                        model_a,
                        align_metadata,
                        audio,
                        self.device
                    )
                    pbar.update(100)
                    logging.info("Alignment completed")
                except Exception as e:
                    logging.error(f"Error during alignment: {e}")
                    print(f"{Fore.RED}Alignment error: {str(e)}{Style.RESET_ALL}")
                    raise

            # Clear GPU memory after alignment
            del model
            del model_a
            gc.collect()
            torch.cuda.empty_cache()

            # Debug print aligned result structure
            print("\nAligned Result Structure:")
            self._debug_print_structure(result, "Aligned")

            # Pre-diarization speaker count check
            speaker_count = metadata.get('speaker_count', 2)
            print(f"\n{Fore.CYAN}Speaker Detection Info:{Style.RESET_ALL}")
            print(f"🎯 Target speaker count from metadata: {speaker_count}")
            logging.info(f"Starting diarization with target {speaker_count} speakers")

            # Diarize
            print(f"\n{Fore.YELLOW}Diarizing with {speaker_count} speakers...{Style.RESET_ALL}")
            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=self.hf_token,
                device=self.device
            )

            with tqdm(total=100, desc="Diarizing") as pbar:
                try:
                    diarize_segments = diarize_model(
                        audio,
                        min_speakers=speaker_count,
                        max_speakers=speaker_count
                    )
                    pbar.update(100)
                    logging.info("Diarization completed")

                    # Debug print diarization structure
                    print("\nDiarization Result Structure:")
                    self._debug_print_structure(diarize_segments, "Diarization")

                    # Post-diarization speaker verification
                    diarize_speakers = set()
                    if isinstance(diarize_segments, dict) and 'segments' in diarize_segments:
                        segments_to_check = diarize_segments['segments']
                    else:
                        segments_to_check = diarize_segments if isinstance(diarize_segments, list) else []

                    for segment in segments_to_check:
                        if isinstance(segment, dict) and 'speaker' in segment:
                            diarize_speakers.add(segment['speaker'])

                    print(f"\n{Fore.CYAN}Diarization Results:{Style.RESET_ALL}")
                    print(f"🔍 Detected speakers after diarization: {len(diarize_speakers)}")
                    print(f"👥 Speaker IDs found: {sorted(list(diarize_speakers))}")
                    logging.info(f"Diarization found {len(diarize_speakers)} speakers: {sorted(list(diarize_speakers))}")

                    # Assign speakers with error handling
                    try:
                        result = whisperx.assign_word_speakers(diarize_segments, result)
                        logging.info("Speaker assignment completed")
                    except Exception as e:
                        print(f"\n{Fore.RED}Error in speaker assignment: {str(e)}{Style.RESET_ALL}")
                        logging.error(f"Speaker assignment error: {e}")
                        raise

                except Exception as e:
                    print(f"\n{Fore.RED}Error during diarization: {str(e)}{Style.RESET_ALL}")
                    logging.error(f"Diarization error: {e}")
                    raise

            # Final speaker verification
            final_speakers = set()
            if isinstance(result, dict) and 'segments' in result:
                for segment in result['segments']:
                    if isinstance(segment, dict):
                        if 'speaker' in segment:
                            final_speakers.add(segment['speaker'])
                        for word in segment.get('words', []):
                            if isinstance(word, dict) and 'speaker' in word:
                                final_speakers.add(word['speaker'])

            print(f"\n{Fore.CYAN}Final Speaker Assignment:{Style.RESET_ALL}")
            print(f"📊 Final speaker count: {len(final_speakers)}")
            print(f"🏷️  Final speaker IDs: {sorted(list(final_speakers))}")

            # Log any discrepancies
            if len(final_speakers) != speaker_count:
                print(f"\n{Fore.YELLOW}⚠️  Notice: Final speaker count ({len(final_speakers)}) " +
                      f"differs from target ({speaker_count}){Style.RESET_ALL}")
                logging.warning(f"Speaker count mismatch - Target: {speaker_count}, Final: {len(final_speakers)}")

            logging.info(f"Speaker detection summary: Target={speaker_count}, " +
                        f"Diarized={len(diarize_speakers)}, Final={len(final_speakers)}")

            # Cleanup
            del diarize_model
            gc.collect()
            torch.cuda.empty_cache()

            return result

        except Exception as e:
            logging.error(f"Error processing audio: {e}")
            print(f"\n{Fore.RED}Error stack trace:{Style.RESET_ALL}")
            traceback.print_exc()
            raise

    def save_results(self, results: dict, metadata: dict) -> bool:
        """Save processing results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"\n{Fore.GREEN}Saving results...{Style.RESET_ALL}")

            # Debug print results structure before saving
            print("\nResults Structure Before Saving:")
            self._debug_print_structure(results, "Results")

            # Save detailed transcript
            detailed_path = self.work_dir / f"transcript_detailed_{timestamp}.json"
            with open(detailed_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # Save conversation format
            conversation = []
            current_speaker = None
            current_text = ''

            if isinstance(results, dict) and 'segments' in results:
                segments = results['segments']
            else:
                segments = results if isinstance(results, list) else []

            for segment in segments:
                speaker = segment.get('speaker', 'Unknown')
                text = segment.get('text', '').strip()

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

            conversation_path = self.work_dir / f"transcript_conversation_{timestamp}.json"
            with open(conversation_path, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, ensure_ascii=False, indent=2)

            # Save readable text
            text_path = self.work_dir / f"transcript_{timestamp}.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                for segment in segments:
                    speaker = segment.get('speaker', 'Unknown')
                    text = segment.get('text', '').strip()
                    f.write(f"{speaker}: {text}\n")

            print(f"{Fore.GREEN}Results saved:{Style.RESET_ALL}")
            print(f"  📝 Detailed transcript: {detailed_path.name}")
            print(f"  💭 Conversation format: {conversation_path.name}")
            print(f"  📄 Text format: {text_path.name}")

            logging.info("Successfully saved all results")
            return True

        except Exception as e:
            logging.error(f"Error saving results: {e}")
            print(f"\n{Fore.RED}Error stack trace:{Style.RESET_ALL}")
            traceback.print_exc()
            raise

def main():
    parser = argparse.ArgumentParser(description='GPU Service for WhisperX Processing')
    parser.add_argument('--wav', required=True, help='WAV file name')
    parser.add_argument('--json', required=True, help='JSON metadata file name')
    parser.add_argument('--work_dir', required=True, help='Working directory')
    args = parser.parse_args()

    try:
        print(f"\n{Fore.CYAN}=== WhisperX GPU Processing ==={Style.RESET_ALL}")
        service = GPUService(args.work_dir)
        logging.info(f"Starting GPU processing in {args.work_dir}")
        
        # Load metadata
        metadata = service.load_metadata(args.json)
        
        # Process audio
        logging.info(f"Processing audio file: {args.wav}")
        results = service.process_audio(args.wav, metadata)
        
        # Save results
        logging.info("Saving results...")
        service.save_results(results, metadata)
        
        # Create completion marker
        completed_file = Path(args.work_dir) / 'COMPLETED'
        completed_file.touch()
        
        print(f"\n{Fore.GREEN}✓ Processing completed successfully!{Style.RESET_ALL}")
        logging.info("Processing completed successfully")

    except Exception as e:
        print(f"\n{Fore.RED}❌ Processing failed: {str(e)}{Style.RESET_ALL}")
        logging.error(f"Processing failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
