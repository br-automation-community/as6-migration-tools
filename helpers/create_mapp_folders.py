import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from lxml import etree

from utils import utils

# --- Toggle for optional packages ---
# If you later want to exclude mappCockpit when using mappMotion, set this to False.
ENABLE_MAPP_COCKPIT = True


def log_v(message: str, verbose: bool = False) -> None:
    """Verbose logger that routes through utils.log."""
    if verbose:
        utils.log(message, severity="INFO")


# ---------------------------- XML helpers ---------------------------------


def _find_cpu_pkg_path(config_folder_path: str) -> Optional[Path]:
    """Return the path to cpu.pkg by searching first-level subfolders of the config.

    We avoid relying on subfolder order; pick the first subfolder containing cpu.pkg.
    """
    cfg = Path(config_folder_path)
    if not cfg.is_dir():
        return None
    # deterministic order
    for sub in sorted(cfg.iterdir()):
        if sub.is_dir():
            cand = sub / "cpu.pkg"
            if cand.exists():
                return cand
    return None


def _get_objects_node(root: etree._Element) -> Optional[etree._Element]:
    """Return the <Objects> node regardless of namespace quirks."""
    # Try default ns
    ns_default = {"cpu": root.nsmap.get(None)}
    if ns_default["cpu"]:
        node = root.find("cpu:Objects", ns_default)
        if node is not None:
            return node
    # Try no-ns / prefixed / by localname
    node = root.find("Objects")
    if node is not None:
        return node
    for child in root:
        if etree.QName(child).localname == "Objects":
            return child
    return None


