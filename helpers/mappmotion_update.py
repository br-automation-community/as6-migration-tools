# The mappMotion libraries have been updated for standardisation and correction reasons
# To migrate a project from an older mappMotion to mappMotion 6.x, modifications to the program are necessary.
import argparse
import os
import re
from pathlib import Path

from utils import utils


def warn_inputs(file_path: Path, item_mappings):
    """
    Warn about enumerators and FB-inputs in a file based on the provided mappings.
    """

    original_content = utils.read_file(file_path)

    for old_item, new_item in item_mappings.items():
        pattern = re.escape(old_item)
        matches = re.findall(pattern, original_content)
        if matches:
            utils.log(
                f"Found usages of '{old_item}', needs replacing with '{new_item}' "
                "- skipping auto-replacement due to possible functionality change",
                when="AS6",
                severity="WARNING",
            )


def replace_enums(file_path: Path, enum_mapping, verbose=False):
    """
    Replace enumerators in a file based on the provided mappings.
    """

    original_hash = utils.calculate_file_hash(file_path)
    original_content = utils.read_file(file_path)
    modified_content = original_content
    enum_replacements = 0

    # Replace enums
    for old_const, new_const in enum_mapping.items():
        pattern = re.escape(old_const)
        replacement = new_const
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        if num_replacements > 0 and verbose:
            utils.log(
                f"Replaced {num_replacements} occurance(s) of '{old_const}' with '{new_const}'",
                severity="INFO",
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


def replace_inputs(file_path: Path, input_mapping, verbose=False):
    """
    Replace various FUB-inputs in code based on the provided mappings
    """
    original_hash = utils.calculate_file_hash(file_path)
    original_content = utils.read_file(file_path)
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
        if num_replacements > 0 and verbose:
            utils.log(
                f"Replaced {num_replacements} occurance(s) of '{old_input}' with '{old_input}'",
                severity="INFO",
            )
        input_replacements += num_replacements

    if modified_content != original_content:
        file_path.write_text(modified_content, encoding="iso-8859-1")
        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return input_replacements, False

        log(
            f"{input_replacements:4d} change(s) written to: {file_path}",
            severity="INFO",
        )
        return input_replacements, True

    return input_replacements, False


def replace_fbs_and_types(
    file_path: Path, fb_mapping, type_mapping, fb_removal_mapping, verbose=False
):
    """
    Replace function block calls and types in a file based on the provided mappings.
    """

    original_hash = utils.calculate_file_hash(file_path)
    original_content = utils.read_file(file_path)
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
        if num_replacements > 0 and verbose:
            utils.log(
                f"Replaced {num_replacements} instance(s) of FB '{old_fb}' with '{new_fb}'",
                severity="INFO",
            )
        fb_replacements += num_replacements

    for old_fb, new_fb in fb_removal_mapping.items():
        pattern = rf"\b{re.escape(old_fb)}\b"
        replacement = new_fb
        if re.search(pattern, modified_content):
            if "." in replacement:
                parts = replacement.split(".")
                utils.log(
                    f"Found usage(s) of '{old_fb}', the functionality is now covered by the "
                    f"element '{parts[1]}' of the FB '{parts[0]}' "
                    "- skipping auto-replacement due to expected functionality change",
                    when="AS6",
                    severity="MANDATORY",
                )
            else:
                utils.log(
                    f"Found usage(s) of '{old_fb}', the functionality is now covered by the FB '{new_fb}'"
                    "- skipping auto-replacement due to expected functionality change",
                    when="AS6",
                    severity="MANDATORY",
                )

    # Replace types
    for old_type, new_type in type_mapping.items():
        pattern = rf"\b{re.escape(old_type)}\b"
        replacement = new_type
        modified_content, num_replacements = re.subn(
            pattern, replacement, modified_content
        )
        if num_replacements > 0 and verbose:
            utils.log(
                f"Replaced {num_replacements} instance(s) of type '{old_type}' with '{new_type}'",
                severity="INFO",
            )
        type_replacements += num_replacements

    if modified_content != original_content:
        file_path.write_text(modified_content, encoding="iso-8859-1")

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return fb_replacements, type_replacements, False

        utils.log(
            f"{fb_replacements + type_replacements:4d} change(s) written to: {file_path}",
            severity="INFO",
        )
        return fb_replacements, type_replacements, True

    return fb_replacements, type_replacements, False


def check_for_library(project_path, library_names):
    """
    Checks if any specified library is used in the project.
    """
    pkg_file = Path(project_path) / "Logical" / "Libraries" / "Package.pkg"
    if not pkg_file.is_file():
        utils.log(
            f"Error: Could not find Package.pkg file in: {pkg_file}", severity="ERROR"
        )
        return []

    content = utils.read_file(pkg_file)
    return [lib for lib in library_names if lib in content]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Updates mappMotion in regards to FBs, Enums, Types, ..."
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        type=str,
        default=os.getcwd(),
        help="Automation Studio 4.x path containing *.apj file",
    )
    parser.add_argument("-v", "--verbose", action="store_true", required=False)

    return parser.parse_args()


