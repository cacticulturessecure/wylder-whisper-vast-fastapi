import json
from pathlib import Path
from colorama import init, Fore, Style
import inquirer
from datetime import datetime
import logging

# Initialize colorama
init()

class MetadataManager:
    def __init__(self):
        self.current_dir = Path.cwd()
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )

    def list_wav_files(self):
        """List all WAV files in current directory"""
        return list(self.current_dir.glob("*.wav"))

    def select_wav_file(self, wav_files):
        """Prompt user to select a WAV file"""
        if not wav_files:
            print(f"{Fore.RED}No WAV files found in current directory!{Style.RESET_ALL}")
            return None

        questions = [
            inquirer.List('wav_file',
                         message="Select WAV file to add metadata",
                         choices=[f.name for f in wav_files])
        ]
        
        answers = inquirer.prompt(questions)
        return self.current_dir / answers['wav_file'] if answers else None

    def get_speaker_count(self):
        """Prompt user for number of speakers"""
        while True:
            try:
                count = input(f"\n{Fore.GREEN}Enter number of speakers (1-10): {Style.RESET_ALL}")
                count = int(count)
                if 1 <= count <= 10:
                    return count
                print(f"{Fore.RED}Please enter a number between 1 and 10{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number{Style.RESET_ALL}")

    def save_metadata(self, wav_file, speaker_count):
        """Save metadata in WhisperX compatible format"""
        # Extract event details from filename
        filename_parts = wav_file.stem.split('_')
        if len(filename_parts) >= 6:  # audio_only_Event_Name_YYYYMMDD_HHMMSS
            date_str = filename_parts[-2]  # YYYYMMDD format
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            event_name = '_'.join(filename_parts[2:-2])
        else:
            event_name = wav_file.stem
            formatted_date = datetime.now().strftime("%Y-%m-%d")

        # Create WhisperX compatible metadata
        metadata = {
            'speaker_count': speaker_count,
            'event_title': event_name,
            'date': formatted_date,
            'file_name': wav_file.name,
            'date_modified': datetime.now().isoformat(),
            'metadata_version': '1.0'
        }
        
        metadata_file = wav_file.with_suffix('.metadata.json')
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4)
            print(f"\n{Fore.GREEN}✓ Metadata saved successfully to: {metadata_file.name}{Style.RESET_ALL}")
            return True
        except Exception as e:
            print(f"\n{Fore.RED}Error saving metadata: {e}{Style.RESET_ALL}")
            return False

    def verify_metadata(self, wav_file):
        """Verify metadata in WhisperX format"""
        print(f"\n{Fore.CYAN}=== Verifying Metadata ==={Style.RESET_ALL}")
        print(f"File: {wav_file.name}")
        
        metadata_file = wav_file.with_suffix('.metadata.json')
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                print(f"\n{Fore.GREEN}✓ Found metadata file: {metadata_file.name}{Style.RESET_ALL}")
                print("\nMetadata contents:")
                for key, value in metadata.items():
                    print(f"  • {key}: {value}")
                
                # Verify required WhisperX fields
                required_fields = ['speaker_count', 'event_title', 'date']
                missing_fields = [field for field in required_fields if field not in metadata]
                
                if missing_fields:
                    print(f"\n{Fore.YELLOW}⚠️ Missing required fields: {', '.join(missing_fields)}{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.GREEN}✓ All required fields present{Style.RESET_ALL}")
                    print(f"Speaker count: {metadata['speaker_count']}")
                
                return True
            
            except Exception as e:
                print(f"{Fore.RED}Error reading metadata file: {e}{Style.RESET_ALL}")
                return False
        else:
            print(f"{Fore.RED}✗ No metadata file found ({metadata_file.name}){Style.RESET_ALL}")
            return False

    def run(self):
        print(f"\n{Fore.CYAN}=== WAV File Metadata Manager ==={Style.RESET_ALL}")
        
        try:
            # List WAV files
            wav_files = self.list_wav_files()
            if not wav_files:
                return
            
            # Select WAV file
            wav_file = self.select_wav_file(wav_files)
            if not wav_file:
                return
            
            # Menu for actions
            questions = [
                inquirer.List('action',
                             message="Select action",
                             choices=['Add/Update Metadata', 'Verify Metadata', 'Both'])
            ]
            
            answers = inquirer.prompt(questions)
            action = answers['action']
            
            if action in ['Add/Update Metadata', 'Both']:
                speaker_count = self.get_speaker_count()
                self.save_metadata(wav_file, speaker_count)
            
            if action in ['Verify Metadata', 'Both']:
                self.verify_metadata(wav_file)
            
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Operation cancelled by user{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

def main():
    manager = MetadataManager()
    manager.run()

if __name__ == "__main__":
    main()

