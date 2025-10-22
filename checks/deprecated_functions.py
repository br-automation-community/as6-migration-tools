import re
from pathlib import Path
from utils import utils


def check_deprecated_string_functions(file: str, deprecated_functions: list):
    """
    Scans the given file for deprecated string functions.
    """

    path = Path(file)
    if path.is_file():
        content = utils.read_file(path)
        if any(re.search(rf"\b{func}\b", content) for func in deprecated_functions):
            return [file]

    return []


def check_deprecated_math_functions(file: str, deprecated_functions: list):
    """
    Scans the given file for deprecated math function calls.
    """

    # Match function names only when followed by '('
    function_pattern = re.compile(r"\b(" + "|".join(deprecated_functions) + r")\s*\(")

    path = Path(file)
    if path.is_file():
        content = utils.read_file(path)
        if function_pattern.search(content):  # Only matches function calls
            return [file]

    return []


def check_deprecated_functions(
    logical_path,
    log,
    verbose=False,
    deprecated_string_functions=None,
    deprecated_math_functions=None,
):
    # Store the list of files containing deprecated string functions
    deprecated_string_files = utils.scan_files_parallel(
        logical_path,
        [".st", ".ab"],
        check_deprecated_string_functions,
        deprecated_string_functions,
    )

    # Store the list of files containing deprecated math functions
    deprecated_math_files = utils.scan_files_parallel(
        logical_path,
        [".st"],
        check_deprecated_math_functions,
        deprecated_math_functions,
    )

    if deprecated_string_files:
        log(
            "- Deprecated AsString functions detected in the project: "
            "Consider using the helper asstring_to_asbrstr.py to replace them.",
            when="AS6",
            severity="WARNING",
        )

        # Verbose: Print where the deprecated string functions were found only if --verbose is enabled
        if verbose:
            output = "Deprecated AsString functions detected in the following files:"
            for f in deprecated_string_files:
                output += f"\n- {f}"
            log(output, severity="INFO")

    if deprecated_math_files:
        log(
            "- Deprecated AsMath functions detected in the project: "
            "Consider using the helper asmath_to_asbrmath.py to replace them.",
            when="AS6",
            severity="WARNING",
        )

        # Verbose: Print where the deprecated math functions were found only if --verbose is enabled
        if verbose and deprecated_math_files:
            output = "Deprecated AsMath functions detected in the following files:"
            for f in deprecated_math_files:
                output += f"\n- {f}"
            log(output, severity="INFO")


def check_obsolete_functions(
    log,
    verbose=False,
    invalid_var_typ_files=None,
    invalid_st_c_files=None,
):
    if invalid_var_typ_files:
        output = (
            "The following invalid function blocks were found in .var and .typ files:"
        )
        for block, reason, file_path in invalid_var_typ_files:
            output += f"\n- {block}: {reason} (Found in: {file_path})"
        log(output, severity="WARNING")

    if invalid_st_c_files:
        output = "The following invalid functions were found in .st, .c and .cpp files:"
        for function, reason, file_path in invalid_st_c_files:
            output += f"\n- {function}: {reason} (Found in: {file_path})"
        log(output, severity="WARNING")

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
    content = utils.read_file(Path(file_path))

    pattern_map = {p.lower(): (p, reason) for p, reason in patterns.items()}
    matches = re.findall(r"\b([A-Za-z0-9_]+)\b", content)
    for match in matches:
        key = match.lower()
        if key in pattern_map:
            results.append((pattern_map[key][0], pattern_map[key][1], file_path))
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
