# The mappMotion libraries have been updated for standardisation and correction reasons
# To migrate a project from an older mappMotion to mappMotion 6.x, modifications to the program are necessary.
import os
import re
import sys

from utils import utils


def warn_enums_and_inputs(file_path, item_mappings):
    """
    Warn about enumerators and FB-inputs in a file based on the provided mappings.
    """

    with open(file_path, "r", encoding="iso-8859-1", errors="ignore") as f:
        original_content = f.read()

    for item in item_mappings:
        for old_item, new_item in item.items():
            pattern = re.escape(old_item)
            matches = re.findall(pattern, original_content)
            if matches:
                print(
                    f"Found usages of '{old_item}', needs replacing with '{new_item}' "
                    "- skipping auto-replacement due to possible functionality change"
                )


def replace_inputs(file_path, input_mapping):
    """
    Replace various FUB-inputs in code based on the provided mappings
    """
    original_hash = utils.calculate_file_hash(file_path)

    with open(file_path, "r", encoding="iso-8859-1", errors="ignore") as f:
        original_content = f.read()

    modified_content = original_content
    input_replacements = 0

    # Replace function inputs
    for old_input, new_input in input_mapping.items():
        # We add the leading "." on both, old and new, to be sure to only replace elements of FBs
        old_input = f".{old_input}"
        replacement = f".{new_input}"
        pattern = rf"\b{re.escape(old_input)}\b"
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        input_replacements += num_replacements

    if modified_content != original_content:
        with open(file_path, "w", encoding="iso-8859-1") as f:
            f.write(modified_content)

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return input_replacements, False

        print(f"{input_replacements:4d} changes written to: {file_path}")
        return input_replacements, True

    return input_replacements, False


def replace_fbs_and_types(file_path, fb_mapping, type_mapping, fb_removal_mapping):
    """
    Replace function block calls and types in a file based on the provided mappings.
    """

    original_hash = utils.calculate_file_hash(file_path)

    with open(file_path, "r", encoding="iso-8859-1", errors="ignore") as f:
        original_content = f.read()

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

    for old_fb, new_fb in fb_removal_mapping.items():
        pattern = rf"\b{re.escape(old_fb)}\b"
        replacement = new_fb
        if re.search(pattern, modified_content):
            if "." in replacement:
                parts = replacement.split(".")
                print(
                    f"Found usages of '{old_fb}', the functionality is now covered by the "
                    f"element '{parts[1]}' of the FB '{parts[0]}' "
                    "- skipping auto-replacement due to expected functionality change"
                )
            else:
                print(
                    f"Found usages of '{old_fb}', the functionality is now covered by the FB '{new_fb}'"
                    "- skipping auto-replacement due to expected functionality change"
                )

    # Replace types
    for old_typ, new_typ in type_mapping.items():
        pattern = rf"\b{re.escape(old_typ)}\b"
        replacement = new_typ
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        type_replacements += num_replacements

    if modified_content != original_content:
        with open(file_path, "w", encoding="iso-8859-1") as f:
            f.write(modified_content)

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return fb_replacements, type_replacements, False

        print(
            f"{fb_replacements + type_replacements:4d} changes written to: {file_path}"
        )
        return fb_replacements, type_replacements, True

    return fb_replacements, type_replacements, False


