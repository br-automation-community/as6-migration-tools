import re
from pathlib import Path

from lxml import etree

from utils import utils

version_pattern = re.compile(r'AutomationStudio (?:Working)?Version="?([\d.]+)')


def check_all_file_versions(project_path: Path, log, verbose: bool) -> None:
    physical_path = project_path / "Physical"

    results = utils.scan_files_parallel(project_path, [".apj"], check_file_version)
    results += utils.scan_files_parallel(physical_path, [".hw"], check_file_version)
    if results:
        output = "The following files are incompatible with the required version:"
        for file_path, version in results:
            output += f"\n- {file_path}: {version}"
        log(output, severity="MANDATORY")
        log(
            "Please ensure these files are saved at least once with Automation Studio 4.12",
            severity="MANDATORY",
        )
    else:
        if verbose:
            log("All project and hardware files are valid.", severity="VERBOSE")


def check_file_version(file_path: Path) -> list:
    """
    Checks the version of a given file
    """
    accepted_prefixes = ("4.12", "6.")

    result = set()
    content = utils.read_file(file_path)
    version_match = version_pattern.search(content)
    if version_match:
        version = version_match.group(1).strip()
        if not version.startswith(accepted_prefixes):
            result.add((file_path, version))
    else:
        result.add((file_path, "Version Unknown"))
    return list(result)


def check_for_referenced_files(project_path: Path, log, verbose=False) -> None:
    reference_files = utils.scan_files_parallel(
        project_path / "Physical", [".pkg"], has_file_reference
    )

    if reference_files:
        output = (
            "Some files are converted to a new format in AS6. This may break references, "
            "The following .pkg files contain file reference, make sure that the references are valid after converting to AS6:"
        )
        for ref_file in reference_files:
            output += f"\n- {ref_file}"
        log(output, severity="WARNING")


def has_file_reference(file_path: Path) -> list:
    """
    Checks if a .pkg file contains referenced files.
    """
    results = []
    if not file_path.is_file() or "mappView" in file_path.parts:
        return results

    try:
        tree = etree.parse(str(file_path))
        root = tree.getroot()
        # Search with XPath for all elements with Type="File" and Reference="true"
        matches = root.xpath('.//*[@Type="File" and @Reference="true"]')
        if matches:
            results.append(file_path)
    except Exception as e:
        # Fallback: ignore file if not valid XML
        pass
    return results


def check_files_for_compatibility(project_path: Path, log, verbose=False) -> None:
    """
    Checks the compatibility of .apj and .hw files within an apj_path.
    Validates that files have a minimum required version.
    Generates warning when files are converted to a new format in AS6 that may break references.
    """
    log(
        utils.section_header(
            "file-compat", "Checking project and hardware files for compatibility..."
        )
    )

    check_all_file_versions(project_path, log, verbose)
    check_for_referenced_files(project_path, log, verbose)
