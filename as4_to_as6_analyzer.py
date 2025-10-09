import argparse
import os
import sys
import time
from pathlib import Path

from checks import *
from utils import utils


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
    parser.add_argument(
        "--no-file",
        action="store_true",
        help="Do not write a result file; log only to console/UI.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Custom output file path. If not provided, defaults to 'as4_to_as6_analyzer_result.txt' in the project folder.",
    )
    # Parse the arguments

    # Fallback if no arguments are provided (e.g. when run from GUI)
    if len(sys.argv) == 1:
        # Default to current directory as project path, verbose on,
        # and NO file output when launched via GUI.
        sys.argv += [".", "-v", "--no-file"]

    return parser.parse_args()


def open_output_file(project_path, no_file, custom_output):
    """
    Opens the output file based on the given arguments.
    """
    output_file = None
    file_handle = None

    if not no_file:
        output_file = custom_output or str(
            Path(project_path) / "as4_to_as6_analyzer_result.txt"
        )
        try:
            file_handle = open(output_file, "w", encoding="utf-8")
        except Exception as e:
            # If file cannot be opened, continue without file output but warn the user.
            utils.log(
                f"Failed to open result file '{output_file}' for writing: {e}. "
                f"Continuing without file output.",
                severity="WARNING",
            )
            output_file = None
            file_handle = None

    return output_file, file_handle


# Update main function to handle project directory input and optional verbose flag
def main():
    """
    Main function to scan for obsolete libraries, function blocks, functions, and unsupported hardware.
    Writes to a file only when requested; otherwise logs to console/UI only.
    """

    build_version = utils.get_version()
    utils.log(f"Script version: {build_version}")

    args = parse_args()
    apj_file = utils.get_and_check_project_file(args.project_path)

    utils.log(f"Project path validated: {args.project_path}")
    utils.log(f"Using project file: {apj_file}")

    # Decide whether to write a result file.
    # - If parse_args() defines '--no-file' and sets it for GUI runs, no file is created.
    # - If '--output' is provided, use it; otherwise default to the project folder.
    output_file, file_handle = open_output_file(
        args.project_path, args.no_file, args.output
    )

    # Unified logger: always logs to console; optionally mirrors to file if file_handle is set.
    def log(message, when="", severity=""):
        utils.log(message, log_file=file_handle, when=when, severity=severity)

    try:
        log(
            "Scanning started... Please wait while the script analyzes your project files."
        )
        start_time = time.time()

        # Validate naming and basic structure
        check_project_path_and_name(args.project_path, apj_file, log, args.verbose)

        # Resolve key paths
        apj_path = Path(args.project_path) / apj_file
        logical_path = Path(args.project_path) / "Logical"
        physical_path = Path(args.project_path) / "Physical"

        # Generic file compatibility checks
        check_files_for_compatibility(args.project_path, log, args.verbose)

        # Hardware & configuration checks
        check_ar(physical_path, log, args.verbose)
        check_uad_files(physical_path, log, args.verbose)
        check_hardware(physical_path, log, args.verbose)
        check_file_devices(physical_path, log, args.verbose)

        # Software/libraries/function checks
        check_libraries(logical_path, log, args.verbose)
        check_functions(logical_path, log, args.verbose)

        # Access & Security (UserRoleSystem + ANSL in .hw)
        check_access_security(physical_path, log, args.verbose)

        # Special-domain checks
        check_safety(apj_path, log, args.verbose)  # Safety system issues
        check_vision_settings(apj_path, log, args.verbose)  # mappVision issues
        check_mappView(apj_path, log, args.verbose)  # mappView issues
        check_widget_lib_usage(
            logical_path, log, args.verbose
        )  # Detect widget libraries (WDK usage or User Widget Libraries from AS4)
        check_mapp_version(
            apj_path, log, args.verbose
        )  # mappService/mapp version issues
        check_scene_viewer(
            apj_path, log, args.verbose
        )  # Scene Viewer usage & requirements
        check_visual_components(
            apj_path, log, args.verbose
        )  # Visual Components VC4/VC3 issues

        # Finish up

        log("─" * 80)
        log(
            "After upgrading the Automation Studio 4 project:",
            when="AS6",
            severity="INFO",
        )
        log(
            " - The Automation Runtime version, Visual Components version and Technology Package versions must still be set in Runtime versions dialog box."
            "\n - To ensure correct functionality, it is mandatory to perform a Project / Clean up configuration or Project / Rebuild configuration with AS 6 for all configurations."
        )

        end_time = time.time()
        log(
            "─" * 80
            + f"\nScanning completed successfully in {end_time - start_time:.2f} seconds."
        )

    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        # Always report to console/UI
        utils.log(error_message, severity="ERROR")

        # Append to file only if file output was enabled
        if output_file:
            try:
                with open(output_file, "a", encoding="utf-8") as error_log:
                    error_log.write(f"\n[ERROR] {error_message}\n")
            except Exception as log_error:
                utils.log(
                    f"Failed to write error to log file: {log_error}", severity="ERROR"
                )

    finally:
        # Close the file handle if we opened one
        if file_handle:
            try:
                file_handle.close()
            except Exception:
                pass

    # Tail message only if a file was actually created
    if output_file:
        utils.log(f"Results have been saved to {output_file}\n")


if __name__ == "__main__":
    main()
