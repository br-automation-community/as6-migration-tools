import re
from pathlib import Path


def check_files_for_compatibility(directory, extensions):
    """
    Checks the compatibility of .apj and .hw files within a directory.
    Validates that files have a minimum required version.

    Args:
        directory (str): Path to the directory to scan.
        extensions (list): Extensions of files to check, e.g., ['.apj', '.hw'].

    Returns:
        list: Results for incompatible files in the format (file_path, issue).
    """
    incompatible_files = []
    required_version_prefix = "4.12"
    version_pattern = re.compile(r'AutomationStudio Version="?([\d.]+)')

    for ext in extensions:
        for path in Path(directory).rglob(f"*{ext}"):
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                    version_match = version_pattern.search(content)
                    if version_match:
                        version = version_match.group(1)
                        if not version.startswith(required_version_prefix):
                            incompatible_files.append((str(path), f"Version {version}"))
                    else:
                        incompatible_files.append((str(path), "Version Unknown"))
                except Exception as e:
                    incompatible_files.append((str(path), f"Error reading file: {e}"))

    return incompatible_files
