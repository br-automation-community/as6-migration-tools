import os
import re
from pathlib import Path

from utils import utils


def process_hw_file(file_path, hardware_dict):
    """
    Processes a .hw file to find unsupported hardware matches.

    Args:
        file_path (str): Path to the .hw file.
        hardware_dict (dict): Dictionary of unsupported hardware and their reasons.

    Returns:
        list: Unique matches found in the file.
    """
    results = set()  # Use a set to store unique matches
    content = utils.read_file(Path(file_path))

    # Regex to extract the Type value from the <Module> elements
    matches = re.findall(r'<Module [^>]*Type="([^"]+)"', content)
    for hw_type in matches:
        for reason, items in hardware_dict.items():
            if hw_type in items:
                results.add(
                    (hw_type, reason, file_path)
                )  # Add as a tuple to ensure uniqueness
    return list(results)  # Convert back to a list for consistency


def check_hardware(physical_path, log, verbose=False):
    log("─" * 80 + "\nChecking for invalid hardware...")

    unsupported_hardware = utils.load_discontinuation_info("unsupported_hw")
    hardware_results = utils.scan_files_parallel(
        physical_path,
        [".hw"],
        process_hw_file,
        unsupported_hardware,
    )

    if hardware_results:
        log(
            "The following unsupported hardware were found:",
            when="AS4",
            severity="WARNING",
        )
        grouped_results = {}
        for hardware_id, reason, file_path in hardware_results:
            config_name = os.path.basename(os.path.dirname(file_path))
            grouped_results.setdefault(config_name, set()).add((hardware_id, reason))

        for config_name, entries in grouped_results.items():
            log(f"\nHardware configuration: {config_name}")
            for hardware_id, reason in sorted(entries):
                log(f"- {hardware_id}: {reason}")
    else:
        if verbose:
            log("No unsupported hardware found in the project.", severity="INFO")
