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
        # ASCII Logo
        logo_text = "    ▄▀▀▄\n   ▀▀▀▀▀▀\n  ▀▀▀▀▀▀▀▀\n ▄▀▀    ▀▀▄\n▄▀▀      ▀▀▄"
        self.lbl_logo = ctk.CTkLabel(
            self.header_frame,
            text=logo_text,
            font=ctk.CTkFont(family="Courier", size=14, weight="bold"),
            text_color=AGY_BLUE,
            justify="center"
        )
        self.lbl_logo.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 15))
        
        # Title
        self.lbl_title = ctk.CTkLabel(
            self.header_frame, 
            text="Antigravity Profiles (BETA)", 
            font=ctk.CTkFont(family="San Francisco", size=24, weight="bold"),
            text_color=("black", "white")
        )
        self.lbl_title.grid(row=0, column=1, rowspan=2, sticky="w")
        
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # Action Icons Frame (Top Right)
        self.icons_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.icons_frame.grid(row=0, column=2, rowspan=2, sticky="e")

        # Theme Icon Toggle
        self.theme_btn = ctk.CTkButton(
            self.icons_frame,
            text="☀",
            width=30,
            height=30,
            corner_radius=15,
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray20"),
            font=ctk.CTkFont(size=20),
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=5)

        # Close Window Icon
        self.close_btn = ctk.CTkButton(
            self.icons_frame,
            text="✕",
            width=30,
            height=30,
            corner_radius=15,
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color="#FF3B30", # iOS Red on hover
            font=ctk.CTkFont(size=20, weight="bold"),
            command=self.destroy
        )
        self.close_btn.pack(side="left")
        
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
            font=ctk.CTkFont(family="San Francisco", size=16, weight="bold"),
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
            font=ctk.CTkFont(family="San Francisco", size=16, weight="bold"),
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
            font=ctk.CTkFont(family="San Francisco", size=16),
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
            font=ctk.CTkFont(family="San Francisco", size=16, weight="bold"),
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
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text="☾")
            self.btn_delete.configure(hover_color="gray90")
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text="☀")
            self.btn_delete.configure(hover_color="gray15")
            
    def get_profiles(self):
        if not AGY_ACCOUNTS_DIR.exists():
            AGY_ACCOUNTS_DIR.mkdir(parents=True)
        return sorted([d.name for d in AGY_ACCOUNTS_DIR.iterdir() if d.is_dir()])

    def on_profile_select(self, profile_name):
        self.selected_profile.set(profile_name)
        
        # Cancel any pending inline delete
        if hasattr(self, 'cancel_delete'):
            self.cancel_delete()
            
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
                font=ctk.CTkFont(family="San Francisco", size=16),
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
        
        # Hide standard action buttons
        self.btn_launch.grid_forget()
        self.btn_delete.grid_forget()
        
        # Show inline confirmation buttons
        self.btn_confirm = ctk.CTkButton(
            self.action_frame,
            text=f"Confirm Delete '{p}'?",
            font=ctk.CTkFont(family="San Francisco", size=15, weight="bold"),
            fg_color="#FF3B30",
            hover_color="#c92a22",
            text_color="white",
            corner_radius=25,
            height=50,
            command=self.execute_delete
        )
        self.btn_confirm.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_cancel_del = ctk.CTkButton(
            self.action_frame,
            text="Cancel",
            font=ctk.CTkFont(family="San Francisco", size=15, weight="bold"),
            fg_color="transparent",
            border_width=2,
            border_color=("gray70", "gray40"),
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            corner_radius=25,
            height=50,
            command=self.cancel_delete
        )
        self.btn_cancel_del.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def cancel_delete(self):
        if hasattr(self, 'btn_confirm') and self.btn_confirm.winfo_exists():
            self.btn_confirm.destroy()
            self.btn_cancel_del.destroy()
        # Restore standard action buttons
        self.btn_launch.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.btn_delete.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        
    def execute_delete(self):
        p = self.selected_profile.get()
        if p:
            shutil.rmtree(AGY_ACCOUNTS_DIR / p)
        self.cancel_delete()
        self.refresh_list()

if __name__ == "__main__":
    App().mainloop()
