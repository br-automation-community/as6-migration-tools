import re
from pathlib import Path


def check_deprecated_string_functions(root_dir, extensions, deprecated_functions):
    """
    Scans all .st files in the project directory for deprecated string functions.

    Returns:
        list: A list of file paths where deprecated string functions were found.
    """
    deprecated_files = []

    for ext in extensions:
        for path in Path(root_dir).rglob(f"*{ext}"):
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    if any(re.search(rf"\b{func}\b", content) for func in deprecated_functions):
                        deprecated_files.append(str(path))
                except Exception:
                    pass

    return deprecated_files


def check_deprecated_math_functions(root_dir, extensions, deprecated_functions):
    """
    Scans files for deprecated math function calls.

    Args:
        root_dir (Path): The root directory to search in.
        extensions (list): List of file extensions to check.
        deprecated_functions (set): Set of deprecated math functions.

    Returns:
        list: A list of file paths where deprecated math functions were found.
    """
    deprecated_files = []
    # Match function names only when followed by '('
    function_pattern = re.compile(r"\b(" + "|".join(deprecated_functions) + r")\s*\(")

    for path in Path(root_dir).rglob("*"):
        if path.suffix in extensions and path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if function_pattern.search(content):  # Only matches function calls
                    deprecated_files.append(str(path))
            except Exception:
                pass

    return deprecated_files
