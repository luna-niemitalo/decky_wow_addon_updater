import os
import json
import subprocess
from pathlib import Path

def load_config(config_file):
    """Load configuration parameters from a JSON file."""
    with open(config_file, 'r') as file:
        return json.load(file)



def transfer_files(config):
    """Transfer files to the target server using rsync."""
    rsync_command = [
        "rsync", "-azp", "--chmod=D0755,F0755",
        f"--rsh=ssh -p {config['deckport']} {config['deckkey']}",
        "out/",
        f"{config['deckuser']}@{config['deckip']}:{config['deckdir']}/homebrew/plugins"
    ]
    print(f"Running rsync command: {' '.join(rsync_command)}")
    subprocess.run(rsync_command, check=True)

def extract_files(config):
    """Extract files on the target server."""
    plugin_dir = f"{config['deckdir']}/homebrew/plugins/{config['pluginname']}"
    escaped_plugin_dir = plugin_dir.replace(' ', '-')

    extract_command = (
        f"ssh {config['deckuser']}@{config['deckip']} -p {config['deckport']} {config['deckkey']} "
        f"\"echo {config['deckpass']} | sudo -S mkdir -p '{escaped_plugin_dir}' && "
        f"echo {config['deckpass']} | sudo -S chown {config['deckuser']}:{config['deckuser']} '{escaped_plugin_dir}' && "
        f"echo {config['deckpass']} | sudo -S bsdtar -xzpf '{plugin_dir}.zip' -C '{escaped_plugin_dir}' --strip-components=1 --fflags\""
    )

    print(f"Running extraction command: {extract_command}")
    subprocess.run(extract_command, shell=True, check=True)

def main():
    workspace_folder = Path(os.getenv("workspaceFolder", "."))
    vscode_config_file = workspace_folder / ".vscode/settings.json"

    # Load settings from configuration file
    config = load_config(vscode_config_file)

    # Transfer files to the server
    transfer_files(config)

    # Extract files on the target server
    extract_files(config)

if __name__ == "__main__":
    main()
