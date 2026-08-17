#!/usr/bin/env python3
"""
Antigravity Desktop Manager
A robust, cross-platform GUI manager for the Antigravity Desktop App.
Built with standard tkinter (ttk) to guarantee 100% zero-dependency support on Linux, Mac, and Windows.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

AGY_ACCOUNTS_DIR = Path.home() / ".agy_accounts"
TARGET_CMD = "antigravity"
APP_TITLE = "Antigravity Desktop Manager"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("550x500")
        self.resizable(False, False)
        
        # Try to use a modern theme if available
        style = ttk.Style(self)
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")
        elif "vista" in available_themes:
            style.theme_use("vista")
            
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header = ttk.Label(self, text=APP_TITLE, font=("Helvetica", 18, "bold"))
        header.grid(row=0, column=0, pady=20)
        
        # Profile List
        list_frame = ttk.LabelFrame(self, text="Select an existing profile:")
        list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Helvetica", 11))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.listbox.yview)
        
        # Controls Frame
        control_frame = ttk.Frame(self)
        control_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        # Control Buttons
        btn_launch = ttk.Button(control_frame, text="🚀 Launch", command=self.launch_profile)
        btn_launch.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        btn_shortcut = ttk.Button(control_frame, text="💻 Shortcut", command=self.create_shortcut)
        btn_shortcut.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        btn_export = ttk.Button(control_frame, text="📦 Export", command=self.export_profile)
        btn_export.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        btn_delete = ttk.Button(control_frame, text="🗑️ Delete", command=self.delete_profile)
        btn_delete.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        # New Profile Frame
        new_frame = ttk.LabelFrame(self, text="Create or Import Profile:")
        new_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        self.entry_new = ttk.Entry(new_frame, font=("Helvetica", 11))
        self.entry_new.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)
        self.entry_new.bind("<Return>", lambda e: self.create_profile())
        
        btn_new = ttk.Button(new_frame, text="Create & Launch", command=self.create_profile)
        btn_new.pack(side=tk.LEFT, padx=5)
        
        btn_import = ttk.Button(new_frame, text="Import Zip", command=self.import_profile)
        btn_import.pack(side=tk.LEFT, padx=10)
        
        self.refresh_list()
        
    def get_profiles(self):
        if not AGY_ACCOUNTS_DIR.exists():
            AGY_ACCOUNTS_DIR.mkdir(parents=True)
        return sorted([d.name for d in AGY_ACCOUNTS_DIR.iterdir() if d.is_dir()])

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        profiles = self.get_profiles()
        for p in profiles:
            self.listbox.insert(tk.END, p)

    def get_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a profile from the list.")
            return None
        return self.listbox.get(selection[0])

    def load_env(self, profile_dir):
        env_file = profile_dir / ".env"
        env = os.environ.copy()
        env["HOME"] = str(profile_dir)
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip()
        else:
            env_file.write_text("# Add environment variables here (e.g. API_KEY=value)\n")
        return env

    def do_launch(self, profile_name):
        profile_dir = AGY_ACCOUNTS_DIR / profile_name
        profile_dir.mkdir(exist_ok=True)
        env = self.load_env(profile_dir)
        
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", TARGET_CMD], env=env)
            elif sys.platform == "win32":
                subprocess.Popen(f'start "" {TARGET_CMD}', env=env, shell=True)
            else:
                subprocess.Popen([TARGET_CMD], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Could not find '{TARGET_CMD}' on your system.")

    def launch_profile(self):
        p = self.get_selected()
        if p: self.do_launch(p)

    def create_profile(self):
        p = self.entry_new.get().strip()
        if p:
            self.do_launch(p)
            self.entry_new.delete(0, tk.END)
            self.refresh_list()
        else:
            messagebox.showwarning("Warning", "Profile name cannot be empty!")

    def create_shortcut(self):
        p = self.get_selected()
        if not p: return
        desktop = Path.home() / "Desktop"
        
        if sys.platform == "linux":
            s = desktop / f"Antigravity ({p}).desktop"
            cmd = f"env HOME='{AGY_ACCOUNTS_DIR/p}' {TARGET_CMD}"
            s.write_text(f"[Desktop Entry]\nName=Antigravity ({p})\nExec={cmd}\nType=Application\nTerminal=false\nCategories=Development;\n")
            s.chmod(0o755)
        elif sys.platform == "win32":
            s = desktop / f"Antigravity ({p}).bat"
            s.write_text(f"@echo off\nset HOME={AGY_ACCOUNTS_DIR/p}\nstart \"\" {TARGET_CMD}\n")
        elif sys.platform == "darwin":
            s = desktop / f"Antigravity ({p}).command"
            s.write_text(f"#!/bin/bash\nexport HOME='{AGY_ACCOUNTS_DIR/p}'\nopen -a {TARGET_CMD}\n")
            s.chmod(0o755)
            
        messagebox.showinfo("Success", f"Shortcut created on your Desktop for '{p}'!")

    def export_profile(self):
        p = self.get_selected()
        if not p: return
        f = filedialog.asksaveasfilename(defaultextension=".zip", initialfile=f"{p}_backup.zip")
        if f:
            shutil.make_archive(f.replace('.zip', ''), 'zip', AGY_ACCOUNTS_DIR / p)
            messagebox.showinfo("Success", "Profile exported successfully!")

    def import_profile(self):
        f = filedialog.askopenfilename(filetypes=[("Zip files", "*.zip")])
        if f:
            name = Path(f).stem.replace("_backup", "")
            target = AGY_ACCOUNTS_DIR / name
            if target.exists():
                name = name + "_imported"
                target = AGY_ACCOUNTS_DIR / name
            shutil.unpack_archive(f, target)
            self.refresh_list()
            messagebox.showinfo("Success", f"Profile imported as {name}!")

    def delete_profile(self):
        p = self.get_selected()
        if not p: return
        if messagebox.askyesno("Confirm", f"Are you sure you want to permanently delete profile '{p}'?"):
            shutil.rmtree(AGY_ACCOUNTS_DIR / p)
            self.refresh_list()

if __name__ == "__main__":
    App().mainloop()
