import os
import sys
import subprocess
from pathlib import Path
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.progress import Progress
from rich import print as rprint
from rich.markdown import Markdown

console = Console()

class InteractiveSSHSetup:
    def __init__(self):
        self.setup_logging()
        self.console = Console()
        
    def setup_logging(self):
        logging.basicConfig(
            filename='ssh_setup.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def display_banner(self):
        console.print(Panel.fit(
            "Vast.ai SSH Key Setup\n"
            "This script will help you generate and configure SSH keys for Vast.ai instances",
            style="bold blue"
        ))

    def get_connection_details(self) -> dict:
        console.print("\n[yellow]Please enter the Vast.ai instance details:[/yellow]")
        
        details = {
            'host': Prompt.ask("Enter the instance IP"),
            'port': IntPrompt.ask("Enter the SSH port shown in Vast.ai console"),
            'user': Prompt.ask("Enter the username", default="root")
        }
        
        # Port forwarding for Vast.ai (typically 8080)
        if Confirm.ask("Set up port forwarding for Jupyter/web services (recommended)?", default=True):
            details['forwards'] = [('8080', 'localhost', '8080')]
            console.print("[green]Added port forwarding: 8080:localhost:8080[/green]")
        else:
            details['forwards'] = []
            
        return details

    def generate_key(self, env_name: str, key_path: str) -> Optional[str]:
        try:
            key_path = os.path.expanduser(key_path)
            key_dir = os.path.dirname(key_path)
            
            if not os.path.exists(key_dir):
                os.makedirs(key_dir, mode=0o700)

            if os.path.exists(key_path):
                if Confirm.ask(f"\nKey already exists at {key_path}. Generate new key?"):
                    backup_path = f"{key_path}.backup"
                    os.rename(key_path, backup_path)
                    if os.path.exists(f"{key_path}.pub"):
                        os.rename(f"{key_path}.pub", f"{backup_path}.pub")
                    console.print(f"[yellow]Backed up existing key to {backup_path}[/yellow]")
                else:
                    with open(f"{key_path}.pub", 'r') as f:
                        return f.read().strip()

            console.print("\n[cyan]Generating new SSH key...[/cyan]")
            
            process = subprocess.run([
                'ssh-keygen',
                '-t', 'rsa',  # Vast.ai uses RSA keys
                '-b', '4096',
                '-f', key_path,
                '-N', '',
                '-C', f"vast_ai_{env_name}_{datetime.now().strftime('%Y%m%d')}"
            ], capture_output=True, text=True)

            if process.returncode != 0:
                raise Exception(f"Key generation failed: {process.stderr}")

            with open(f"{key_path}.pub", 'r') as f:
                public_key = f.read().strip()

            os.chmod(key_path, 0o600)
            os.chmod(f"{key_path}.pub", 0o644)

            console.print("[green]Key generation successful![/green]")
            return public_key

        except Exception as e:
            logging.error(f"Error generating key for {env_name}: {str(e)}")
            console.print(f"[red]Error generating key: {str(e)}[/red]")
            return None

    def verify_connection(self, host: str, user: str, key_path: str, port: int, forwards: List[Tuple[str, str, str]] = None) -> bool:
        try:
            key_path = os.path.expanduser(key_path)
            console.print("\n[cyan]Testing SSH connection...[/cyan]")
            
            cmd = [
                'ssh',
                '-i', key_path,
                '-p', str(port),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10'
            ]

            if forwards:
                for local_port, remote_host, remote_port in forwards:
                    cmd.extend(['-L', f'{local_port}:{remote_host}:{remote_port}'])

            cmd.extend([
                f'{user}@{host}',
                'echo "Connection successful"'
            ])

            console.print(f"[yellow]Testing command: {' '.join(cmd)}[/yellow]")
            
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if process.returncode == 0:
                console.print("[green]Connection test successful![/green]")
                return True
            else:
                console.print(f"[red]Connection test failed: {process.stderr}[/red]")
                return False
            
        except subprocess.TimeoutExpired:
            console.print("[red]Connection test timed out[/red]")
            return False
        except Exception as e:
            logging.error(f"Connection test failed for {host}: {str(e)}")
            console.print(f"[red]Connection test failed: {str(e)}[/red]")
            return False

    def interactive_setup(self):
        self.display_banner()
        
        while True:
            env_name = Prompt.ask("\nEnter a name for this instance", default="vast_gpu")
            key_path = f"~/.ssh/id_rsa_{env_name}"
            
            # Generate key first
            console.print(f"\n[bold blue]Generating SSH Key for {env_name}[/bold blue]")
            public_key = self.generate_key(env_name, key_path)
            
            if not public_key:
                if not Confirm.ask("\nKey generation failed. Retry?"):
                    break
                continue
            
            # Show Vast.ai instructions
            console.print("\n[yellow]Follow these steps to add your SSH key to Vast.ai:[/yellow]")
            console.print(Panel.fit(
                "1. Copy the SSH public key below\n"
                "2. Go to the Vast.ai console in your browser\n"
                "3. Click 'Manage SSH Keys' for your instance\n"
                "4. Click 'ADD SSH KEY' and paste the key\n"
                "5. Wait a few moments for the key to be added",
                title="Vast.ai Setup Instructions",
                style="cyan"
            ))
            
            console.print("\n[green]Your SSH Public Key:[/green]")
            console.print(Panel(public_key, style="bold green"))
            
            if not Confirm.ask("\nHave you added the key to Vast.ai console?"):
                console.print("[yellow]Please add the key before continuing[/yellow]")
                continue
            
            # Get connection details
            env_details = self.get_connection_details()
            
            # Test connection
            if self.verify_connection(
                env_details['host'], 
                env_details['user'], 
                key_path, 
                env_details['port'],
                env_details['forwards']
            ):
                # Display the final connection command
                if env_details['forwards']:
                    forwards = ' '.join(f"-L {local}:{remote_host}:{remote}" 
                                     for local, remote_host, remote in env_details['forwards'])
                    connection_cmd = (f"ssh -i {key_path} -p {env_details['port']} "
                                    f"{forwards} {env_details['user']}@{env_details['host']}")
                else:
                    connection_cmd = (f"ssh -i {key_path} -p {env_details['port']} "
                                    f"{env_details['user']}@{env_details['host']}")
                
                console.print("\n[green]Use this command to connect to your Vast.ai instance:[/green]")
                console.print(Panel(connection_cmd, style="bold green"))
            
            if not Confirm.ask("\nSet up another instance?"):
                break

        console.print("\n[bold green]Setup process completed![/bold green]")

if __name__ == "__main__":
    setup = InteractiveSSHSetup()
    setup.interactive_setup()
