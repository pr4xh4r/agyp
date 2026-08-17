#!/usr/bin/env python3
"""
Antigravity Desktop Manager
An iOS-inspired, minimalist GUI manager for the Antigravity Desktop App.
Built with customtkinter with automatic Dark/Light mode switching.
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
ctk.set_default_color_theme("blue")

AGY_ACCOUNTS_DIR = Path.home() / ".agy_accounts"
TARGET_CMD = "antigravity"
APP_TITLE = "Antigravity Profiles"
AGY_BLUE = "#007AFF" # iOS Blue

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("700x650")
        self.resizable(False, False)
        
        # Main Container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header Frame
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(30, 15), padx=30, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        # Logo/Title
        self.lbl_title = ctk.CTkLabel(
            self.header_frame, 
            text="Antigravity", 
            font=ctk.CTkFont(family="Helvetica", size=28, weight="bold"),
            text_color=("black", "white")
        )
        self.lbl_title.grid(row=0, column=0, sticky="w")
        
        self.lbl_subtitle = ctk.CTkLabel(
            self.header_frame,
            text="Isolated Workspaces",
            font=ctk.CTkFont(family="Helvetica", size=14),
            text_color=("gray40", "gray60")
        )
        self.lbl_subtitle.grid(row=1, column=0, sticky="w")
        
        # Theme Switch (Icon based)
        self.switch_var = ctk.StringVar(value="on")
        self.theme_switch = ctk.CTkSwitch(
            self.header_frame, 
            text="☾ Dark", 
            command=self.toggle_theme,
            variable=self.switch_var, 
            onvalue="on", 
            offvalue="off",
            font=ctk.CTkFont(family="Helvetica", size=14, weight="bold"),
            progress_color=AGY_BLUE,
            button_color=("gray30", "white")
        )
        self.theme_switch.grid(row=0, column=1, rowspan=2, sticky="e")
        
        # Profile List Frame (iOS style card)
        self.list_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray12"), corner_radius=20)
        self.list_frame.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # Scrollable Frame for List
        self.scrollable_list = ctk.CTkScrollableFrame(self.list_frame, fg_color="transparent")
        self.scrollable_list.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.scrollable_list.grid_columnconfigure(0, weight=1)
        
        self.profile_buttons = []
        self.selected_profile = tk.StringVar(value="")
        
        # Action Buttons (Launch / Delete)
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=2, column=0, padx=30, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.btn_launch = ctk.CTkButton(
            self.action_frame, 
            text="Launch", 
            font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"),
            fg_color=AGY_BLUE,
            hover_color="#005bb5",
            text_color="white",
            corner_radius=25,
            height=50,
            command=self.launch_profile,
            state="disabled"
        )
        self.btn_launch.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_delete = ctk.CTkButton(
            self.action_frame, 
            text="Delete", 
            font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"),
            fg_color="transparent", 
            border_width=2,
            border_color="#FF3B30",
            text_color="#FF3B30",
            hover_color="gray15",
            corner_radius=25,
            height=50,
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
            font=ctk.CTkFont(family="Helvetica", size=16),
            height=50,
            corner_radius=25,
            fg_color=("white", "gray16"),
            border_width=1,
            border_color=("gray80", "gray25")
        )
        self.entry_new.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry_new.bind("<Return>", lambda e: self.create_profile())
        
        self.btn_add = ctk.CTkButton(
            self.new_frame, 
            text="Add Profile", 
            font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"),
            fg_color="#34C759", # iOS Green
            hover_color="#248a3d",
            text_color="white",
            width=140,
            height=50,
            corner_radius=25,
            command=self.create_profile
        )
        self.btn_add.grid(row=0, column=1)
        
        self.refresh_list()
        
    def toggle_theme(self):
        if self.switch_var.get() == "on":
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="☾ Dark")
            # Update hover color for outline button in dark mode
            self.btn_delete.configure(hover_color="gray15")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="☀ Light")
            # Update hover color for outline button in light mode
            self.btn_delete.configure(hover_color="gray90")
            
    def get_profiles(self):
        if not AGY_ACCOUNTS_DIR.exists():
            AGY_ACCOUNTS_DIR.mkdir(parents=True)
        return sorted([d.name for d in AGY_ACCOUNTS_DIR.iterdir() if d.is_dir()])

    def on_profile_select(self, profile_name):
        self.selected_profile.set(profile_name)
        # Update styling for iOS list style
        for btn in self.profile_buttons:
            if btn.cget("text") == profile_name:
                btn.configure(fg_color=AGY_BLUE, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("black", "gray90"))
        
        # Enable action buttons
        self.btn_launch.configure(state="normal")
        self.btn_delete.configure(state="normal")

    def refresh_list(self):
        for btn in self.profile_buttons:
            btn.destroy()
        self.profile_buttons.clear()
        self.selected_profile.set("")
        
        self.btn_launch.configure(state="disabled")
        self.btn_delete.configure(state="disabled")
        
        profiles = self.get_profiles()
        
        if not profiles:
            lbl = ctk.CTkLabel(self.scrollable_list, text="No profiles exist yet", font=ctk.CTkFont(size=15), text_color=("gray50", "gray60"))
            lbl.grid(row=0, column=0, pady=20)
            self.profile_buttons.append(lbl)
            return

        for i, p in enumerate(profiles):
            btn = ctk.CTkButton(
                self.scrollable_list,
                text=p,
                fg_color="transparent",
                text_color=("black", "gray90"),
                hover_color=("gray85", "gray20"),
                anchor="w",
                corner_radius=10,
                font=ctk.CTkFont(family="Helvetica", size=16),
                height=45,
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
            dialog = ctk.CTkToplevel(self)
            dialog.title("Error")
            dialog.geometry("300x150")
            dialog.transient(self)
            dialog.grab_set()
            lbl = ctk.CTkLabel(dialog, text=f"Could not find '{TARGET_CMD}'\non your system.", text_color="#FF3B30")
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
            self.on_profile_select(p)

    def delete_profile(self):
        p = self.selected_profile.get()
        if not p: return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.geometry("350x150")
        dialog.transient(self)
        dialog.grab_set()
        
        lbl = ctk.CTkLabel(dialog, text=f"Delete '{p}'?", font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"))
        lbl.pack(pady=(20, 10))
        
        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack()
        
        def confirm():
            shutil.rmtree(AGY_ACCOUNTS_DIR / p)
            self.refresh_list()
            dialog.destroy()
            
        btn_yes = ctk.CTkButton(frame, text="Yes, Delete", fg_color="#FF3B30", hover_color="#c92a22", width=100, corner_radius=15, command=confirm)
        btn_yes.pack(side=tk.LEFT, padx=10)
        
        btn_no = ctk.CTkButton(frame, text="Cancel", fg_color=("gray75", "gray30"), text_color=("black", "white"), hover_color=("gray65", "gray25"), width=100, corner_radius=15, command=dialog.destroy)
        btn_no.pack(side=tk.RIGHT, padx=10)

if __name__ == "__main__":
    App().mainloop()
