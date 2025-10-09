import re
from pathlib import Path

from lxml import etree


def check_visual_components(apj_path: Path, log, verbose: bool = False):
    """
    Check for the use of VA_Textout and VA_wsTextout functions.
    """

    log("─" * 80 + "\nChecking Visual components usage...")

    check_vc3(apj_path, log, verbose)

    logical_path = apj_path.parent / "Logical"
    found_vc4_functions = False

    for st_path in logical_path.rglob("*.st"):

        # Try different encodings
        encodings = ["utf-8", "latin1", "cp1252", "iso-8859-1"]
        content = None

        for encoding in encodings:
            try:
                with open(st_path, "r", encoding=encoding) as f:
                    content = f.read()
                break  # If successful, break the loop
            except UnicodeDecodeError:
                continue  # Try next encoding

        if content is None:
            log(
                f"Warning: Could not read file {st_path.relative_to(apj_path.parent)} with any supported encoding",
                severity="WARNING",
            )
            continue

        # Search for VA_Textout and VA_wsTextout using regex
        # Look for function calls with optional whitespace and parameters
        va_textout_matches = re.finditer(r"\bVA_Textout\s*\(", content)
        va_wctextout_matches = re.finditer(r"\bVA_wcTextout\s*\(", content)

        # Process matches for VA_Textout
        for match in va_textout_matches:
            found_vc4_functions = True
            if verbose:
                log(
                    f"Found VA_Textout function call in {st_path.relative_to(apj_path.parent)}",
                    when="AS6",
                    severity="INFO",
                )

        # Process matches for VA_wsTextout
        for match in va_wctextout_matches:
            found_vc4_functions = True
            if verbose:
                log(
                    f"Found VA_wsTextout function call in {st_path.relative_to(apj_path.parent)}",
                    when="AS6",
                    severity="INFO",
                )

    if found_vc4_functions:
        log(
            "VA_Textout and VA_wsTextout functions found"
            "\n - VA_Textout and VA_wsTextout needs increased stack in task class."
            "\n - More info: community/VC4",
            when="AS6",
            severity="WARNING",
        )
    elif verbose:
        log("No VA_Textout or VA_wsTextout functions found.")

    return


def check_vc3(apj_path: Path, log, verbose: bool = False):
    """
    Check for VC3 usage in the project.
    """
    logical_path = apj_path.parent / "Logical"

    # Walk through all Package.pkg files in the Logical directory
    for pkg_file in logical_path.rglob("Package.pkg"):
        try:
            tree = etree.parse(pkg_file)
            root_element = tree.getroot()
            matches = root_element.xpath(
                ".//*[local-name()='Object'][@Type='DataObject'][@Language='Vc3']"
            )

            if matches:
                log(
                    "VC3 components found in project. VC3 is not supported in AS6",
                    when="AS4",
                    severity="MANDATORY",
                )

        except Exception as e:
            log(
                f"Error parsing {pkg_file.relative_to(apj_path.parent)}: {str(e)}",
                severity="WARNING",
            )
            continue
