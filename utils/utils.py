# Utilities to call in multiple files
import concurrent.futures
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Union

from charset_normalizer import from_path
from CTkMessagebox import CTkMessagebox

_CACHED_LINKS = None


class ConsoleColors:
    RESET = "\x1b[0m"  # Reset all formatting
    MANDATORY = "\x1b[1;31m"  # Set style to bold, red foreground.
    WARNING = "\x1b[1;33m"  # Set style to bold, yellow foreground.
    INFO = "\x1b[92m"  # Set style to light green foreground.
    UNDERLINE = "\x1b[4;94m"  # Set style to underlined


def get_version() -> str:
    """
    Resolve tool version for GUI/CLI.

    Order:
      1) env RELEASE_VERSION (set by CI)
      2) version.txt next to the frozen EXE (or PyInstaller _MEIPASS)
      3) 'not_released' for local/dev runs

    We intentionally DO NOT read version.txt from CWD/repo during dev
    to avoid accidental overrides.
    """
    # 1) CI-provided environment variable
    env_ver = os.getenv("RELEASE_VERSION")
    if env_ver:
        # Strip optional build metadata (e.g. 2025.10.09.0955+g67b92ee -> 2025.10.09.0955)
        base = env_ver.strip().split("+", 1)[0]
        if base:
            return base

    # 2) When frozen by PyInstaller, read bundled version.txt if present
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates = [exe_dir / "version.txt"]
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "version.txt")
            for vf in candidates:
                if vf.is_file():
                    txt = read_file(vf).strip()
                    if txt:
                        txt_base = txt.split("+", 1)[0]
                        if txt_base:
                            return txt_base
    except Exception:
        pass

    # 3) Default for local/dev runs
    return "dev"


def url(text):
    return f"{ConsoleColors.UNDERLINE}{text}{ConsoleColors.RESET}"


def get_links():
    global _CACHED_LINKS
    if _CACHED_LINKS is None:
        _CACHED_LINKS = load_file_info("links", "links")
    return _CACHED_LINKS


def extract_urls(text):
    """
    Extracts all HTTP and HTTPS URLs from the given text.
    """
    url_pattern = (
        r"\bhttps?:\/\/(?:www\.)?[a-zA-Z0-9\-._~%]+(?:\.[a-zA-Z]{2,})(?:\/[^\s]*)?\b"
    )
    return re.findall(url_pattern, text)


def linkify(text):
    links = get_links()
    for link in links:
        if link in text:
            text = text.replace(link, url(link))
    urls = extract_urls(text)
    for u in urls:
        text = text.replace(u, url(u))
    return text


def log(message, log_file=None, when="", severity=""):
    message = linkify(message)
    if when != "":
        message = f"[{when}] {message}"
    if severity != "":
        # Color highlighting based on severity level
        if severity.upper() == "MANDATORY" or severity.upper() == "ERROR":
            colored_severity = (
                f"{ConsoleColors.MANDATORY}[{severity}]{ConsoleColors.RESET}"
            )
        elif severity.upper() == "WARNING":
            colored_severity = (
                f"{ConsoleColors.WARNING}[{severity}]{ConsoleColors.RESET}"
            )
        elif severity.upper() == "INFO":
            colored_severity = f"{ConsoleColors.INFO}[{severity}]{ConsoleColors.RESET}"
        else:
            colored_severity = f"[{severity}]"

        # For console with color
        console_message = f"{colored_severity} {message}"
        # For file without color
        file_message = f"[{severity}] {message}"
    else:
        console_message = message
        file_message = message

    # Print to console with colors (with newline at start)
    print(
        f"\n{console_message}",
        file=(sys.stderr if severity.upper() == "ERROR" else sys.stdout),
    )
    if log_file:
        log_file.write(file_message + "\n")  # Write to file without colors
        log_file.flush()  # Ensure data is written immediately


def get_and_check_project_file(project_path):
    project_path = Path(project_path)
    if not project_path.exists():
        log(
            f"The provided project path does not exist: '{project_path}'"
            "\nEnsure the path is correct and the project folder exists."
            "\nIf the path contains spaces, make sure to wrap it in quotes, like this:"
            f'\n   python {os.path.basename(sys.argv[0])} "C:\\path\\to\\your\\project"',
            severity="ERROR",
        )
        sys.exit(1)

    # Check if .apj file exists in the provided path
    apj_file = next(project_path.glob("*.apj"), None)
    if not apj_file:
        log(
            f"No .apj file found in the provided path: {project_path}"
            "\nPlease specify a valid Automation Studio project path.",
            severity="ERROR",
        )
        sys.exit(1)

    return os.path.basename(apj_file)


