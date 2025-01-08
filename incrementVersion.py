import os
import json
from pathlib import Path


def increment_version(package_json_path):
    """Increment the version string in package.json."""
    with open(package_json_path, 'r') as file:
        package_data = json.load(file)

    version_parts = package_data["version"].split('.')
    version_parts[-1] = str(int(version_parts[-1]) + 1)  # Increment patch version
    package_data["version"] = '.'.join(version_parts)

    with open(package_json_path, 'w') as file:
        json.dump(package_data, file, indent=2)

    print(f"Updated version to {package_data['version']} in {package_json_path}")

def main():
    workspace_folder = Path(os.getenv("workspaceFolder", "."))
    package_json_file = workspace_folder / "package.json"


    # Increment version
    increment_version(package_json_file)



if __name__ == "__main__":
    main()
