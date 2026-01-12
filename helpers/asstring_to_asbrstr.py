import os
import re
import sys
from pathlib import Path

from utils import utils


def replace_functions_and_constants(
    file_path: Path, function_mapping: dict, constant_mapping: dict
) -> tuple[int, int, bool]:
    """
    Replace function calls and constants in a file based on the provided mappings.
    """
    original_content, original_encoding, original_bytes = utils.read_file_with_encoding(
        file_path
    )

    modified_content = original_content
    function_replacements = 0
    constant_replacements = 0

    # Replace function calls
    for old_func, new_func in function_mapping.items():

        pattern = rf"\b{re.escape(old_func)}\s*\("
        replacement = f"{new_func}("
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        function_replacements += num_replacements

    # Replace constants
    for old_const, new_const in constant_mapping.items():
        pattern = rf"\b{re.escape(old_const)}\b"
        replacement = new_const
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        constant_replacements += num_replacements

    if utils.write_file_if_changed(
        file_path, modified_content, original_encoding, original_bytes
    ):
        utils.log(
            f"{function_replacements + constant_replacements:4d} changes written to: {file_path}",
            severity="INFO",
        )
        return function_replacements, constant_replacements, True

    return function_replacements, constant_replacements, False


def check_for_library(project_path: Path, library_names: list) -> list:
    """
    Checks if any specified library is used in the project.
    """
    pkg_file = project_path / "Logical" / "Libraries" / "Package.pkg"
    if not pkg_file.is_file():
        utils.log(f"Could not find Package.pkg file in: {pkg_file}", severity="ERROR")
        return []

    content = utils.read_file(pkg_file)
    return [lib for lib in library_names if lib in content]


def main():
    project_path = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    apj_file = utils.get_and_check_project_file(project_path)

    utils.log(f"Project path validated: {project_path}")
    utils.log(f"Using project file: {apj_file}\n")

    library_names = ["AsString", "AsWStr"]
    found_libraries = check_for_library(project_path, library_names)

    utils.log(
        "This script will search for usages of AsString and AsWStr functions and constants and replace them with the AsBr equivalents.",
        severity="INFO",
    )
    utils.log(
        "Before proceeding, make sure you have a backup or are using version control (e.g., Git).",
        severity="WARNING",
    )

    if not found_libraries:
        utils.log("Neither AsString nor AsWStr libraries found.", severity="INFO")
        proceed = utils.ask_user(
            "Do you want to proceed with replacing functions and constants anyway? (y/n) [y]: ",
            extra_note="Note: This script updates code to use AsBrStr. You must manually remove AsString/AsWStr and add AsBrStr/AsBrWStr in the library manager. Compatible with AS4 and AS6 after that.",
        )
    else:
        utils.log(f"Libraries found: {', '.join(found_libraries)}.", severity="INFO")
        proceed = utils.ask_user(
            "Do you want to continue? (y/n) [y]: ",
            extra_note="Note: After conversion, manually remove AsString/AsWStr and add AsBrStr/AsBrWStr in the library manager.",
        )

    if proceed != "y":
        utils.log("Operation cancelled. No changes were made.", severity="WARNING")
        return

    info = utils.load_discontinuation_info("deprecated_string_functions")
    function_mapping = {}
    for item in info:
        function_mapping[item] = f"br{item}" if item.startswith("wcs") else f"brs{item}"

    constant_mapping = {
        "U8toUC": "brwU8toUC",
        "UCtoU8": "brwUCtoU8",
    }

    logical_path = project_path / "Logical"
    total_function_replacements = 0
    total_constant_replacements = 0
    total_files_changed = 0

    # Loop through the files in the "Logical" directory and process .st and .ab files
    for file_path in logical_path.rglob("*"):
        if file_path.suffix in {".st", ".ab"}:
            function_replacements, constant_replacements, changed = (
                replace_functions_and_constants(
                    file_path, function_mapping, constant_mapping
                )
            )
            if changed:
                total_function_replacements += function_replacements
                total_constant_replacements += constant_replacements
                total_files_changed += 1

    utils.log("─" * 80 + "\nSummary:")
    utils.log(f"Total functions replaced: {total_function_replacements}")
    utils.log(f"Total constants replaced: {total_constant_replacements}")
    utils.log(f"Total files changed: {total_files_changed}")

    if total_function_replacements == 0 and total_constant_replacements == 0:
        utils.log("No functions or constants needed to be replaced.", severity="INFO")
    else:
        utils.log("Replacement completed successfully.", severity="INFO")


if __name__ == "__main__":
    main()
