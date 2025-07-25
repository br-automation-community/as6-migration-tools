import os
import sys
import re
import concurrent.futures
import time
import json
import argparse
from pathlib import Path
from checks import *
from utils import utils

# path to the current script
script_directory = Path(__file__).resolve().parent


# filens containing discontinuation information
discontinuation_info = {
    "obsolete_libs": {},
    "manual_process_libs": {},
    "obsolete_fbks": {},
    "obsolete_funcs": {},
    "unsupported_hw": {},
    "deprecated_string_functions": {},
    "deprecated_math_functions": {},
}

try:
    discontinuation_dir = Path(script_directory) / "discontinuations"
    for filename in discontinuation_info:
        file_path = discontinuation_dir / f"{filename}.json"
        with file_path.open("r", encoding="utf-8") as json_file:
            discontinuation_info[filename] = json.load(json_file)
except Exception as e:
    print(
        f"\033[1;31m[ERROR]\033[0m Error reading discontinuation lists: {e}",
        file=sys.stderr,
    )
    sys.exit(1)

# obsolete libraries with reasons
obsolete_dict = discontinuation_info["obsolete_libs"]
# Libraries that must be handled manually
manual_process_libraries = discontinuation_info["manual_process_libs"]
# list of obsolete function blocks with reasons
obsolete_function_blocks = discontinuation_info["obsolete_fbks"]
# Hardcoded list of obsolete functions with reasons
obsolete_functions = discontinuation_info["obsolete_funcs"]
# hardware not supported by >= 6.0
unsupported_hardware = discontinuation_info["unsupported_hw"]
# deprecated string functions 8 bit and 16 bit
deprecated_string_functions = set(discontinuation_info["deprecated_string_functions"])
# deprecated math functions
deprecated_math_functions = set(discontinuation_info["deprecated_math_functions"])

pass


def display_progress(message):
    """
    Displays a progress message on the same line in the terminal.
    In GUI mode, stdout may be None, so we fall back to printing.
    """
    try:
        sys.stdout.write("\r" + " " * 80)
        sys.stdout.write("\r" + message)
        sys.stdout.flush()
    except Exception:
        # Fallback: simple print if stdout is unavailable
        print(message)


def process_stub(file_path, *args):
    """
    Stub process function for demonstration purposes.
    Simulates processing of files without actual logic.

    Args:
        file_path (str): The file path to process.
        *args: Additional arguments.

    Returns:
        list: An empty list for this stub function.
    """
    return []


def scan_files_parallel(root_dir, extensions, process_function, *args):
    """
    Scans files in a directory tree in parallel for specific content.

    Args:
        root_dir (Path): The root directory to search in.
        extensions (list): File extensions to include.
        process_function (callable): The function to apply on each file.
        *args: Additional arguments to pass to the process_function.

    Returns:
        list: Aggregated results from all scanned files.
    """
    results = []

    file_paths = [
        str(path)
        for ext in extensions
        for path in root_dir.rglob(f"*{ext}")
        if path.is_file()
    ]

    total_files = len(file_paths)
    display_progress(f"Found {total_files} files to process...")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_function, str(path), *args): path
            for path in file_paths
        }
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            display_progress(f"Processing file {i}/{total_files}...")
            results.extend(future.result())

    display_progress("Processing complete.".ljust(50))  # Clear line
    return results


def process_pkg_file(file_path, patterns):
    """
    Processes a .pkg file to find matches for obsolete libraries.

    Args:
        file_path (str): Path to the .pkg file.
        patterns (dict): Patterns to match with reasons.

    Returns:
        list: Matches found in the file.
    """
    results = []
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    # Regex for library names between > and <
    matches = re.findall(r">([^<]+)<", content, re.IGNORECASE)
    for match in matches:
        for pattern, reason in patterns.items():
            if match.lower() == pattern.lower():
                results.append((pattern, reason, file_path))
    return results


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
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

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
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    # Check for other patterns if necessary
    for pattern, reason in patterns.items():
        if (
            re.search(rf"\b{re.escape(pattern)}\b", content)
            and file_path not in matched_files
        ):
            results.append((pattern, reason, file_path))
            matched_files.add(file_path)  # Ensure file is added only once
    return results


