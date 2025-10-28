import re
from lxml import etree
from pathlib import Path

from utils import utils


def check_safety_release(apj_path: Path, log, verbose=False) -> bool:
    """
    Checks if the project uses MappSafety or SafetyRelease.
    """

    project_root = apj_path.parent

    # 1. Check .apj file in root for MappSafety
    if apj_path:
        try:
            tree = etree.parse(apj_path)
            root = tree.getroot()
            # Check <mappSafety Version="..."/>
            if root.find(".//{*}mappSafety") is not None:
                log(
                    "Migrating from mapp Safety 5.x to mapp Safety 6.x - "
                    "All conversion steps are carried out automatically by the system; no action by the user is necessary.",
                    severity="INFO",
                )
                return True  # Valid project
        except Exception as e:
            log(f"Failed to parse .apj file: {e}", severity="ERROR")

    # 2. Search for *.pkg files in the Physical view containing 'SafetyRelease' with version != 0.0
    search_path = project_root / "Physical"

    for file in search_path.rglob("*.pkg"):
        content = utils.read_file(file)
        if 'SafetyRelease="' in content:
            match = re.search(r'SafetyRelease="(\d+)\.(\d+)"', content)
            if match and (match.group(1) != "0" or match.group(2) != "0"):
                log(
                    "Legacy safety is no longer supported with AS 6.x."
                    "\n - When upgrading from a Safety Release to mapp Safety 6.x, all conversion steps from the Safety Release "
                    "to mapp Safety 5.x must be performed in AS 4.x first."
                    "\n - More info: Safety/Conversion",
                    when="AS4",
                    severity="MANDATORY",
                )
                return True

    # 3. Check for *.swt files in Physical folders
    for swt_path in project_root.rglob("*.swt"):
        log(
            f"Safety .swt file found but no SafetyRelease or MappSafety version found: {swt_path}",
            severity="WARNING",
        )

    return False


def check_safety(apj_path: Path, log, verbose=False) -> None:
    """
    Args:
        apj_path: path of the project file

    Returns:
        Nothing
    """

    log("─" * 80 + "\nChecking for safety...")

    found = check_safety_release(apj_path, log, verbose)

    if not found:
        log("No safety system detected", severity="INFO")
