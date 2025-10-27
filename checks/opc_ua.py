from lxml import etree
from pathlib import Path


def check_uad_files(root_dir: Path, log, verbose=False) -> None:
    """
    Checks if .uad files are located in any directory ending with Connectivity/OpcUA
    and if they have at least file version 9.
    Also checks hardware files for activation of deprecated OPC UA model 1.
    """

    log("─" * 80 + "\nChecking OPC configuration...")

    # Find misplaced and old opc ua files
    required_suffix = ("Connectivity", "OpcUA")
    misplaced_files = []
    old_version = []

    for path in root_dir.rglob("*.uad"):
        if path.parent.parts[-2:] != required_suffix:
            misplaced_files.append(str(path))

        try:
            tree = etree.parse(path)
            root_element = tree.getroot()
            file_version = int(root_element.attrib.get("FileVersion", 0))
            if file_version < 9:
                old_version.append(str(path))
        except Exception:
            pass

    # report misplaced files
    if misplaced_files:
        log(
            "The following .uad files are not located in the required Connectivity/OpcUA directory:",
            when="AS4",
            severity="MANDATORY",
        )
        for file_path in misplaced_files:
            log(f"- {file_path}", severity="MANDATORY")
        log(
            "\nPlease create (via AS 4.12) and move these files to the required directory: Connectivity/OpcUA.",
            severity="MANDATORY",
        )
    else:
        if verbose:
            log("- All .uad files are in the correct location.", severity="INFO")

    # report old opc ua file version
    if old_version:
        output = (
            "The following .uad files do not have the minimum file version 9.\n"
            + "Please edit these, make a small change and save them to trigger the update.\n"
        )
        for file_path in old_version:
            output += f"\n- {file_path}"
        log(output, when="AS4", severity="MANDATORY")
    else:
        if verbose:
            log("- All .uad files have the correct minimum version.", severity="INFO")

    # Check for OPC UA activation in hardware files
    # Search in subdirectories for .hw files
    output = ""
    for subdir in root_dir.iterdir():
        if not subdir.is_dir():
            continue

        for hw_file in subdir.rglob("*.hw"):
            if not hw_file.is_file():
                continue

            try:
                tree = etree.parse(hw_file)
                root_element = tree.getroot()
                # Search for Parameter with ID="ActivateOpcUa" and Value="1" anywhere in the XML tree
                matches = root_element.xpath(
                    ".//*[local-name()='Parameter'][@ID='ActivateOpcUa'][@Value='1']"
                )

                if matches:
                    if len(output) == 0:
                        output += (
                            "OPC UA model 1 is not supported in AS6 and will be automatically converted to model 2. "
                            "This changes the namespace ID for variables."
                            "\nThe following hardware files have OPC UA model 1 activated:\n"
                        )
                    output += f"\n- {hw_file}"

            except Exception:
                # Skip files that can't be parsed as XML
                continue

    if output:
        log(output, severity="INFO")
