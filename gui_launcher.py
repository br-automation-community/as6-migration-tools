import importlib.util
import os
import sys
import threading
import tkinter as tk
import webbrowser
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

        import utils.utils as shared_utils

        original_ask_user = shared_utils.ask_user

        def ask_user_gui_wrapper(*args, **kwargs):
            if "parent" not in kwargs or kwargs["parent"] is None:
                kwargs["parent"] = self.root
            return original_ask_user(*args, **kwargs)

        shared_utils.ask_user = ask_user_gui_wrapper
        sys.modules["utils.utils"] = shared_utils
        self.utils = shared_utils

        build = utils.get_build_number()
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
        }

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
        self.save_log_option = file_dropdown.add_option("Save Log", self.save_log)
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

    def toggle_save_buttons(self, *args):
        state = "normal" if self.script_ran.get() else "disabled"
        self.save_button.configure(state=state)
        self.save_log_option.configure(state=state)

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

    def build_save_ui(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(0, 20))
        self.save_button = ctk.CTkButton(
            frame,
            text="Save Log",
            command=self.save_log,
            state="disabled",
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
            corner_radius=8,
        )
        self.save_button.pack(anchor="e")
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

        if not os.path.exists(folder):
            self.append_log(f"[ERROR] Folder does not exist:\n{folder}")
            self.update_status("Invalid folder")
            self.spinner_running = False
            return

        if not self.is_valid_as4_project(folder):
            self.append_log(f"[ERROR] Folder is not a valid AS4 project:\n{folder}")
            self.update_status("Not a valid AS4 project")
            self.spinner_running = False
            return

        if not os.path.exists(script):
            self.append_log(f"[ERROR] Script not found:\n{script}")
            self.update_status("Script missing")
            self.spinner_running = False
            return

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            stdlib_path = Path(sys._MEIPASS) / "lib"
            if stdlib_path.exists():
                sys.path.insert(0, str(stdlib_path.resolve()))

        spec = importlib.util.spec_from_file_location("selected_script", script)
        module = importlib.util.module_from_spec(spec)
        sys.modules["selected_script"] = module

        original_stdout, original_stderr = sys.stdout, sys.stderr
        redirector = RedirectText(self.append_log, self.update_status)
        sys.stdout = redirector
        sys.stderr = redirector

        try:
            spec.loader.exec_module(module)
            sys.argv = ["analyzer", folder]
            if verbose:
                sys.argv.append("--verbose")
            module.main()
        except Exception as e:
            import traceback

            print(f"[ERROR] Execution failed: {e}")
            print(traceback.format_exc())
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self.spinner_running = False

        self.update_status("Script finished successfully")
        self.script_ran.set(True)

    def append_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def update_status(self, message):
        self.status_label.after(0, lambda: self.status_label.configure(text=message))

    def save_log(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if file_path:
            try:
                log_content = self.log_text.get("1.0", "end")
                Path(file_path).write_text(log_content, encoding="utf-8")
                messagebox.showinfo("Success", f"Log saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ModernMigrationGUI()
    app.run()
