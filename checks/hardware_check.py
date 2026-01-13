import re
from pathlib import Path

from utils import utils


def process_hw_file(file_path: Path, hardware_dict: dict) -> list:
    """
    Processes a .hw file to find unsupported hardware matches.
    """
    results = set()  # Use a set to store unique matches
    content = utils.read_file(file_path)

    # Regex to extract the Type value from the <Module> elements
    matches = re.findall(r'<Module [^>]*Type="([^"]+)"', content)
    for hw_type in matches:
        for reason, items in hardware_dict.items():
            if hw_type in items:
                results.add(
                    (hw_type, reason, file_path)
                )  # Add as a tuple to ensure uniqueness
    return list(results)  # Convert back to a list for consistency


def check_hardware(physical_path: Path, log, verbose=False) -> None:
    log(utils.section_header("hardware", "Checking for invalid hardware..."))

    unsupported_hardware = utils.load_discontinuation_info("unsupported_hw")
    hardware_results = utils.scan_files_parallel(
        physical_path,
        [".hw"],
        process_hw_file,
        unsupported_hardware,
    )

    if hardware_results:
        grouped_results = {}
        for hardware_id, reason, file_path in hardware_results:
            config_name = file_path.parent.parts[-1]
            grouped_results.setdefault(config_name, set()).add((hardware_id, reason))

        output = "The following unsupported hardware were found:"
        for config_name, entries in grouped_results.items():
            hw_list = ", ".join(f"{hw}" for hw, reason in sorted(entries))
            output += f"\n\nHardware configuration '{config_name}':\n{hw_list}"
        log(output, when="AS4", severity="WARNING")

        if verbose:
            hw_reason_map = {}
            for hw, reason, _ in hardware_results:
                if hw not in hw_reason_map:
                    hw_reason_map[hw] = reason
            reason_list = "\n".join(
                f"- {hw}: {reason}" for hw, reason in hw_reason_map.items()
            )
            log(
                f"Summary of unsupported hardware and reasons:\n{reason_list}",
                severity="INFO",
            )
    else:
        if verbose:
            log("No unsupported hardware found in the project.", severity="INFO")


def count_hardware(folder: Path) -> dict:
    result = {}
    for file_path in folder.rglob("*.hw"):
        content = utils.read_file(file_path)
        matches = re.findall(r'<Module [^>]*Type="([^"]+)"', content)
        for match in matches:
            module = match
            result.setdefault(module, {"cnt": 0})
            result[module]["cnt"] += 1
    return result
