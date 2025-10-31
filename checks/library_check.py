import re
from pathlib import Path

from utils import utils


def process_pkg_file(file_path: Path, args: dict) -> list:
    """
    Processes a .pkg file to find matches for obsolete libraries.
    """
    patterns = args["obsolete_dict"]
    results = []
    content = utils.read_file(file_path)

    # Regex for library names between > and <
    matches = re.findall(r">([^<]+)<", content, re.IGNORECASE)
    for match in matches:
        for pattern, reason in patterns.items():
            if match.lower() == pattern.lower():
                # if we find a match, check if we can find a matching *.lby file in the subdir
                pkg_path = file_path.parent / pattern
                is_lib = any(pkg_path.rglob("*.lby"))
                if is_lib:
                    results.append((pattern, reason, file_path))
    return results


def process_lby_file(file_path: Path, args: dict) -> list:
    """
    Processes a .lby file to find obsolete dependencies.
    """
    patterns = args["obsolete_dict"]
    results = []
    content = utils.read_file(file_path)

    # Extract library name (directory name as identifier)
    library_name = file_path.parent.parts[-1]
    # Extract dependencies from the XML content
    dependencies = re.findall(
        r'<Dependency ObjectName="([^"]+)"', content, re.IGNORECASE
    )
    for dependency in dependencies:
        for pattern, reason in patterns.items():
            # Compare case-insensitively
            if dependency.lower() == pattern.lower():
                results.append((library_name, dependency, reason, file_path))
    return results


def process_binary_lby_file(file_path: Path, args: dict) -> list:
    """
    Processes a .lby file to find custom binaries binary libraries
    """
    patterns = args["whitelist_set"]
    results = []
    content = utils.read_file(file_path)

    # Only consider binary libraries
    if not re.search(r'SubType\s*=\s*"Binary"', content, re.IGNORECASE):
        return results

    # Library name = folder name
    library_name = file_path.parent.parts[-1]

    # Case-insensitive presence check against whitelist
    if library_name.lower() not in patterns:
        results.append((library_name, file_path))

    return results


def process_c_cpp_hpp_includes_file(file_path: Path, patterns: dict) -> list:
    """
    Processes a C, C++, or header (.hpp) file to find obsolete dependencies in #include statements.
    """
    results = []
    include_pattern = re.compile(r'#include\s+[<"]([^">]+)[">]')
    content = utils.read_file(file_path)

    for line in content:
        match = include_pattern.search(line)
        if match:
            included_library = match.group(1).lower()  # Normalize case
            for pattern, reason in patterns.items():
                if included_library == f"{pattern.lower()}.h":
                    results.append((pattern, reason, file_path))
    return results


# Function to process libraries requiring manual process
def process_manual_libraries(file_path: Path, args: dict) -> list:
    """
    Processes .pkg or .lby files to find libraries that require manual action during migration.
    """
    patterns = args["manual_process_libraries"]
    results = []
    content = utils.read_file(file_path)

    matches = re.findall(r">([^<]+)<", content, re.IGNORECASE)
    for match in matches:
        for library, action in patterns.items():
            if match.lower() == library.lower():
                results.append((library, action, file_path))
    return results


def check_libraries(logical_path, log, verbose=False):
    log("─" * 80 + "\nChecking for invalid libraries and dependencies...")

    manual_process_libraries = utils.load_discontinuation_info("manual_process_libs")
    obsolete_dict = utils.load_discontinuation_info("obsolete_libs")
    whitelist_raw = utils.load_discontinuation_info("binary_lib_whitelist") or []
    whitelist_set = {str(x).lower() for x in whitelist_raw}

    args = {
        "manual_process_libraries": manual_process_libraries,
        "obsolete_dict": obsolete_dict,
        "whitelist_set": whitelist_set,
    }

    result = utils.scan_files_parallel(
        logical_path,
        [".pkg"],
        [process_manual_libraries, process_pkg_file],
        args,
    )
    manual_libs_results = result["process_manual_libraries"]
    invalid_pkg_files = result["process_pkg_file"]

    result = utils.scan_files_parallel(
        logical_path,
        [".lby"],
        [process_lby_file, process_binary_lby_file],
        args,
    )
    lby_dependency_results = result["process_lby_file"]
    non_whitelisted_binaries = result["process_binary_lby_file"]

    c_include_dependency_results = utils.scan_files_parallel(
        logical_path,
        [".c", ".cpp", ".hpp"],
        process_c_cpp_hpp_includes_file,
        obsolete_dict,
    )

    if non_whitelisted_binaries:
        # De-duplicate by library name to avoid noisy output
        seen = set()
        deduped = []
        for lib_name, file_path in non_whitelisted_binaries:
            key = lib_name.lower()
            if key not in seen:
                seen.add(key)
                deduped.append((lib_name, file_path))

        output = (
            "Potential custom/third-party binaries; make sure you have the source code "
            "or an AS6 replacement/version:"
        )
        for library_name, file_path in deduped:
            output += f"\n- {library_name} (Found in: {file_path})"
        log(output, when="AS6", severity="WARNING")
    else:
        if verbose:
            log("No non-whitelisted binary libraries detected.", severity="INFO")

    if invalid_pkg_files:
        output = "The following invalid libraries were found in .pkg files:"
        for library, reason, file_path in invalid_pkg_files:
            output += f"\n- {library}: {reason} (Found in: {file_path})"
        log(output, when="AS6", severity="MANDATORY")
    else:
        if verbose:
            log("No invalid libraries found in .pkg files.", severity="INFO")

    if manual_libs_results:
        output = "The following libraries might require manual action after migrating the project to Automation Studio 6:"
        for library, reason, file_path in manual_libs_results:
            output += f"\n- {library}: {reason} (Found in: {file_path})"
        log(output, when="AS6", severity="WARNING")
    else:
        if verbose:
            log(
                "No libraries requiring manual action found in .pkg files.",
                severity="INFO",
            )

    # Convert .lby results to match the (library_name, reason, file_path) format
    normalized_lby_results = [
        (lib, f"Dependency on {dep}: {reason}", path)
        for lib, dep, reason, path in lby_dependency_results
    ]

    # Merge results from .lby and C/C++/HPP include dependencies
    all_dependency_results = normalized_lby_results + c_include_dependency_results

    if all_dependency_results:
        output = "The following obsolete dependencies were found in .lby, .c, .cpp, and .hpp files:"
        for library_name, reason, file_path in all_dependency_results:
            output += f"\n- {library_name}: {reason} (Found in: {file_path})"
        log(output, when="AS6", severity="MANDATORY")
    else:
        if verbose:
            log(
                "No obsolete dependencies found in .lby, .c, .cpp, or .hpp files.",
                severity="INFO",
            )