def process_hw_file(file_path, hardware_dict):
    """
    Processes a .hw file to find unsupported hardware matches.

    Args:
        file_path (str): Path to the .hw file.
        hardware_dict (dict): Dictionary of unsupported hardware and their reasons.

    Returns:
        list: Unique matches found in the file.
    """
    results = set()  # Use a set to store unique matches
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    # Regex to extract the Type value from the <Module> elements
    matches = re.findall(r'<Module [^>]*Type="([^"]+)"', content)
    for hw_type in matches:
        for reason, items in hardware_dict.items():
            if hw_type in items:
                results.add(
                    (hw_type, reason, file_path)
                )  # Add as a tuple to ensure uniqueness
    return list(results)  # Convert back to a list for consistency


def process_file_devices(file_path):
    """
    Args:
        file_path: Path to the .hw file.

    Returns:
        list: Unique matches found in the file.
    """
    exclude = ["C:\\", "D:\\", "E:\\", "F:\\"]
    results = set()  # Use a set to store unique matches
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    # Regex to extract the value from the file device elements
    matches = re.findall(
        r'<Group ID="FileDevice\d+" />\s*<Parameter ID="FileDeviceName\d+" Value="(.*?)" />\s*<Parameter ID="FileDevicePath\d+" Value="(.*?)" />',
        content,
    )
    for name, path in matches:
        for exclusion in exclude:
            if path.lower().startswith(exclusion.lower()):
                results.add((name, path, file_path))
    return list(results)  # Convert back to a list for consistency


def process_ftp_configurations(file_path):
    """
    Args:
        file_path: Path to the .hw file.

    Returns:
        list: Unique matches found in the file.
    """
    results = set()
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    # Regex to extract if the FTP server is activated
    matches = re.search(r'<Parameter ID="ActivateFtpServer"\s+Value="(\d)" />', content)
    if not matches or matches.group(0) == "1":
        matches = re.findall(
            r'<Parameter ID="FTPMSPartition\d+"\s+Value="(.*?)" />', content
        )
        if matches:
            for match in matches:
                if "SYSTEM" == match:
                    results.add((match, file_path))
    return list(results)  # Convert back to a list for consistency


def process_lby_file(file_path, patterns):
    """
    Processes a .lby file to find obsolete dependencies.

    Args:
        file_path (str): Path to the .lby file.
        patterns (dict): Patterns of obsolete dependencies with reasons.

    Returns:
        list: Matches found in the file in the format (library_name, dependency, reason, file_path).
    """
    results = []
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    # Extract library name (directory name as identifier)
    library_name = os.path.basename(os.path.dirname(file_path))
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


def process_c_cpp_hpp_includes_file(file_path, patterns):
    """
    Processes a C, C++, or header (.hpp) file to find obsolete dependencies in #include statements.

    Args:
        file_path (str): Path to the file.
        patterns (dict): Dictionary of obsolete libraries with reasons.

    Returns:
        list: Matches found in the file in the format (library_name, reason, file_path).
    """
    results = []
    include_pattern = re.compile(r'#include\s+[<"]([^">]+)[">]')
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    for line in content:
        match = include_pattern.search(line)
        if match:
            included_library = match.group(1).lower()  # Normalize case
            for pattern, reason in patterns.items():
                if included_library == f"{pattern.lower()}.h":
                    results.append((pattern, reason, file_path))
    return results


# Function to process libraries requiring manual process
def process_manual_libraries(file_path, patterns):
    """
    Processes .pkg or .lby files to find libraries that require manual action during migration.

    Args:
        file_path (str): Path to the file.
        patterns (dict): Libraries to be checked for manual process.

    Returns:
        list: Matches found in the file.
    """
    results = []
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    matches = re.findall(r">([^<]+)<", content, re.IGNORECASE)
    for match in matches:
        for library, action in patterns.items():
            if match.lower() == library.lower():
                results.append((library, action, file_path))
    return results


def parse_args():
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="Scans Automation Studio project for transition from AS4 to AS6",
        usage="python %(prog)s project_path [options]",
        epilog="Ensure the path is correct and the project folder exists.\n"
        "A valid AS 4 project folder must contain an *.apj file.\n"
        'If the path contains spaces, make sure to wrap it in quotes (e.g. like this: "C:\\My documents\\project")\n'
        "If you enter a  '.' as project_path the current directory will be used.\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Add arguments
    parser.add_argument(
        "project_path",
        type=str,
        help="Automation Studio 4.x path containing *.apj file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        help="Outputs verbose information",
    )
    # Parse the arguments

    # Fallback if no arguments are provided (e.g. when run from GUI)
    if len(sys.argv) == 1:
        # Default to current directory as project path
        sys.argv += [".", "-v"]
        # Optionally enable verbose mode by default from GUI
        # sys.argv += ["-v"]

    return parser.parse_args()


