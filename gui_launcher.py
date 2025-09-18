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
from tkinter import filedialog, messagebox

import customtkinter as ctk
from CTkMenuBar import CTkMenuBar, CustomDropdownMenu

import utils.utils as utils

B_R_BLUE = "#3B82F6"
HOVER_BLUE = "#2563EB"

LABEL_FONT = ("Segoe UI", 14, "bold")
FIELD_FONT = ("Segoe UI", 13)
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
            "Create mapp folders": self.resource_path("helpers/create_mapp_folders.py"),
            "MappMotion Update": self.resource_path("helpers/mappmotion_update.py"),
            "License checker": self.resource_path("helpers/license_checker.py"),
        }

        self.links = utils.load_file_info("links", "links")

        self.build_ui()
        self.script_ran.trace_add("write", self.toggle_save_buttons)
        self.update_menubar_theme()
        self.selected_folder.trace_add("write", self.toggle_run_button)
        self.toggle_run_button()

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
        import os, subprocess, tempfile

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
        import shutil, subprocess, re
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
            messagebox.showerror("Export failed", f"Could not export report:\n{e}")
            return

        subject = self._build_email_subject()
        body_html = (
            self._build_email_body_html()
        )  # short HTML summary (see helper below)

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
        about_text = (
            "Open-source tools for analyzing and migrating B&R Automation Studio 4 (AS4) projects to Automation Studio 6 (AS6).\n\n"
            "Detects obsolete libraries, unsupported hardware, deprecated functions – and includes helper scripts for automatic code conversion.\n\n"
            "🔶 Disclaimer: This project is unofficial and not provided or endorsed by B&R Industrial Automation.\n"
            "It is offered as an open-source tool, with no warranty or guarantees.\n"
            "Use at your own risk — contributions and improvements are very welcome!"
        )

        appearance = ctk.get_appearance_mode()
        bg = "#f0f0f0" if appearance == "Light" else "#2a2d2e"
        fg = "#000000" if appearance == "Light" else "#ffffff"

        msg_win = tk.Toplevel(self.root)
        msg_win.withdraw()  # Hide initially
        msg_win.title("About")
        msg_win.configure(bg=bg)
        msg_win.geometry("720x360")
        msg_win.resizable(False, False)

        try:
            icon_path = os.path.join(
                getattr(sys, "_MEIPASS", os.path.abspath(".")), "gui_icon.ico"
            )
            msg_win.iconbitmap(icon_path)
        except Exception:
            pass

        msg_win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (720 // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (360 // 2)
        msg_win.geometry(f"+{x}+{y}")

        # Show version/build at the top of the About box
        build = utils.get_version()
        tk.Label(msg_win, text=f"Version: {build}", font=LABEL_FONT, bg=bg, fg=fg).pack(
            pady=(8, 4)
        )

        tk.Label(
            msg_win,
            text=about_text,
            justify="left",
            bg=bg,
            fg=fg,
            font=FIELD_FONT,
            padx=20,
            pady=20,
            wraplength=680,
        ).pack(anchor="w")

        ctk.CTkButton(
            master=msg_win,
            text="Open GitHub",
            command=lambda: webbrowser.open_new(
                "https://github.com/br-automation-community/as6-migration-tools"
            ),
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            width=160,
            height=36,
            corner_radius=8,
        ).pack(pady=(0, 20))

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
        elif not os.path.exists(script):
            error_message = f"Script not found: {script}"

        if error_message:
            utils.log(error_message, severity="ERROR")
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
        ansi_pattern = r"(\x1b\[[0-9;]*m)"

        parts = re.split(ansi_pattern, text)
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
    # HTML export (Save Log)
    # ---------------------------

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

    def generate_html_log(self) -> str:
        """
        Convert the raw ANSI-colored log (self.raw_log_buffer) into an HTML document.
        - Preserves colors (ERROR/WARNING/INFO) via CSS classes.
        - Turns underline+blue segments into <a href="...">...</a> using links.json mapping.
        - Adds a simple header with project path, date, and tool version.
        """
        # Fallback if raw buffer is empty (shouldn't happen if a script ran)
        if not self.raw_log_buffer:
            text_only = self.log_text.get("1.0", "end-1c")
            return self._wrap_html_document(self._wrap_pre(escape(text_only)))

        ansi_pattern = r"(\x1b\[[0-9;]*m)"  # SGR sequences
        # Fast-path for known severity colors (kept for compatibility)
        fast_color_map = {
            "\x1b[1;31m": "red",  # ERROR/MANDATORY
            "\x1b[1;33m": "orange",  # WARNING
            "\x1b[92m": "green",  # INFO
        }

        body_parts = []
        current = "normal"

        # Track SGR flags to detect links robustly
        underline_on = False
        blue_on = False

        link_buffer = []

        def flush_link():
            """Flush accumulated link text into an <a> tag and reset the link buffer."""
            nonlocal link_buffer
            link_text = "".join(link_buffer).strip()
            link_buffer.clear()
            if link_text:
                try:
                    href = utils.build_web_path(self.links, link_text)
                except Exception:
                    href = link_text  # best effort fallback
                body_parts.append(f'<a href="{escape(href)}">{escape(link_text)}</a>')

        import re as _re

        for raw_line in self.raw_log_buffer:
            tokens = _re.split(ansi_pattern, raw_line)  # keep ANSI tokens
            for t in tokens:
                if not t:
                    continue

                # Is this an SGR code?
                if _re.fullmatch(ansi_pattern, t):
                    # Parse SGR params, e.g. "1;31", "4", "94", "0"
                    params = t[2:-1]  # strip \x1b[  and trailing m
                    codes = []
                    if params:
                        for c in params.split(";"):
                            if c.isdigit():
                                try:
                                    codes.append(int(c))
                                except ValueError:
                                    pass

                    # Reset?
                    if 0 in codes:
                        # Leaving any modes, close a pending link if needed
                        if current == "blue":
                            flush_link()
                        underline_on = False
                        blue_on = False
                        current = "normal"
                        continue

                    # Toggle underline/color flags (24 = underline off, 39 = default fg color)
                    if 4 in codes:
                        underline_on = True
                    if 24 in codes:
                        underline_on = False
                    if 94 in codes:
                        blue_on = True
                    if 39 in codes:
                        blue_on = False

                    # Determine if we should be in link (blue+underline) mode
                    want_blue = underline_on and blue_on
                    if current == "blue" and not want_blue:
                        flush_link()
                        current = "normal"
                        # Note: keep evaluating for severity fast-path below

                    if want_blue and current != "blue":
                        current = "blue"
                        continue  # style change handled; next token will be text

                    # Fast-path severity colors (still allow them to override normal mode)
                    if t in fast_color_map:
                        # If we were in link mode, close it before switching to colored spans
                        if current == "blue":
                            flush_link()
                            current = "normal"
                        current = fast_color_map[t]
                        continue

                    # Any other SGR we don't care about
                    continue

                # --- Normal text chunk ---
                if current == "blue":
                    # Handle possible embedded newlines inside link text
                    s = t.replace("\r\n", "\n")
                    parts = s.split("\n")
                    for i, seg in enumerate(parts):
                        if seg:
                            link_buffer.append(seg)
                        if i < len(parts) - 1:
                            flush_link()
                            body_parts.append("\n")
                else:
                    safe = escape(t)
                    if current in ("red", "orange", "green"):
                        body_parts.append(f'<span class="{current}">{safe}</span>')
                    else:
                        body_parts.append(safe)

        # End of stream: close any pending link
        if current == "blue":
            flush_link()

        # Build header/meta
        project_path = (
            self.selected_folder.get()
            if hasattr(self.selected_folder, "get")
            else str(self.selected_folder)
        )

        release_version = utils.get_version()

        header_html = self._build_header(project_path, release_version)

        body_html = "".join(body_parts)
        # Add icons/labels to [ERROR]/[MANDATORY]/[WARNING]/[INFO]
        body_html = self._add_severity_icons(body_html)

        return self._wrap_html_document(header_html + self._wrap_pre(body_html))

    def _wrap_pre(self, inner: str) -> str:
        """Wrap log body in <pre> to preserve whitespace/newlines."""
        return f'<pre class="log">{inner}</pre>'

    def _add_severity_icons(self, html: str) -> str:
        """
        Post-process the rendered HTML (inside <pre>) and prepend an icon + ARIA label
        to severity tokens like [ERROR]/[MANDATORY]/[WARNING]/[INFO].
        Keeps the original token for familiarity, improves accessibility/scanability.
        """
        import re

        replacements = {
            r"\[ERROR\]": '<span class="sev sev-error" role="img" aria-label="Error">❗</span><span class="sr-only">Error: </span>[ERROR]',
            r"\[MANDATORY\]": '<span class="sev sev-error" role="img" aria-label="Mandatory">❗</span><span class="sr-only">Mandatory: </span>[MANDATORY]',
            r"\[WARNING\]": '<span class="sev sev-warning" role="img" aria-label="Warning">⚠️</span><span class="sr-only">Warning: </span>[WARNING]',
            r"\[INFO\]": '<span class="sev sev-info" role="img" aria-label="Info">ℹ️</span><span class="sr-only">Info: </span>[INFO]',
        }
        for pat, repl in replacements.items():
            html = re.sub(pat, repl, html)
        return html

    def _build_header(self, project_path: str, release_version: str) -> str:
        """Build the header with counters, metadata and a repo link."""
        raw = "".join(self.raw_log_buffer)
        err = raw.count("[ERROR]") + raw.count("[MANDATORY]")
        warn = raw.count("[WARNING]")
        info = raw.count("[INFO]")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Read/clean version and build the link label
        version = (release_version or "").strip()
        repo_url = "https://github.com/br-automation-community/as6-migration-tools"
        link_label = "as6-migration-tools" + (f" {escape(version)}" if version else "")
        tool_link_html = f'<a href="{repo_url}">{link_label}</a>'

        badges = (
            f'<span class="badge red"><span class="ico" role="img" aria-label="Errors">❗</span>Errors: {err}</span>'
            f'<span class="badge orange"><span class="ico" role="img" aria-label="Warnings">⚠️</span>Warnings: {warn}</span>'
            f'<span class="badge green"><span class="ico" role="img" aria-label="Info items">ℹ️</span>Info: {info}</span>'
        )

        meta = f"""
    <div class="meta">
      <div><strong>Project:</strong> {escape(project_path or "-")}</div>
      <div><strong>Generated:</strong> {escape(ts)}</div>
      <div>{tool_link_html}</div>  <!-- replaces 'Tool version:' line -->
    </div>
    """
        return f"<header><h1>AS4 to AS6 Migration Log</h1>{badges}{meta}<hr></header>"

    def _wrap_html_document(self, body_inner: str) -> str:
        """Return a minimal standalone HTML document with dark theme and print-friendly light mode."""
        css = """
    :root {
      --bg: #0f172a;       /* slate-900 */
      --fg: #e5e7eb;       /* gray-200 */
      --muted: #94a3b8;    /* slate-400 */
      --hr: rgba(148, 163, 184, 0.25);
      --badge-bg: #1f2937; /* gray-800 */
      --link: #60a5fa;     /* blue-400 */
      --red: #ef4444;      /* red-500 */
      --orange: #f59e0b;   /* amber-500 */
      --green: #22c55e;    /* green-500 */
    }
    @media print {
      :root {
        --bg: #ffffff;
        --fg: #111827;
        --muted: #374151;
        --hr: #e5e7eb;
        --badge-bg: #f3f4f6;
        --link: #1d4ed8;
      }
      body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
    html, body { height: 100%; }
    body {
      background: var(--bg);
      color: var(--fg);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      margin: 20px;
      line-height: 1.35;
    }
    header h1 { margin: 0 0 6px 0; font-size: 20px; font-weight: 700; color: var(--fg); }

    /* Badges */
    .badge {
      display: inline-block; padding: 2px 8px; border-radius: 9999px; margin-right: 8px;
      font-size: 12px; font-weight: 700; background: var(--badge-bg);
      font-variant-numeric: tabular-nums;   /* stable widths for counts */
    }
    .badge.red    { color: var(--red); }
    .badge.orange { color: var(--orange); }
    .badge.green  { color: var(--green); }
    .badge .ico { margin-right: 6px; display: inline-block; }

    /* Meta */
    .meta { margin-top: 8px; font-size: 12px; color: var(--muted); }

    /* Log body */
    .log {
      white-space: pre-wrap;
      font-size: 13px;
      margin: 0;           /* avoid extra spacing around the log */
      tab-size: 4;         /* nicer alignment for indented/log-style text */
    }
    .log a { word-break: break-word; overflow-wrap: anywhere; }

    /* Severity color spans (already emitted by generator) */
    .red    { color: var(--red);   font-weight: 700; }
    .orange { color: var(--orange);font-weight: 700; }
    .green  { color: var(--green); }

    /* Anchors, rule */
    a { color: var(--link); text-decoration: underline; }
    hr { border: 0; height: 1px; background: var(--hr); margin: 12px 0 16px 0; }

    /* Screen-reader only label (for accessibility) */
    .sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
    }

    /* Inline severity icon used in lines */
    .sev {
      display: inline-block; width: 1.25em; text-align: center; margin-right: .25em;
      vertical-align: -0.08em; /* icon baseline alignment */
    }
    .sev-error   { color: var(--red);   font-weight: 700; }
    .sev-warning { color: var(--orange);font-weight: 700; }
    .sev-info    { color: var(--green); }
    """
        return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AS4 to AS6 Migration Log</title>
    <style>{css}</style>
    </head>
    <body>
    {body_inner}
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


if __name__ == "__main__":
    app = ModernMigrationGUI()
    app.run()
