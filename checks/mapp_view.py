import re
from pathlib import Path


def check_mappView(directory):
    """
    Checks for the presence of mappView settings files in the specified directory.

    Args:
        directory (str): Path to the directory to scan.

    Returns:
        dict: Contains information about mappView settings found:
             - 'found': Boolean indicating if mappVision was found
             - 'version': Version of mappView if found
    """
    mappView_settings_result = {"found": False, "version": "", "locations": []}
    directory = Path(directory)

    # Find the .apj file in the directory
    apj_file = next(directory.glob("*.apj"), None)
    if not apj_file:
        return mappView_settings_result

    # If .apj file is found, check for mappView line in the .apj file
    for line in apj_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "<mappView " in line and "Version=" in line:
            match = re.search(r'Version="(\d+)\.(\d+)', line)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                mappView_settings_result["found"] = True
                mappView_settings_result["version"] = f"{major}.{minor}"

    # Walk through all directories
    physical = directory / "Physical"
    for path in physical.rglob("mappView"):
        if path.is_dir():
            mappView_settings_result["locations"].append(str(path))

    return mappView_settings_result
