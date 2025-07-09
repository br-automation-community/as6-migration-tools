import os
import sys
import re
import concurrent.futures
import time
import json
import argparse
from pathlib import Path
from checks import *

# Path to the main package file
root_pkg_path = r"Logical\Libraries\Package.pkg"

# path to the current script
script_directory = Path(__file__).resolve().parent


# filens containing discontinuation information
discontinuation_info = {
    "obsolete_libs": {},
    "manual_process_libs": {},
    "obsolete_fbks": {},
    "obsolete_funcs": {},
    "unsupported_hw": {},
    "deprecated_string_functions" : {},
    "deprecated_math_functions" : {},
}

try:
    for filename in discontinuation_info:
        with open( f"{script_directory}/discontinuations/{filename}.json", "r") as json_file:
            discontinuation_info[filename]  = json.load(json_file)
except Exception as e:
    print(f"\033[1;31m[ERROR]\033[0m Error reading discontinuation lists: {e}", file=sys.stderr)
    sys.exit(1)
    
obsolete_dict = discontinuation_info["obsolete_libs"] # obsolete libraries with reasons
manual_process_libraries = discontinuation_info["manual_process_libs"] # Libraries that must be handled manually
obsolete_function_blocks = discontinuation_info["obsolete_fbks"] # list of obsolete function blocks with reasons
obsolete_functions = discontinuation_info["obsolete_funcs"] # Hardcoded list of obsolete functions with reasons
unsupported_hardware = discontinuation_info["unsupported_hw"] # hardware not supported by >= 6.0
deprecated_string_functions = set(discontinuation_info["deprecated_string_functions"]) # deprecated string functions 8 bit and 16 bit   
deprecated_math_functions = set(discontinuation_info["deprecated_math_functions"]) # deprecated math functions  

pass
def display_progress(message):
    """
    Displays a progress message on the same line in the terminal.
    In GUI mode, stdout may be None, so we fall back to printing.
    """
    try:
        sys.stdout.write('\r' + ' ' * 80)
        sys.stdout.write('\r' + message)
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

# Get build number from version.txt
def get_build_number():
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'version.txt')
    if os.path.exists(version_file):
        with open(version_file, 'r') as file:
            return file.read().strip()
    return "1"  # Default build number if version.txt doesn't exist

def scan_files_parallel(root_dir, extensions, process_function, *args):
    """
    Scans files in a directory tree in parallel for specific content.

    Args:
        root_dir (str): The root directory to search in.
        extensions (list): File extensions to include.
        process_function (callable): The function to apply on each file.
        *args: Additional arguments to pass to the process_function.

    Returns:
        list: Aggregated results from all scanned files.
    """
    results = []
    file_paths = []

    for root, _, files in os.walk(root_dir):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_paths.append(os.path.join(root, file))

    total_files = len(file_paths)
    display_progress(f"Found {total_files} files to process...")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_function, path, *args): path for path in file_paths}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            display_progress(f"Processing file {i}/{total_files}...")
            results.extend(future.result())
    
    display_progress("Processing complete.".ljust(50))  # Clear line
    print()  # Move to next line
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
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Regex for library names between > and <
        matches = re.findall(r'>([^<]+)<', content, re.IGNORECASE)
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
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Regex for function block declarations, e.g., : MpAlarmXConfigMapping;
        matches = re.findall(r':\s*([A-Za-z0-9_]+)\s*;', content)
        for match in matches:
            for pattern, reason in patterns.items():
                if match.lower() == pattern.lower():
                    results.append((pattern, reason, file_path))
    return results

def process_var_typ_file(file_path, patterns):
    """
    Processes a .var file to find matches for the given patterns.
    Ensures function block names in variable declarations are matched.

    Args:
        file_path (str): Path to the file.
        patterns (dict): Patterns to match with reasons.

    Returns:
        list: Matches found in the file.
    """
    results = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Regex to match the format: name : FunctionBlockName;
        matches = re.findall(r':\s*([A-Za-z0-9_]+)\s*;', content)
        for match in matches:
            for pattern, reason in patterns.items():
                # Compare case-insensitively
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

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

        # Check for other patterns if necessary
        for pattern, reason in patterns.items():
            if re.search(rf'\b{re.escape(pattern)}\b', content) and file_path not in matched_files:
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
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Regex to extract the Type value from the <Module> elements
        matches = re.findall(r'<Module [^>]*Type="([^"]+)"', content)
        for hw_type in matches:
            for reason, items in hardware_dict.items():
                if hw_type in items:
                    results.add((hw_type, reason, file_path))  # Add as a tuple to ensure uniqueness
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
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Regex to extract the value from the file device elements
        matches = re.findall(r'<Group ID="FileDevice\d+" />\s*<Parameter ID="FileDeviceName\d+" Value="(.*?)" />\s*<Parameter ID="FileDevicePath\d+" Value="(.*?)" />', content)
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
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        # Regex to extract if the FTP server is activated
        matches = re.search(
            r'<Parameter ID="ActivateFtpServer"\s+Value="(\d)" />', content
        )
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
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Extract library name (directory name as identifier)
        library_name = os.path.basename(os.path.dirname(file_path))
        # Extract dependencies from the XML content
        dependencies = re.findall(r'<Dependency ObjectName="([^"]+)"', content, re.IGNORECASE)
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

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.readlines()

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
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        matches = re.findall(r'>([^<]+)<', content, re.IGNORECASE)
        for match in matches:
            for library, action in patterns.items():
                if match.lower() == library.lower():
                    results.append((library, action, file_path))
    return results