def main():
    args = parse_args()
    project_path = args.project_path
    apj_file = utils.get_and_check_project_file(project_path)

    utils.log(f"Project path validated: {project_path}")
    utils.log(f"Using project file: {apj_file}\n")

    library_names = ["McAxis", "MpAxis", "McBase", "McAcpAx", "McAcpTrak", "McAcpAx"]
    found_libraries = check_for_library(project_path, library_names)

    utils.log(
        "This script will search for usages of mappMotion function blocks, types and enumerators and update the naming.",
        severity="INFO",
    )
    utils.log(
        "Before proceeding, make sure you have a backup or are using version control (e.g., Git).",
        severity="WARNING",
    )

    if not found_libraries:
        utils.log(
            "None of the libraries supported by the script were found.", severity="INFO"
        )
        proceed = utils.ask_user(
            "Do you want to proceed with replacing functions and constants anyway? (y/n) [y]: ",
            extra_note="After conversion, the project will no longer compile in Automation Studio 4.",
        )
        if proceed not in ("", "y"):
            utils.log("Operation cancelled. No changes were made.", severity="WARNING")
            return
    else:
        utils.log(f"Libraries found: {', '.join(found_libraries)}.\n", severity="INFO")
        proceed = utils.ask_user(
            "Do you want to continue? (y/n) [y]: ",
            extra_note="After conversion, the project will no longer compile in Automation Studio 4.",
        )
        if proceed not in ("", "y"):
            utils.log("Operation cancelled. No changes were made.", severity="WARNING")
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
        "McAcpTrakAdvSecAddShWithMovType": "McAcpTrakAdvSecAddShuttleType",
    }

    fb_mapping = {
        "MC_BR_CamAutomatSetPar_AcpAx": "MC_BR_CamAutomatSetPar",
        "MC_BR_CamAutomatGetPar_AcpAx": "MC_BR_CamAutomatGetPar",
        "MC_BR_ShSetUserId_AcpTrak": "MC_BR_ShSetUserID_AcpTrak",
        "MC_BR_TrgPointGetInfo_AcpTrak": "MC_BR_TrgPointReadInfo_AcpTrak",
        "MC_BR_SecAddShWithMov_AcpTrak": "MC_BR_SecAddShuttle_AcpTrak",
        "MC_BR_AsmGetShuttleSel_AcpTrak": "MC_BR_AsmGetShuttle_AcpTrak",
        "MC_BR_SecGetShuttleSel_AcpTrak": "MC_BR_SecGetShuttle_AcpTrak",
    }

    fb_removal_mapping = {
        "MC_BR_AsmSegGrpPowerOn_AcpTrak": "MC_BR_AsmPowerOn_AcpTrak.SegmentGroup",
        "MC_BR_AsmSegGrpPowerOff_AcpTrak": "MC_BR_AsmPowerOff_AcpTrak.SegmentGroup",
    }

    enum_mapping = {
        "mcAFDCSACOPOSMULTIDO_SS1X111": "mcAFDCSACOPOSMULTIDO_SS2X111",
        "mcAFDCSACOPOSMULTIDO_SS1X113": "mcAFDCSACOPOSMULTIDO_SS2X113",
        "mcAFDCSACOPOSMULTIDO_SS1X115": "mcAFDCSACOPOSMULTIDO_SS2X115",
        "mcAFDCSACOPOSMULTIDO_SS1X116": "mcAFDCSACOPOSMULTIDO_SS2X116",
    }

    logical_path = Path(project_path) / "Logical"
    total_input_replacements = 0
    total_function_replacements = 0
    total_enums_replacements = 0
    total_type_replacements = 0
    total_files_changed = 0

    # Loop through the files in the "Logical" directory and process .st, .c, .cpp and .ab files

    for file_path in logical_path.rglob("*"):
        # For now, we skip all libraries, ideally we would also search and replace in user libraries
        if "Libraries" in file_path.parts:
            continue
        if file_path.suffix in {".st", ".c", ".cpp", ".ab"}:
            warn_inputs(file_path, input_mapping_warning)
            enum_replacements, changed = replace_enums(
                file_path, enum_mapping, args.verbose
            )
            if changed:
                total_enums_replacements += enum_replacements
                total_files_changed += 1
            input_replacements, changed = replace_inputs(
                file_path, input_mapping, args.verbose
            )
            if changed:
                total_input_replacements += input_replacements
                total_files_changed += 1
        elif file_path.suffix in {".typ", ".var", ".fun"}:
            function_replacements, type_replacements, changed = replace_fbs_and_types(
                file_path, fb_mapping, type_mapping, fb_removal_mapping, args.verbose
            )
            if changed:
                total_type_replacements += type_replacements
                total_function_replacements += function_replacements
                total_files_changed += 1

    utils.log("─" * 80 + "\nSummary:")
    utils.log(f"Total function blocks replaced: {total_function_replacements}")
    utils.log(f"Total function block inputs replaced: {total_input_replacements}")
    utils.log(f"Total enumerators replaced: {total_enums_replacements}")
    utils.log(f"Total types replaced: {total_type_replacements}")
    utils.log(f"Total files changed: {total_files_changed}")

    if all(
        count == 0
        for count in [
            total_function_replacements,
            total_enums_replacements,
            total_type_replacements,
            total_input_replacements,
        ]
    ):
        utils.log(
            "No functions, inputs or constants needed to be replaced.", severity="INFO"
        )
    else:
        utils.log("Replacement completed successfully.", severity="INFO")


if __name__ == "__main__":
    main()
