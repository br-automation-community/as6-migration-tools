# checks/scene_viewer.py
import re
from pathlib import Path

from utils import utils


def check_scene_viewer(apj_path: Path, log, verbose: bool = False) -> None:
    """
    Detect whether B&R Scene Viewer is used by the project and, if so,
    inform about the minimum required version and setup steps.

    Short-circuit order (stop at first hit):
      2a) mapp Robotics: any *.objecthierarchy that mentions "Scene Viewer"
          AND has a non-empty "File Device"/FileDeviceNameN value.
      2b) mapp Trak: any *.hw that has a property FileDeviceName<N> with Value="SvgData".
      1)  Logical view fallback: presence of any *.scn file.
    """
    log("─" * 80 + "\nChecking Scene Viewer usage...")

    project_root = apj_path.parent

    # ---- 2a) mapp Robotics via .objecthierarchy ----
    for oh_file in project_root.rglob("*.objecthierarchy"):
        text = utils.read_file(oh_file)

        has_scene_viewer = (
            re.search(r"Scene\s*Viewer", text, flags=re.IGNORECASE) is not None
        )
        if not has_scene_viewer:
            continue

        values: list[str] = []

        # XML-ish: handle ID/Name and any attribute order
        values += re.findall(
            r'(?:ID|Name)\s*=\s*"(?:File\s*Device|FileDeviceName\d+)"[^>]*\bValue\s*=\s*"([^"]*)"',
            text,
            flags=re.IGNORECASE,
        )

        # Key/Value fallback: File Device = path  OR  FileDeviceName42 = Something
        values += re.findall(
            r'(?:File\s*Device|FileDeviceName\d+)\s*[:=]\s*"?(?!")([^<>\r\n"]+)"?',
            text,
            flags=re.IGNORECASE,
        )

        values = [v.strip() for v in values if v and v.strip()]
        if values:
            _emit_scene_viewer_message(
                log=log,
                origin=f"mapp Robotics (.objecthierarchy): {oh_file}",
                generated=True,
            )
            return
        elif verbose:
            log(
                f"- Found '.objecthierarchy' mentioning 'Scene Viewer' but no file device value set: {oh_file}",
                severity="INFO",
            )

    # ---- 2b) mapp Trak via .hw ----
    physical_path = project_root / "Physical"
    for hw_file in physical_path.rglob("*.hw"):
        text = utils.read_file(hw_file)

        if re.search(
            r'Name\s*=\s*"FileDeviceName\d+"\s+Value\s*=\s*"SvgData"',
            text,
            flags=re.IGNORECASE,
        ) or re.search(
            r'FileDeviceName\d+[^<>\r\n]*Value\s*=\s*"SvgData"',
            text,
            flags=re.IGNORECASE,
        ):
            _emit_scene_viewer_message(
                log=log,
                origin=f"mapp Trak (.hw): {hw_file}",
                generated=True,
            )
            return

    # ---- 1) Fallback: any .scn files in Logical view ----
    logical = project_root / "Logical"
    if logical.exists():
        scn = next(logical.rglob("*.scn"), None)
        if scn:
            _emit_scene_viewer_message(
                log=log,
                origin=f".scn file present: {scn}",
                generated=False,
            )
            return

    if verbose:
        log("No Scene Viewer usage was detected in this project.", severity="INFO")


def _emit_scene_viewer_message(log, origin: str, generated: bool) -> None:
    log(f"Scene Viewer usage detected ({origin}).", when="AS4", severity="INFO")

    if generated:
        # Auto-generated scenes (mapp Robotics/Trak) → strict requirements
        log(
            "Automatically generated scenes from mapp Robotics and mapp Trak require Scene Viewer 6.0 or newer. (Scene Viewer Download)"
            "\n - To establish a connection, enable the OPC UA server and configure a user with the system role BR_Observer or BR_Engineer.",
            when="AS6",
            severity="WARNING",
        )
    else:
        # Generic .scn presence → neutral info
        log(
            "Scene files (.scn) were detected in the project. For best compatibility, we recommend Scene Viewer 6.0 or newer. (Scene Viewer Download)"
            "\n - To establish a connection, enable the OPC UA server and configure a user with the system role BR_Observer or BR_Engineer.",
            when="AS6",
            severity="INFO",
        )
