"""
Detect legacy mappView WDK (Widget Development Kit) usage.

Rule of thumb:
- Under the project's Logical tree, look for any 'mappView/Widgets' folder.
- If ANY folder at or below that Widgets root contains BOTH a '.js' file and a '.html' file
  in the same folder, the project is considered to be using WDK.
- As soon as we find the first such folder, we stop scanning (performance).

Action:
- Emit a MANDATORY AS6 warning with guidance to migrate to WDTC (Widget Development Tool Chain)
  and provide a link to the B&R community.
"""

from pathlib import Path
from typing import Iterator, Optional
from enum import Enum
import xml.etree.ElementTree as ET

class WidgetLibraryType(Enum):
    WDK = "WDK"
    WDTC = "WDTC"
    USER_WIDGET_LIB_4 = "User Widget Library 4"
    USER_WIDGET_LIB_6 = "User Widget Library 6"


def _find_widgets_roots(logical_path: Path) -> Iterator[Path]:
    """
    Yield all 'Widgets' directories under any 'mappView' folder in the Logical tree.
    """
    if not logical_path or not logical_path.exists():
        return
    # Search for 'mappView' folders anywhere below Logical, then append 'Widgets'
    for mv in logical_path.rglob("mappView"):
        widgets = mv / "Widgets"
        if widgets.is_dir():
            yield widgets


def _find_first_wdk_folder(widgets_root: Path) -> Optional[Path]:
    """
    Return the first folder (any depth under the given Widgets root, including the root)
    that contains BOTH a .js and a .html file. If none found, return None.
    Avoid multiple directory listings by storing the folders
    """
    already_checked = set()
    for js_file in widgets_root.rglob("*.js"):
        folder = js_file.parent
        if folder in already_checked:
            continue
        if list(folder.glob("*.html")):
            return folder
        already_checked.add(folder)
    return None

def _detect_widget_library_type(widget_lib_path: Path) -> Optional[WidgetLibraryType]:
    """
    Detect the type of widget library by the path to the base folder of the widget library.
    Returns one of the WidgetLibraryType enum values.

    For WDK & WDTC:
    - In base folder: "mappView/Widgets/{library_name}", a file "WidgetLibrary.mapping" should exist.
    - To diff WDK & WDTC, the file "WidgetLibrary.mapping" in WDTC each "Mapping" node as a attribute "oType", that didn't exist in WDK.

    For Widget Library 4 & 6:
    - In base folder: "mappView/Widgets/{library_name}", a file "Description.widgetlibrary" should exist.
    - To diff 4 & 6, we compare the "version" attribute in the file (it's mappView version)
    """

    if not widget_lib_path or not widget_lib_path.exists() or not widget_lib_path.is_dir():
        return None

    mapping_file = widget_lib_path / "WidgetLibrary.mapping"
    if mapping_file.exists():
        # Parse xml file WidgetLibrary.mapping and search for the first "Mapping" in the Mapping node test if a <oType> attribute exists
        tree = ET.parse(mapping_file)
        root = tree.getroot()
        mapping_node = root.find("Mapping")
        if mapping_node is not None and mapping_node.get("oType") is not None:
            return WidgetLibraryType.WDTC
        elif mapping_node is not None:
            return WidgetLibraryType.WDK


    description_file = widget_lib_path / "Description.widgetlibrary"
    if description_file.exists():
        with description_file.open() as f:
            content = f.read()
            if 'version="5.' in content:
                return WidgetLibraryType.USER_WIDGET_LIB_4
            elif 'version="6.' in content:
                return WidgetLibraryType.USER_WIDGET_LIB_6

    return None


def check_widget_lib_usage(logical_path: Path, log, verbose: bool = False) -> None:
    """
    Detect usage of the legacy mappView *WDK* (Widget Development Kit) or User widget libraries and warn that it
    must be migrated to *WDTC* (Widget Development Tool Chain) in AS6.

    Detection:
    - Look for a 'Widgets' folder under any 'mappView' directory inside the project's 'Logical' tree.
    - For each directory under 'Widgets', detect the type of the widget libraries (WDK, WDTC, User Widget Library 4, User Widget Library 6).

    Logging:
    - Severity: MANDATORY (WDK) / WARNING (User Widget Libraries 4)
    - Scope: AS6
    - Include a community link for WDTC migration info.
    - Log path to the library folder.
    """
    if verbose:
        log("Checking for legacy mappView WDK and User widget library usage...")

    widgets_roots = list(_find_widgets_roots(logical_path))
    if not widgets_roots:
        if verbose:
            log("No 'mappView/Widgets' folders found under Logical.", severity="INFO")
        return
    nb_lib_to_change_found: int = 0
    for root in widgets_roots:
        libraries_folder: list[Path] = [f for f in root.iterdir() if f.is_dir()]
        for lib_path in libraries_folder:
            rel = lib_path.relative_to(logical_path)
            lib_name = lib_path.name
            lib_type = _detect_widget_library_type(lib_path)
            if lib_type != WidgetLibraryType.USER_WIDGET_LIB_6 and lib_type != WidgetLibraryType.WDTC:
                nb_lib_to_change_found += 1

            if lib_type == WidgetLibraryType.WDK:
                if verbose:
                    log(f"Found WDK library: {lib_name} ({rel})")
                
                log(
                    f"Widget library {lib_name} ({rel}) appears to be a WDK (Widget Development Kit) library, which is deprecated and no longer supported in AS6."
                    "\nFor more information, visit the B&R Community: https://community.br-automation.com/c/wdtc/10",
                    when="AS6",
                    severity="MANDATORY"
                )
            elif lib_type == WidgetLibraryType.WDTC:
                if verbose:
                    log(f"Found WDTC library: {lib_name} ({rel})")
            elif lib_type == WidgetLibraryType.USER_WIDGET_LIB_4:
                if verbose:
                    log(f"Found User Widget Library 4: {lib_name} ({rel})")
                
            elif lib_type == WidgetLibraryType.USER_WIDGET_LIB_6:
                if verbose:
                    log(f"Found User Widget Library 6: {lib_name} ({rel})")

    if nb_lib_to_change_found == 0:
        if verbose:
            log("No WDK usage or User Widget Library detected in mappView/Widgets.", severity="INFO")
