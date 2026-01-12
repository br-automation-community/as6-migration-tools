import importlib.util
import os
import re
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from CTkMenuBar import CTkMenuBar, CustomDropdownMenu

import utils.utils as utils
from utils.get_changelog import get_changelog_between_versions

B_R_BLUE = "#3B82F6"
HOVER_BLUE = "#2563EB"

LABEL_FONT = ("Segoe UI", 14, "bold")
FIELD_FONT = ("Segoe UI", 15)
BUTTON_FONT = ("Segoe UI", 14, "bold")
LOG_FONT = ("Consolas", 12)

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class RedirectText:
    def __init__(self, append_func, status_func):
        self.append_func = append_func
        self.status_func = status_func

    def write(self, string):
        if "\r" in string:
            self.status_func(string.strip())
        else:
            self.append_func(string)

    def flush(self):
        pass


class ModernMigrationGUI:
    def __init__(self):
        self.browse_button = None
        self.log_text = None
        self.menubar = None
        self.run_button = None
        self.save_button = None
        self.save_log_option = None
        self.status_label = None
        self.root = ctk.CTk()

        # Color mapping for ANSI codes (used for GUI rendering)
        self.color_map = {
            "\x1b[1;31m": "red",  # Bold red (ERROR/MANDATORY)
            "\x1b[1;33m": "orange",  # Bold yellow (WARNING)
            "\x1b[92m": "green",  # Light green (INFO)
            "\x1b[4;94m": "blue",  # Underline Blue (LINK)
            "\x1b[0m": "normal",  # Reset
        }

        # Keep a raw buffer of everything appended to the log (including ANSI codes)
        # This is the single source of truth for HTML export.
        self.raw_log_buffer = []

        import utils.utils as shared_utils

        original_ask_user = shared_utils.ask_user

        def ask_user_gui_wrapper(*args, **kwargs):
            if "parent" not in kwargs or kwargs["parent"] is None:
                kwargs["parent"] = self.root
            return original_ask_user(*args, **kwargs)

        shared_utils.ask_user = ask_user_gui_wrapper
        sys.modules["utils.utils"] = shared_utils
        self.utils = shared_utils

        build = utils.get_version()
        self.root.title(f"AS4 to AS6 Migration Tool (Build {build})")
        self.root.geometry("1500x900")

        icon_path = os.path.join(
            getattr(sys, "_MEIPASS", os.path.abspath(".")), "gui_icon.ico"
        )
        try:
            self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self.selected_folder = ctk.StringVar()
        self.selected_script = ctk.StringVar(value="Evaluate AS4 project")
        self.verbose_mode = ctk.BooleanVar(value=False)
        self.script_ran = ctk.BooleanVar(value=False)
        self.spinner_running = False
        self.spinner_index = 0

        self.scripts = {
            "Evaluate AS4 project": self.resource_path("as4_to_as6_analyzer.py"),
            "AsMathToAsBrMath": self.resource_path("helpers/asmath_to_asbrmath.py"),
            "AsStringToAsBrStr": self.resource_path("helpers/asstring_to_asbrstr.py"),
            "OpcUa Update": self.resource_path("helpers/asopcua_update.py"),
            "MappMotion Update": self.resource_path("helpers/mappmotion_update.py"),
            "License checker": self.resource_path("helpers/license_checker.py"),
        }

        self.links = utils.load_file_info("links", "links")

        self.build_ui()
        self.script_ran.trace_add("write", self.toggle_save_buttons)
        self.update_menubar_theme()
        self.selected_folder.trace_add("write", self.toggle_run_button)
        self.toggle_run_button()
        # After building UI trigger async update check
        try:
            threading.Thread(target=self._async_check_updates, daemon=True).start()
        except Exception:
            pass

    def resource_path(self, rel_path):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.normpath(os.path.join(base, rel_path))

    def build_ui(self):
        self.build_header_ui()
        self.build_folder_ui()
        self.build_options_ui()
        self.build_status_ui()
        self.build_log_ui()
        self.build_save_ui()

    def update_menubar_theme(self):
        appearance = ctk.get_appearance_mode()
        color = "#f5f5f5" if appearance == "Light" else "#000000"
        self.menubar.configure(bg_color=color)

    def build_header_ui(self):
        self.menubar = CTkMenuBar(master=self.root)

        file_btn = self.menubar.add_cascade("File")
        file_dropdown = CustomDropdownMenu(widget=file_btn)
        file_dropdown.add_option("Browse AS4 project", self.browse_folder)
        self.save_log_option = file_dropdown.add_option("Save as HTML", self.save_log)
        # New menu item: send via Outlook
        self.send_report_option = file_dropdown.add_option(
            "Send via Outlook", self.send_report_outlook
        )
        file_dropdown.add_separator()
        file_dropdown.add_option("Exit", self.root.quit)

        theme_btn = self.menubar.add_cascade("Theme")
        theme_dropdown = CustomDropdownMenu(widget=theme_btn)
        theme_dropdown.add_option("Light Mode", lambda: self.set_theme("Light"))
        theme_dropdown.add_option("Dark Mode", lambda: self.set_theme("Dark"))

        self.menubar.add_cascade("About", command=self.show_about)

        self.menubar.pack(fill="x")

    def set_theme(self, mode):
        self.update_menubar_theme()
        ctk.set_appearance_mode(mode)
        self.menubar.configure(bg_color="#ffffff" if mode == "Light" else "#000000")

        # Update normal text color based on theme
        normal_color = "black" if mode == "Light" else "white"
        if hasattr(self, "log_text") and self.log_text:
            self.log_text._textbox.tag_configure("normal", foreground=normal_color)

    def toggle_save_buttons(self, *args):
        state = "normal" if self.script_ran.get() else "disabled"
        self.save_button.configure(state=state)
        self.save_log_option.configure(state=state)
        # New:
        if hasattr(self, "send_button"):
            self.send_button.configure(state=state)
        if hasattr(self, "send_report_option"):
            self.send_report_option.configure(state=state)

    def _export_report_to_temp(self) -> Path:
        """Render current report to a temp HTML file and return the path."""
        from tempfile import gettempdir

        project = self.selected_folder.get() or "project"
        project_name = os.path.basename(project.rstrip("\\/")) or "project"
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"{project_name}_AS4_To_AS6_Migration_Report_{ts}.html"
        out_path = Path(gettempdir()) / filename
        html_content = self.generate_html_log()
        out_path.write_text(html_content, encoding="utf-8")
        return out_path

    def _build_email_subject(self) -> str:
        """Build a clean subject without error/warning/info counters."""
        project = self.selected_folder.get() or ""
        project_name = os.path.basename(project.rstrip("\\/")) if project else ""
        if project_name:
            return f"{project_name} - AS4 to AS6 Migration Report"
        return "AS4 to AS6 Migration Report"

    def _build_email_body_html(self) -> str:
        """Short, Outlook-friendly HTML body. Full report is attached."""
        repo_url = "https://github.com/br-automation-community/as6-migration-tools"
        project = self.selected_folder.get() or "-"
        raw = "".join(self.raw_log_buffer)
        err = raw.count("[ERROR]") + raw.count("[MANDATORY]")
        warn = raw.count("[WARNING]")
        info = raw.count("[INFO]")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""
        <div style="font-family: Segoe UI, Arial, sans-serif; font-size: 12pt;">
          <p><strong>AS4 to AS6 Migration Report</strong></p>
          <p><strong>Project:</strong> {escape(project)}<br>
             <strong>Generated:</strong> {escape(ts)}<br>
             <strong>Summary:</strong> Errors: {err}, Warnings: {warn}, Info: {info}</p>
          <p>Full HTML report is attached.<br>
             Tool: <a href="{repo_url}">as6-migration-tools</a></p>
        </div>
        """

    def _send_report_via_pywin32(self, report_path: Path, subject: str, body_html: str):
        """Use pywin32 COM (if bundled) to open a draft with signature + attachment."""
        import win32com.client  # requires pywin32

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.Display()  # load user's default signature
        signature_html = mail.HTMLBody or ""
        mail.Subject = subject
        mail.HTMLBody = body_html + signature_html
        mail.Attachments.Add(str(report_path.resolve()))
        # leave draft open

    def _send_report_via_powershell(
        self, report_path: Path, subject: str, body_html: str
    ):
        """Automate Outlook via PowerShell COM (works without pywin32 inside your exe)."""
        import os
        import subprocess
        import tempfile

        ps_script = r"""
    $ErrorActionPreference = 'Stop'
    $ol = New-Object -ComObject Outlook.Application
    $mail = $ol.CreateItem(0)
    $mail.Display()
    $signature = $mail.HTMLBody
    $mail.Subject  = $env:SUBJECT
    $mail.HTMLBody = $env:BODY + $signature
    $mail.Attachments.Add($env:ATTACH)
    """

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".ps1", mode="w", encoding="utf-8-sig"
        ) as f:
            f.write(ps_script)
            ps_path = f.name

        env = os.environ.copy()
        env["SUBJECT"] = subject
        env["BODY"] = body_html
        env["ATTACH"] = str(report_path.resolve())

        exe = "powershell"
        try:
            subprocess.run(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                check=True,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            exe = "pwsh"
            subprocess.run(
                [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                check=True,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

    def _send_report_via_outlook_cli(
        self, report_path: Path, subject: str, body_html: str
    ):
        """Use Outlook command-line switches as last resort (body becomes plaintext)."""
        import re
        import shutil
        import subprocess
        from urllib.parse import quote

        outlook = shutil.which("outlook.exe")
        if not outlook:
            raise RuntimeError("outlook.exe not found on PATH")

        plain = re.sub(r"<[^>]+>", "", body_html)  # strip HTML
        mailto = f"mailto:?subject={quote(subject)}&body={quote(plain)}"

        subprocess.run(
            [outlook, "/c", "ipm.note", "/m", mailto, "/a", str(report_path.resolve())],
            check=True,
        )

    def send_report_outlook(self):
        """Open an Outlook draft with the exported HTML report attached.
        Tries: pywin32 COM → PowerShell COM → Outlook CLI.
        """
        # Guard: need content
        if not self.raw_log_buffer and self.log_text.get("1.0", "end-1c").strip() == "":
            messagebox.showwarning(
                "No content", "Run a script before sending a report."
            )
            return

        # Export report to a temp file
        try:
            report_path = self._export_report_to_temp()
        except Exception as e:
            import traceback

            messagebox.showerror(
                "Export failed",
                f"Could not export report:\n{e}\n\n{traceback.format_exc()}",
            )
            return

        try:
            subject = self._build_email_subject()
            body_html = self._build_email_body_html()
        except Exception as e:
            import traceback

            messagebox.showerror(
                "Build email failed",
                f"Could not build email content:\n{e}\n\n{traceback.format_exc()}",
            )
            return

        # 1) Try pywin32 COM
        try:
            self._send_report_via_pywin32(report_path, subject, body_html)
            self.update_status(f"Outlook draft (pywin32) opened: {report_path.name}")
            return
        except Exception:
            pass  # fall through

        # 2) Try PowerShell COM (no pywin32 dependency at runtime)
        try:
            self._send_report_via_powershell(report_path, subject, body_html)
            self.update_status(f"Outlook draft (PowerShell) opened: {report_path.name}")
            return
        except Exception as e_ps:
            ps_err = str(e_ps)

        # 3) Try Outlook CLI as last resort (plain body)
        try:
            self._send_report_via_outlook_cli(report_path, subject, body_html)
            self.update_status(f"Outlook draft (CLI) opened: {report_path.name}")
            return
        except Exception as e_cli:
            cli_err = str(e_cli)

        # All failed
        messagebox.showerror(
            "Outlook not available",
            "Could not open an Outlook draft via pywin32, PowerShell, or Outlook CLI.\n\n"
            f"- PowerShell error: {ps_err if 'ps_err' in locals() else 'n/a'}\n"
            f"- CLI error: {cli_err if 'cli_err' in locals() else 'n/a'}\n"
            "Ensure classic Outlook (Win32) is installed. If you use the new Store 'Outlook', COM/CLI may not work.",
        )

    def show_about(self):
        # Text + links (keep in English)
        about_text = (
            "Open-source tools for analyzing and migrating B&R Automation Studio 4 (AS4) "
            "projects to Automation Studio 6 (AS6).\n\n"
            "Highlights:\n"
            "• One clean, actionable report (deprecated libraries & functions, unsupported hardware, mapp changes, common pitfalls).\n"
            "• Works fully offline; no telemetry; everything runs locally.\n"
            "• Fast feedback on large projects; verbose mode for deep dives.\n\n"
            "Unofficial community project — not affiliated with B&R Industrial Automation.\n"
            "Provided as-is, without warranty."
        )

        GITHUB_URL = "https://github.com/br-automation-community/as6-migration-tools"
        RELEASES_URL = (
            "https://github.com/br-automation-community/as6-migration-tools/releases"
        )
        ISSUES_URL = (
            "https://github.com/br-automation-community/as6-migration-tools/issues"
        )
        LICENSE_URL = "https://github.com/br-automation-community/as6-migration-tools/blob/main/LICENSE"

        appearance = ctk.get_appearance_mode()
        fg = "#000000" if appearance == "Light" else "#ffffff"

        msg_win = ctk.CTkToplevel(self.root)
        msg_win.withdraw()  # Hide initially
        msg_win.title("About")
        msg_win.resizable(False, False)  # user can't resize; we will set geometry below

        try:
            icon_path = os.path.join(
                getattr(sys, "_MEIPASS", os.path.abspath(".")), "gui_icon.ico"
            )
            msg_win.after(250, lambda: msg_win.iconbitmap(icon_path))
        except Exception:
            pass

        # Header + version
        ctk.CTkLabel(
            msg_win,
            text="AS6 Migration Tools",
            font=LABEL_FONT,
            text_color=fg,
        ).pack(pady=(10, 2))
        build = utils.get_version()
        ctk.CTkLabel(
            msg_win, text=f"Version: {build}", font=LABEL_FONT, text_color=fg
        ).pack(pady=(0, 6))

        # Body
        ctk.CTkLabel(
            msg_win,
            text=about_text,
            justify="left",
            text_color=fg,
            font=FIELD_FONT,
            padx=20,
            pady=10,
            wraplength=680,
        ).pack(anchor="w")

        # License line (clickable)
        license_lbl = ctk.CTkLabel(
            msg_win,
            text="License: MIT",
            justify="left",
            text_color=fg,
            font=("Segoe UI", 10),
            padx=20,
            wraplength=680,
            cursor="hand2",
        )
        license_lbl.pack(anchor="w", pady=(0, 8))
        license_lbl.bind("<Button-1>", lambda _e: webbrowser.open_new(LICENSE_URL))

        # Buttons (anchored to bottom so they stay visible)
        btn_row = ctk.CTkFrame(msg_win)
        btn_row.pack(side="bottom", fill="x", pady=12, padx=16)

        ctk.CTkButton(
            master=btn_row,
            text="Open GitHub",
            command=lambda: webbrowser.open_new(GITHUB_URL),
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(side="left")

        ctk.CTkButton(
            master=btn_row,
            text="Releases",
            command=lambda: webbrowser.open_new(RELEASES_URL),
            fg_color="#444444",
            hover_color="#555555",
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            master=btn_row,
            text="Report an issue",
            command=lambda: webbrowser.open_new(ISSUES_URL),
            fg_color="#444444",
            hover_color="#555555",
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(side="right")

        # --- Center & autosize AFTER layout ---
        msg_win.update_idletasks()
        req_w, req_h = msg_win.winfo_reqwidth(), msg_win.winfo_reqheight()
        screen_h = self.root.winfo_screenheight()
        max_h = min(int(screen_h * 0.8), 700)  # clamp to 80% of screen or 700 px
        w = max(720, req_w)  # keep your desired min width
        h = min(max(360, req_h), max_h)  # min 360, but allow growth up to clamp

        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
        msg_win.geometry(f"{w}x{h}+{x}+{y}")

        msg_win.transient(self.root)
        msg_win.grab_set()
        msg_win.focus_set()
        msg_win.bind("<Escape>", lambda e: msg_win.destroy())
        msg_win.deiconify()

    def build_folder_ui(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=10)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Project folder:", font=LABEL_FONT).grid(
            row=0, column=0, sticky="w"
        )
        entry = ctk.CTkEntry(
            frame, textvariable=self.selected_folder, font=FIELD_FONT, width=1000
        )
        entry.bind("<Double-Button-1>", lambda e: self.browse_folder())
        entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(0, 5))
        self.browse_button = ctk.CTkButton(
            frame,
            text="Browse",
            command=self.browse_folder,
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            width=100,
            height=36,
            corner_radius=8,
            font=BUTTON_FONT,
        )
        self.browse_button.grid(row=1, column=1, pady=(0, 5))

    def build_options_ui(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(frame, text="Select script:", font=LABEL_FONT).pack(side="left")
        combobox = ctk.CTkComboBox(
            frame,
            variable=self.selected_script,
            values=list(self.scripts.keys()),
            width=250,
            font=FIELD_FONT,
        )
        combobox.pack(side="left", padx=10)

        # noinspection PyProtectedMember
        def open_dropdown():
            if hasattr(combobox, "_open_dropdown_menu"):
                combobox._open_dropdown_menu()

        combobox.bind("<Button-1>", lambda e: open_dropdown())

        ctk.CTkCheckBox(
            frame, text="Verbose Mode", variable=self.verbose_mode, font=FIELD_FONT
        ).pack(side="left", padx=10)
        self.run_button = ctk.CTkButton(
            frame,
            text="Run",
            command=self.execute_script,
            state="disabled",
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
        )
        self.run_button.pack(side="left", padx=15)

    def build_status_ui(self):
        self.status_label = ctk.CTkLabel(
            self.root, text="", height=25, anchor="w", font=FIELD_FONT, wraplength=1400
        )
        self.status_label.pack(fill="x", padx=20, pady=(0, 5))

    def build_log_ui(self):
        self.log_text = ctk.CTkTextbox(
            self.root, wrap="word", font=LOG_FONT, border_width=1, corner_radius=6
        )
        self.log_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_text.configure(state="disabled")

        # Configure color tags for different severity levels
        self.log_text._textbox.tag_configure("red", foreground="red")
        self.log_text._textbox.tag_configure("orange", foreground="orange")
        self.log_text._textbox.tag_configure("green", foreground="green")
        self.log_text._textbox.tag_configure(
            "blue", foreground="#1db6e0", underline="true"
        )
        self.log_text._textbox.tag_configure(
            "normal",
            foreground="white" if ctk.get_appearance_mode() == "Dark" else "black",
        )

    def build_save_ui(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(0, 20))

        # Export button
        self.save_button = ctk.CTkButton(
            frame,
            text="Save as HTML",
            command=self.save_log,
            state="disabled",
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
        )
        self.save_button.pack(side="right")

        # Send via Outlook button
        self.send_button = ctk.CTkButton(
            frame,
            text="Send via Outlook",
            command=self.send_report_outlook,
            state="disabled",
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
        )
        self.send_button.pack(side="right", padx=(0, 10))

        self.script_ran.trace_add("write", self.toggle_save_buttons)

    def toggle_run_button(self, *args):
        self.run_button.configure(
            state="normal" if self.selected_folder.get() else "disabled"
        )

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder.set(folder)

    def is_valid_as4_project(self, folder):
        required_dirs = ["Physical", "Logical"]
        has_apj_file = any(f.endswith(".apj") for f in os.listdir(folder))
        has_dirs = all(os.path.isdir(os.path.join(folder, d)) for d in required_dirs)
        return has_apj_file and has_dirs

    def execute_script(self):
        self.spinner_running = True
        self.spinner_index = 0
        self.animate_spinner()
        threading.Thread(target=self._worker_execute_script, daemon=True).start()

    def animate_spinner(self):
        if not self.spinner_running:
            return
        frame = SPINNER_FRAMES[self.spinner_index % len(SPINNER_FRAMES)]
        self.status_label.configure(text=f"{frame} Running")
        self.spinner_index += 1
        self.status_label.after(100, self.animate_spinner)

    def _worker_execute_script(self):
        self.clear_log()
        folder = self.selected_folder.get()
        script = self.scripts.get(self.selected_script.get())
        verbose = self.verbose_mode.get()

        original_stdout, original_stderr = sys.stdout, sys.stderr
        redirector = RedirectText(self.append_log, self.update_status)
        sys.stdout = redirector
        sys.stderr = redirector

        error_message = None
        if not os.path.exists(folder):
            error_message = f"Folder does not exist: {folder}"
        elif not self.is_valid_as4_project(folder):
            error_message = f"Folder is not a valid AS4 project: {folder}"
        elif not script or not os.path.exists(script):
            error_message = f"Script not found: {self.selected_script.get()}"

        if error_message:
            utils.log(error_message, severity="ERROR")
            self.update_status("Script execution failed")
            self.spinner_running = False
            return

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            stdlib_path = Path(sys._MEIPASS) / "lib"
            if stdlib_path.exists():
                sys.path.insert(0, str(stdlib_path.resolve()))

        spec = importlib.util.spec_from_file_location("selected_script", script)
        module = importlib.util.module_from_spec(spec)
        sys.modules["selected_script"] = module

        try:
            spec.loader.exec_module(module)

            # Build sys.argv for the selected script (no restore version)
            sys.argv = ["analyzer", folder]

            # Only the AS4→AS6 analyzer supports/needs --no-file from the GUI
            if self.selected_script.get() == "Evaluate AS4 project":
                sys.argv.append("--no-file")

            if verbose:
                sys.argv.append("--verbose")

            module.main()
        except Exception as e:
            import traceback

            utils.log(
                f"Execution failed: {e}",
                severity="ERROR",
            )
            utils.log(
                f"Traceback:\n{traceback.format_exc()}",
                severity="ERROR",
            )
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self.spinner_running = False

        self.update_status("Script finished successfully")
        self.script_ran.set(True)

    def append_log(self, message):
        """Append message to log with color support for ANSI escape codes, and keep raw buffer for HTML export."""
        # Store raw message for HTML export
        self.raw_log_buffer.append(message)

        # Append to GUI
        self.log_text.configure(state="normal")
        self.parse_and_insert_colored_text(message)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def urlClick(self, event):
        index = self.log_text._textbox.index(f"@{event.x},{event.y}")
        tags = self.log_text._textbox.tag_names(index)
        clicked_text = None
        for tag in tags:
            # Get all ranges for the tag
            ranges = self.log_text._textbox.tag_ranges(tag)
            for start, end in zip(ranges[::2], ranges[1::2]):
                # Check if the click was within this range
                if self.log_text._textbox.compare(
                    index, ">=", start
                ) and self.log_text._textbox.compare(index, "<", end):
                    clicked_text = self.log_text._textbox.get(start, end)
                    break
        if clicked_text is not None:
            webbrowser.open_new(utils.build_web_path(self.links, clicked_text))

    def parse_and_insert_colored_text(self, text):
        """Parse ANSI escape codes and insert text with appropriate colors in the GUI widget."""
        # Remove section markers from display (they're for HTML parsing only)
        section_marker_pattern = re.compile(r"§§SECTION:[^:]+:[^§]+§§")
        display_text = section_marker_pattern.sub("", text)

        # Skip if the entire message was only a section marker (no other content)
        # But preserve empty lines and newlines that are part of the original text
        if not display_text.replace("\n", "").strip():
            # Still insert newlines if the original text had them
            if "\n" in text:
                self.log_text.insert("end", "\n")
            return

        ansi_pattern = r"(\x1b\[[0-9;]*m)"

        parts = re.split(ansi_pattern, display_text)
        current_tag = "normal"

        for part in parts:
            if part in self.color_map:
                current_tag = self.color_map[part]
            elif part:
                start_pos = self.log_text._textbox.index("end-1c")
                self.log_text.insert("end", part)
                end_pos = self.log_text._textbox.index("end-1c")

                if current_tag != "normal":
                    self.log_text._textbox.tag_add(current_tag, start_pos, end_pos)

        self.log_text._textbox.tag_bind("blue", "<1>", self.urlClick)
        self.log_text._textbox.tag_bind("blue", "<Enter>", self.on_enter)
        self.log_text._textbox.tag_bind("blue", "<Leave>", self.on_leave)

    def on_enter(self, event):
        self.log_text._textbox.config(cursor="hand2")  # Changes to hand cursor

    def on_leave(self, event):
        self.log_text._textbox.config(cursor="")  # Resets to default cursor

    def update_status(self, message):
        self.status_label.after(0, lambda: self.status_label.configure(text=message))

    # ---------------------------
    # HTML export (Save Log) - Modern UI with checklist
    # ---------------------------

    # Inline SVG icons (Heroicons/Lucide style)
    SVG_ICONS = {
        "error": '<svg class="icon icon-error" viewBox="0 0 20 20" fill="currentColor"><circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M10 6v5m0 3v.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
        "warning": '<svg class="icon icon-warning" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2L1 18h18L10 2z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/><path d="M10 8v4m0 2v.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "info": '<svg class="icon icon-info" viewBox="0 0 20 20" fill="currentColor"><circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M10 9v5m0-8v.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
        "check": '<svg class="icon icon-check" viewBox="0 0 20 20" fill="currentColor"><path d="M4 10l4 4 8-8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "chevron": '<svg class="icon icon-chevron" viewBox="0 0 20 20" fill="currentColor"><path d="M6 8l4 4 4-4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "folder": '<svg class="icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 5a2 2 0 012-2h3l2 2h5a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V5z"/></svg>',
    }

    def save_log(self):
        """Save the current log as a standalone .html file and open it in the default browser."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
        )
        if not file_path:
            return
        try:
            html_content = self.generate_html_log()
            Path(file_path).write_text(html_content, encoding="utf-8")
            # Always open in default browser after saving
            webbrowser.open_new_tab(Path(file_path).resolve().as_uri())
            messagebox.showinfo("Success", f"HTML log saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def _parse_sections(self, raw_lines: list) -> list:
        """
        Parse raw log lines and split into sections based on §§SECTION:id:title§§ markers.
        Returns list of dicts: [{"id": str, "title": str, "lines": [str], "errors": int, "warnings": int, "info": int}]
        """
        sections = []
        # Use SECTION_METADATA title for intro section if available
        intro_meta = utils.SECTION_METADATA.get("intro", {})
        current_section = {
            "id": "intro",
            "title": intro_meta.get("title", "Introduction"),
            "lines": [],
            "errors": 0,
            "warnings": 0,
            "info": 0,
        }

        section_pattern = re.compile(r"§§SECTION:([^:]+):(.+?)§§")
        # Characters used in separator lines
        separator_chars = set("─━═╌╍┄┅┈┉-")

        def is_separator_line(line: str) -> bool:
            """Check if line is primarily a separator (80%+ separator chars)."""
            stripped = line.strip()
            if not stripped:
                return False
            sep_count = sum(1 for c in stripped if c in separator_chars)
            # If line is 80%+ separator characters, treat it as a separator
            return sep_count / len(stripped) > 0.8

        for line in raw_lines:
            match = section_pattern.search(line)
            if match:
                # Save previous section if it has content
                if current_section["lines"] or current_section["id"] != "intro":
                    sections.append(current_section)
                # Start new section
                section_id = match.group(1)
                # Use SECTION_METADATA title if available, otherwise use marker title
                meta = utils.SECTION_METADATA.get(section_id, {})
                section_title = meta.get("title", match.group(2))
                # Remove the marker from the line completely
                clean_line = section_pattern.sub("", line)
                current_section = {
                    "id": section_id,
                    "title": section_title,
                    "lines": [],  # Don't include the marker line itself
                    "errors": 0,
                    "warnings": 0,
                    "info": 0,
                }
            else:
                # Skip separator lines (lines with only dashes or box-drawing characters)
                if is_separator_line(line):
                    continue
                current_section["lines"].append(line)
                # Count severities
                if "[ERROR]" in line or "[MANDATORY]" in line:
                    current_section["errors"] += 1
                elif "[WARNING]" in line:
                    current_section["warnings"] += 1
                elif "[INFO]" in line:
                    current_section["info"] += 1

        # Don't forget the last section
        if current_section["lines"] or current_section["id"] != "intro":
            sections.append(current_section)

        return sections

    def _convert_ansi_line(self, line: str) -> str:
        """Convert a single ANSI-colored line to HTML with proper escaping and links."""
        ansi_pattern = r"(\x1b\[[0-9;]*m)"
        fast_color_map = {
            "\x1b[1;31m": "sev-error",
            "\x1b[1;33m": "sev-warning",
            "\x1b[92m": "sev-info",
        }

        parts = []
        current_class = ""
        underline_on = False
        blue_on = False
        link_buffer = []

        def flush_link():
            nonlocal link_buffer
            link_text = "".join(link_buffer).strip()
            link_buffer.clear()
            if link_text:
                try:
                    href = utils.build_web_path(self.links, link_text)
                except Exception:
                    href = link_text
                parts.append(f'<a href="{escape(href)}">{escape(link_text)}</a>')

        tokens = re.split(ansi_pattern, line)
        for t in tokens:
            if not t:
                continue

            if re.fullmatch(ansi_pattern, t):
                params = t[2:-1]
                codes = []
                if params:
                    for c in params.split(";"):
                        if c.isdigit():
                            try:
                                codes.append(int(c))
                            except ValueError:
                                pass

                if 0 in codes:
                    if blue_on and underline_on:
                        flush_link()
                    underline_on = False
                    blue_on = False
                    current_class = ""
                    continue

                if 4 in codes:
                    underline_on = True
                if 24 in codes:
                    underline_on = False
                if 94 in codes:
                    blue_on = True
                if 39 in codes:
                    blue_on = False

                if not (underline_on and blue_on) and link_buffer:
                    flush_link()

                if t in fast_color_map:
                    current_class = fast_color_map[t]
                continue

            # Text content
            if underline_on and blue_on:
                link_buffer.append(t)
            elif current_class:
                parts.append(f'<span class="{current_class}">{escape(t)}</span>')
            else:
                parts.append(escape(t))

        if link_buffer:
            flush_link()

        # Join all parts together (each line is processed separately, no embedded newlines)
        return "".join(parts)

    def _generate_finding_html(self, line: str, finding_id: str) -> str:
        """Generate HTML for a single finding line with checkbox."""
        converted = self._convert_ansi_line(line)

        # Determine severity for styling
        sev_class = ""
        icon_html = ""
        if "[ERROR]" in line or "[MANDATORY]" in line:
            sev_class = "finding-error"
            icon_html = self.SVG_ICONS["error"]
            converted = re.sub(
                r"\[(ERROR|MANDATORY)\]",
                f'{icon_html}<span class="sev-label">[\\1]</span>',
                converted,
            )
        elif "[WARNING]" in line:
            sev_class = "finding-warning"
            icon_html = self.SVG_ICONS["warning"]
            converted = re.sub(
                r"\[WARNING\]",
                f'{icon_html}<span class="sev-label">[WARNING]</span>',
                converted,
            )
        elif "[INFO]" in line:
            sev_class = "finding-info"
            icon_html = self.SVG_ICONS["info"]
            converted = re.sub(
                r"\[INFO\]",
                f'{icon_html}<span class="sev-label">[INFO]</span>',
                converted,
            )
        else:
            # Non-finding line, just return converted text
            return f'<div class="log-line">{converted}</div>'

        return f"""<label class="finding {sev_class}" data-id="{finding_id}">
            <input type="checkbox" class="finding-checkbox" id="{finding_id}">
            <span class="finding-check">{self.SVG_ICONS["check"]}</span>
            <span class="finding-content">{converted}</span>
        </label>"""

    def _generate_section_html(self, section: dict, section_index: int) -> str:
        """Generate HTML for a single collapsible section."""
        section_id = section["id"]
        title = section["title"]
        errors = section["errors"]
        warnings = section["warnings"]
        info_count = section["info"]
        total_findings = errors + warnings + info_count

        # Build badge summary
        badges = []
        if errors > 0:
            badges.append(f'<span class="section-badge badge-error">{errors}</span>')
        if warnings > 0:
            badges.append(
                f'<span class="section-badge badge-warning">{warnings}</span>'
            )
        if info_count > 0:
            badges.append(f'<span class="section-badge badge-info">{info_count}</span>')
        badges_html = (
            "".join(badges)
            if badges
            else '<span class="section-badge badge-ok">✓</span>'
        )

        # Generate content lines
        content_lines = []
        finding_counter = 0
        for line in section["lines"]:
            if not line.strip():
                content_lines.append('<div class="log-line empty-line">&nbsp;</div>')
                continue

            # Check if this is a finding (has severity marker)
            if any(
                marker in line
                for marker in ["[ERROR]", "[MANDATORY]", "[WARNING]", "[INFO]"]
            ):
                # Use double underscore to separate parts since section IDs contain hyphens
                finding_id = (
                    f"finding__{section_id}__{section_index}__{finding_counter}"
                )
                content_lines.append(self._generate_finding_html(line, finding_id))
                finding_counter += 1
            else:
                converted = self._convert_ansi_line(line)
                content_lines.append(f'<div class="log-line">{converted}</div>')

        content_html = "\n".join(content_lines)

        # Get metadata for ordering
        meta = utils.SECTION_METADATA.get(
            section_id, {"order": 50, "category": "Other", "icon": "folder"}
        )

        return f"""<details class="section" id="section-{section_id}" open data-total="{total_findings}">
            <summary class="section-header">
                <span class="section-chevron">{self.SVG_ICONS["chevron"]}</span>
                <span class="section-title">{escape(title)}</span>
                <span class="section-badges">{badges_html}</span>
                <span class="section-progress" data-section="{section_id}">0/{total_findings}</span>
            </summary>
            <div class="section-content">
                {content_html}
            </div>
        </details>"""

    def generate_html_log(self) -> str:
        """
        Convert the raw ANSI-colored log (self.raw_log_buffer) into a modern HTML document.
        - Parses section markers for collapsible categories
        - Adds checkboxes per finding with localStorage persistence
        - Modern UI with glassmorphism and dark/light mode support
        """
        if not self.raw_log_buffer:
            text_only = self.log_text.get("1.0", "end-1c")
            return self._wrap_html_document(
                '<pre class="log">' + escape(text_only) + "</pre>", [], 0, 0, 0
            )

        # Parse sections from raw buffer
        sections = self._parse_sections(self.raw_log_buffer)

        # Count totals
        total_errors = sum(s["errors"] for s in sections)
        total_warnings = sum(s["warnings"] for s in sections)
        total_info = sum(s["info"] for s in sections)

        # Generate section HTML - skip sections with no findings
        sections_html = []
        for i, section in enumerate(sections):
            # Skip sections with no findings
            total = section["errors"] + section["warnings"] + section["info"]
            if total == 0:
                continue
            sections_html.append(self._generate_section_html(section, i))

        main_content = "\n".join(sections_html)

        return self._wrap_html_document(
            main_content, sections, total_errors, total_warnings, total_info
        )

    def _wrap_html_document(
        self,
        body_inner: str,
        sections: list,
        total_errors: int,
        total_warnings: int,
        total_info: int,
    ) -> str:
        """Return a modern standalone HTML document with glassmorphism, dark/light mode, and checklist functionality."""

        # Get project info for header
        project_path = (
            self.selected_folder.get()
            if hasattr(self.selected_folder, "get")
            else str(self.selected_folder)
        )
        release_version = utils.get_version()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_findings = total_errors + total_warnings + total_info

        # Generate sidebar navigation - only show sections with findings
        nav_items = []
        for section in sections:
            sec_id = section["id"]
            sec_title = section["title"]
            sec_total = section["errors"] + section["warnings"] + section["info"]
            # Skip sections with no findings in navigation
            if sec_total == 0:
                continue
            # Truncate long titles
            display_title = sec_title[:25] + "..." if len(sec_title) > 28 else sec_title
            nav_items.append(
                f"""<a href="#section-{sec_id}" class="nav-item" data-section="{sec_id}">
                <span class="nav-title">{escape(display_title)}</span>
                <span class="nav-progress" data-nav-section="{sec_id}">0/{sec_total}</span>
            </a>"""
            )
        nav_html = "\n".join(nav_items)

        repo_url = "https://github.com/br-automation-community/as6-migration-tools"
        version_label = (
            f" v{escape(release_version)}"
            if release_version and release_version != "dev"
            else ""
        )

        css = """
:root {
    --bg: #0f172a;
    --bg-card: rgba(30, 41, 59, 0.8);
    --bg-card-solid: #1e293b;
    --fg: #e2e8f0;
    --fg-muted: #94a3b8;
    --border: rgba(148, 163, 184, 0.2);
    --border-hover: rgba(148, 163, 184, 0.4);
    --accent: #3b82f6;
    --accent-hover: #60a5fa;
    --error: #ef4444;
    --error-bg: rgba(239, 68, 68, 0.1);
    --warning: #f59e0b;
    --warning-bg: rgba(245, 158, 11, 0.1);
    --info: #22c55e;
    --info-bg: rgba(34, 197, 94, 0.1);
    --success: #10b981;
    --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -4px rgba(0, 0, 0, 0.2);
}

/* Light mode */
[data-theme="light"] {
    --bg: #f8fafc;
    --bg-card: rgba(255, 255, 255, 0.9);
    --bg-card-solid: #ffffff;
    --fg: #1e293b;
    --fg-muted: #64748b;
    --border: rgba(0, 0, 0, 0.1);
    --border-hover: rgba(0, 0, 0, 0.2);
    --error-bg: rgba(239, 68, 68, 0.08);
    --warning-bg: rgba(245, 158, 11, 0.08);
    --info-bg: rgba(34, 197, 94, 0.08);
    --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
}

@media (prefers-color-scheme: light) {
    :root:not([data-theme="dark"]) {
        --bg: #f8fafc;
        --bg-card: rgba(255, 255, 255, 0.9);
        --bg-card-solid: #ffffff;
        --fg: #1e293b;
        --fg-muted: #64748b;
        --border: rgba(0, 0, 0, 0.1);
        --border-hover: rgba(0, 0, 0, 0.2);
        --error-bg: rgba(239, 68, 68, 0.08);
        --warning-bg: rgba(245, 158, 11, 0.08);
        --info-bg: rgba(34, 197, 94, 0.08);
        --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
    }
}

@media print {
    :root {
        --bg: #ffffff;
        --bg-card: #ffffff;
        --bg-card-solid: #ffffff;
        --fg: #000000;
        --fg-muted: #4b5563;
    }
    .sidebar { display: none !important; }
    .main-content { margin-left: 0 !important; }
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; font-size: 16px; }
body {
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 1rem;
    line-height: 1.7;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* Layout */
.layout {
    display: flex;
    min-height: 100vh;
}

/* Sidebar */
.sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 300px;
    height: 100vh;
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-right: 1px solid var(--border);
    padding: 20px 16px;
    overflow-y: auto;
    z-index: 100;
}

.sidebar-header {
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}

.sidebar-title {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0 0 6px 0;
    color: var(--fg);
}

.sidebar-meta {
    font-size: 0.75rem;
    color: var(--fg-muted);
    line-height: 1.4;
}

/* Theme toggle */
.theme-toggle {
    display: flex;
    gap: 4px;
    margin-top: 10px;
    background: var(--border);
    border-radius: 6px;
    padding: 3px;
}

.theme-btn {
    flex: 1;
    padding: 5px 8px;
    border: none;
    border-radius: 5px;
    background: transparent;
    color: var(--fg-muted);
    font-size: 0.7rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
}

.theme-btn:hover {
    color: var(--fg);
}

.theme-btn.active {
    background: var(--bg-card-solid);
    color: var(--fg);
    box-shadow: var(--shadow);
}

.theme-btn svg {
    width: 12px;
    height: 12px;
}

.sidebar-meta a {
    color: var(--accent);
    text-decoration: none;
}
.sidebar-meta a:hover {
    text-decoration: underline;
}

/* Progress summary */
.progress-summary {
    background: var(--bg-card-solid);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 14px;
    border: 1px solid var(--border);
}

.progress-bar-container {
    background: var(--border);
    border-radius: 999px;
    height: 6px;
    overflow: hidden;
    margin-bottom: 10px;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--success), var(--accent));
    border-radius: 999px;
    width: 0%;
    transition: width 0.3s ease;
}

.progress-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--fg);
    text-align: center;
}

/* Summary badges */
.summary-badges {
    display: flex;
    gap: 6px;
    margin-top: 10px;
}

.summary-badge {
    flex: 1;
    text-align: center;
    padding: 6px 4px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}

.summary-badge.error {
    background: var(--error-bg);
    color: var(--error);
}
.summary-badge.warning {
    background: var(--warning-bg);
    color: var(--warning);
}
.summary-badge.info {
    background: var(--info-bg);
    color: var(--info);
}

/* Navigation */
.nav-section {
    margin-bottom: 8px;
}

.nav-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--fg-muted);
    padding: 6px 10px 3px;
}

.nav-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border-radius: 8px;
    color: var(--fg);
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.15s ease;
    margin-bottom: 3px;
    background: var(--bg-card-solid);
    border: 1px solid var(--border);
}

.nav-item:hover {
    background: var(--border);
}

.nav-item.completed {
    opacity: 0.6;
}

.nav-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
}

.nav-progress {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--fg);
    background: var(--border);
    padding: 3px 8px;
    border-radius: 12px;
    font-variant-numeric: tabular-nums;
    min-width: 44px;
    text-align: center;
}

/* Main content */
.main-content {
    margin-left: 300px;
    padding: 32px 40px;
    flex: 1;
    min-width: 0;
}

.header {
    margin-bottom: 32px;
}

.header h1 {
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: var(--fg);
}

.header-meta {
    color: var(--fg-muted);
    font-size: 0.9rem;
}

/* Sections */
.section {
    background: var(--bg-card);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    border-radius: 16px;
    margin-bottom: 16px;
    overflow: hidden;
    box-shadow: var(--shadow);
    transition: all 0.2s ease;
}

.section:hover {
    border-color: var(--border-hover);
}

.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    cursor: pointer;
    user-select: none;
    list-style: none;
    transition: background 0.15s ease;
}

.section-header:hover {
    background: var(--border);
}

.section-header::-webkit-details-marker {
    display: none;
}

.section-chevron {
    transition: transform 0.2s ease;
    color: var(--fg-muted);
}

details[open] .section-chevron {
    transform: rotate(180deg);
}

.section-title {
    flex: 1;
    font-weight: 600;
    font-size: 1.1rem;
}

.section-badges {
    display: flex;
    gap: 6px;
}

.section-badge {
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    min-width: 28px;
    text-align: center;
}

.badge-error { background: var(--error-bg); color: var(--error); }
.badge-warning { background: var(--warning-bg); color: var(--warning); }
.badge-info { background: var(--info-bg); color: var(--info); }
.badge-ok { background: var(--info-bg); color: var(--success); }

.section-progress {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--fg);
    background: var(--border);
    padding: 4px 12px;
    border-radius: 20px;
    font-variant-numeric: tabular-nums;
    min-width: 55px;
    text-align: center;
}

.section-content {
    padding: 0 20px 20px;
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.9rem;
}

/* Log lines */
.log-line {
    padding: 6px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.7;
}

.log-line br {
    display: block;
    content: "";
    margin-top: 0.3em;
}

.empty-line {
    height: 0.75em;
}

/* Findings (checkable items) */
.finding {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
}

.finding:hover {
    background: var(--border);
}

.finding-error { background: var(--error-bg); border-left: 3px solid var(--error); }
.finding-warning { background: var(--warning-bg); border-left: 3px solid var(--warning); }
.finding-info { background: var(--info-bg); border-left: 3px solid var(--info); }

.finding-checkbox {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
}

.finding-check {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-hover);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
    background: var(--bg-card-solid);
}

.finding-check .icon {
    opacity: 0;
    transform: scale(0.5);
    transition: all 0.15s ease;
    color: var(--success);
}

.finding-checkbox:checked + .finding-check {
    background: var(--success);
    border-color: var(--success);
}

.finding-checkbox:checked + .finding-check .icon {
    opacity: 1;
    transform: scale(1);
    color: white;
}

.finding-checkbox:checked ~ .finding-content {
    opacity: 0.5;
    text-decoration: line-through;
}

.finding-content {
    flex: 1;
    transition: opacity 0.15s ease;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.7;
}

/* Icons */
.icon {
    width: 16px;
    height: 16px;
    display: inline-block;
    vertical-align: middle;
}

.icon-error { color: var(--error); }
.icon-warning { color: var(--warning); }
.icon-info { color: var(--info); }
.icon-chevron { width: 20px; height: 20px; }

/* Severity labels */
.sev-error { color: var(--error); font-weight: 700; }
.sev-warning { color: var(--warning); font-weight: 700; }
.sev-info { color: var(--info); }
.sev-label { margin-left: 4px; }

/* Links */
a {
    color: var(--accent);
    text-decoration: none;
    transition: color 0.15s ease;
}
a:hover {
    color: var(--accent-hover);
    text-decoration: underline;
}

/* Responsive */
@media (max-width: 1100px) {
    .sidebar {
        width: 260px;
        padding: 16px 12px;
    }
    .main-content {
        margin-left: 260px;
        padding: 24px;
    }
}

@media (max-width: 900px) {
    .sidebar {
        position: static;
        width: 100%;
        height: auto;
        border-right: none;
        border-bottom: 1px solid var(--border);
    }
    .main-content {
        margin-left: 0;
        padding: 20px;
    }
    .nav-item {
        padding: 10px 12px;
    }
}
"""

        js = """
(function() {
    const STORAGE_KEY = 'as6-migration-checklist-' + location.pathname;
    
    // Load saved state
    function loadState() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
        } catch (e) {
            return {};
        }
    }
    
    // Save state
    function saveState(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (e) {}
    }
    
    // Update progress displays
    function updateProgress() {
        const state = loadState();
        const checkboxes = document.querySelectorAll('.finding-checkbox');
        let totalChecked = 0;
        const sectionCounts = {};
        
        checkboxes.forEach(cb => {
            // ID format: finding__sectionId__sectionIndex__findingCounter
            const parts = cb.id.split('__');
            const sectionId = parts[1]; // Extract section ID
            if (!sectionCounts[sectionId]) {
                sectionCounts[sectionId] = { checked: 0, total: 0 };
            }
            sectionCounts[sectionId].total++;
            if (cb.checked) {
                sectionCounts[sectionId].checked++;
                totalChecked++;
            }
        });
        
        // Update section progress
        Object.keys(sectionCounts).forEach(sectionId => {
            const { checked, total } = sectionCounts[sectionId];
            // Only update elements with class .section-progress or .nav-progress, not the entire nav-item
            const els = document.querySelectorAll(`.section-progress[data-section="${sectionId}"], .nav-progress[data-nav-section="${sectionId}"]`);
            els.forEach(el => el.textContent = `${checked}/${total}`);
            
            // Mark nav item as completed
            const navItem = document.querySelector(`.nav-item[data-section="${sectionId}"]`);
            if (navItem) {
                navItem.classList.toggle('completed', checked === total && total > 0);
            }
        });
        
        // Update total progress
        const total = checkboxes.length;
        const percent = total > 0 ? Math.round((totalChecked / total) * 100) : 0;
        const progressBar = document.querySelector('.progress-bar');
        const progressText = document.querySelector('.progress-text');
        if (progressBar) progressBar.style.width = percent + '%';
        if (progressText) progressText.textContent = `${totalChecked} of ${total} completed (${percent}%)`;
    }
    
    // Theme handling
    const THEME_KEY = 'as6-migration-theme';
    
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    
    function setTheme(theme) {
        if (theme === 'auto') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
        localStorage.setItem(THEME_KEY, theme);
        updateThemeButtons(theme);
    }
    
    function updateThemeButtons(theme) {
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === theme);
        });
    }
    
    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        const state = loadState();
        
        // Restore checkbox states
        document.querySelectorAll('.finding-checkbox').forEach(cb => {
            if (state[cb.id]) {
                cb.checked = true;
            }
            
            // Listen for changes
            cb.addEventListener('change', function() {
                const newState = loadState();
                if (this.checked) {
                    newState[this.id] = true;
                } else {
                    delete newState[this.id];
                }
                saveState(newState);
                updateProgress();
            });
        });
        
        // Restore section collapse states and listen for changes
        const SECTIONS_KEY = 'as6-migration-sections-' + location.pathname;
        let sectionState = {};
        try {
            sectionState = JSON.parse(localStorage.getItem(SECTIONS_KEY)) || {};
        } catch (e) {}
        
        document.querySelectorAll('details.section').forEach(details => {
            const sectionId = details.id;
            // Restore saved state (default is open)
            if (sectionState[sectionId] === false) {
                details.removeAttribute('open');
            }
            
            // Listen for toggle events
            details.addEventListener('toggle', function() {
                let currentState = {};
                try {
                    currentState = JSON.parse(localStorage.getItem(SECTIONS_KEY)) || {};
                } catch (e) {}
                currentState[this.id] = this.open;
                try {
                    localStorage.setItem(SECTIONS_KEY, JSON.stringify(currentState));
                } catch (e) {}
            });
        });
        
        // Initialize theme
        const savedTheme = localStorage.getItem(THEME_KEY) || 'auto';
        setTheme(savedTheme);
        
        // Theme toggle buttons
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => setTheme(btn.dataset.theme));
        });
        
        updateProgress();
    });
})();
"""

        header_html = f"""
<div class="header">
    <h1>AS4 to AS6 Migration Report</h1>
    <div class="header-meta">
        <strong>Project:</strong> {escape(project_path or "-")} &nbsp;|&nbsp;
        <strong>Generated:</strong> {escape(ts)}
    </div>
</div>
"""

        sidebar_html = f"""
<aside class="sidebar">
    <div class="sidebar-header">
        <h2 class="sidebar-title">Migration Checklist</h2>
        <div class="sidebar-meta">
            <a href="{repo_url}">as6-migration-tools{version_label}</a>
        </div>
        <div class="theme-toggle">
            <button class="theme-btn" data-theme="light" title="Light mode">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                Light
            </button>
            <button class="theme-btn active" data-theme="auto" title="Auto (system)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0 0 20V2z" fill="currentColor"/></svg>
                Auto
            </button>
            <button class="theme-btn" data-theme="dark" title="Dark mode">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
                Dark
            </button>
        </div>
    </div>
    
    <div class="progress-summary">
        <div class="progress-bar-container">
            <div class="progress-bar"></div>
        </div>
        <div class="progress-text">0 of {total_findings} completed (0%)</div>
        <div class="summary-badges">
            <div class="summary-badge error">{total_errors} Errors</div>
            <div class="summary-badge warning">{total_warnings} Warnings</div>
            <div class="summary-badge info">{total_info} Info</div>
        </div>
    </div>
    
    <nav class="nav-section">
        <div class="nav-label">Sections</div>
        {nav_html}
    </nav>
</aside>
"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AS4 to AS6 Migration Report</title>
    <style>{css}</style>
</head>
<body>
    <div class="layout">
        {sidebar_html}
        <main class="main-content">
            {header_html}
            {body_inner}
        </main>
    </div>
    <script>{js}</script>
</body>
</html>"""

    def clear_log(self):
        """Clear GUI log and the raw buffer."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.raw_log_buffer.clear()

    def run(self):
        self.root.mainloop()

    # --- Update Check Integration ---
    def _async_check_updates(self):
        try:
            from update_check import check_for_newer

            current = utils.get_version()

            info = check_for_newer(current)
            if info:
                # Schedule popup in main thread
                self.root.after(0, lambda: self._show_update_popup(info))
        except Exception:
            pass

    def _show_update_popup(self, info: dict):
        # Do not show if window already destroyed
        if not hasattr(self, "root"):
            return

        appearance = ctk.get_appearance_mode()
        bg = "#f0f0f0" if appearance == "Light" else "#2a2d2e"
        fg = "#000000" if appearance == "Light" else "#ffffff"

        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title("Update available")
        win.configure(bg=bg)
        win.geometry("720x420")
        win.resizable(False, False)
        try:
            icon_path = os.path.join(
                getattr(sys, "_MEIPASS", os.path.abspath(".")), "gui_icon.ico"
            )
            win.iconbitmap(icon_path)
        except Exception:
            pass

        tag = info.get("tag")
        url = info.get("html_url") or info.get("download_url")
        raw_body = info.get("body", "") or ""
        body = raw_body.strip()[:4000]

        # Header (keep it simple and consistent)
        tk.Label(
            win, text=f"New version available: {tag}", font=LABEL_FONT, bg=bg, fg=fg
        ).pack(pady=(10, 4), anchor="w", padx=16)

        # Compute changelog text
        current_version = utils.get_version()
        new_version = tag.replace("v", "") if tag else ""
        changelog = body
        if current_version != "dev":
            changelog_info = get_changelog_between_versions(
                current_version, new_version
            )
            if changelog_info.get("success"):
                changelog = changelog_info.get("changelog") or changelog

        # "What's new"
        tk.Label(
            win, text="What's new", font=("Segoe UI", 10, "bold"), bg=bg, fg=fg
        ).pack(pady=(0, 4), anchor="w", padx=16)

        # Scrollable notes with a visible scrollbar (CTk if available; else ttk)
        text_frame = tk.Frame(win, bg=bg)
        text_frame.pack(fill="both", expand=True, padx=16)

        # Use grid to make the textbox and scrollbar resize nicely
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        try:
            # Preferred: CTkTextbox + CTkScrollbar for consistent theming
            notes = ctk.CTkTextbox(text_frame, wrap="word")
            notes.grid(row=0, column=0, sticky="nsew")
            sb = ctk.CTkScrollbar(text_frame, command=notes.yview)
            sb.grid(row=0, column=1, sticky="ns", padx=(6, 0))
            notes.configure(yscrollcommand=sb.set)
        except Exception:
            # Fallback: tk.Text + ttk.Scrollbar
            notes = tk.Text(
                text_frame,
                wrap="word",
                bg=bg,
                fg=fg,
                relief="flat",
                borderwidth=0,
            )
            notes.grid(row=0, column=0, sticky="nsew")
            sb = ttk.Scrollbar(text_frame, orient="vertical", command=notes.yview)
            sb.grid(row=0, column=1, sticky="ns", padx=(6, 0))
            notes.configure(yscrollcommand=sb.set)

        notes.insert("1.0", changelog or "(No release notes)")
        notes.configure(state="disabled")

        # Button row
        btn_row = tk.Frame(win, bg=bg)
        # Anchor buttons at the bottom so they stay visible
        btn_row.pack(side="bottom", fill="x", pady=12, padx=16)

        def ignore_version():
            try:
                from update_check import set_ignored_version

                set_ignored_version(tag)
            except Exception:
                pass
            win.destroy()

        def get_version():
            if url:
                webbrowser.open_new(url)
            win.destroy()

        def later():
            win.destroy()

        ctk.CTkButton(
            btn_row,
            text="Skip this version",
            command=ignore_version,
            fg_color="#444444",
            hover_color="#555555",
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="Open release page",
            command=get_version,
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(
            side="right", padx=(8, 0)
        )  # spacing to the left

        ctk.CTkButton(
            btn_row,
            text="Remind me later",
            command=later,
            fg_color="#444444",
            hover_color="#555555",
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(side="right")

        # Center and show
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (720 // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (420 // 2)
        win.geometry(f"+{x}+{y}")
        win.transient(self.root)
        win.grab_set()
        win.focus_set()
        win.bind("<Escape>", lambda e: win.destroy())
        win.deiconify()

    def _center_window(self, win, w, h):
        try:
            win.update_idletasks()
            x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
            y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass


if __name__ == "__main__":
    app = ModernMigrationGUI()
    app.run()
