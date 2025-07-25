import argparse
import os
import sys
from pathlib import Path

from lxml import etree

from utils import utils


def add_mapp_package(
    config_folder_path, subfolders, folder, package_name, package_type
):
    """
    Adds a mapp package (mappServices, mappMotion, mappView) to the cpu.pkg file and creates the folder structure.

    Args:
        config_folder_path (str): Path to the config folder
        subfolders (list): List of subfolders in the config folder
        folder (str): Name of the current folder being processed
        package_name (str): Name of the mapp package (e.g., 'mappServices', 'mappMotion', 'mappView')
        package_type (str):The package type to use for the attribute "PackageType" in Package.pkg
    """
    utils.log(f"\nStart fixing {package_name}")

    # Try to open and parse cpu.pkg as XML
    cpu_pkg_path = Path(config_folder_path) / subfolders[0] / "cpu.pkg"
    if cpu_pkg_path.exists():
        try:
            tree = etree.parse(cpu_pkg_path)
            root = tree.getroot()

            # Try to find Objects node with different namespace approaches
            objects_node = None

            # Method 1: Try with default namespace
            ns_default = {"ns": "http://br-automation.co.at/AS/Cpu"}
            objects_node = root.find("ns:Objects", ns_default)

            # Method 2: If not found, try without namespace (for files with xmlns:ns0)
            if objects_node is None:
                objects_node = root.find("Objects")

            # Method 3: If still not found, try with ns0 prefix
            if objects_node is None:
                ns_prefixed = {"ns0": "http://br-automation.co.at/AS/Cpu"}
                objects_node = root.find("ns0:Objects", ns_prefixed)

            # Method 4: Last resort - search by local name (ignoring namespace)
            if objects_node is None:
                for child in root:
                    if child.tag.endswith("Objects"):
                        objects_node = child
                        break

            if objects_node is not None:
                utils.log_v(f"Found Objects node in cpu.pkg in {folder}")

                # Check if package object already exists
                existing_package = None

                # Try different methods to find Object elements
                object_elements = objects_node.findall("ns:Object", ns_default)
                if not object_elements:
                    object_elements = objects_node.findall("Object")
                if not object_elements:
                    ns_prefixed = {"ns0": "http://br-automation.co.at/AS/Cpu"}
                    object_elements = objects_node.findall("ns0:Object", ns_prefixed)
                if not object_elements:
                    # Last resort - find by local name
                    object_elements = [
                        child for child in objects_node if child.tag.endswith("Object")
                    ]

                for obj in object_elements:
                    if obj.text == package_name and obj.get("Type") == "Package":
                        existing_package = obj
                        utils.log_v(
                            f"{package_name} entry already exists in cpu.pkg in {folder}"
                        )
                        break

                if existing_package is None:
                    # Create new element without namespace prefix
                    new_object = etree.SubElement(objects_node, "Object")
                    new_object.set("Type", "Package")
                    new_object.text = package_name

                    # Save with pretty formatting
                    tree.write(
                        cpu_pkg_path,
                        encoding="utf-8",
                        xml_declaration=True,
                        pretty_print=True,
                    )
                    utils.log_v(f"Added {package_name} object to cpu.pkg in {folder}")
                else:
                    utils.log_v(
                        f"{package_name} object already exists in cpu.pkg in {folder}"
                    )
            else:
                utils.log("Objects node not found in cpu.pkg")
        except etree.ParseError as e:
            utils.log(f"Error parsing cpu.pkg XML in {folder}: {e}")
        except Exception as e:
            utils.log(f"Error opening cpu.pkg in {folder}: {e}")
    else:
        utils.log(f"cpu.pkg file not found in {config_folder_path}")

    # Check if package folder exists in the subfolders
    plc_folder_path = Path(config_folder_path) / subfolders[0] / package_name
    if plc_folder_path.exists():
        utils.log_v(f"Found {package_name} folder in {folder}")
        return True
    else:
        # Create package folder structure
        plc_folder_path.mkdir(parents=True, exist_ok=True)
        utils.log_v(f"No {package_name} folder found")
        utils.log_v(f"Created {package_name} directory: {plc_folder_path}")

        # Create Package.pkg file with specified content
        package_content = f"""<?xml version="1.0" encoding="utf-8"?><?AutomationStudio FileVersion="4.9"?><Package SubType="{package_type}" PackageType="{package_type}" xmlns="http://br-automation.co.at/AS/Package"><Objects /></Package>"""
        package_file_path = plc_folder_path / "Package.pkg"
        package_file_path.write_text(package_content, encoding="utf-8")

        utils.log_v(f"Created Package.pkg file in {package_file_path}")
        utils.log(f"{package_name} folder structure created successfully!")
        return False


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Creates non existing mapp folders")
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
    """
    Main function to add mapp folder structure to an Automation Studio project.
    """
    args = parse_args(sys.argv)
    project_path = args.project_path
    apj_file = utils.get_and_check_project_file(project_path)

    utils.set_verbose(args.verbose)

    utils.log(f"Project path validated: {project_path}")
    utils.log(f"Using project file: {apj_file}\n")

    # Get all folders in the Physical directory
    physical_path = Path(project_path) / "Physical"
    if not physical_path.is_dir():
        utils.log("Could not find Physical folder")
        return

    config_folders = [f for f in physical_path.iterdir() if f.is_dir()]
    for config_folder in config_folders:
        # Check if mappServices folder exists in the config folder directory
        utils.log(f"\nFound configuration folder: {config_folder.name}")

        # Check for sub folders in the config folder
        subfolders = [sf for sf in config_folder.iterdir() if sf.is_dir()]
        if not subfolders:
            continue

        # Add mappServices package
        mapp_services_exists = add_mapp_package(
            str(config_folder),
            subfolders,
            config_folder.name,
            "mappServices",
            "mappServices",
        )

        # Add mappMotion package
        mapp_motion_exists = add_mapp_package(
            str(config_folder),
            subfolders,
            config_folder.name,
            "mappMotion",
            "mappMotion",
        )

        # Add mappView package
        mapp_view_exists = add_mapp_package(
            str(config_folder),
            subfolders,
            config_folder.name,
            "mappView",
            "mappViewControl",
        )

    utils.log(
        f"\nPlease close and reopen the project in Automation Studio to see the changes."
    )


if __name__ == "__main__":
    main()
