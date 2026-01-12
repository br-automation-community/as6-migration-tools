import re
from pathlib import Path

from utils import utils


def process_file_devices(file_path: Path) -> list:
    """
    Checks for used file devices that access system partitions.
    """
    exclude = ["C:\\", "D:\\", "E:\\", "F:\\"]
    results = set()  # Use a set to store unique matches
    content = utils.read_file(file_path)

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


def process_ftp_configurations(file_path: Path) -> list:
    """
    Checks for FTP configurations that access the SYSTEM partition.
    """
    results = set()
    content = utils.read_file(file_path)

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


def check_file_devices(physical_path: Path, log, verbose=False) -> None:
    log(
        utils.section_header(
            "file-devices",
            "Checking for invalid file devices and FTP configurations...",
        )
    )

    results = utils.scan_files_parallel(
        physical_path, [".hw"], [process_file_devices, process_ftp_configurations]
    )
    file_devices = results["process_file_devices"]
    ftp_configs = results["process_ftp_configurations"]

    if file_devices:
        grouped_results = {}
        for name, path, file_path in file_devices:
            config_name = file_path.parent.parts[-1]
            grouped_results.setdefault(config_name, set()).add((name, path))

        output = "The following invalid file devices were found: (accessing system partitions / using drive letters)"
        for config_name, entries in grouped_results.items():
            results = []
            for name, path in sorted(entries):
                results.append(f"{name} ({path})")
            result_string = ", ".join(results)
            output += f"\n - Hardware configuration '{config_name}': {result_string}"
        log(output, when="AS6", severity="MANDATORY")

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
        grouped_results = {}
        for name, file_path in ftp_configs:
            config_name = file_path.parent.parts[-1]
            grouped_results.setdefault(config_name, set()).add(name)

        output = "The following potentially invalid ftp configurations were found: (accessing system instead of user partition)"
        for config_name, entries in grouped_results.items():
            output += f"\n\nHardware configuration: {config_name}"
            for name in sorted(entries):
                output += f"\n- Accessing '{name}'"
        log(output, when="AS6", severity="WARNING")
    else:
        if verbose:
            log("No potentially invalid ftp configurations found", severity="INFO")