def calculate_file_hash(file_path):
    """
    Calculates the hash (MD5) of a file for comparison purposes.
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(4096):
            md5.update(chunk)
    return md5.hexdigest()


def ask_user(message, default="y", parent=None, extra_note=""):
    """
    Ask the user a yes/no question. Uses terminal input if no GUI context.
    """
    if parent is not None:
        cleaned_msg = (
            message.replace("(y/n)", "")
            .replace("[y]", "")
            .replace("[n]", "")
            .strip(": ")
            .strip()
        )
        result = ask_user_gui(cleaned_msg, extra_note=extra_note)
        choice = "y" if result else "n"
        log(f"{message} (User selected: '{choice}')", severity="INFO")
        return choice

    # Fallback to terminal
    try:
        if sys.stdin and sys.stdin.isatty():
            return input(message).strip().lower()
    except Exception as e:
        log(f"ask_user fallback triggered due to: {e}", severity="DEBUG")
    log(f"{message} (Automatically using default: '{default}')", severity="INFO")
    return default


def ask_user_gui(message: str, extra_note: str = "") -> bool:
    """
    Display a Yes/No confirmation popup using customtkinter.
    An optional extra_note can be provided for additional info.
    """
    final_message = f"{extra_note}\n\n" if extra_note else ""
    final_message += message
    msg = CTkMessagebox(
        title="Question",
        message=final_message,
        icon="question",
        option_1="Yes",
        option_2="No",
        width=460,
        wraplength=390,
    )
    response = msg.get()
    return response == "Yes"


def scan_files_parallel(
    root_dir: Path,
    extensions: list,
    process_functions: Union[Callable, list[Callable]],
    *args,
):
    """
    Scans files in a directory tree in parallel for specific content.

    Args:
        root_dir (Path): The root directory to search in.
        extensions (list): File extensions to include.
        process_functions (callable or list): The function to apply on each file.
        *args: Additional arguments to pass to the process_function.

    Returns:
        dict or list: Aggregated results from all scanned files.
    """
    single_function_mode = not isinstance(process_functions, list)
    if single_function_mode:
        process_functions = [process_functions]

    results = {func.__name__: [] for func in process_functions}

    files = []
    for ext in extensions:
        files.extend(p for p in root_dir.rglob(f"*{ext}") if p.is_file())

    def process_file(path):
        return {func.__name__: func(path, *args) for func in process_functions}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for func_results in executor.map(process_file, files):
            for func_name, result in func_results.items():
                results[func_name].extend(result)

    if single_function_mode:
        # Flatten results if only one function was used
        return results[process_functions[0].__name__]
    else:
        return results


def load_discontinuation_info(filename):
    return load_file_info("discontinuations", filename)


def load_file_info(folder, filename):
    try:
        root_path = Path(__file__).resolve().parent.parent
        file_dir = root_path / folder
        file_path = file_dir / f"{filename}.json"
        with file_path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except Exception as e:
        log(f"Error loading JSON file '{filename}': {e}", severity="ERROR")
        return {}


def build_web_path(links, url):
    path_web = "https://www.br-automation.com/en"
    path_help = "https://help.br-automation.com/#/en/6"
    path_community = "https://community.br-automation.com/"

    # Direct check for external links
    if "http" in url or "https" in url:
        return url

    # Check if url is in links
    if url in links:
        item = links[url]

        # Dictionary for Prefix-Mappings
        prefix_paths = {
            "br_web": f"{path_web}/",
            "online_help": f"{path_help}/",
            "community": f"{path_community}/",
            "mapp_view_license": f"{path_web}/products/software/mapp-technology/mapp-view/mapp-view-licensing/",
            "mapp_view_widget": f"{path_help}/visualization/mappview/widgets/",
            "mapp_view_help": f"{path_help}/visualization/mappview/",
            "mapp_view_widget_buttons": f"{path_help}/visualization/mappview/widgets/buttons/",
            "mapp_view_widget_chart": f"{path_help}/visualization/mappview/widgets/chart/",
            "mapp_view_widget_container": f"{path_help}/visualization/mappview/widgets/container/",
            "mapp_view_widget_numeric": f"{path_help}/visualization/mappview/widgets/numeric/",
            "mapp_view_widget_media": f"{path_help}/visualization/mappview/widgets/media/",
            "mapp_connect_help": f"{path_help}/visualization/mappconnect/",
            "mapp_control_help": f"{path_help}/mechatronics/mappcontrol/",
            "mapp_services_license": f"{path_web}/products/software/mapp-technology/mapp-services/mapp-services-licensing/",
            "mapp_services_help": f"{path_help}/services/mapp_services/",
            "mapp_vision_license": f"{path_web}/products/software/mapp-technology/mapp-vision/mapp-vision-licensing/",
            "mapp_vision_help": f"{path_help}/machine_vision/mapp_vision/programming/vfs/",
            "mapp_motion_help": f"{path_help}/motion/mapp_motion/",
            "safety_help": f"{path_help}/safety/",
            "opc_ua_help": f"{path_help}/communication/opcua/",
            "as4_migration": f"{path_help}/revinfos/version-info/projekt_aus_automation_studio_4_ubernehmen/automation_studio/",
            "homepage_software": f"{path_web}/downloads/software/",
            "": f"{path_help}/",
        }

        # Get base path if we have a prefix
        base_path = prefix_paths.get(item.get("prefix", ""), "")
        return base_path + item["url"]

    # Default-url for unknown paths
    return f"{path_web}/product/{url}"


def read_file(file: Path):
    try:
        return file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        result = from_path(file).best()
        if result:
            return file.read_text(encoding=result.encoding, errors="ignore")
    return ""


def file_value_count(file_path: Path, pairs):
    for line in read_file(file_path).splitlines():
        for obj in pairs:
            if f'ID="{obj["id"]}"' in line and f'Value="{obj["value"]}"' in line:
                obj["cnt"] += 1

    return pairs


def file_value_by_id(file_path: Path, ids):
    result = []
    for line in read_file(file_path).splitlines():
        for item in ids:
            if item in line:
                match = re.search(r'Value="([^"]+)"', line)
                if match:
                    result.append({"name": item, "value": match.group(1)})

    return result


def file_type_count(file_path: Path, pairs):
    for line in read_file(file_path).splitlines():
        for type_obj in pairs:
            if f'Type="{type_obj["type"]}"' in line:
                type_obj["cnt"] += 1
    return pairs
