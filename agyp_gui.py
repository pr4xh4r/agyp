#!/usr/bin/env python3
"""
Antigravity Desktop Manager
A simple, minimalist GUI manager for the Antigravity Desktop App.
Built with standard tkinter (ttk).
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

AGY_ACCOUNTS_DIR = Path.home() / ".agy_accounts"
TARGET_CMD = "antigravity"
APP_TITLE = "Antigravity Profiles"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("400x450")
        self.resizable(False, False)
        
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
            
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header = tk.Label(self, text=APP_TITLE, font=("Helvetica", 18, "bold"), fg="#4285F4")
        header.grid(row=0, column=0, pady=20)
        
        # Profile List
        list_frame = ttk.Frame(self)
        list_frame.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Helvetica", 12), selectbackground="#4285F4", selectforeground="white")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-1>", lambda e: self.launch_profile())
        scrollbar.config(command=self.listbox.yview)
        
        # Action Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, padx=30, pady=10, sticky="ew")
        
        btn_launch = tk.Button(btn_frame, text="Launch Profile", bg="#4285F4", fg="white", font=("Helvetica", 11, "bold"), relief="flat", command=self.launch_profile)
        btn_launch.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        btn_delete = tk.Button(btn_frame, text="Delete", bg="#EA4335", fg="white", font=("Helvetica", 11, "bold"), relief="flat", command=self.delete_profile)
        btn_delete.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)
        
        # New Profile Frame
        new_frame = ttk.Frame(self)
        new_frame.grid(row=3, column=0, padx=30, pady=20, sticky="ew")
        
        self.entry_new = ttk.Entry(new_frame, font=("Helvetica", 12))
        self.entry_new.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_new.bind("<Return>", lambda e: self.create_profile())
        
        btn_new = tk.Button(new_frame, text="Add Profile", bg="#34A853", fg="white", font=("Helvetica", 11, "bold"), relief="flat", command=self.create_profile)
        btn_new.pack(side=tk.RIGHT)
        
        self.refresh_list()
        
    def get_profiles(self):
        if not AGY_ACCOUNTS_DIR.exists():
            AGY_ACCOUNTS_DIR.mkdir(parents=True)
        return sorted([d.name for d in AGY_ACCOUNTS_DIR.iterdir() if d.is_dir()])

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.get_profiles():
            self.listbox.insert(tk.END, p)

    def get_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a profile from the list.")
            return None
        return self.listbox.get(selection[0])

    def do_launch(self, profile_name):
        profile_dir = AGY_ACCOUNTS_DIR / profile_name
        profile_dir.mkdir(exist_ok=True)
        
        env = os.environ.copy()
        env["HOME"] = str(profile_dir)
        
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

    def delete_profile(self):
        p = self.get_selected()
        if not p: return
        if messagebox.askyesno("Confirm", f"Are you sure you want to permanently delete profile '{p}'?"):
            shutil.rmtree(AGY_ACCOUNTS_DIR / p)
            self.refresh_list()

if __name__ == "__main__":
    App().mainloop()
