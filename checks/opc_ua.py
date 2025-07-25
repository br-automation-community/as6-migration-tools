import os
import xml.etree.ElementTree as ET
from pathlib import Path


def check_uad_files(root_dir: Path):
    """
    Checks if .uad files are located in any directory ending with Connectivity/OpcUA.
    Returns a list of misplaced .uad files.

    Args:
        root_dir: Root directory of the project.

    Returns:
        list: List of misplaced .uad file paths.
    """
    required_suffix = os.path.normpath(os.path.join("Connectivity", "OpcUA"))
    misplaced_files = []
    old_version = []

    for path in root_dir.rglob("*.uad"):
        relative_parent = path.parent.relative_to(root_dir)
        if not str(relative_parent).endswith(str(required_suffix)):
            misplaced_files.append(str(path))

        try:
            tree = ET.parse(path)
            root_element = tree.getroot()
            file_version = int(root_element.attrib.get("FileVersion", 0))
            if file_version < 9:
                old_version.append(str(path))
        except Exception:
            pass

    return misplaced_files, old_version