def _scan_package_presence(
    cpu_pkg_path: Path, package_name: str
) -> Tuple[bool, bool, Optional[str]]:
    """Detect if a package exists locally and/or as a reference in cpu.pkg.

    Returns: (has_local_object, has_reference_object, reference_path_text)
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(cpu_pkg_path), parser)
    root = tree.getroot()
    objects_node = _get_objects_node(root)
    if objects_node is None:
        return False, False, None

    has_local = False
    has_ref = False
    ref_path = None
    for obj in objects_node:
        if etree.QName(obj).localname != "Object":
            continue
        if obj.get("Type") != "Package":
            continue
        text = (obj.text or "").strip()
        if obj.get("Reference", "").lower() == "true":
            # Normalize path and match against …\<package>\Package.pkg (allowing both / and \)
            path_txt = text.replace("/", "\\").lower()
            if f"\\{package_name.lower()}\\package.pkg" in path_txt:
                has_ref = True
                ref_path = text
        else:
            if text == package_name:
                has_local = True
    return has_local, has_ref, ref_path


def _ensure_package_locally(
    cpu_pkg_path: Path, package_name: str, package_type: str
) -> Tuple[bool, bool]:
    """
    Ensure the package has a local <Object> in cpu.pkg and a folder with Package.pkg.
    Returns: (created_object, created_folder)
    NOTE: This function is intentionally silent (no INFO logs). Caller handles messaging.
    """
    created_object = False
    created_folder = False

    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(cpu_pkg_path), parser)
    root = tree.getroot()
    ns_uri = root.nsmap.get(None)
    objects_node = _get_objects_node(root)
    if objects_node is None:
        raise RuntimeError("Objects node not found in cpu.pkg")

    # Detect existing local object (Type="Package", not a reference) with exact text match
    has_local = False
    for obj in objects_node:
        if etree.QName(obj).localname != "Object":
            continue
        if obj.get("Type") != "Package":
            continue
        if obj.get("Reference", "").lower() == "true":
            continue
        if (obj.text or "").strip() == package_name:
            has_local = True
            break

    # Create <Object> if missing
    if not has_local:
        new_obj = (
            etree.SubElement(objects_node, f"{{{ns_uri}}}Object")
            if ns_uri
            else etree.SubElement(objects_node, "Object")
        )
        new_obj.set("Type", "Package")
        new_obj.text = package_name
        tree.write(
            str(cpu_pkg_path), encoding="utf-8", xml_declaration=True, pretty_print=True
        )
        created_object = True

    # Ensure folder structure exists next to cpu.pkg
    plc_dir = cpu_pkg_path.parent
    pkg_dir = plc_dir / package_name
    if not pkg_dir.exists():
        pkg_dir.mkdir(parents=True, exist_ok=True)
        pkg_xml = (
            f'<?xml version="1.0" encoding="utf-8"?><?AutomationStudio FileVersion="4.9"?>'
            f'<Package SubType="{package_type}" PackageType="{package_type}" '
            f'xmlns="http://br-automation.co.at/AS/Package"><Objects /></Package>'
        )
        (pkg_dir / "Package.pkg").write_text(pkg_xml, encoding="utf-8")
        created_folder = True

    return created_object, created_folder


def add_mapp_package(
    config_folder_path: str,
    folder: str,
    package_name: str,
    package_type: str,
    verbose: bool = False,
) -> bool:
    """
    Add a mapp package (mappServices, mappMotion, mappView) to cpu.pkg and create folders —
    but *skip entirely* if the package is referenced in cpu.pkg.

    Returns True if the local package folder already existed (or exists via reference);
    False if we created it this run (or cpu.pkg not found).
    """
    # Single header line; details follow as bullets:
    utils.log(f"Checking {package_name} folder:", severity="INFO")

    cpu_pkg_path = _find_cpu_pkg_path(config_folder_path)
    if cpu_pkg_path is None:
        utils.log(
            f"- Skipping {package_name} in {folder}: cpu.pkg not found", severity="INFO"
        )
        return False

    try:
        # Detect presence and references
        has_local, has_ref, ref_path = _scan_package_presence(
            cpu_pkg_path, package_name
        )

        if has_ref:
            utils.log(
                f"- Skipping {package_name} in {folder}: referenced from {ref_path}",
                severity="INFO",
            )
            return True  # Treat as 'exists via reference'

        # At this point, we either have a local object or need to create it.
        before_folder_exists = (cpu_pkg_path.parent / package_name).exists()

        # Create local object/folder if needed
        created_object, created_folder = _ensure_package_locally(
            cpu_pkg_path, package_name, package_type
        )

        # Object result line
        if created_object:
            utils.log(
                f"- Object in cpu.pkg: created for {package_name}", severity="INFO"
            )
        else:
            if has_local:
                utils.log(
                    f"- Object in cpu.pkg: exists for {package_name}", severity="INFO"
                )
            else:
                utils.log(
                    f"- Object in cpu.pkg: not found and not created (unexpected)",
                    severity="INFO",
                )

        # Folder result lines
        pkg_dir = cpu_pkg_path.parent / package_name
        if created_folder:
            utils.log(f"- Folder: created -> {pkg_dir}", severity="INFO")
            utils.log(f"- File: created -> {pkg_dir / 'Package.pkg'}", severity="INFO")
        else:
            if pkg_dir.exists():
                utils.log(f"- Folder: exists -> {pkg_dir}", severity="INFO")
            else:
                utils.log(
                    f"- Folder: missing (unexpected) -> {pkg_dir}", severity="INFO"
                )

        exists_locally = pkg_dir.exists()
        return exists_locally or before_folder_exists

    except etree.ParseError as e:
        utils.log(f"- Error parsing cpu.pkg XML in {folder}: {e}", severity="ERROR")
    except Exception as e:
        utils.log(f"- Error handling cpu.pkg in {folder}: {e}", severity="ERROR")

    return False


# ----------------------- .apj motion detection -----------------------------


def detect_motion_choice(apj_path: str) -> str:
    """Return 'acp10', 'mappMotion', or 'none' based on TechnologyPackages in .apj.

    Namespace-agnostic and robust against BOM/formatting. Falls back to text search.
    """
    p = Path(apj_path)
    try:
        parser = etree.XMLParser(remove_blank_text=True, recover=True)
        tree = etree.parse(str(p), parser)
        root = tree.getroot()

        # Namespace-agnostic XPath (works regardless of default/prefixed ns)
        tps = root.xpath('//*[local-name()="TechnologyPackages"]')
        has_acp10 = False
        has_mappmotion = False
        if tps:
            tp = tps[0]
            # Look for any child whose local-name starts with 'Acp10'
            acp_nodes = tp.xpath('./*[starts-with(local-name(), "Acp10")]')
            if acp_nodes:
                has_acp10 = True
            # Explicit mappMotion tag
            mm_nodes = tp.xpath('./*[local-name()="mappMotion"]')
            if mm_nodes:
                has_mappmotion = True
        else:
            # Fallback: global scan ignoring namespaces
            if root.xpath('//*[starts-with(local-name(), "Acp10")]'):
                has_acp10 = True
            if root.xpath('//*[local-name()="mappMotion"]'):
                has_mappmotion = True

        # Final fallback: tolerant text search (covers odd encodings)
        if not has_acp10 and not has_mappmotion:
            txt = utils.read_file(p)
            has_acp10 = "<Acp10" in txt or "Acp10" in txt
            has_mappmotion = "<mappMotion" in txt

        if has_mappmotion and not has_acp10:
            return "mappMotion"
        if has_acp10 and not has_mappmotion:
            return "acp10"
        if not has_acp10 and not has_mappmotion:
            return "none"
        # If both (shouldn't happen), prefer ACP10 per either/or rule
        return "mappMotion"
    except Exception as e:
        # As a last resort, do a very cheap text probe
        txt = utils.read_file(p)
        if "<mappMotion" in txt:
            return "mappMotion"
        if "<Acp10" in txt or "Acp10" in txt:
            return "acp10"
        return "none"


# ------------------------------ CLI ---------------------------------------


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Creates non-existing mapp folders (reference-aware)"
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
    """Main: add mapp folder structure to an Automation Studio project, respecting references and motion tech choice."""
    args = parse_args(sys.argv)
    project_path = args.project_path
    apj_file = utils.get_and_check_project_file(project_path)

    utils.log(f"Project path validated: {project_path}")
    apj_full_path = (
        str(Path(project_path) / apj_file)
        if not Path(apj_file).is_absolute()
        else apj_file
    )
    utils.log(f"Using project file: {apj_full_path}")

    motion_choice = detect_motion_choice(apj_full_path)
    utils.log(f"Detected motion technology: {motion_choice}", severity="INFO")

    # Get all folders in the Physical directory
    physical_path = Path(project_path) / "Physical"
    if not physical_path.is_dir():
        utils.log("Could not find Physical folder", severity="ERROR")
        return

    config_folders = [f for f in physical_path.iterdir() if f.is_dir()]
    for config_folder in config_folders:
        utils.log("─" * 80)
        utils.log(f"Found configuration folder: {config_folder.name}", severity="INFO")

        # Skip if config contains no subfolder at all
        subfolders = [sf for sf in config_folder.iterdir() if sf.is_dir()]
        if not subfolders:
            continue

        # Always ensure mappServices (independent of motion choice)
        add_mapp_package(
            str(config_folder),
            config_folder.name,
            "mappServices",
            "mappServices",
            args.verbose,
        )

        # mappView (respect references)
        add_mapp_package(
            str(config_folder),
            config_folder.name,
            "mappView",
            "mappViewControl",
            args.verbose,
        )

        # mappMotion only if project uses mappMotion (never for ACP10 or none)
        if motion_choice == "mappMotion":
            add_mapp_package(
                str(config_folder),
                config_folder.name,
                "mappMotion",
                "mappMotion",
                args.verbose,
            )
            # Optional: mappCockpit (only alongside mappMotion, toggle via constant)
            if ENABLE_MAPP_COCKPIT:
                add_mapp_package(
                    str(config_folder),
                    config_folder.name,
                    "mappCockpit",
                    "mappCockpit",
                    args.verbose,
                )
        else:
            utils.log(
                f"Skipping mappMotion in {config_folder.name}: project uses '{motion_choice}'",
                severity="INFO",
            )

    utils.log("─" * 80)
    utils.log(
        "Please close and reopen the project in Automation Studio to see the changes.",
        severity="INFO",
    )


if __name__ == "__main__":
    main()
