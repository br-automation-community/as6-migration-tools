import os
import sys
import threading
import importlib.util
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter import messagebox
from pathlib import Path

from utils import utils


def resource_path(rel_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(base, rel_path))


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


class MigrationGUI:
    def __init__(self, root):
        self.root = root
        # Set application icon (for taskbar and window title)
        icon_path = os.path.join(
            getattr(sys, "_MEIPASS", os.path.abspath(".")), "gui_icon.ico"
        )
        self.root.iconbitmap(icon_path)

        build = utils.get_build_number()
        self.root.title(f"AS4 to AS6 Migration Tool (Build {build})")
        self.root.geometry("1500x700")

        self.selected_folder = tk.StringVar()
        self.selected_script = tk.StringVar(value="Evaluate AS4 project")
        self.verbose_mode = tk.BooleanVar(value=False)

        self.scripts = {
            "Evaluate AS4 project": resource_path("as4_to_as6_analyzer.py"),
            "AsMathToAsBrMath": resource_path("helpers/asmath_to_asbrmath.py"),
            "AsStringToAsBrStr": resource_path("helpers/asstring_to_asbrstr.py"),
            "OpcUa Update": resource_path("helpers/asopcua_update.py"),
            "Create mapp folders": resource_path("helpers/create_mapp_folders.py"),
            "mappMotion Update": resource_path("helpers/mappmotion_update.py"),
        }

        self.build_ui()
        # self.append_log(f"Running from: {os.getcwd()}\n")

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="x")

        ttk.Label(frame, text="Project folder:").pack(anchor="w")
        folder_entry = ttk.Entry(frame, textvariable=self.selected_folder, width=80)
        folder_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="Browse", command=self.browse_folder).pack(
            side="left", padx=5
        )

        script_frame = ttk.Frame(self.root, padding=10)
        script_frame.pack(fill="x")
        ttk.Label(script_frame, text="Select script:").pack(side="left", anchor="w")
        script_menu_frame = ttk.Frame(script_frame, borderwidth=2, relief="groove")
        script_menu_frame.pack(side="left", padx=5, pady=5)
        script_menu = ttk.OptionMenu(
            script_menu_frame,
            self.selected_script,
            self.selected_script.get(),
            *self.scripts.keys(),
        )
        script_menu.pack(anchor="w")
        script_menu.config(width=20)

        verbose_checkbox = ttk.Checkbutton(
            script_frame, text="Verbose Mode", variable=self.verbose_mode
        )
        verbose_checkbox.pack(side="left", padx=5)

        run_button = ttk.Button(script_frame, text="Run", command=self.execute_script)
        run_button.pack(side="left", padx=5)
        run_button.config(state="disabled")
        self.selected_folder.trace_add(
            "write",
            lambda *args: run_button.config(
                state="normal" if self.selected_folder.get() else "disabled"
            ),
        )

        save_log_button = ttk.Button(
            script_frame, text="Save Log As...", command=self.save_log
        )
        save_log_button.pack(side="left", padx=5)
        save_log_button.config(state="disabled")
        self.script_ran = tk.BooleanVar(value=False)
        self.script_ran.trace_add(
            "write",
            lambda *args: save_log_button.config(
                state="normal" if self.script_ran.get() else "disabled"
            ),
        )

        self.status_label = ttk.Label(
            self.root,
            text="",
            font=("Courier", 12),
            background="black",
            foreground="yellow",
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=10)

        self.log_text = tk.Text(
            self.root, wrap="word", height=25, bg="black", fg="lime"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.config(state="disabled")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder.set(folder)

    def execute_script(self):
        threading.Thread(target=self._worker_execute_script, daemon=True).start()

    def _worker_execute_script(self):
        self.clear_log()
        folder = self.selected_folder.get()
        script = self.scripts.get(self.selected_script.get())
        verbose = self.verbose_mode.get()
        # self.append_log(f"[DEBUG] Selected script -> {script}\n")

        if not os.path.exists(folder):
            self.append_log(f"Error: Folder does not exist:\n{folder}")
            return
        if not os.path.exists(script):
            self.append_log(f"Error: Script not found:\n{script}")
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
        except Exception as e:
            self.append_log(f"Error loading script: {e}\n")
            return

        original_stdout, original_stderr = sys.stdout, sys.stderr
        redirector = RedirectText(self.append_log, self.update_status)
        sys.stdout = redirector
        sys.stderr = redirector

        try:
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

        self.status_label.config(text="--- Script Finished ---")
        self.script_ran.set(True)

    def append_log(self, message):
        self.log_text.config(state="normal")
        try:
            self.log_text.insert(tk.END, message)
        except UnicodeEncodeError:
            self.log_text.insert(
                tk.END, message.encode("utf-8", errors="replace").decode("utf-8")
            )
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def update_status(self, message):
        self.status_label.after(0, lambda: self.status_label.config(text=message))

    def save_log(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if file_path:
            try:
                log_content = self.log_text.get("1.0", tk.END)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("Success", f"Log saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = MigrationGUI(root)
    root.mainloop()
