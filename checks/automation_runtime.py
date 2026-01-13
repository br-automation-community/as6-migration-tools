import re
from pathlib import Path
from typing import Optional

from utils import utils

MIN_LETTER = "B"
MIN_VERSION = 4.25
AR_VERSION_PATTERN = r'<AutomationRuntime Version="([A-Z])(\d+\.\d+)"\s*/>'


def _parse_version(version_str: str) -> Optional[float]:
    """Parse version string to float, return None if invalid."""
    try:
        return float(version_str)
    except ValueError:
        return None


def _is_version_valid(letter: str, version: float) -> bool:
    """Check if AR version meets minimum requirements."""
    return letter >= MIN_LETTER and version >= MIN_VERSION


def check_ar(physical_path: Path, log, verbose: bool = False) -> None:
    log(utils.section_header("ar", "Checking Automation Runtime..."))

    for file in physical_path.rglob("Cpu.pkg"):
        if not file.is_file():
            continue

        config = file.parts[-3]
        content = utils.read_file(file)
        ar_match = re.search(AR_VERSION_PATTERN, content)

        if ar_match:
            letter = ar_match.group(1)
            version = _parse_version(ar_match.group(2))

            if _is_version_valid(letter, version):
                if verbose:
                    log(
                        f"{config}: Automation Runtime version {letter}{version} is valid (must be at least B4.25 before upgrading, see AS4/Migration).",
                        severity="INFO",
                        when="AS4",
                    )
            else:
                log(
                    f"{config}: Automation Runtime version {letter}{version} is too low. "
                    f"Please update to at least {MIN_LETTER}{MIN_VERSION} (see AS4/Migration).",
                    severity="MANDATORY",
                    when="AS4",
                )
        else:
            if verbose:
                log(
                    f"No Automation Runtime version found in {file}.",
                    severity="INFO",
                )