# Update main function to handle project directory input and optional verbose flag
def main():
    """
    Main function to scan for obsolete libraries, function blocks, functions, and unsupported hardware.
    Outputs the results to a file as well as the console.
    """

    build_number = get_build_number()
    print(f"Script build number: {build_number}")

    
    class CONSOLE_COLORS:
        RESET =  '\x1b[1;0m'   # reset all modes (styles and colors)
        ERROR =  '\x1b[1;31m'  # Set style to bold, red foreground.
    
    
    parser = argparse.ArgumentParser( prog= os.path.basename(__file__), 
                        description="Scans Automation Studio project for transition from AS4 to AS6",
                        usage='python %(prog)s project_path [options]',
                        epilog = "Ensure the path is correct and the project folder exists.\n"\
                            "A valid AS 4 project folder must contain an *.apj file.\n"\
                            'If the path contains spaces, make sure to wrap it in quotes (e.g. like this: "C:\\My documents\\project")\n'\
                            "If you enter a  '.' as project_path the current directory will be used.\n",
                        formatter_class=argparse.RawDescriptionHelpFormatter                            
                        )
     # Add arguments
    parser.add_argument('project_path', type=str, help='Automation Studio 4.x path containing *.apj file')
    parser.add_argument('-v','--verbose', action='store_true', required=False, help='Outputs verbose information')
    # Parse the arguments

    # Fallback if no arguments are provided (e.g. when run from GUI)
    if len(sys.argv) == 1:
        # Default to current directory as project path
        sys.argv += [".", "-v"]
        # Optionally enable verbose mode by default from GUI
        # sys.argv += ["-v"]

    args = parser.parse_args()
       
    # Check if valid project path
    if not os.path.exists(args.project_path):
        print(f"{CONSOLE_COLORS.ERROR}Error: The provided project path does not exist: '{args.project_path}'", file=sys.stderr)
        print(CONSOLE_COLORS.RESET + "\n", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Check if .apj file exists in the provided path
    apj_files = [file for file in os.listdir(args.project_path) if file.endswith(".apj")]
    if not apj_files:
        print(f"{CONSOLE_COLORS.ERROR}Error: No .apj file found in the provided path: '{args.project_path}'", file=sys.stderr)
        print("Please specify a valid Automation Studio 4 project path.", file=sys.stderr)
        print(CONSOLE_COLORS.RESET + "\n", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    print(f"Project path validated: {args.project_path}")
    print(f"Using project file: {apj_files[0]}")

    output_file = os.path.join(args.project_path, "as4_to_as6_analyzer_result.txt")
    with open(output_file, "w", encoding="utf-8") as file:
        try:
            def log(message, log_file=file):
                print(message)  # Print to console
                log_file.write(message + "\n")  # Write to file
                log_file.flush()  # Ensure data is written immediately

            log("Scanning started... Please wait while the script analyzes your project files.\n", file)

            start_time = time.time()

            # Use project_path as the root directory for scanning
            manual_libs_results = scan_files_parallel(
                os.path.join(args.project_path, "Logical"), [".pkg"], process_manual_libraries, manual_process_libraries
            )
            
            invalid_pkg_files = scan_files_parallel(
                os.path.join(args.project_path, "Logical"), [".pkg"], process_pkg_file, obsolete_dict
            )

            invalid_var_typ_files = scan_files_parallel(
                os.path.join(args.project_path, "Logical"), [".var", ".typ"], process_var_file, obsolete_function_blocks
            )

            invalid_st_c_files = scan_files_parallel(
                os.path.join(args.project_path, "Logical"), [".st", ".c", ".cpp"], process_st_c_file, obsolete_functions
            )

            hardware_results = scan_files_parallel(
                os.path.join(args.project_path, "Physical"), [".hw"], process_hw_file, unsupported_hardware
            )

            file_devices = scan_files_parallel(
                os.path.join(args.project_path, "Physical"), [".hw"], process_file_devices
            )

            ftp_configs = scan_files_parallel(
                os.path.join(args.project_path, "Physical"), [".hw"], process_ftp_configurations,
            )

            lby_dependency_results = scan_files_parallel(
                os.path.join(args.project_path, "Logical"), [".lby"], process_lby_file, obsolete_dict
            )

            c_include_dependency_results = scan_files_parallel(
                os.path.join(args.project_path, "Logical"), [".c", ".cpp", ".hpp"], process_c_cpp_hpp_includes_file, obsolete_dict
            )

            # Store the list of files containing deprecated string functions
            deprecated_string_files = check_deprecated_string_functions(
                os.path.join(args.project_path, "Logical"), 
                [".st"], 
                deprecated_string_functions 
            )

            # Ensure we have a valid list, even if no deprecated functions are found
            if not isinstance(deprecated_string_files, list):
                deprecated_string_files = []  # Fallback to an empty list

            # Boolean flag to indicate whether deprecated string functions were found
            found_deprecated_string = bool(deprecated_string_files)

            # Store the list of files containing deprecated math functions
            deprecated_math_files = check_deprecated_math_functions(
                os.path.join(args.project_path, "Logical"),
                [".st"],
                deprecated_math_functions
            )

            # Ensure we have a valid list, even if no deprecated functions are found
            if not isinstance(deprecated_math_files, list):
                deprecated_math_files = []  # Fallback to an empty list

            # Boolean flag to indicate whether deprecated math functions were found
            found_deprecated_math = bool(deprecated_math_files)

            log("\n\nChecking project and hardware files for compatibility...")
            file_patterns = ["*.apj", "*.hw"]
            compatibility_results = check_files_for_compatibility(args.project_path, file_patterns)
            if compatibility_results:
                for file_path, issue in compatibility_results:
                    log(f"- {file_path}: {issue}")
                log("\nPlease ensure these files are saved at least once with Automation Studio 4.12.")
            else:
                log("- All project and hardware files are valid.")

            log("\n\nChecking OPC configuration...")
            uad_misplaced_files, uad_old_version = check_uad_files(os.path.join(args.project_path, "Physical"))
            if uad_misplaced_files:
                log("The following .uad files are not located in the required Connectivity/OpcUA directory:")
                for file_path in uad_misplaced_files:
                    log(f"- {file_path}")
                log("\nPlease create (via AS 4.12) and move these files to the required directory: Connectivity/OpcUA.")
            else:
                log("- All .uad files are in the correct location.")

            if uad_old_version:
                log("\nThe following .uad files do not have the minimum file version 9:")
                for file_path in uad_old_version:
                    log(f"- {file_path}")
                log("\nPlease edit the uad file, make a small change and save the file to trigger the file update.")
            else:
                log("- All .uad files have the correct minimum version.")

            log("\n\nThe following unsupported hardware were found:")
            if hardware_results:
                grouped_results = {}
                for hardware_id, reason, file_path in hardware_results:
                    config_name = os.path.basename(os.path.dirname(file_path))
                    grouped_results.setdefault(config_name, set()).add((hardware_id, reason))

                for config_name, entries in grouped_results.items():
                    log(f"\nHardware configuration: {config_name}")
                    for hardware_id, reason in sorted(entries):
                        log(f"- {hardware_id}: {reason}")
            else:
                log("- None")

            log("\n\nThe following invalid file devices were found: (accessing system partitions)")
            if file_devices:
                grouped_results = {}
                for name, path, file_path in file_devices:
                    config_name = os.path.basename(os.path.dirname(file_path))
                    grouped_results.setdefault(config_name, set()).add((name, path))

                for config_name, entries in grouped_results.items():
                    log(f"\nHardware configuration: {config_name}")
                    for name, path in sorted(entries):
                        log(f"- {name}: {path}")
            else:
                log("- None")

            log("\n\nThe following potentially invalid ftp configurations were found: (accessing system instead of user partition)")
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
                log("- None")

            log("\n\nThe following invalid libraries were found in .pkg files:")
            if invalid_pkg_files:
                for library, reason, file_path in invalid_pkg_files:
                    log(f"- {library}: {reason} (Found in: {file_path})")
            else:
                log("- None")

            log("\n\nThe following libraries might require manual action after migrating the project to Automation Studio 6:")
            if manual_libs_results:
                for library, reason, file_path in manual_libs_results:
                    log(f"- {library}: {reason} (Found in: {file_path})")
            else:
                log("- None")

            # Convert .lby results to match the (library_name, reason, file_path) format
            normalized_lby_results = [(lib, f"Dependency on {dep}: {reason}", path) for lib, dep, reason, path in lby_dependency_results]

            # Merge results from .lby and C/C++/HPP include dependencies
            all_dependency_results = normalized_lby_results + c_include_dependency_results

            log("\n\nThe following obsolete dependencies were found in .lby, .c, .cpp, and .hpp files:")
            if all_dependency_results:
                for library_name, reason, file_path in all_dependency_results:
                    log(f"- {library_name}: {reason} (Found in: {file_path})")
            else:
                log("- None")

            log("\n\nThe following invalid function blocks were found in .var and .typ files:")
            if invalid_var_typ_files:
                for block, reason, file_path in invalid_var_typ_files:
                    log(f"- {block}: {reason} (Found in: {file_path})")
            else:
                log("- None")

            log("\n\nThe following invalid functions were found in .st, .c and .cpp files:")
            found_any_invalid_functions = False

            if invalid_st_c_files:
                for function, reason, file_path in invalid_st_c_files:
                    log(f"- {function}: {reason} (Found in: {file_path})")
                found_any_invalid_functions = True

            if found_deprecated_string:
                log("- Deprecated AsString functions detected in the project: Consider using the helper asstring_to_asbrstr.py to replace them.")
                found_any_invalid_functions = True

                # Verbose: Print where the deprecated string functions were found only if --verbose is enabled
                if  args.verbose and deprecated_string_files:
                    print("\n[VERBOSE] Deprecated AsString functions detected in the following files:")
                    for file in deprecated_string_files:
                        print(f"[VERBOSE] - {file}")

            if found_deprecated_math:
                log("- Deprecated AsMath functions detected in the project: Consider using the helper asmath_to_asbrmath.py to replace them.")
                found_any_invalid_functions = True

                # Verbose: Print where the deprecated math functions were found only if --verbose is enabled
                if args.verbose and found_deprecated_math:
                    print("\n[VERBOSE] Deprecated AsMath functions detected in the following files:")
                    for file in deprecated_math_files:
                        print(f"[VERBOSE] - {file}")
            
            if not found_any_invalid_functions:
                log("- None")

            log("\n\nChecking for safety...")
            safety_results = check_safety(args.project_path)
            if safety_results:
                for entry in safety_results:
                    log(f"- {entry}")
            else:
                log("- None")

            vision_settings_results = check_vision_settings(args.project_path)
            if vision_settings_results['found']:
                log(f"\n\nFound usage of mapp Vision (Version: {vision_settings_results['version']}). After migrating to AS6 make sure that IP forwarding is activated under the Powerlink interface!")
                
                # Verbose: Print detailed information about mappVision locations if verbose mode is enabled
                if args.verbose and vision_settings_results['locations']:
                    print("\n[VERBOSE] mappVision folders found at:")
                    for location in vision_settings_results['locations']:
                        print(f"[VERBOSE] - {location}")
                
                found_any_invalid_functions = True

            mappView_settings_results = check_mappView(args.project_path)
            if mappView_settings_results['found']:
                log(f"\n\nFound usage of mappView (Version: {mappView_settings_results['version']}). Several security seetings will be enforced after the migration.")
                log("\n- To allow access without a certificate")
                log("  Change the following settings in the OPC Client/Server configuration (Physical View/Connectivity/OpcUaCs/UaCsConfig.uacfg):")
                log("  ClientServerConfiguration->Security->MessageSecurity->SecurityPolicies->None: Enabled")
                log("\n- User login will be enabled by default. To allow anonymous access")
                log("  Change the following settings in mappView configuration (Physical View/mappView/Config.mappviewcfg):")
                log("  MappViewConfiguration->Server Configuration->Startup User: anonymous token")
                log("\n  Change the following settings in the OPC Client/Server configuration (Physical View/Connectivity/OpcUaCs/UaCsConfig.uacfg):")
                log("  ClientServerConfiguration->Security->Authentication->Authentication Methods->Anymous: Enabled")
                log("  ClientServerConfiguration->Security->Authorization->Anonymous Access Add new user role and select \"everyone\"")
                                    
                # Verbose: Print detailed information about mappVision locations if verbose mode is enabled
                if args.verbose and mappView_settings_results['locations']:
                    print("\n[VERBOSE] mappView folders found at:")
                    for location in mappView_settings_results['locations']:
                        print(f"[VERBOSE] - {location}")
                
                found_any_invalid_functions = True                

            log("\n\nChecking mapp version in project file...")
            mapp_results = check_mapp_version(args.project_path)
            if mapp_results:
                for msg in mapp_results:
                    log(f"- {msg}")
            else:
                log("- No mapp version information found.")

            end_time = time.time()
            log(f"\n\nScanning completed successfully in {end_time - start_time:.2f} seconds.")

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