# Check the project name and path for invalid characters
# As opposed to what's in the help, we need to allow : and \ and / as well since these are valid
# path separators
def check_project_path_and_name(path, name):
    project_name_pattern = r"^(\w+)\.apj$"
    project_path_pattern = r"^[\w :\\/!(){}+\-@\.\^=]+$"
    return re.fullmatch(project_path_pattern, path) and re.fullmatch(
        project_name_pattern, name
    )


# Update main function to handle project directory input and optional verbose flag
def main():
    """
    Main function to scan for obsolete libraries, function blocks, functions, and unsupported hardware.
    Outputs the results to a file as well as the console.
    """

    build_number = utils.get_build_number()
    print(f"Script build number: {build_number}")

    args = parse_args()
    apj_file = utils.get_and_check_project_file(args.project_path)

    utils.set_verbose(args.verbose)

    print(f"Project path validated: {args.project_path}")
    print(f"Using project file: {apj_file}")

    output_file = os.path.join(args.project_path, "as4_to_as6_analyzer_result.txt")
    with open(output_file, "w", encoding="utf-8") as file:
        try:

            def log(message, log_file=file):
                utils.log(message, log_file)

            def log_v(message, log_file=file, prepend=""):
                utils.log_v(message, log_file, prepend)

            log(
                "Scanning started... Please wait while the script analyzes your project files.\n",
                file,
            )

            start_time = time.time()

            if not check_project_path_and_name(args.project_path, apj_file):
                log(
                    "Invalid path or project name, see "
                    "https://help.br-automation.com/#/en/6/revinfos/version-info/projekt_aus_automation_studio_4_ubernehmen/automation_studio/notwendige_anpassungen_im_automation_studio_4_projekt.html"
                )

            logical_path = Path(args.project_path) / "Logical"
            physical_path = Path(args.project_path) / "Physical"

            # Use project_path as the root directory for scanning
            manual_libs_results = scan_files_parallel(
                logical_path,
                [".pkg"],
                process_manual_libraries,
                manual_process_libraries,
            )

            invalid_pkg_files = scan_files_parallel(
                logical_path,
                [".pkg"],
                process_pkg_file,
                obsolete_dict,
            )

            invalid_var_typ_files = scan_files_parallel(
                logical_path,
                [".var", ".typ"],
                process_var_file,
                obsolete_function_blocks,
            )

            invalid_st_c_files = scan_files_parallel(
                logical_path,
                [".st", ".c", ".cpp"],
                process_st_c_file,
                obsolete_functions,
            )

            hardware_results = scan_files_parallel(
                physical_path,
                [".hw"],
                process_hw_file,
                unsupported_hardware,
            )

            file_devices = scan_files_parallel(
                physical_path,
                [".hw"],
                process_file_devices,
            )

            ftp_configs = scan_files_parallel(
                physical_path,
                [".hw"],
                process_ftp_configurations,
            )

            lby_dependency_results = scan_files_parallel(
                logical_path,
                [".lby"],
                process_lby_file,
                obsolete_dict,
            )

            c_include_dependency_results = scan_files_parallel(
                logical_path,
                [".c", ".cpp", ".hpp"],
                process_c_cpp_hpp_includes_file,
                obsolete_dict,
            )

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

            log("\n\nChecking project and hardware files for compatibility...")
            file_patterns = [".apj", ".hw"]
            compatibility_results = check_files_for_compatibility(
                args.project_path, file_patterns
            )
            if compatibility_results:
                for file_path, issue in compatibility_results:
                    log(f"- {file_path}: {issue}")
                log(
                    "\nPlease ensure these files are saved at least once with Automation Studio 4.12."
                )
            else:
                log_v("- All project and hardware files are valid.")

            log("\n\nChecking OPC configuration...")
            uad_misplaced_files, uad_old_version = check_uad_files(physical_path)
            if uad_misplaced_files:
                log(
                    "The following .uad files are not located in the required Connectivity/OpcUA directory:"
                )
                for file_path in uad_misplaced_files:
                    log(f"- {file_path}")
                log(
                    "\nPlease create (via AS 4.12) and move these files to the required directory: Connectivity/OpcUA."
                )
            else:
                log_v("- All .uad files are in the correct location.")

            if uad_old_version:
                log(
                    "\nThe following .uad files do not have the minimum file version 9:"
                )
                for file_path in uad_old_version:
                    log(f"- {file_path}")
                log(
                    "\nPlease edit the uad file, make a small change and save the file to trigger the file update."
                )
            else:
                log_v("- All .uad files have the correct minimum version.")

            log("\n\nThe following unsupported hardware were found:")
            if hardware_results:
                grouped_results = {}
                for hardware_id, reason, file_path in hardware_results:
                    config_name = os.path.basename(os.path.dirname(file_path))
                    grouped_results.setdefault(config_name, set()).add(
                        (hardware_id, reason)
                    )

                for config_name, entries in grouped_results.items():
                    log(f"\nHardware configuration: {config_name}")
                    for hardware_id, reason in sorted(entries):
                        log(f"- {hardware_id}: {reason}")
            else:
                log_v("- None")

            log(
                "\n\nThe following invalid file devices were found: (accessing system partitions / using drive letters)"
            )
            if file_devices:
                grouped_results = {}
                for name, path, file_path in file_devices:
                    config_name = os.path.basename(os.path.dirname(file_path))
                    grouped_results.setdefault(config_name, set()).add((name, path))

                for config_name, entries in grouped_results.items():
                    results = []
                    for name, path in sorted(entries):
                        results.append(f"{name} ({path})")
                    result_string = ", ".join(results)
                    log(f"Hardware configuration '{config_name}': {result_string}")

                log(
                    "\nWrite operations on a system partition (C:, D:, E:) are not allowed. In the event of error, "
                    "a write operation could destroy the system partition so that the target system can no longer be booted.\n"
                    "The User partition USER_PATH should be used instead!\n"
                    "In ARsim, the directory corresponding to USER_PATH is found at \\<Project>\\Temp\\Simulation\\<Configuration>\\<CPU>\\USER\\."
                )
            else:
                log_v("- None")

            log(
                "\n\nThe following potentially invalid ftp configurations were found: (accessing system instead of user partition)"
            )
            if ftp_configs:
                grouped_results = {}
                for name, file_path in ftp_configs:
                    config_name = os.path.basename(os.path.dirname(file_path))
                    grouped_results.setdefault(config_name, set()).add(name)

                for config_name, entries in grouped_results.items():
                    log(f"\nHardware configuration: {config_name}")
                    for name in sorted(entries):
                        log(f"- Accessing '{name}'")
            else:
                log_v("- None")

            log("\n\nThe following invalid libraries were found in .pkg files:")
            if invalid_pkg_files:
                for library, reason, file_path in invalid_pkg_files:
                    log(f"- {library}: {reason} (Found in: {file_path})")
            else:
                log_v("- None")

            log(
                "\n\nThe following libraries might require manual action after migrating the project to Automation Studio 6:"
            )
            if manual_libs_results:
                for library, reason, file_path in manual_libs_results:
                    log(f"- {library}: {reason} (Found in: {file_path})")
            else:
                log_v("- None")

            # Convert .lby results to match the (library_name, reason, file_path) format
            normalized_lby_results = [
                (lib, f"Dependency on {dep}: {reason}", path)
                for lib, dep, reason, path in lby_dependency_results
            ]

            # Merge results from .lby and C/C++/HPP include dependencies
            all_dependency_results = (
                normalized_lby_results + c_include_dependency_results
            )

            log(
                "\n\nThe following obsolete dependencies were found in .lby, .c, .cpp, and .hpp files:"
            )
            if all_dependency_results:
                for library_name, reason, file_path in all_dependency_results:
                    log(f"- {library_name}: {reason} (Found in: {file_path})")
            else:
                log_v("- None")

            log(
                "\n\nThe following invalid function blocks were found in .var and .typ files:"
            )
            if invalid_var_typ_files:
                for block, reason, file_path in invalid_var_typ_files:
                    log(f"- {block}: {reason} (Found in: {file_path})")
            else:
                log_v("- None")

            log(
                "\n\nThe following invalid functions were found in .st, .c and .cpp files:"
            )
            found_any_invalid_functions = False

            if invalid_st_c_files:
                for function, reason, file_path in invalid_st_c_files:
                    log(f"- {function}: {reason} (Found in: {file_path})")
                found_any_invalid_functions = True

            if found_deprecated_string:
                log(
                    "- Deprecated AsString functions detected in the project: Consider using the helper asstring_to_asbrstr.py to replace them."
                )
                found_any_invalid_functions = True

                # Verbose: Print where the deprecated string functions were found only if --verbose is enabled
                if args.verbose and deprecated_string_files:
                    log_v(
                        "Deprecated AsString functions detected in the following files:",
                        prepend="\n",
                    )
                    for f in deprecated_string_files:
                        log_v(f"- {f}")

            if found_deprecated_math:
                log(
                    "- Deprecated AsMath functions detected in the project: Consider using the helper asmath_to_asbrmath.py to replace them."
                )
                found_any_invalid_functions = True

                # Verbose: Print where the deprecated math functions were found only if --verbose is enabled
                if deprecated_math_files:
                    log_v(
                        "Deprecated AsMath functions detected in the following files:",
                        prepend="\n",
                    )
                    for f in deprecated_math_files:
                        log_v(f"- {f}")

            if not found_any_invalid_functions:
                log_v("- None")

            log("\n\nChecking for safety...")
            safety_results = check_safety(args.project_path)
            if safety_results:
                for entry in safety_results:
                    log(f"- {entry}")
            else:
                log_v("- None")

            vision_settings_results = check_vision_settings(args.project_path)
            if vision_settings_results["found"]:
                log(
                    f"\n\nFound usage of mapp Vision (Version: {vision_settings_results['version']}). "
                    "After migrating to AS6 make sure that IP forwarding is activated under the Powerlink interface!"
                )

                # Verbose: Print detailed information about mappVision locations if verbose mode is enabled
                if vision_settings_results["locations"]:
                    log_v("mappVision folders found at:", prepend="\n")
                    for location in vision_settings_results["locations"]:
                        log_v(f"- {location}")

                found_any_invalid_functions = True

            mappView_settings_results = check_mappView(args.project_path)
            if mappView_settings_results["found"]:
                log(
                    f"\n\nFound usage of mappView (Version: {mappView_settings_results['version']}). Several security settings will be enforced after the migration."
                    "\n"
                    "\n- To allow access without a certificate"
                    "\n  Change the following settings in the OPC Client/Server configuration (Configuration View/Connectivity/OpcUaCs/UaCsConfig.uacfg):"
                    "\n  ClientServerConfiguration->Security->MessageSecurity->SecurityPolicies->None: Enabled"
                    "\n"
                    "\n- User login will be enabled by default. To allow anonymous access"
                    "\n  Change the following settings in mappView configuration (Configuration View/mappView/Config.mappviewcfg):"
                    "\n  MappViewConfiguration->Server Configuration->Startup User: anonymous token"
                    "\n"
                    "\n- Change the following settings in the OPC Client/Server configuration (Configuration View/Connectivity/OpcUaCs/UaCsConfig.uacfg):"
                    "\n  ClientServerConfiguration->Security->Authentication->Authentication Methods->Anymous: Enabled"
                    "\n"
                    "\n- Change the following settings in the User role system (Configuration View/AccessAndSecurity/UserRoleSystem/User.user):"
                    '\n  Assign the role "BR_Engineer" to the user "Anonymous". Create that user if it doesn\'t already exist, assign no password.'
                    "\n"
                    "\n- To allow access to a File device from a running mappView application, it is now required to explicitly whitelist it for reading:"
                    "\n  - Open the mappView server configuration file Configuration View/mappView/Config.mappviewcfg)"
                    '\n  - Check "Change Advanced Parameter Visibility" button in the editor toolbar'
                    '\n  - Enter your accessed File device "Name" under "MappViewConfiguration->Server configuration->File device whitelist"'
                )

                # Verbose: Print detailed information about mappVision locations if verbose mode is enabled
                if mappView_settings_results["locations"]:
                    log_v("mappView folders found at:", prepend="\n")
                    for location in mappView_settings_results["locations"]:
                        log_v(f"- {location}")

                found_any_invalid_functions = True

            log("\n\nChecking mapp version in project file...")
            mapp_results = check_mapp_version(args.project_path)
            if mapp_results:
                for msg in mapp_results:
                    log(f"- {msg}")
            else:
                log_v("- No mapp version information found.")

            end_time = time.time()
            log(
                f"\n\nScanning completed successfully in {end_time - start_time:.2f} seconds."
            )

        except Exception as e:
            error_message = f"\n[ERROR] An unexpected error occurred: {str(e)}"

            # Print error to console
            print(error_message)

            # Ensure log file is open before writing
            try:
                with open(output_file, "a", encoding="utf-8") as error_log:
                    error_log.write(error_message + "\n")
            except Exception as log_error:
                print(f"[ERROR] Failed to write error to log file: {log_error}")

    print(f"\nResults have been saved to {output_file}\n")


if __name__ == "__main__":
    main()
