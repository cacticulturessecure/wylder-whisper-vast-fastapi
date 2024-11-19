#!/usr/bin/env python3
import os
import json
import logging
import argparse
import time
from pathlib import Path
import torch
import whisperx
import gc
from typing import Optional, Dict, List
from datetime import datetime

class GPUService:
    def __init__(self, work_dir: str):
        self.work_dir = Path(work_dir)
        self.setup_logging()
        
        # GPU configuration
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "float32"
        self.hf_token = "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"  # Your HuggingFace token
        
        # Disable TF32 for consistency
        if self.device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            logging.info("TF32 disabled for consistency")

    def setup_logging(self):
        """Configure logging system"""
        log_file = self.work_dir / 'process.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        logging.info(f"Initialized GPU Service in {self.work_dir}")

    def load_metadata(self, json_path: Path) -> Optional[Dict]:
        """Load metadata from JSON file"""
        try:
            logging.info(f"Loading metadata from: {json_path}")
            
            if not json_path.exists():
                raise FileNotFoundError(f"Metadata file not found: {json_path}")
                
            with open(json_path, 'r') as f:
                metadata = json.load(f)
                
            # Validate and extract speaker information
            if 'speaker_count' in metadata:
                speaker_count = metadata['speaker_count']
                logging.info(f"Found speaker_count in metadata: {speaker_count}")
            elif 'speakers' in metadata:
                speaker_count = len(metadata['speakers'])
                logging.info(f"Calculated speaker_count from speakers: {speaker_count}")
            else:
                speaker_count = 2  # Default fallback
                logging.warning(f"No speaker information found, defaulting to {speaker_count} speakers")
                metadata['speaker_count'] = speaker_count

            if 'attendees' in metadata:
                logging.info("Found attendee information in metadata")
                for attendee in metadata['attendees']:
                    logging.info(f"Attendee: {attendee.get('name', 'Unknown')}")

            return metadata

        except Exception as e:
            logging.error(f"Error loading metadata: {e}")
            return None

    def process_audio(self, wav_path: Path, metadata: Dict) -> Optional[Dict]:
        """Process audio with WhisperX"""
        try:
            if not wav_path.exists():
                raise FileNotFoundError(f"Audio file not found: {wav_path}")

            logging.info("Loading audio file...")
            audio = whisperx.load_audio(str(wav_path))

            # 1. Transcribe with Whisper
            logging.info("Loading Whisper model...")
            model = whisperx.load_model(
                "large-v2",
                self.device,
                compute_type=self.compute_type,
                language='en'
            )

            logging.info("Transcribing audio...")
            result = model.transcribe(
                audio,
                batch_size=16,
                language='en'
            )

            # 2. Align transcription
            logging.info("Loading alignment model...")
            model_a, metadata_a = whisperx.load_align_model(
                language_code="en",
                device=self.device
            )

            logging.info("Aligning transcript...")
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata_a,
                audio,
                self.device
            )

            # Clear GPU memory after alignment
            del model
            del model_a
            gc.collect()
            torch.cuda.empty_cache()

            # 3. Diarize
            speaker_count = metadata.get('speaker_count', 2)
            logging.info(f"Diarizing with {speaker_count} speakers...")
            
            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=self.hf_token,
                device=self.device
            )

            diarize_segments = diarize_model(
                audio,
                min_speakers=speaker_count,
                max_speakers=speaker_count
            )

            # 4. Assign speakers to words
            logging.info("Assigning speakers to segments...")
            result = whisperx.assign_word_speakers(diarize_segments, result)

            # Final cleanup
            del diarize_model
            gc.collect()
            torch.cuda.empty_cache()

            return result

        except Exception as e:
            logging.error(f"Error processing audio: {e}", exc_info=True)
            return None

    def save_results(self, results: Dict, metadata: Dict):
        """Save processing results in multiple formats"""
        try:
            base_name = self.work_dir.name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create speaker mapping
            speaker_mapping = {}
            if 'attendees' in metadata:
                for i, attendee in enumerate(metadata['attendees'], 1):
                    speaker_mapping[f'SPEAKER_{i}'] = attendee['name']
                logging.info(f"Created speaker mapping: {speaker_mapping}")

            # Apply speaker mapping to results
            if speaker_mapping:
                for segment in results["segments"]:
                    if 'speaker' in segment:
                        segment['speaker'] = speaker_mapping.get(
                            segment['speaker'],
                            segment['speaker']
                        )

            # 1. Save detailed JSON
            detailed_path = self.work_dir / f"{base_name}_detailed_{timestamp}.json"
            with open(detailed_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logging.info(f"Saved detailed transcript: {detailed_path}")

            # 2. Save conversation format
            conversation = self._create_conversation_format(results)
            conversation_path = self.work_dir / f"{base_name}_conversation_{timestamp}.json"
            with open(conversation_path, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, ensure_ascii=False, indent=2)
            logging.info(f"Saved conversation format: {conversation_path}")

            # 3. Save readable text format
            text_path = self.work_dir / f"{base_name}_transcript_{timestamp}.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                for segment in results["segments"]:
                    speaker = segment.get('speaker', 'Unknown')
                    text = segment['text'].strip()
                    f.write(f"{speaker}: {text}\n")
            logging.info(f"Saved text transcript: {text_path}")

            # Create completion marker
            completion_marker = self.work_dir / 'COMPLETED'
            completion_marker.touch()
            logging.info("Processing completed successfully")

            return True

        except Exception as e:
            logging.error(f"Error saving results: {e}", exc_info=True)
            return False

    def _create_conversation_format(self, results: Dict) -> List[Dict]:
        """Create conversation format from segments"""
        conversation = []
        current_speaker = None
        current_text = ''

        for segment in results["segments"]:
            speaker = segment.get('speaker', 'Unknown')
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

        return conversation

def main():
    parser = argparse.ArgumentParser(description='GPU Service for WhisperX Processing')
    parser.add_argument('--wav', required=True, help='WAV file name')
    parser.add_argument('--json', required=True, help='JSON metadata file name')
    parser.add_argument('--work_dir', required=True, help='Working directory')
    args = parser.parse_args()

    try:
        service = GPUService(args.work_dir)
        work_dir = Path(args.work_dir)

        # Verify files exist
        wav_path = work_dir / args.wav
        json_path = work_dir / args.json

        logging.info(f"Processing files:")
        logging.info(f"WAV: {wav_path}")
        logging.info(f"JSON: {json_path}")

        # Load metadata
        metadata = service.load_metadata(json_path)
        if not metadata:
            logging.error("Failed to load metadata")
            return

        # Process audio
        results = service.process_audio(wav_path, metadata)
        if not results:
            logging.error("Failed to process audio")
            return

        # Save results
        if service.save_results(results, metadata):
            logging.info("Processing completed successfully")
        else:
            logging.error("Failed to save results")

    except Exception as e:
        logging.error(f"Service error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
