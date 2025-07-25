import os
import re
import sys
from pathlib import Path

from utils import utils


def replace_functions_and_constants(file_path: Path, function_mapping, constant_mapping):
    """
    Replace function calls and constants in a file based on the provided mappings.
    """
    original_hash = utils.calculate_file_hash(str(file_path))
    original_content = file_path.read_text(encoding="iso-8859-1", errors="ignore")

    modified_content = original_content
    function_replacements = 0
    constant_replacements = 0

    # if file_path.endswith('ncsdcctrlInit.st'):
    #     modified_content, num_replacements = re.subn(r'(\s*)((?:strcpy)|(?:strcat))', r'\1brs\2', original_content)
    #     pass

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

    if modified_content != original_content:
        file_path.write_text(modified_content, encoding="iso-8859-1")

        new_hash = utils.calculate_file_hash(str(file_path))
        if original_hash == new_hash:
            return function_replacements, constant_replacements, False

        print(
            f"{function_replacements + constant_replacements:4d} changes written to: {file_path}"
        )
        return function_replacements, constant_replacements, True

    return function_replacements, constant_replacements, False


def check_for_library(project_path, library_names):
    """
    Checks if any specified library is used in the project.
    """
    project_path = Path(project_path)
    pkg_file = project_path / "Logical" / "Libraries" / "Package.pkg"
    if not pkg_file.is_file():
        print(f"Error: Could not find Package.pkg file in: {pkg_file}")
        return []

    content = pkg_file.read_text(encoding="iso-8859-1", errors="ignore")
    return [lib for lib in library_names if lib in content]


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    apj_file = utils.get_and_check_project_file(project_path)

    print(f"Project path validated: {project_path}")
    print(f"Using project file: {apj_file}\n")

    library_names = ["AsString", "AsWStr"]
    found_libraries = check_for_library(project_path, library_names)

    print(
        "This script will search for usages of AsString and AsWStr functions and constants and replace them with the AsBr equivalents.\n"
        "Before proceeding, make sure you have a backup or are using version control (e.g., Git).\n"
    )

    if not found_libraries:
        print("Neither AsString nor AsWStr libraries found.\n")
        proceed = utils.ask_user(
            "Do you want to proceed with replacing functions and constants anyway? (y/n) [y]: ",
            extra_note="Note: This script updates code to use AsBrStr. You must manually remove AsString/AsWStr and add AsBrStr/AsBrWStr in the library manager. Compatible with AS4 and AS6 after that.",
        )
    else:
        print(f"Libraries found: {', '.join(found_libraries)}.\n")
        proceed = utils.ask_user(
            "Do you want to continue? (y/n) [y]: ",
            extra_note="Note: After conversion, manually remove AsString/AsWStr and add AsBrStr/AsBrWStr in the library manager.",
        )

    if proceed != "y":
        print("Operation cancelled. No changes were made.")
        return

    function_mapping = {
        "ftoa": "brsftoa",
        "atof": "brsatof",
        "itoa": "brsitoa",
        "atoi": "brsatoi",
        "memset": "brsmemset",
        "memcpy": "brsmemcpy",
        "memmove": "brsmemmove",
        "memcmp": "brsmemcmp",
        "strcat": "brsstrcat",
        "strlen": "brsstrlen",
        "strcpy": "brsstrcpy",
        "strcmp": "brsstrcmp",
        "wcscat": "brwcscat",
        "wcschr": "brwcschr",
        "wcscmp": "brwcscmp",
        "wcsconv": "brwcsconv",
        "wcscpy": "brwcscpy",
        "wcslen": "brwcslen",
        "wcsncat": "brwcsncat",
        "wcsncmp": "brwcsncmp",
        "wcsncpy": "brwcsncpy",
        "wcsrchr": "brwcsrchr",
        "wcsset": "brwcsset",
    }

    constant_mapping = {
        "U8toUC": "brwU8toUC",
        "UCtoU8": "brwUCtoU8",
    }

    logical_path = Path(project_path) / "Logical"
    total_function_replacements = 0
    total_constant_replacements = 0
    total_files_changed = 0

    # Loop through the files in the "Logical" directory and process .st and .ab files
    for file_path in Path(logical_path).rglob("*"):
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

    print("\nSummary:")
    print(f"Total functions replaced: {total_function_replacements}")
    print(f"Total constants replaced: {total_constant_replacements}")
    print(f"Total files changed: {total_files_changed}")

    if total_function_replacements == 0 and total_constant_replacements == 0:
        print("No functions or constants needed to be replaced.")
    else:
        print("Replacement completed successfully.")


if __name__ == "__main__":
    main()