def check_for_library(project_path, library_names):
    """
    Checks if any specified library is used in the project.
    """
    pkg_file = os.path.join(project_path, "Logical", "Libraries", "Package.pkg")
    if not os.path.isfile(pkg_file):
        print(f"Error: Could not find Package.pkg file in: {pkg_file}")
        return []

    with open(pkg_file, "r", encoding="iso-8859-1", errors="ignore") as f:
        content = f.read()
        found_libraries = [lib for lib in library_names if lib in content]

    return found_libraries


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    apj_file = utils.get_and_check_project_file(project_path)

    print(f"Project path validated: {project_path}")
    print(f"Using project file: {apj_file}\n")

    library_names = ["McAxis", "MpAxis", "McBase", "McAcpAx"]
    found_libraries = check_for_library(project_path, library_names)

    print(
        "This script will search for usages of mappMotion function blocks, types and enumerators and update the naming.\n"
        "Before proceeding, make sure you have a backup or are using version control (e.g., Git).\n"
    )

    if __name__ == "__main__" and sys.stdin.isatty():

        if not found_libraries:
            print("None of the libraries supported by the script were found.\n")
            proceed = (
                input(
                    "Do you want to proceed with replacing functions and constants anyway? (y/n) [y]: "
                )
                .strip()
                .lower()
            )
            if proceed not in ("", "y"):
                print("Operation cancelled. No changes were made.")
                return
        else:
            print(f"Libraries found: {', '.join(found_libraries)}.\n")
            proceed = input("Do you want to continue? (y/n) [y]: ").strip().lower()
            if proceed not in ("", "y"):
                print("Operation cancelled. No changes were made.")
                return

    input_mapping = {
        "Parameter.AxesGroup": "Parameter.Component",
        "StandBy": "Standby",
        "DataAdress": "DataAddress",
        "Info.AutoTuneDone": "AutoTuneDone",
        "Info.MechDeviationCompState": "Info.AxisAdditionalInfo.MechDeviationCompState",
        "Info.AutoTuneState": "Info.AxisAdditionalInfo.AutoTuneState",
        "Info.CommunicationState": "Info.AxisAdditionalInfo.CommunicationState",
        "Info.StartupCount": "Info.AxisAdditionalInfo.StartupCount",
        "Info.DigitalInputStatus": "Info.AxisAdditionalInfo.DigitalInputStatus",
        "Info.PLCopenState": "Info.AxisAdditionalInfo.PLCopenState",
        "Info.ActualOffsetShift": "Info.Offset.ActualShift",
        "Info.OffsetValid": "Info.Offset.Valid",
        "Info.ActualPhaseShift": "Info.Phasing.ActualShift",
        "Info.PhasingValid": "Info.Phasing.Valid",
        "Common.AdvancedParameters.StartStateParam.StartState": "Common.StartStateParam.StartState",
        "Common.AdvancedParameters.StartStateParam.MasterStartRelPos": "Common.StartStateParam.MasterStartPositionInCam",
        "CompensationParameters.MasterCamLeadIn": "AdvancedParameters.MasterCamLeadIn",
        "AdvancedParameters.ShuttleIndex": "AdvancedParameters.ShuttleID",
        "AssemblyInfo.ShuttlesCount": "AssemblyInfo.ShuttleCount.Count",
        "AssemblyInfo.ShuttlesInStandstillCount": "AssemblyInfo.ShuttleCount.InStandstill",
        "AssemblyInfo.ShuttlesInDisabledCount": "AssemblyInfo.ShuttleCount.InDisabled",
        "AssemblyInfo.ShuttlesInStoppingCount": "AssemblyInfo.ShuttleCount.InStopping",
        "AssemblyInfo.ShuttlesInErrorStopCount": "AssemblyInfo.ShuttleCount.InErrorStop",
        "AssemblyInfo.VirtualShuttlesCount": "AssemblyInfo.ShuttleCount.VirtualShuttles",
        "AssemblyInfo.ConvoysCount": "AssemblyInfo.ShuttleCount.Convoys",
        "AssemblyInfo.SegmentsInDisabledCount": "AssemblyInfo.SegmentCount.SegmentsInDisabled",
        "AssemblyInfo.SegmentsInStoppingCount": "AssemblyInfo.SegmentCount.SegmentsInStopping",
        "AssemblyInfo.SegmentsInErrorStopCount": "AssemblyInfo.SegmentCount.SegmentsInErrorStop",
        "Distance.Junction": "Distance.Diverter",
    }

    input_mapping_warning = {"StopMode": "AdvancedParameters.StopMode"}

    type_mapping = {
        "MpAxisCouplingRecoveryParType": "MpAxisRecoveryParType",
        "MpAxisSequencerRecoveryParType": "MpAxisRecoveryParType",
        "McAcpAxCamAutDefineType": "McCamAutDefineType",
    }

    fb_mapping = {
        "MC_BR_CamAutomatSetPar_AcpAx": "MC_BR_CamAutomatSetPar",
        "MC_BR_CamAutomatGetPar_AcpAx": "MC_BR_CamAutomatGetPar",
        "MC_BR_ShSetUserId_AcpTrak": "MC_BR_ShSetUserID_AcpTrak",
        "MC_BR_TrgPointGetInfo_AcpTrak": "MC_BR_TrgPointReadInfo_AcpTrak",
    }

    fb_removal_mapping = {
        "MC_BR_AsmSegGrpPowerOn_AcpTrak": "MC_BR_AsmPowerOn_AcpTrak.SegmentGroup",
        "MC_BR_AsmSegGrpPowerOff_AcpTrak": "MC_BR_AsmPowerOff_AcpTrak.SegmentGroup",
        "MC_BR_SecAddShWithMov_AcpTrak": "MC_BR_SecAddShuttle_AcpTrak",
        "MC_BR_AsmGetShuttleSel_AcpTrak": "MC_BR_AsmGetShuttle_AcpTrak",
        "MC_BR_SecGetShuttleSel_AcpTrak": "MC_BR_SecGetShuttle_AcpTrak",
    }

    enum_mapping_warn = {
        "mcAFDCSACOPOSMULTIDO_SS1X111": "mcAFDCSACOPOSMULTIDO_SS2X111",
        "mcAFDCSACOPOSMULTIDO_SS1X113": "mcAFDCSACOPOSMULTIDO_SS2X113",
        "mcAFDCSACOPOSMULTIDO_SS1X115": "mcAFDCSACOPOSMULTIDO_SS2X115",
        "mcAFDCSACOPOSMULTIDO_SS1X116": "mcAFDCSACOPOSMULTIDO_SS2X116",
    }

    logical_path = os.path.join(project_path, "Logical")
    total_input_replacements = 0
    total_function_replacements = 0
    total_enums_replacements = 0
    total_type_replacements = 0
    total_files_changed = 0

    # Loop through the files in the "Logical" directory and process .st, .c, .cpp and .ab files
    for root, _, files in os.walk(logical_path):
        for file in files:
            # For now we skip all libraries, ideally we would also search and replace in user libraries
            if "Libraries" in root:
                continue
            file_path = os.path.join(root, file)
            if file.endswith((".st", ".c", ".cpp", ".ab")):
                warn_enums_and_inputs(
                    file_path, (enum_mapping_warn, input_mapping_warning)
                )
                input_replacements, changed = replace_inputs(file_path, input_mapping)
                if changed:
                    total_input_replacements += input_replacements
                    total_files_changed += 1
            elif file.endswith((".typ", ".var", ".fun")):
                function_replacements, type_replacements, changed = (
                    replace_fbs_and_types(
                        file_path, fb_mapping, type_mapping, fb_removal_mapping
                    )
                )
                if changed:
                    total_type_replacements += type_replacements
                    total_function_replacements += function_replacements
                    total_files_changed += 1

    print("\nSummary:")
    print(f"Total function blocks replaced: {total_function_replacements}")
    print(f"Total function block inputs replaced: {total_input_replacements}")
    print(f"Total enumerators replaced: {total_enums_replacements}")
    print(f"Total types replaced: {total_type_replacements}")
    print(f"Total files changed: {total_files_changed}")

    if all(
        count == 0
        for count in [
            total_function_replacements,
            total_enums_replacements,
            total_type_replacements,
            total_input_replacements,
        ]
    ):
        print("No functions, inputs or constants needed to be replaced.")
    else:
        print("Replacement completed successfully.")


if __name__ == "__main__":
    main()
