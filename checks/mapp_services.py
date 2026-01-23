import re
from pathlib import Path

from lxml import etree

from utils import utils


def check_mapp_version(apj_path: Path, log, verbose=False) -> None:
    """
    Checks mapp Services / mappMotion versions in the .apj. Respects referenced packages in cpu.pkg.
    """

    log(
        utils.section_header(
            "mapp-services", "Checking mapp configuration in project file..."
        )
    )

    # --- Read .apj as plain text (robust vs. namespaces/BOM) ---
    txt = utils.read_file(apj_path)

    # --- Version detection (mapp Services & mappMotion 5.x) ---
    for line in txt.splitlines():
        if ("<mapp " in line and "Version=" in line) or (
            "<mappServices" in line and "Version=" in line
        ):
            m = re.search(r'Version="(\d+)\.(\d+)', line)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                version_str = f"{major}.{minor}"
                log(f"Detected Mapp Services version: {version_str}", severity="INFO")

                if major < 5 or (major == 5 and minor < 20):
                    log(
                        "It is recommended to use a mapp Services version 5.20 or later for the conversion."
                        "\n - If a mapp Services version older than 5.20 is used, the correct conversion of all configuration parameters is not guaranteed."
                        "\n - Please update the mapp Services version in AS4 to 5.20 or later before migrating to AS6.",
                        when="AS4",
                        severity="MANDATORY",
                    )

                log(
                    "The automatic mapp Services configuration upgrade is only available with mapp Services 6.0."
                    "\n - Please ensure the project is converted using AS6 and mapp Services 6.0 before upgrading to newer mapp versions. (MappServices/Configuration_update)",
                    when="AS6",
                    severity="MANDATORY",
                )

        if "<mappMotion " in line and 'Version="5.' in line:
            m = re.search(r'Version="(\d+)\.(\d+)', line)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                version_str = f"{major}.{minor}"
                log(f"Detected Mapp Motion version: {version_str}", severity="INFO")
                log(
                    "\nYou must first upgrade mappMotion to version 6.0 using 'Change runtime versions' in AS6."
                    "\nOnce mappMotion 6.0 is set, a dialog will assist with converting all project configurations. (MappMotion/Configuration_update)",
                    when="AS6",
                    severity="MANDATORY",
                )

    physical_path = apj_path.parent / "Physical"
    if not physical_path.is_dir():
        log(f"Could not find Physical in {apj_path.parent}", severity="ERROR")
        return

    # Check access rights in mpfile
    # Search in subdirectories for .mpfilemanager files
    for subdir in physical_path.iterdir():
        if not subdir.is_dir():
            continue

        for mpfilemanager in subdir.rglob("*.mpfilemanager"):
            if not mpfilemanager.is_file():
                continue

            try:
                tree = etree.parse(mpfilemanager)
                xpath = ".//*[local-name()='Property'][@ID='Role'][@Value='Everyone']"
                matches = tree.xpath(xpath)

                if matches:
                    log(
                        f"Detected file manager access role 'Everyone' in: {mpfilemanager}. "
                        "This will no longer work unless the user anonymous also has one of the well-known roles. "
                        "See help (MappServices/mapp File/Configuration) under access rights for more details.",
                        severity="MANDATORY",
                    )
            except Exception:
                # Skip files that can't be parsed as XML
                continue

    # Check access rights in mpuserx
    # Search in subdirectories for .mpuserx files
    for mpuserx in physical_path.rglob("*.mpuserx"):
        if not mpuserx.is_file():
            continue

        log(
            f"Detected mappUserX configuration in: {mpuserx}. "
            "After upgrading to AS6 a variety of password policies will be enforced that may require adjustments to your configuration."
            "Check UserMgmtX->Password policy.",
            severity="WARNING",
            when="AS6",
        )
