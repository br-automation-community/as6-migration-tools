import re
from pathlib import Path


def check_vision_settings(directory):
    """
    Checks for the presence of mappVision settings files in the specified directory.

    Args:
        directory (str): Path to the directory to scan.

    Returns:
        dict: Contains information about mappVision settings found:
             - 'found': Boolean indicating if mappVision was found
             - 'version': Version of mappVision if found
             - 'locations': List of mappVision folder paths
             - 'total_files': Total number of files in all mappVision folders
    """
    vision_settings_result = {
        "found": False,
        "version": "",
        "locations": [],
        "total_files": 0,
    }

    # Find the .apj file in the directory
    apj_file = next(Path(directory).glob("*.apj"), None)
    if not apj_file:
        return vision_settings_result

    # If .apj file is found, check for mappVision line in the .apj file
    with Path(apj_file).open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "<mappVision " in line and "Version=" in line:
                match = re.search(r'Version="(\d+)\.(\d+)', line)
                if match:
                    vision_settings_result["found"] = True
                    vision_settings_result["version"] = f"{match.group(1)}.{match.group(2)}"

    # Walk through all directories
    physical_path = Path(directory) / "Physical"
    for path in physical_path.rglob("mappVision"):
        if path.is_dir():
            vision_settings_result["locations"].append(str(path))

            # Count all files in mappVision and its subdirectories
            total_files = sum(1 for _ in path.rglob("*") if _.is_file())
            vision_settings_result["total_files"] += total_files

    return vision_settings_result
