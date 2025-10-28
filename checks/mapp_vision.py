import re
from pathlib import Path

from utils import utils


def check_vision_settings(apj_path: Path, log, verbose=False) -> None:
    """
    Checks for the presence of mappVision settings files in the specified directory.
    """
    log("─" * 80 + "\nChecking mappVision version in project file...")

    # Check for mappVision line in the .apj file
    for line in utils.read_file(apj_path).splitlines():
        if "<mappVision " in line and "Version=" in line:
            match = re.search(r'Version="(\d+)\.(\d+)', line)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                version = f"{major}.{minor}"

                log(
                    f"Found usage of mapp Vision (Version: {version})",
                    severity="INFO",
                )
                log(
                    f"Several security settings will be enforced after the migration:"
                    "\n"
                    "\n- After migrating to AS6 make sure that IP forwarding is activated under the Powerlink interface! (AR/Features_and_changes)"
                    "\n"
                    "\n- There is no more anonymous access to mappVision applications. Make sure to create users and assign them to the appropriate roles (ex. BR_Engineer) after migrating to AS6.",
                    when="AS6",
                    severity="MANDATORY",
                )

    if verbose:
        # Walk through all directories
        physical_path = apj_path.parent / "Physical"
        for vision_path in physical_path.rglob("mappVision"):
            if vision_path.is_dir():
                log(f"mappVision folders found at: {vision_path}", severity="INFO")
