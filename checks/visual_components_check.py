from pathlib import Path

from lxml import etree

from utils import utils

XML_PARSER = etree.XMLParser(
    recover=True, ns_clean=True, remove_blank_text=True, huge_tree=True
)


def check_visual_components(apj_path: Path, log, verbose: bool = False):
    """
    Check for the use of VA_Textout and VA_wcTextout functions.
    """

    log(
        utils.section_header("visual-components", "Checking Visual Components usage...")
    )

    logical_path = apj_path.parent / "Logical"

    check_vc3(logical_path, log, verbose)
    check_vc4(logical_path, log, verbose)


def check_vc4(logical_path: Path, log, verbose: bool) -> None:
    """
    Check for used VC4 functions that require increased stack size.
    """

    results = utils.scan_files_parallel(
        logical_path, [".st", ".c", ".ab"], find_stack_functions
    )

    found = {}
    if results:
        for item in results:
            found.setdefault(item[1], set()).add(item[0])

    if found:
        output = ""
        for function, files in found.items():
            paths = "\n".join(
                f"- {Path(f).relative_to(logical_path.parent)}" for f in sorted(files)
            )
            output += f"\n\n{function} found in {len(files)} file(s):\n{paths}"

        log(
            "VA_Textout or VA_wcTextout functions found"
            "\n - VA_Textout and VA_wcTextout need increased stack in the task class."
            "\n - More info: community/VC4"
            "\n" + output,
            when="AS6",
            severity="WARNING",
        )
    elif verbose:
        log("No VA_Textout or VA_wcTextout functions found.", severity="VERBOSE")


def check_vc3(logical_path: Path, log, verbose: bool = False) -> None:
    """
    Check for VC3 usage in the project.
    """

    # Walk through all Package.pkg files in the Logical directory
    for pkg_file in logical_path.rglob("Package.pkg"):
        try:
            tree = etree.parse(str(pkg_file), parser=XML_PARSER)
            root_element = tree.getroot()
            matches = root_element.xpath(
                ".//*[local-name()='Object'][@Type='DataObject'][@Language='Vc3']"
            )

            if matches:
                log(
                    "VC3 components found in project. VC3 is not supported in AS6",
                    when="AS4",
                    severity="MANDATORY",
                )

        except Exception as e:
            log(
                f"Error parsing {pkg_file.relative_to(logical_path.parent)}: {str(e)}",
                severity="WARNING",
            )
            continue


def find_stack_functions(file_path: Path) -> list:
    content = utils.read_file(file_path)

    found = set()
    methods = ["VA_Textout", "VA_wcTextout"]
    for method in methods:
        if method in content:
            found.add((file_path, method))
    return list(found)
