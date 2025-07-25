# Utilities to call in multiple files
import hashlib
import os
import sys
from pathlib import Path

from CTkMessagebox import CTkMessagebox

from classes.ConsoleColors import ConsoleColors

_is_verbose = False


def get_build_number():
    try:
        version_file = Path(__file__).resolve().parent.parent / "version.txt"
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "?"


def set_verbose(verbose):
    global _is_verbose
    _is_verbose = verbose


def log(message, log_file=None):
    print(message)  # Print to console
    if log_file:
        log_file.write(message + "\n")  # Write to file
        log_file.flush()  # Ensure data is written immediately


def log_v(message, log_file=None, prepend=""):
    if _is_verbose:
        log(f"{prepend}[VERBOSE] {message}", log_file)


def get_and_check_project_file(project_path):
    project_path = Path(project_path)
    if not project_path.exists():
        if sys.stdin.isatty():
            print(ConsoleColors.ERROR)
        print(
            f"Error: The provided project path does not exist: '{project_path}'"
            "\nEnsure the path is correct and the project folder exists."
            "\nIf the path contains spaces, make sure to wrap it in quotes, like this:"
            f'\n   python {os.path.basename(sys.argv[0])} "C:\\path\\to\\your\\project"',
            file=sys.stderr,
        )
        if sys.stdin.isatty():
            print(f"{ConsoleColors.RESET}\n")
        sys.exit(1)

    # Check if .apj file exists in the provided path
    apj_file = next(project_path.glob("*.apj"), None)
    if not apj_file:
        if sys.stdin.isatty():
            print(ConsoleColors.ERROR)
        print(
            f"Error: No .apj file found in the provided path: {project_path}"
            "\nPlease specify a valid Automation Studio project path.",
            file=sys.stderr,
        )
        if sys.stdin.isatty():
            print(f"{ConsoleColors.RESET}\n")
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
        print(f"[INFO] {message} (User selected: '{choice}')")
        return choice

    # Fallback to terminal
    try:
        if sys.stdin and sys.stdin.isatty():
            return input(message).strip().lower()
    except Exception as e:
        print(f"[DEBUG] ask_user fallback triggered due to: {e}")
    print(f"[INFO] {message} (Automatically using default: '{default}')")
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
        wraplength=390
    )
    response = msg.get()
    return response == "Yes"
