import re

from utils import utils


def check_mapp_version(apj_path, log, verbose=False):
    """
    Checks mapp Services / mappMotion versions in the .apj and verifies required mapp folders
    per configuration. Respects referenced packages in cpu.pkg.
    """

    log("─" * 80 + "\nChecking mapp version in project file...")

    # --- Read .apj as plain text (robust vs. namespaces/BOM) ---
    txt = utils.read_file(apj_path)

    # --- Version detection (mapp Services & mappMotion 5.x) ---
    for line in txt.splitlines():
        if ("<mapp " in line and "Version=" in line) or (
            "<mappServices" in line and "Version=" in line
        ):
            m = re.search(r'Version="(\d+)\.(\d+)', line)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                version_str = f"{major}.{minor}"
                log(f"Detected Mapp Services version: {version_str}", severity="INFO")

                if major == 5 and minor < 20:
                    log(
                        "It is recommended to use a mapp Services version 5.20 or later for the conversion."
                        "\n - If a mapp Services version older than 5.20 is used, the correct conversion of all configuration parameters is not guaranteed."
                        "\n - Please update the mapp Services version in AS4 to 5.20 or later before migrating to AS6.",
                        when="AS4",
                        severity="MANDATORY",
                    )
                else:
                    log(
                        "The automatic mapp Services configuration upgrade is only available with mapp Services 6.0."
                        "\n - Please ensure the project is converted using AS6 and mapp Services 6.0 before upgrading to newer mapp versions.",
                        when="AS6",
                        severity="MANDATORY",
                    )

        if "<mappMotion " in line and 'Version="5.' in line:
            m = re.search(r'Version="(\d+)\.(\d+)', line)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                version_str = f"{major}.{minor}"
                log(f"Detected Mapp Motion version: {version_str}", severity="INFO")
                log(
                    "\nYou must first upgrade mappMotion to version 6.0 using 'Change runtime versions' in AS6."
                    "\nOnce mappMotion 6.0 is set, a dialog will assist with converting all project configurations.",
                    when="AS6",
                    severity="MANDATORY",
                )

    # --- Motion choice detection (plain text; no XML parsing) ---
    has_acp10 = (
        re.search(r"<\s*Acp10[A-Za-z0-9_]*\b", txt, flags=re.IGNORECASE) is not None
    )
    has_mappmotion = (
        re.search(r"<\s*mappMotion\b", txt, flags=re.IGNORECASE) is not None
    )
    if has_mappmotion and not has_acp10:
        motion_choice = "mappMotion"
    elif has_acp10 and not has_mappmotion:
        motion_choice = "acp10"
    elif not has_acp10 and not has_mappmotion:
        motion_choice = "none"
    else:
        motion_choice = "mappMotion"  # prefer ACP10 if both somehow appear

    # --- Determine which mapp folders are required to exist for this project ---
    required_mapp_folders = ["mappServices", "mappView"]
    if motion_choice == "mappMotion":
        required_mapp_folders += [
            "mappMotion",
            "mappCockpit",
        ]  # cockpit only relevant with mappMotion

    # --- Check Physical/<Config> for required folders (respect references in cpu.pkg) ---
    physical_path = apj_path.parent / "Physical"
    if not physical_path.is_dir():
        log(f"Could not find Physical in {apj_path.parent}", severity="ERROR")
        return

    grouped_results = {}
    config_folders = [f for f in physical_path.iterdir() if f.is_dir()]
    for config_folder in config_folders:
        # 1) Detect present packages by looking for .../<PackageName>/Package.pkg anywhere under the config
        found = {name: False for name in required_mapp_folders}
        for pkg_file in config_folder.rglob("Package.pkg"):
            pkg_parent = pkg_file.parent.name
            if pkg_parent in found:
                found[pkg_parent] = True

        missing = {name for name, ok in found.items() if not ok}
        if not missing:
            continue

        # 2) If missing, try to resolve via cpu.pkg references (case-insensitive name for the file)
        def _find_cpu_pkg_path(cfg_dir):
            for sub in sorted(cfg_dir.iterdir()):
                if not sub.is_dir():
                    continue
                for candidate in ("cpu.pkg", "Cpu.pkg", "CPU.pkg"):
                    p = sub / candidate
                    if p.exists():
                        return p
            return None

        cpu_pkg_path = _find_cpu_pkg_path(config_folder)
        if cpu_pkg_path:
            cpu_txt = utils.read_file(cpu_pkg_path)
            # Remove from missing if Reference="true" -> ...\<name>\Package.pkg
            for name in list(missing):
                if re.search(
                    rf'Reference\s*=\s*"true".*?{re.escape(name)}[\\/]+Package\.pkg',
                    cpu_txt,
                    flags=re.IGNORECASE | re.DOTALL,
                ):
                    missing.discard(name)

        if missing:
            grouped_results[config_folder.name] = missing

    # --- Report consolidated result (only if something is still missing) ---
    if grouped_results:
        message = (
            "\nSome configurations are missing one or more of the required mapp folders"
        )
        for config_name, missing_mapp_folders in grouped_results.items():
            message += (
                f"\n  - '{config_name}': {', '.join(sorted(missing_mapp_folders))}"
            )
        message += "\n\nYou can use the script 'helpers/create_mapp_folders.py' to create the mapp folder structure in the Physical directory."
        log(message, when="AS4", severity="MANDATORY")
