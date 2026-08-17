#!/usr/bin/env python3
"""
Antigravity Desktop Manager
An iOS-inspired, minimalist GUI manager for the Antigravity Desktop App.
Built with customtkinter with automatic Dark/Light mode switching.
"""
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
import customtkinter as ctk

# Configure CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

AGY_ACCOUNTS_DIR = Path.home() / ".agyp-profiles"
TARGET_CMD = "antigravity"
APP_TITLE = "Antigravity Profiles"
AGY_BLUE = "#007AFF" # iOS Blue

# Cross-platform UI font
UI_FONT = 'SF Pro Display' if sys.platform == 'darwin' else ('Segoe UI' if sys.platform == 'win32' else 'sans-serif')

def detect_icon_support() -> bool:
    """Return True if JetBrainsMono Nerd Font is available in tkinter font families."""
    try:
        import tkinter.font as tkfont
        _root = tk.Tk()
        _root.withdraw()
        families = tkfont.families(_root)
        _root.destroy()
        return "JetBrainsMono Nerd Font" in families
    except Exception:
        return False

_NERD_FONTS = detect_icon_support()
ICON_SUN   = "\U000f0599" if _NERD_FONTS else "\u2600"   # ☀
ICON_MOON  = "\U000f0594" if _NERD_FONTS else "\u263d"   # ☽
ICON_CLOSE = "\U000f0156" if _NERD_FONTS else "\u2715"   # ✕

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.bind('<Command-w>', lambda e: self.destroy())
        self.geometry("700x650")
        self.resizable(False, False)
        
        # Main Container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header Frame
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(30, 15), padx=30, sticky="ew")
        # Logo (Single string for native line spacing)
        logo_text = "       ▄▀▀▄       \n      ▀▀▀▀▀▀      \n     ▀▀▀▀▀▀▀▀     \n    ▄▀▀    ▀▀▄    \n   ▄▀▀      ▀▀▄   "
        self.lbl_logo = ctk.CTkLabel(
            self.header_frame,
            text=logo_text,
            font=ctk.CTkFont(family="JetBrainsMono Nerd Font", size=14, weight="bold"),
            text_color=AGY_BLUE,
            justify="left"
        )
        self.lbl_logo.grid(row=0, column=0, sticky="w")
        
        # Logo/Title
        self.lbl_title = ctk.CTkLabel(
            self.header_frame, 
            text="Antigravity Profiles (BETA)", 
            font=ctk.CTkFont(family=UI_FONT, size=24, weight="bold"),
            text_color=("black", "white")
        )
        self.lbl_title.grid(row=0, column=1, sticky="w", padx=10)
        
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # Action Icons Frame (Top Right)
        self.icons_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.icons_frame.grid(row=0, column=2, sticky="e")

        # Theme Icon Toggle
        _icon_font_family = "JetBrainsMono Nerd Font" if _NERD_FONTS else UI_FONT
        self.theme_btn = ctk.CTkButton(
            self.icons_frame,
            text=ICON_SUN,
            width=36,
            height=36,
            corner_radius=18,
            fg_color=("gray90", "gray15"),
            text_color=("black", "white"),
            hover_color=("gray80", "gray25"),
            font=ctk.CTkFont(family=_icon_font_family, size=20),
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=5)

        # Close Window Icon
        self.close_btn = ctk.CTkButton(
            self.icons_frame,
            text=ICON_CLOSE,
            width=36,
            height=36,
            corner_radius=18,
            fg_color=("gray90", "gray15"),
            text_color=("black", "white"),
            hover_color=("#FF3B30", "#FF453A"),
            font=ctk.CTkFont(family=_icon_font_family, size=20),
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
            font=ctk.CTkFont(family=UI_FONT, size=16, weight="bold"),
            fg_color=("#007AFF", "#0A84FF"),
            hover_color=("#005bb5", "#0066cc"),
            text_color="white",
            corner_radius=12,
            height=45,
            command=self.launch_profile,
            state="disabled"
        )
        self.btn_launch.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_delete = ctk.CTkButton(
            self.action_frame, 
            text="Delete", 
            font=ctk.CTkFont(family=UI_FONT, size=16, weight="bold"),
            fg_color=("gray85", "#2C2C2E"), # iOS System Gray 5
            text_color=("#FF3B30", "#FF453A"),
            hover_color=("gray75", "#3A3A3C"),
            corner_radius=12,
            height=45,
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
            font=ctk.CTkFont(family=UI_FONT, size=16),
            height=45,
            corner_radius=12,
            fg_color=("gray90", "#1C1C1E"),
            border_width=0
        )
        self.entry_new.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry_new.bind("<Return>", lambda e: self.create_profile())
        
        self.btn_add = ctk.CTkButton(
            self.new_frame, 
            text="Add Profile", 
            font=ctk.CTkFont(family=UI_FONT, size=16, weight="bold"),
            fg_color=("#34C759", "#32D74B"), # iOS System Green
            hover_color=("#2eab4d", "#2ebf43"),
            text_color="white",
            width=140,
            height=45,
            corner_radius=12,
            command=self.create_profile
        )
        self.btn_add.grid(row=0, column=1)
        
        self.refresh_list()
        
    def toggle_theme(self):
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text=ICON_MOON)
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text=ICON_SUN)
            
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
                font=ctk.CTkFont(family=UI_FONT, size=16),
                height=45,
                command=lambda name=p: self.on_profile_select(name)
            )
            btn.grid(row=i, column=0, sticky="ew", pady=2)
            self.profile_buttons.append(btn)

    def show_error(self, msg):
        if not hasattr(self, 'lbl_error'):
            self.lbl_error = ctk.CTkLabel(
                self,
                text="",
                text_color="#FF453A",
                font=ctk.CTkFont(family="San Francisco", size=14, weight="bold")
            )
        self.lbl_error.configure(text=msg)
        self.lbl_error.grid(row=4, column=0, pady=(0, 10))
        self.after(4000, self.lbl_error.grid_forget)

    def do_launch(self, profile_name):
        profile_dir = AGY_ACCOUNTS_DIR / profile_name
        profile_dir.mkdir(exist_ok=True)
        
        if sys.platform == "darwin":
            # macOS relies on the App bundle name
            cmd = ["open", "-n", "-a", "Antigravity", "--args", f"--user-data-dir={profile_dir}"]
            try:
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode != 0:
                    self.show_error("Could not find 'Antigravity' in Applications.")
            except Exception as e:
                self.show_error(f"Launch failed: {e}")
                
        elif sys.platform == "win32":
            # Windows shell execution
            try:
                subprocess.Popen(f'start "" "antigravity" --user-data-dir="{profile_dir}"', shell=True)
            except Exception as e:
                self.show_error(f"Launch failed: {e}")
                
        else:
            # Linux: Search PATH and common local installation directories
            linux_cmds = [
                "antigravity", 
                "Antigravity", 
                "antigravity-desktop", 
                "antigravity-bin",
                "antigravity-ide",
                str(Path.home() / ".local/share/antigravity-ide/bin/antigravity-ide"),
                str(Path.home() / "Downloads/Antigravity/Antigravity-x64/antigravity")
            ]
            valid_cmd = None
            for c in linux_cmds:
                if shutil.which(c):
                    valid_cmd = shutil.which(c)
                    break
                elif os.path.isfile(c) and os.access(c, os.X_OK):
                    valid_cmd = c
                    break
            
            if valid_cmd:
                try:
                    # Pass the profile directory natively to the Electron app
                    subprocess.Popen([valid_cmd, f"--user-data-dir={profile_dir}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    self.show_error(f"Launch failed: {e}")
            else:
                self.show_error("Could not find 'antigravity' in your PATH.")

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
            corner_radius=12,
            height=45,
            command=self.execute_delete
        )
        self.btn_confirm.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_cancel_del = ctk.CTkButton(
            self.action_frame,
            text="Cancel",
            font=ctk.CTkFont(family="San Francisco", size=15, weight="bold"),
            fg_color=("gray85", "#2C2C2E"),
            text_color=("black", "white"),
            hover_color=("gray75", "#3A3A3C"),
            corner_radius=12,
            height=45,
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
