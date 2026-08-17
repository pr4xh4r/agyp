#!/usr/bin/env python3
"""
Antigravity Desktop Manager
A premium, minimalist GUI manager for the Antigravity Desktop App.
Built with customtkinter for a sleek, modern UI.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
import customtkinter as ctk

# Configure CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")  # Using default blue theme

AGY_ACCOUNTS_DIR = Path.home() / ".agy_accounts"
TARGET_CMD = "antigravity"
APP_TITLE = "Antigravity Profiles"
AGY_BLUE = "#4285F4"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("450x550")
        self.resizable(False, False)
        
        # Main Container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(30, 15), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        # Logo/Title
        self.lbl_title = ctk.CTkLabel(
            self.header_frame, 
            text="Antigravity Profiles", 
            font=ctk.CTkFont(family="Helvetica", size=24, weight="bold"),
            text_color=AGY_BLUE
        )
        self.lbl_title.grid(row=0, column=0)
        
        self.lbl_subtitle = ctk.CTkLabel(
            self.header_frame,
            text="Select or create an isolated workspace",
            font=ctk.CTkFont(family="Helvetica", size=13),
            text_color="gray60"
        )
        self.lbl_subtitle.grid(row=1, column=0, pady=(0, 10))
        
        # Profile List Frame
        self.list_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        self.list_frame.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # Scrollable Frame for List
        self.scrollable_list = ctk.CTkScrollableFrame(self.list_frame, fg_color="transparent")
        self.scrollable_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.scrollable_list.grid_columnconfigure(0, weight=1)
        
        self.profile_buttons = []
        self.selected_profile = tk.StringVar(value="")
        
        # Action Buttons (Launch / Delete)
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=2, column=0, padx=30, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.btn_launch = ctk.CTkButton(
            self.action_frame, 
            text="🚀 Launch", 
            font=ctk.CTkFont(weight="bold"),
            fg_color=AGY_BLUE,
            hover_color="#3367D6",
            command=self.launch_profile,
            state="disabled"
        )
        self.btn_launch.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_delete = ctk.CTkButton(
            self.action_frame, 
            text="Delete", 
            font=ctk.CTkFont(weight="bold"),
            fg_color="#EA4335",
            hover_color="#C5221F",
            command=self.delete_profile,
            state="disabled"
        )
        self.btn_delete.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
        # New Profile Frame
        self.new_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.new_frame.grid(row=3, column=0, padx=30, pady=(10, 30), sticky="ew")
        self.new_frame.grid_columnconfigure(0, weight=1)
        
        self.entry_new = ctk.CTkEntry(
            self.new_frame, 
            placeholder_text="New profile name...",
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.entry_new.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry_new.bind("<Return>", lambda e: self.create_profile())
        
        self.btn_add = ctk.CTkButton(
            self.new_frame, 
            text="+ Add Profile", 
            font=ctk.CTkFont(weight="bold"),
            fg_color="#34A853",
            hover_color="#188038",
            width=120,
            height=40,
            command=self.create_profile
        )
        self.btn_add.grid(row=0, column=1)
        
        self.refresh_list()
        
    def get_profiles(self):
        if not AGY_ACCOUNTS_DIR.exists():
            AGY_ACCOUNTS_DIR.mkdir(parents=True)
        return sorted([d.name for d in AGY_ACCOUNTS_DIR.iterdir() if d.is_dir()])

    def on_profile_select(self, profile_name):
        self.selected_profile.set(profile_name)
        # Update styling
        for btn in self.profile_buttons:
            if btn.cget("text") == profile_name:
                btn.configure(fg_color=AGY_BLUE, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="gray80")
        
        # Enable action buttons
        self.btn_launch.configure(state="normal")
        self.btn_delete.configure(state="normal")

    def refresh_list(self):
        # Clear existing
        for btn in self.profile_buttons:
            btn.destroy()
        self.profile_buttons.clear()
        self.selected_profile.set("")
        
        # Disable action buttons
        self.btn_launch.configure(state="disabled")
        self.btn_delete.configure(state="disabled")
        
        profiles = self.get_profiles()
        
        if not profiles:
            lbl = ctk.CTkLabel(self.scrollable_list, text="(No profiles exist yet)", text_color="gray50")
            lbl.grid(row=0, column=0, pady=20)
            self.profile_buttons.append(lbl)
            return

        for i, p in enumerate(profiles):
            btn = ctk.CTkButton(
                self.scrollable_list,
                text=p,
                fg_color="transparent",
                text_color="gray80",
                hover_color="#3a3a3a",
                anchor="w",
                font=ctk.CTkFont(size=14),
                height=35,
                command=lambda name=p: self.on_profile_select(name)
            )
            btn.grid(row=i, column=0, sticky="ew", pady=2)
            self.profile_buttons.append(btn)

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
            # Custom message dialog for error
            dialog = ctk.CTkToplevel(self)
            dialog.title("Error")
            dialog.geometry("300x150")
            dialog.transient(self)
            dialog.grab_set()
            lbl = ctk.CTkLabel(dialog, text=f"Could not find '{TARGET_CMD}'\non your system.", text_color="#EA4335")
            lbl.pack(pady=20)
            btn = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
            btn.pack()

    def launch_profile(self):
        p = self.selected_profile.get()
        if p: self.do_launch(p)

    def create_profile(self):
        p = self.entry_new.get().strip()
        if p:
            self.do_launch(p)
            self.entry_new.delete(0, 'end')
            self.refresh_list()
            # Select the newly created profile
            self.on_profile_select(p)

    def delete_profile(self):
        p = self.selected_profile.get()
        if not p: return
        
        # Simple custom confirm dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.geometry("350x150")
        dialog.transient(self)
        dialog.grab_set()
        
        lbl = ctk.CTkLabel(dialog, text=f"Delete '{p}'?", font=ctk.CTkFont(weight="bold"))
        lbl.pack(pady=(20, 10))
        
        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack()
        
        def confirm():
            shutil.rmtree(AGY_ACCOUNTS_DIR / p)
            self.refresh_list()
            dialog.destroy()
            
        btn_yes = ctk.CTkButton(frame, text="Yes, Delete", fg_color="#EA4335", hover_color="#C5221F", width=100, command=confirm)
        btn_yes.pack(side=tk.LEFT, padx=10)
        
        btn_no = ctk.CTkButton(frame, text="Cancel", fg_color="gray40", hover_color="gray30", width=100, command=dialog.destroy)
        btn_no.pack(side=tk.RIGHT, padx=10)

if __name__ == "__main__":
    App().mainloop()
