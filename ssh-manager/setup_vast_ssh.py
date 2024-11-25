#!/usr/bin/env python3

import os
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

class VastAIKeySetup:
    def __init__(self):
        self.base_dir = Path.home() / "gpu-tunnel"
        self.config_file = self.base_dir / "config" / "tunnel_config.json"
        self.key_output = self.base_dir / "temp_copy_to_vast.txt"
        self.setup_logging()
        
    def setup_logging(self):
        log_dir = self.base_dir / "logs"
        logging.basicConfig(
            filename=log_dir / "ssh_setup.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def validate_environment(self):
        """Check if required files and directories exist"""
        if not self.base_dir.exists():
            raise RuntimeError("gpu-tunnel directory not found. Run setup_tunnel_and_ssh_structure.sh first")
        if not self.config_file.exists():
            raise RuntimeError("Configuration file not found. Run setup_tunnel_and_ssh_structure.sh first")

    def load_config(self):
        """Load existing configuration"""
        with open(self.config_file) as f:
            return json.load(f)

    def save_config(self, config):
        """Save updated configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)

    def generate_ssh_key(self):
        """Generate a new SSH key pair"""
        try:
            console.print("\n[cyan]Generating new SSH key pair...[/cyan]")
            
            # Create .ssh directory if it doesn't exist
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(mode=0o700, exist_ok=True)
            
            # Generate unique key name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            key_name = f"vast_ai_{timestamp}"
            key_path = ssh_dir / f"id_rsa_{key_name}"
            
            # Generate key
            cmd = [
                'ssh-keygen',
                '-t', 'rsa',
                '-b', '4096',
                '-C', f"vast_ai_{timestamp}",
                '-f', str(key_path),
                '-N', ''  # Empty passphrase
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Key generation failed: {result.stderr}")
            
            # Set permissions
            key_path.chmod(0o600)
            key_path.with_suffix('.pub').chmod(0o644)
            
            # Save public key to temp file
            with open(key_path.with_suffix('.pub')) as f:
                public_key = f.read().strip()
            
            with open(self.key_output, 'w') as f:
                f.write(public_key)
            
            console.print("[green]✓ SSH key pair generated successfully![/green]")
            return str(key_path), public_key
            
        except Exception as e:
            logging.error(f"Failed to generate SSH key: {e}")
            console.print(f"[red]Error generating SSH key: {str(e)}[/red]")
            return None, None

    def update_config_with_key(self, key_path):
        """Update configuration with SSH key information"""
        try:
            config = self.load_config()
            config['ssh'] = {
                'private_key': str(key_path),
                'public_key': f"{key_path}.pub",
                'generated_at': datetime.now().isoformat()
            }
            self.save_config(config)
            console.print("[green]✓ Configuration updated with SSH key paths[/green]")
            
        except Exception as e:
            logging.error(f"Failed to update config: {e}")
            console.print(f"[red]Error updating configuration: {str(e)}[/red]")

    def show_instructions(self, public_key):
        """Display instructions for adding the key to Vast.ai"""
        console.print(Panel(
            Markdown("""
            # Next Steps
            
            1. Your SSH public key has been saved to: [bold]temp_copy_to_vast.txt[/bold]
            2. Open the [bold]Vast.ai console[/bold] in your browser
            3. Click [bold]Manage SSH Keys[/bold]
            4. Click [bold]ADD SSH KEY[/bold]
            5. Copy and paste the following key:
            """),
            title="Vast.ai SSH Key Setup Instructions",
            style="cyan"
        ))
        
        console.print(Panel(public_key, style="bold green"))
        
        console.print("\n[yellow]The key has been saved to:[/yellow]")
        console.print(f"[green]{self.key_output}[/green]")

    def setup(self):
        """Run the complete setup process"""
        try:
            console.print(Panel.fit(
                "Vast.ai SSH Key Setup\n"
                "This script will generate and configure SSH keys for your Vast.ai instance",
                style="bold blue"
            ))
            
            self.validate_environment()
            
            # Generate new key
            key_path, public_key = self.generate_ssh_key()
            if not key_path:
                return False
                
            # Update configuration
            self.update_config_with_key(key_path)
            
            # Show instructions
            self.show_instructions(public_key)
            
            # Verify completion
            if Confirm.ask("\nHave you added the SSH key to Vast.ai?"):
                console.print("\n[green]✓ SSH key setup completed successfully![/green]")
                console.print("\nYou can now proceed with starting the tunnel service.")
            else:
                console.print("\n[yellow]Please add the SSH key to Vast.ai before starting the tunnel service[/yellow]")
            
            return True
            
        except Exception as e:
            logging.error(f"Setup failed: {e}")
            console.print(f"\n[red]Setup failed: {str(e)}[/red]")
            return False

if __name__ == "__main__":
    setup = VastAIKeySetup()
    success = setup.setup()
    sys.exit(0 if success else 1)
