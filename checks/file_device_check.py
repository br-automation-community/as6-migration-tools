import os
import re
from pathlib import Path

from utils import utils


def process_file_devices(file_path):
    """
    Args:
        file_path: Path to the .hw file.

    Returns:
        list: Unique matches found in the file.
    """
    exclude = ["C:\\", "D:\\", "E:\\", "F:\\"]
    results = set()  # Use a set to store unique matches
    content = utils.read_file(Path(file_path))

    # Regex to extract the value from the file device elements
    matches = re.findall(
        r'<Group ID="FileDevice\d+" />\s*<Parameter ID="FileDeviceName\d+" Value="(.*?)" />\s*<Parameter ID="FileDevicePath\d+" Value="(.*?)" />',
        content,
    )
    for name, path in matches:
        for exclusion in exclude:
            if path.lower().startswith(exclusion.lower()):
                results.add((name, path, file_path))
    return list(results)  # Convert back to a list for consistency


def process_ftp_configurations(file_path):
    """
    Args:
        file_path: Path to the .hw file.

    Returns:
        list: Unique matches found in the file.
    """
    results = set()
    content = utils.read_file(Path(file_path))

    # Regex to extract if the FTP server is activated
    matches = re.search(r'<Parameter ID="ActivateFtpServer"\s+Value="(\d)" />', content)
    if not matches or matches.group(0) == "1":
        matches = re.findall(
            r'<Parameter ID="FTPMSPartition\d+"\s+Value="(.*?)" />', content
        )
        if matches:
            for match in matches:
                if "SYSTEM" == match:
                    results.add((match, file_path))
    return list(results)  # Convert back to a list for consistency


def check_file_devices(physical_path, log, verbose=False):
    log("─" * 80 + "\nChecking for invalid file devices and ftp configurations...")

    results = utils.scan_files_parallel(
        physical_path, [".hw"], [process_file_devices, process_ftp_configurations]
    )
    file_devices = results["process_file_devices"]
    ftp_configs = results["process_ftp_configurations"]

    if file_devices:
        log(
            "The following invalid file devices were found: (accessing system partitions / using drive letters)",
            when="AS6",
            severity="MANDATORY",
        )
        grouped_results = {}
        for name, path, file_path in file_devices:
            config_name = os.path.basename(os.path.dirname(file_path))
            grouped_results.setdefault(config_name, set()).add((name, path))

        for config_name, entries in grouped_results.items():
            results = []
            for name, path in sorted(entries):
                results.append(f"{name} ({path})")
            result_string = ", ".join(results)
            log(f" - Hardware configuration '{config_name}': {result_string}")

        log(
            "Write operations on a system partition (C:, D:, E:) are not allowed on real targets."
            "\n - In the event of error a write operation could destroy the system partition so that the target system can no longer be booted."
            "\n - The User partition USER_PATH should be used instead! (AR/Features_and_changes)"
            "\n - In ARsim, the directory corresponding to USER_PATH is found at \\<Project>\\Temp\\Simulation\\<Configuration>\\<CPU>\\USER\\.",
            when="AS6",
            severity="MANDATORY",
        )
    else:
        if verbose:
            log("No invalid file device usages were found", severity="INFO")

    if ftp_configs:
        log(
            "The following potentially invalid ftp configurations were found: (accessing system instead of user partition)",
            when="AS6",
            severity="WARNING",
        )
        grouped_results = {}
        for name, file_path in ftp_configs:
            config_name = os.path.basename(os.path.dirname(file_path))
            grouped_results.setdefault(config_name, set()).add(name)

        for config_name, entries in grouped_results.items():
            log(f"Hardware configuration: {config_name}")
            for name in sorted(entries):
                log(f"- Accessing '{name}'")
    else:
        if verbose:
            log("No potentially invalid ftp configurations found", severity="INFO")
