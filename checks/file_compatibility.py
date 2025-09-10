import re
from pathlib import Path

from utils import utils


def check_files_for_compatibility(directory, extensions, log, verbose=False):
    """
    Checks the compatibility of .apj and .hw files within a directory.
    Validates that files have a minimum required version.
    """
    log("─" * 80 + "\nChecking project and hardware files for compatibility...")

    incompatible_files = []
    required_version_prefix = "4.12"
    version_pattern = re.compile(r'AutomationStudio (?:Working)?Version="?([\d.]+)')

    for ext in extensions:
        for path in Path(directory).rglob(f"*{ext}"):
            if path.is_file():
                content = utils.read_file(path)
                version_match = version_pattern.search(content)
                if version_match:
                    version = version_match.group(1)
                    if not version.startswith(required_version_prefix):
                        incompatible_files.append((str(path), f"Version {version}"))
                else:
                    incompatible_files.append((str(path), "Version Unknown"))

    if incompatible_files:
        log(
            "The following files are incompatible with the required version:",
            severity="MANDATORY",
        )
        for file_path, issue in incompatible_files:
            log(f"- {file_path}: {issue}")
        log(
            "Please ensure these files are saved at least once with Automation Studio 4.12",
            severity="MANDATORY",
        )
    else:
        if verbose:
            log("All project and hardware files are valid.", severity="VERBOSE")
