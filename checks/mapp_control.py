import re
from lxml import etree
from pathlib import Path

from utils import utils


def check_mapp_control(apj_path: Path, log, verbose=False):
    """
    Checks if the project uses legacy MT<xxx> libraries that are now part of mappControl.
    """

    log("─" * 80 + "\nChecking mappControl usage...")

    project_root = apj_path.parent

    # 1. Check .apj file in root for mappControl
    if apj_path:
        try:
            tree = etree.parse(str(apj_path))
            root = tree.getroot()
            mapp_control = root.find(".//{*}mappControl")
            if mapp_control is not None:
                if verbose:
                    log("Project uses mappControl, nothing to do", severity="INFO")
                return
        except Exception as e:
            log(f"Failed to parse .apj file: {e}", severity="ERROR")

    # 2. Search for usages of libraries that are now contained in mappControl
    search_path = project_root / "Logical"

    found = set()
    libs = ["MTBasics", "MTLinAlg", "MTFilter", "MTLookup", "MTProfile"]
    for file in search_path.rglob("*.pkg"):
        content = utils.read_file(file)
        for lib in libs:
            if re.search(rf">{lib}<", content):
                found.add(lib)

    if found:
        output = "The project uses libraries that are now part of mappControl, which was not found in the project:"
        for lib in sorted(found):
            output += f"\n- {lib}"
        log(output, severity="INFO", when="AS6")
        log(
            "Please remove the libraries, download and add the mappControl Technology Package to the project before re-adding those libraries from there.",
            severity="MANDATORY",
            when="AS6",
        )
    elif verbose:
        log(
            "No libraries that are part of mappControl found, nothing to do",
            severity="INFO",
        )
