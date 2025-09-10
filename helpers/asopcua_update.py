# The OPC UA client library in Automation Runtime 6 has been updated to OPC 30001 PLC client function blocks based on IEC 61131-3 1.2.
# To migrate a project from an older AR version to AR 6, modifications to the program are necessary.
import os
import re
import sys
from pathlib import Path

from utils import utils


def replace_enums(file_path: Path, enum_mapping):
    """
    Replace enumerators in a file based on the provided mappings.
    """
    if any(part in {"AsOpcUac", "AsOpcUas"} for part in file_path.parts):
        return 0, False

    original_hash = utils.calculate_file_hash(file_path)
    original_content = utils.read_file(Path(file_path))
    modified_content = original_content
    enum_replacements = 0

    # Replace enums
    for old_const, new_const in enum_mapping.items():
        pattern = re.escape(old_const)
        replacement = new_const
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        enum_replacements += num_replacements

    if modified_content != original_content:
        file_path.write_text(modified_content, encoding="iso-8859-1")

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return enum_replacements, False

        utils.log(
            f"{enum_replacements :4d} changes written to: {file_path}", severity="INFO"
        )
        return enum_replacements, True

    return enum_replacements, False


def replace_fbs_and_types(file_path: Path, fb_mapping, type_mapping):
    """
    Replace function block calls and types in a file based on the provided mappings.
    """
    if any(part in {"AsOpcUac", "AsOpcUas"} for part in file_path.parts):
        return 0, 0, False

    original_hash = utils.calculate_file_hash(file_path)
    original_content = utils.read_file(Path(file_path))
    modified_content = original_content
    fb_replacements = 0
    type_replacements = 0

    # Replace function blocks
    for old_fb, new_fb in fb_mapping.items():
        pattern = rf"\b{re.escape(old_fb)}\b"
        replacement = new_fb
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        fb_replacements += num_replacements

    # Replace types
    for old_typ, new_typ in type_mapping.items():
        pattern = rf"\b{re.escape(old_typ)}\b"
        replacement = new_typ
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        type_replacements += num_replacements

    if modified_content != original_content:
        file_path.write_text(encoding="iso-8859-1")

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return fb_replacements, type_replacements, False

        utils.log(
            f"{fb_replacements + type_replacements:4d} changes written to: {file_path}",
            severity="INFO",
        )
        return fb_replacements, type_replacements, True

    return fb_replacements, type_replacements, False


def check_for_library(project_path: Path, library_names):
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
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    apj_file = utils.get_and_check_project_file(project_path)

    utils.log(f"Project path validated: {project_path}")
    utils.log(f"Using project file: {apj_file}\n")

    project_path = Path(project_path)
    library_names = ["AsOpcUac", "AsOpcUas"]
    found_libraries = check_for_library(project_path, library_names)

    utils.log(
        "This script will search for usages of AsOpcUac and AsOpcUas function blocks, types and enumerators and update the naming.",
        severity="INFO",
    )
    utils.log(
        "Before proceeding, make sure you have a backup or are using version control (e.g., Git).",
        severity="WARNING",
    )

    if not found_libraries:
        utils.log("Neither AsOpcUac nor AsOpcUas libraries found.", severity="INFO")
        proceed = utils.ask_user(
            "Do you want to proceed with replacing functions and constants anyway? (y/n) [y]: ",
            extra_note="After conversion, the project will no longer compile in Automation Studio 4.",
        )
        if proceed != "y":
            utils.log("Operation cancelled. No changes were made.", severity="WARNING")
            return
    else:
        utils.log(f"Libraries found: {', '.join(found_libraries)}.", severity="INFO")
        proceed = utils.ask_user(
            "Do you want to continue? (y/n) [y]: ",
            extra_note="After conversion, the project will no longer compile in Automation Studio 4.",
        )
        if proceed != "y":
            utils.log("Operation cancelled. No changes were made.", severity="WARNING")
            return

    fb_mapping = {
        "UA_EventItemOperate": "UA_EventItemOperateList",
        "UA_EventItemRemove": "UA_EventItemRemoveList",
        "UA_GetNamespaceIndex": "UA_NamespaceGetIndex",
        "UA_MonitoredItemAdd": "UA_MonitoredItemAddList",
        "UA_MonitoredItemRemove": "UA_MonitoredItemRemoveList",
        "UA_MonitoredItemOperate": "UA_MonitoredItemOperateList",
        "UaClt_ReadBulk": "BrUa_ReadBulk",
        "UaClt_WriteBulk": "BrUa_WriteBulk",
    }

    type_mapping = {
        "UAArrayLength": "BrUaArrayLength",
        "UAByteString": "BrUaByteString",
        "UADataValue": "BrUaDataValue",
        "UAEUInformation": "BrUaEUInformation",
        "UAMethodArgument": "BrUaMethodArgument",
        "UAMonitoringParameters": "UAMonitoringParameter",
        "UAMonitoringSettings": "UAMonitoringParameter",
        "UANoOfElements": "BrUaNoOfElements",
        "UARange": "BrUaRange",
        "UATimeZoneData": "BrUaTimeZoneDataType",
        "UAVariantType": "BrUaVariantType",
    }

    enum_mapping = {
        "UAAttributeId": "UAAttributeID",
        "UAIdentifierType_String": "UAIT_String",
        "UAIdentifierType_Numeric": "UAIT_Numeric",
        "UAIdentifierType_GUID": "UAIT_GUID",
        "UAIdentifierType_Opaque": "UAIT_Opaque",
        "UASecurityMsgMode_": "UASMM_",
        "UASecurityPolicy_": "UASP_",
        "UAVariantType_": "BrUaVariantType_",
        "UADeadbandType_None": "UADT_None",
        "UADeadbandType_Absolute": "UADT_Absolute",
        "UADeadbandType_Percentt": "UADT_Percentt",
    }

    logical_path = Path(project_path) / "Logical"
    total_function_replacements = 0
    total_enums_replacements = 0
    total_type_replacements = 0
    total_files_changed = 0

    # Loop through the files in the "Logical" directory and process .st, .c, .cpp and .ab files
    for file_path in logical_path.rglob("*"):
        if file_path.suffix in {".st", ".c", ".cpp", ".ab"}:
            enum_replacements, changed = replace_enums(file_path, enum_mapping)
            if changed:
                total_enums_replacements += enum_replacements
                total_files_changed += 1
        elif file_path.suffix in {".typ", ".var", ".fun"}:
            function_replacements, type_replacements, changed = replace_fbs_and_types(
                file_path, fb_mapping, type_mapping
            )
            if changed:
                total_type_replacements += type_replacements
                total_function_replacements += function_replacements
                total_files_changed += 1

    utils.log("─" * 80 + "\nSummary:")
    utils.log(f"Total function blocks replaced: {total_function_replacements}")
    utils.log(f"Total enumerators replaced: {total_enums_replacements}")
    utils.log(f"Total types replaced: {total_type_replacements}")
    utils.log(f"Total files changed: {total_files_changed}")

    if (
        total_function_replacements == 0
        and total_enums_replacements == 0
        and total_type_replacements == 0
    ):
        utils.log("No functions or constants needed to be replaced.", severity="INFO")
    else:
        utils.log("Replacement completed successfully.", severity="INFO")


if __name__ == "__main__":
    main()
