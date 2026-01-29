"""UI helpers for the AB → ST converter.

This module contains all UI / user-interaction helpers (CustomTkinter dialog,
help text display, and terminal fallback prompting).

Keeping these in a separate file makes the core conversion logic easier to read
and to reuse in non-UI contexts.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'from utils import utils' works when
# this module is imported directly or via scripts in the helpers directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import utils


def get_converter_help_markdown_text() -> str:
    try:
        md_path = Path(__file__).resolve().parent / "ab_2_st_converter.md"
        return md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "Could not load ab_2_st_converter.md"


def conversion_checkbox_items() -> dict[str, str]:
    # key -> label
    return {
        "manual": "Manual fix notices insertion",
        "comment": "Comment conversion",
        "keywords": "Keyword replacements",
        "uppercase": "Uppercase conversion",
        "numbers": "Number format conversion",
        "select": "SELECT/STATE/WHEN/NEXT transformation",
        "loop": "LOOP/ENDLOOP conversion",
        "math": "INC/DEC conversion",
        "exitif": "EXITIF conversion",
        "semicolon": "Semicolon insertion",
        "functionblocks": "Function block syntax fix",
        "string_adr": "Conditional ADR wrapping for string assignments",
        "string_adr_whitelist": "ADR wrapping in whitelisted function arguments",
        "equals": "Equals to assignment conversion",
    }


def apply_config_from_checkbox_selections(
    conversion_config: dict[str, bool], selections: dict[str, bool]
) -> None:
    for key in list(conversion_config.keys()):
        if key in selections:
            conversion_config[key] = bool(selections[key])

    disabled = [k for k, v in conversion_config.items() if not v]
    if disabled:
        utils.log(f"Disabled conversions: {', '.join(disabled)}", severity="INFO")


def ask_proceed_with_options_gui(message: str) -> tuple[bool, dict[str, bool]]:
    """CustomTkinter dialog styled like ModernMigrationGUI.

    Returns: (proceed, selections)
    """

    try:
        import threading
        import tkinter as tk
        import customtkinter as ctk
    except Exception:
        return False, {k: True for k in conversion_checkbox_items().keys()}

    # Match ModernMigrationGUI look & feel
    B_R_BLUE = "#3B82F6"
    HOVER_BLUE = "#2563EB"
    LABEL_FONT = ("Segoe UI", 14, "bold")
    FIELD_FONT = ("Segoe UI", 15)
    BUTTON_FONT = ("Segoe UI", 14, "bold")
    LOG_FONT = ("Consolas", 12)

    items = conversion_checkbox_items()

    def _show_dialog(master) -> tuple[bool, dict[str, bool]]:
        win = ctk.CTkToplevel(master)
        win.withdraw()
        win.title("AB → ST converter")
        # Make the options window taller so all checkboxes fit without scrolling
        win.geometry("900x760")
        win.minsize(820, 700)

        try:
            win.transient(master)
        except Exception:
            pass

        container = ctk.CTkFrame(win)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            container,
            text="Convert Automation Basic to Structured Text",
            font=LABEL_FONT,
        ).pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(
            container,
            text=message,
            justify="left",
            wraplength=840,
            font=FIELD_FONT,
        ).pack(anchor="w", fill="x", pady=(0, 12))

        opts = ctk.CTkFrame(container)
        opts.pack(fill="both", expand=True, pady=(0, 12))

        ctk.CTkLabel(opts, text="Options", font=LABEL_FONT).pack(
            anchor="w", padx=10, pady=(10, 6)
        )

        # Increased height to avoid needing to scroll for the default option list
        scroll = ctk.CTkScrollableFrame(opts, height=400)
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        vars_by_key: dict[str, ctk.BooleanVar] = {}
        for key, text in items.items():
            var = ctk.BooleanVar(value=True)
            vars_by_key[key] = var
            ctk.CTkCheckBox(
                scroll,
                text=text,
                variable=var,
                font=FIELD_FONT,
            ).pack(anchor="w", padx=8, pady=6)

        result: dict[str, object] = {"proceed": False}

        def show_help():
            help_win = ctk.CTkToplevel(win)
            help_win.title("Instructions")
            help_win.geometry("1000x760")
            help_win.minsize(860, 620)
            try:
                help_win.transient(win)
            except Exception:
                pass
            txt = ctk.CTkTextbox(help_win, wrap="word", font=LOG_FONT)
            txt.pack(fill="both", expand=True, padx=16, pady=16)
            txt.insert("1.0", get_converter_help_markdown_text())
            txt.configure(state="disabled")
            help_win.focus_set()

        def on_yes():
            result["proceed"] = True
            win.destroy()

        def on_no():
            result["proceed"] = False
            win.destroy()

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text="Show instructions",
            command=show_help,
            fg_color="#444444",
            hover_color="#555555",
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="No",
            command=on_no,
            fg_color="#444444",
            hover_color="#555555",
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
            width=120,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_row,
            text="Yes",
            command=on_yes,
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
            width=120,
        ).pack(side="right")

        def on_close():
            result["proceed"] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        # Center relative to master
        try:
            win.update_idletasks()
            mw = master.winfo_width()
            mh = master.winfo_height()
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            w = win.winfo_reqwidth()
            h = win.winfo_reqheight()
            x = mx + max(0, (mw - w) // 2)
            y = my + max(0, (mh - h) // 2)
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        win.deiconify()
        win.grab_set()
        win.focus_set()
        win.wait_window()

        selections = {k: bool(v.get()) for k, v in vars_by_key.items()}
        return bool(result["proceed"]), selections

    # If we are running under the ModernMigrationGUI, create the dialog on the UI thread.
    master = getattr(tk, "_default_root", None)
    if master is None:
        # Standalone run: create our own CTk root.
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        root.withdraw()
        try:
            return _show_dialog(root)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    # GUI run: ensure UI thread creates widgets
    done = threading.Event()
    out: dict[str, tuple[bool, dict[str, bool]]] = {}

    def _run_on_ui():
        try:
            out["result"] = _show_dialog(master)
        finally:
            done.set()

    try:
        master.after(0, _run_on_ui)
        done.wait()
        res = out.get("result")
        if res is not None:
            return res
        return False, {k: True for k in items.keys()}
    except Exception:
        return False, {k: True for k in items.keys()}


def ask_proceed_with_options(message: str) -> tuple[bool, dict[str, bool]]:
    """Prefer GUI (if available), otherwise fall back to terminal yes/no."""

    try:
        proceed, selections = ask_proceed_with_options_gui(message)
        return proceed, selections
    except Exception:
        proceed = utils.ask_user(f"{message} (y/n) [y]: ", extra_note="Note:")
        return (proceed == "y"), {k: True for k in conversion_checkbox_items().keys()}
