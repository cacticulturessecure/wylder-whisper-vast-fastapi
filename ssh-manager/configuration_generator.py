import os
import json
from pathlib import Path
from string import Template
from dotenv import load_dotenv

def generate_config():
    # Load environment variables
    load_dotenv()
    
    # Read template
    template_path = Path("config/ssh_config.json.template")
    with open(template_path) as f:
        template_content = f.read()
    
    # Replace variables
    template = Template(template_content)
    config_content = template.substitute(os.environ)
    
    # Write actual config
    config_path = Path("config/ssh_config.json")
    with open(config_path, "w") as f:
        f.write(config_content)
    
    print(f"Generated SSH config at {config_path}")

if __name__ == "__main__":
    generate_config()
