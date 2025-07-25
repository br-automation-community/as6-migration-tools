import os
import re
import sys
from pathlib import Path

from utils import utils


def replace_functions_and_constants(file_path: Path, function_mapping, constant_mapping):
    """
    Replace function calls and constants in a file based on the provided mappings.
    """
    original_hash = utils.calculate_file_hash(file_path)
    original_content = file_path.read_text(encoding="iso-8859-1", errors="ignore")
    modified_content = original_content
    function_replacements = 0
    constant_replacements = 0

    for old_func, new_func in function_mapping.items():
        pattern = rf"\b{re.escape(old_func)}\s*\("
        replacement = f"{new_func}("
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        function_replacements += num_replacements

    for old_const, new_const in constant_mapping.items():
        pattern = rf"\b{re.escape(old_const)}\b"
        replacement = new_const
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        constant_replacements += num_replacements

    if modified_content != original_content:
        file_path.write_text(modified_content, encoding="iso-8859-1")

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return function_replacements, constant_replacements, False

        print(
            f"{function_replacements + constant_replacements:4d} changes written to: {file_path}"
        )
        return function_replacements, constant_replacements, True

    return function_replacements, constant_replacements, False


def check_for_asmath_library(project_path):
    """
    Checks if AsMath library is used in the project.
    """
    pkg_file =  Path(project_path) / "Logical" / "Libraries" / "Package.pkg"
    if not pkg_file.is_file():
        # print(f"Debug: Could not find Package.pkg file in: {pkg_file}")
        return False

    content = pkg_file.read_text(encoding="iso-8859-1", errors="ignore")

    if "AsMath" in content:
        print("AsMath library found in Package.pkg!\n")
        return True

    return False


def main():
    """
    Main function to replace AsMath functions and constants with their AsBrMath equivalents.
    """

    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    apj_file = utils.get_and_check_project_file(project_path)

    print(f"Project path validated: {project_path}")
    print(f"Using project file: {apj_file}\n")

    print("Checking for AsMath library in the project...")
    library_found = check_for_asmath_library(project_path)

    print(
        "This script will search for usages of AsMath functions and constants and replace them with the AsBrMath equivalents.\n"
        "Before proceeding, make sure you have a backup or are using version control (e.g., Git).\n"
    )

    if not library_found:
        print("AsMath library not found.")
        proceed = utils.ask_user(
            "Do you want to proceed with replacing functions and constants anyway? (y/n) [y]: ",
            extra_note="Note: This script only updates code. You must manually remove 'AsMath' and add 'AsBrMath' in the library manager. Compatible with both AS4 and AS6 after that.",
        )
    else:
        proceed = utils.ask_user(
            "Do you want to continue? (y/n) [y]: ",
            extra_note="Note: After replacing the code, remember to swap the library from 'AsMath' to 'AsBrMath' manually.",
        )

    if proceed != "y":
        print("Operation cancelled. No changes were made.")
        return

    function_mapping = {
        "atan2": "brmatan2",
        "ceil": "brmceil",
        "cosh": "brmcosh",
        "floor": "brmfloor",
        "fmod": "brmfmod",
        "frexp": "brmfrexp",
        "ldexp": "brmldexp",
        "modf": "brmmodf",
        "pow": "brmpow",
        "sinh": "brmsinh",
        "tanh": "brmtanh",
    }

    constant_mapping = {
        "am2_SQRTPI": "brm2_SQRTPI",
        "amSQRT1_2": "brmSQRT1_2",
        "amSQRTPI": "brmSQRTPI",
        "amLOG2_E": "brmLOG2_E",
        "amLOG10E": "brmLOG10E",
        "amIVLN10": "brmINVLN10",
        "amINVLN2": "brmINVLN2",
        "amTWOPI": "brmTWOPI",
        "amSQRT3": "brmSQRT3",
        "amSQRT2": "brmSQRT2",
        "amLOG2E": "brmLOG2E",
        "amLN2LO": "brmLN2LO",
        "amLN2HI": "brmLN2HI",
        "am3PI_4": "brm3PI_4",
        "amPI_4": "brmPI_4",
        "amPI_2": "brmPI_2",
        "amLN10": "brmLN10",
        "am2_PI": "brm2_PI",
        "am1_PI": "brm1_PI",
        "amLN2": "brmLN2",
        "amPI": "brmPI",
        "amE": "brmE",
    }

    total_function_replacements = 0
    total_constant_replacements = 0
    total_files_changed = 0

    logical_path = Path(project_path) / "Logical"
    for path in logical_path.rglob("*"):
        if path.suffix in (".st", ".ab"):
            function_replacements, constant_replacements, changed = (
                replace_functions_and_constants(
                    path, function_mapping, constant_mapping
                )
            )
            if changed:
                total_function_replacements += function_replacements
                total_constant_replacements += constant_replacements
                total_files_changed += 1

    print("\nSummary:")
    print(f"Total functions replaced: {total_function_replacements}")
    print(f"Total constants replaced: {total_constant_replacements}")
    print(f"Total files changed: {total_files_changed}")

    if total_function_replacements == 0 and total_constant_replacements == 0:
        print("\nNo functions or constants needed to be replaced.")
    else:
        print("\nReplacement completed successfully.")


if __name__ == "__main__":
    main()
