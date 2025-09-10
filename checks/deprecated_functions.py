import re
from pathlib import Path
from utils import utils


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
                content = utils.read_file(path)
                if any(
                    re.search(rf"\b{func}\b", content) for func in deprecated_functions
                ):
                    deprecated_files.append(str(path))

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
            content = utils.read_file(path)
            if function_pattern.search(content):  # Only matches function calls
                deprecated_files.append(str(path))

    return deprecated_files


def check_deprecated_functions(
    logical_path,
    log,
    verbose=False,
    deprecated_string_functions=None,
    deprecated_math_functions=None,
):
    # Store the list of files containing deprecated string functions
    deprecated_string_files = check_deprecated_string_functions(
        logical_path,
        [".st"],
        deprecated_string_functions,
    )

    # Ensure we have a valid list, even if no deprecated functions are found
    if not isinstance(deprecated_string_files, list):
        deprecated_string_files = []  # Fallback to an empty list

    # Boolean flag to indicate whether deprecated string functions were found
    found_deprecated_string = bool(deprecated_string_files)

    # Store the list of files containing deprecated math functions
    deprecated_math_files = check_deprecated_math_functions(
        logical_path,
        [".st"],
        deprecated_math_functions,
    )

    # Ensure we have a valid list, even if no deprecated functions are found
    if not isinstance(deprecated_math_files, list):
        deprecated_math_files = []  # Fallback to an empty list

    # Boolean flag to indicate whether deprecated math functions were found
    found_deprecated_math = bool(deprecated_math_files)

    if found_deprecated_string:
        log(
            "- Deprecated AsString functions detected in the project: "
            "Consider using the helper asstring_to_asbrstr.py to replace them.",
            when="AS6",
            severity="WARNING",
        )

        # Verbose: Print where the deprecated string functions were found only if --verbose is enabled
        if verbose and deprecated_string_files:
            log(
                "Deprecated AsString functions detected in the following files:",
                severity="INFO",
            )
            for f in deprecated_string_files:
                log(f"- {f}")

    if found_deprecated_math:
        log(
            "- Deprecated AsMath functions detected in the project: "
            "Consider using the helper asmath_to_asbrmath.py to replace them.",
            when="AS6",
            severity="WARNING",
        )

        # Verbose: Print where the deprecated math functions were found only if --verbose is enabled
        if verbose and deprecated_math_files:
            log(
                "Deprecated AsMath functions detected in the following files:",
                severity="INFO",
            )
            for f in deprecated_math_files:
                log(f"- {f}")


def check_obsolete_functions(
    log,
    verbose=False,
    invalid_var_typ_files=None,
    invalid_st_c_files=None,
):
    if invalid_var_typ_files:
        log(
            "The following invalid function blocks were found in .var and .typ files:",
            severity="WARNING",
        )
        for block, reason, file_path in invalid_var_typ_files:
            log(f"- {block}: {reason} (Found in: {file_path})")

    if invalid_st_c_files:
        log(
            "The following invalid functions were found in .st, .c and .cpp files:",
            severity="WARNING",
        )
        for function, reason, file_path in invalid_st_c_files:
            log(f"- {function}: {reason} (Found in: {file_path})")

    if verbose:
        if not any([invalid_var_typ_files, invalid_st_c_files]):
            log(
                "No invalid function blocks or functions found in the project.",
                severity="INFO",
            )


def process_var_file(file_path, patterns):
    """
    Processes a .var file to find matches for obsolete function blocks.

    Args:
        file_path (str): Path to the .var file.
        patterns (dict): Patterns to match with reasons.

    Returns:
        list: Matches found in the file.
    """
    results = []
    content = utils.read_file(Path(file_path))

    # Regex for function block declarations, e.g., : MpAlarmXConfigMapping;
    matches = re.findall(r":\s*([A-Za-z0-9_]+)\s*;", content)
    for match in matches:
        for pattern, reason in patterns.items():
            if match.lower() == pattern.lower():
                results.append((pattern, reason, file_path))
    return results


def process_st_c_file(file_path, patterns):
    """
    Processes a .st, .c, or .cpp file to find matches for the given patterns.

    Args:
        file_path (str): Path to the file.
        patterns (dict): Patterns to match with reasons.

    Returns:
        list: Matches found in the file.
    """
    results = []
    matched_files = set()  # To store file paths and ensure uniqueness
    content = utils.read_file(Path(file_path))

    # Check for other patterns if necessary
    for pattern, reason in patterns.items():
        if (
            re.search(rf"\b{re.escape(pattern)}\b", content)
            and file_path not in matched_files
        ):
            results.append((pattern, reason, file_path))
            matched_files.add(file_path)  # Ensure file is added only once
    return results


def check_functions(logical_path, log, verbose=False):
    log("─" * 80 + "\nChecking for obsolete and deprecated FUBs and functions...")

    obsolete_function_blocks = utils.load_discontinuation_info("obsolete_fbks")
    invalid_var_typ_files = utils.scan_files_parallel(
        logical_path,
        [".var", ".typ"],
        process_var_file,
        obsolete_function_blocks,
    )

    obsolete_functions = utils.load_discontinuation_info("obsolete_funcs")
    invalid_st_c_files = utils.scan_files_parallel(
        logical_path,
        [".st", ".c", ".cpp"],
        process_st_c_file,
        obsolete_functions,
    )

    check_obsolete_functions(log, verbose, invalid_var_typ_files, invalid_st_c_files)

    deprecated_string_functions = utils.load_discontinuation_info(
        "deprecated_string_functions"
    )
    deprecated_math_functions = utils.load_discontinuation_info(
        "deprecated_math_functions"
    )
    check_deprecated_functions(
        logical_path,
        log,
        verbose,
        deprecated_string_functions,
        deprecated_math_functions,
    )
