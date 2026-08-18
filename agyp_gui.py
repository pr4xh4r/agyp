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
import threading
import subprocess
from pathlib import Path
import tkinter as tk
import customtkinter as ctk

VERSION = "1.1.0"

# Configure CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Antigravity sets HOME=/home/user/.agy_accounts/N per account.
# We MUST use the $HOME env var so we read/write the correct token location.
if sys.platform == "win32":
    REAL_HOME = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
else:
    _env_home = os.environ.get("HOME")
    if _env_home:
        REAL_HOME = Path(_env_home)
    else:
        try:
            import pwd as _pwd
            REAL_HOME = Path(_pwd.getpwuid(os.getuid()).pw_dir)
        except (ImportError, KeyError):
            REAL_HOME = Path(os.path.expanduser("~"))

# Profiles dir is always in the REAL system home, not the Antigravity sandbox
# so use the passwd db (actual /home/user) for profile storage only
if sys.platform != "win32":
    try:
        import pwd as _pwd
        _SYSTEM_HOME = Path(_pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError):
        _SYSTEM_HOME = REAL_HOME
else:
    _SYSTEM_HOME = REAL_HOME

AGY_ACCOUNTS_DIR = _SYSTEM_HOME / "agyp-profiles"
APP_TITLE = "Antigravity Profiles"

# Color Palette (Light, Dark)
AGY_BLUE       = ("#0A84FF", "#4285F4")  # iOS Blue light, Antigravity Blue dark
AGY_BLUE_HOVER = ("#0066cc", "#2a65cc")
BG_COLOR       = ("#f0f0f5", "#1a1035")
CARD_BG        = ("white",   "#231540")
ELEM_BG        = ("#e5e5ea", "#2a1e50")
ELEM_HOVER     = ("#d1d1d6", "#3a2e60")
TEXT_MAIN      = ("black",   "#e8e8f0")
TEXT_MUTED     = ("#8e8e93", "#6a5e8a")
TEXT_LIST      = ("black",   "#c8c0e8")
SEP_COLOR      = ("#c6c6c8", "#3a2e5a")
RED_TEXT       = ("#FF3B30", "#FF453A")
RED_BTN        = ("#FF3B30", "#FF3B30")
RED_HOVER      = ("#d92c23", "#c92a22")
GREEN_BTN      = ("#34C759", "#34C759")
GREEN_HOVER    = ("#2eab4d", "#2eab4d")
YELLOW_BTN     = ("#FF9F0A", "#FF9F0A")
YELLOW_HOVER   = ("#cc7f08", "#cc7f08")

# Monospace font — matches the terminal aesthetic across platforms
MONO_FONT = ('SF Mono'    if sys.platform == 'darwin'
             else ('Consolas' if sys.platform == 'win32' else 'monospace'))
# UI font for buttons/inputs (readable sans-serif)
UI_FONT   = ('SF Pro Display' if sys.platform == 'darwin'
             else ('Segoe UI' if sys.platform == 'win32' else 'sans-serif'))

# Auth files
AUTH_FILES = [
    (REAL_HOME / ".gemini" / "antigravity-cli" / "antigravity-oauth-token", "antigravity-oauth-token"),
    (REAL_HOME / ".gemini" / "oauth_creds.json",     "oauth_creds.json"),
    (REAL_HOME / ".gemini" / "google_accounts.json", "google_accounts.json"),
]

LAST_ACTIVE_FILE = AGY_ACCOUNTS_DIR / ".last_active"


def detect_icon_support() -> bool:
    """Return True if JetBrainsMono Nerd Font is available in tkinter font families.
    Returns False immediately if no display is available (headless/SSH)."""
    try:
        if sys.platform != "win32" and sys.platform != "darwin":
            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                return False
        import tkinter.font as tkfont
        _root = tk.Tk()
        _root.withdraw()
        families = tkfont.families(_root)
        _root.destroy()
        return "JetBrainsMono Nerd Font" in families
    except Exception:
        return False


_NERD_FONTS = detect_icon_support()
ICON_SUN   = "\U000f0599" if _NERD_FONTS else "\u2600"
ICON_MOON  = "\U000f0594" if _NERD_FONTS else "\u263d"
ICON_CLOSE = "\U000f0156" if _NERD_FONTS else "\u2715"
ICON_GEAR  = "\U000f04fc" if _NERD_FONTS else "\u2699"

import json

CONFIG_FILE = AGY_ACCOUNTS_DIR / "config.json"

def get_custom_ide_path():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return data.get("custom_ide_path")
    except Exception:
        pass
    return None

def set_custom_ide_path(path):
    try:
        data = {}
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if path:
            data["custom_ide_path"] = path
        else:
            data.pop("custom_ide_path", None)
        CONFIG_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _find_linux_cmd():
    """Find the Antigravity desktop binary on Linux."""
    custom = get_custom_ide_path()
    if custom and os.path.isfile(custom) and os.access(custom, os.X_OK):
        return custom

    candidates = [
        "antigravity",
        "Antigravity",
        "antigravity-desktop",
        "antigravity-bin",
        "antigravity-ide",
        str(REAL_HOME / ".local/share/antigravity-ide/bin/antigravity-ide"),
        str(REAL_HOME / "Downloads/Antigravity/Antigravity-x64/antigravity"),
    ]
    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _find_windows_exe():
    """Find the Antigravity desktop binary on Windows."""
    custom = get_custom_ide_path()
    if custom and os.path.isfile(custom):
        return custom

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\antigravity-ide\Antigravity IDE.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\antigravity-ide\antigravity-ide.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Antigravity\Antigravity.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Antigravity IDE\Antigravity IDE.exe"),
        os.path.expandvars(r"%PROGRAMFILES(x86)%\Antigravity\Antigravity.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    
    # Try searching the PATH
    for name in ["Antigravity.exe", "antigravity", "Antigravity IDE.exe", "antigravity-ide.exe", "antigravity-ide"]:
        found = shutil.which(name)
        if found:
            return found
    return None


def _swap_in(profile_dir: Path):
    """Copy this profile's auth files into the live system locations."""
    swapped = 0
    for sys_path, filename in AUTH_FILES:
        src = profile_dir / filename
        sys_path.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            if sys_path.exists():
                shutil.copy2(sys_path, sys_path.with_suffix(".agyp-backup"))
            shutil.copy2(src, sys_path)
            swapped += 1
        else:
            if sys_path.exists():
                shutil.copy2(sys_path, sys_path.with_suffix(".agyp-backup"))
                sys_path.unlink()
    return swapped


def _save_back(profile_dir: Path):
    """Copy live auth files back into the profile dir."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    for sys_path, filename in AUTH_FILES:
        if sys_path.exists():
            shutil.copy2(sys_path, profile_dir / filename)


def _set_last_active(profile_name: str):
    try:
        AGY_ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        LAST_ACTIVE_FILE.write_text(profile_name, encoding="utf-8")
    except OSError:
        pass


def _clear_last_active():
    try:
        if LAST_ACTIVE_FILE.exists():
            LAST_ACTIVE_FILE.unlink()
    except OSError:
        pass


def _get_last_active():
    try:
        if LAST_ACTIVE_FILE.exists():
            return LAST_ACTIVE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind('<Command-w>', lambda e: self.on_close())
        self.geometry("700x680")
        self.resizable(False, False)
        # Dynamic background — matches the terminal UI aesthetic
        self.configure(fg_color=BG_COLOR)

        # ── Recover unsaved tokens from last interrupted session ──────────────
        self._recover_last_session()

        # Main Container
        self.grid_columnconfigure(0, weight=1)

        # Header Frame — dynamic background
        self.header_frame = ctk.CTkFrame(self, fg_color=BG_COLOR)
        self.header_frame.grid(row=0, column=0, pady=(30, 0), padx=30, sticky="ew")

        # Correct block-character logo (▄ = U+2584, ▀ = U+2580) matching CLI exactly
        logo_text = (
            "       ▄▀▀▄       \n"
            "      ▀▀▀▀▀▀      \n"
            "     ▀▀▀▀▀▀▀▀     \n"
            "    ▄▀▀    ▀▀▄    \n"
            "   ▄▀▀      ▀▀▄   "
        )
        self.lbl_logo = ctk.CTkLabel(
            self.header_frame,
            text=logo_text,
            font=ctk.CTkFont(family="monospace", size=13, weight="bold"),
            text_color=AGY_BLUE,
            justify="left"
        )
        self.lbl_logo.grid(row=0, column=0, sticky="w")

        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="Antigravity Profiles (BETA)",
            font=ctk.CTkFont(family=MONO_FONT, size=20, weight="bold"),
            text_color=TEXT_MAIN
        )
        self.lbl_title.grid(row=0, column=1, sticky="w", padx=10)

        self.header_frame.grid_columnconfigure(1, weight=1)

        # Action Icons Frame (Top Right)
        self.icons_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.icons_frame.grid(row=0, column=2, sticky="e")

        _icon_font_family = "JetBrainsMono Nerd Font" if _NERD_FONTS else MONO_FONT
        self.settings_btn = ctk.CTkButton(
            self.icons_frame, text=ICON_GEAR, width=36, height=36, corner_radius=18,
            fg_color=ELEM_BG, text_color=TEXT_MAIN,
            hover_color=ELEM_HOVER,
            font=ctk.CTkFont(family=_icon_font_family, size=20),
            command=self._prompt_for_custom_path
        )
        self.settings_btn.pack(side="left", padx=5)

        self.theme_btn = ctk.CTkButton(
            self.icons_frame, text=ICON_SUN, width=36, height=36, corner_radius=18,
            fg_color=ELEM_BG, text_color=TEXT_MAIN,
            hover_color=ELEM_HOVER,
            font=ctk.CTkFont(family=_icon_font_family, size=20),
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=5)

        self.close_btn = ctk.CTkButton(
            self.icons_frame, text=ICON_CLOSE, width=36, height=36, corner_radius=18,
            fg_color=ELEM_BG, text_color=TEXT_MAIN,
            hover_color=RED_TEXT,
            font=ctk.CTkFont(family=_icon_font_family, size=20),
            command=self.on_close
        )
        self.close_btn.pack(side="left")

        # Separator line
        self.separator = ctk.CTkFrame(self, height=1, fg_color=SEP_COLOR)
        self.separator.grid(row=1, column=0, padx=30, pady=(15, 0), sticky="ew")

        # Profile List Frame
        self.list_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=16)
        self.list_frame.grid(row=2, column=0, padx=30, pady=12, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.scrollable_list = ctk.CTkScrollableFrame(self.list_frame, fg_color="transparent")
        self.scrollable_list.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.scrollable_list.grid_columnconfigure(0, weight=1)

        self.profile_buttons = []
        self.selected_profile = tk.StringVar(value="")

        # Action Buttons (Launch / Delete)
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=3, column=0, padx=30, pady=10, sticky="ew")
        self.action_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_launch = ctk.CTkButton(
            self.action_frame, text="Launch",
            font=ctk.CTkFont(family=MONO_FONT, size=15, weight="bold"),
            fg_color=AGY_BLUE, hover_color=AGY_BLUE_HOVER,
            text_color="white", corner_radius=10, height=45,
            command=self.launch_profile, state="disabled"
        )
        self.btn_launch.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_delete = ctk.CTkButton(
            self.action_frame, text="Delete",
            font=ctk.CTkFont(family=MONO_FONT, size=15, weight="bold"),
            fg_color=ELEM_BG, text_color=RED_TEXT,
            hover_color=ELEM_HOVER, corner_radius=10, height=45,
            command=self.delete_profile, state="disabled"
        )
        self.btn_delete.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # New Profile Frame
        self.new_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.new_frame.grid(row=4, column=0, padx=30, pady=(10, 30), sticky="ew")
        self.new_frame.grid_columnconfigure(0, weight=1)

        self.entry_new = ctk.CTkEntry(
            self.new_frame, placeholder_text="New profile name...",
            font=ctk.CTkFont(family=MONO_FONT, size=15), height=45, corner_radius=10,
            fg_color=ELEM_BG, text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_MUTED, border_width=0
        )
        self.entry_new.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry_new.bind("<Return>", lambda e: self.create_profile())

        self.btn_add = ctk.CTkButton(
            self.new_frame, text="Add Profile",
            font=ctk.CTkFont(family=MONO_FONT, size=15, weight="bold"),
            fg_color=GREEN_BTN, hover_color=GREEN_HOVER,
            text_color="white", width=140, height=45, corner_radius=10,
            command=self.create_profile
        )
        self.btn_add.grid(row=0, column=1)

        self.refresh_list()

    # ─────────────────────────────────────────────────────────────────────────
    # Session recovery (no-op: HOME isolation means tokens auto-save to profile)
    # ─────────────────────────────────────────────────────────────────────────

    def _recover_last_session(self):
        """No-op: with HOME isolation, the IDE writes tokens directly into the
        profile directory. No manual save-back needed."""
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text=ICON_MOON)
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text=ICON_SUN)

    # ─────────────────────────────────────────────────────────────────────────
    # Profile list
    # ─────────────────────────────────────────────────────────────────────────

    def get_profiles(self):
        if not AGY_ACCOUNTS_DIR.exists():
            AGY_ACCOUNTS_DIR.mkdir(parents=True)
        return sorted([d.name for d in AGY_ACCOUNTS_DIR.iterdir() if d.is_dir()])

    def on_profile_select(self, profile_name):
        self.selected_profile.set(profile_name)
        if hasattr(self, 'cancel_delete'):
            self.cancel_delete()
        for btn in self.profile_buttons:
            if btn.cget("text") == profile_name:
                btn.configure(fg_color=AGY_BLUE, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_LIST)
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
            lbl = ctk.CTkLabel(
                self.scrollable_list,
                text="No profiles exist yet",
                font=ctk.CTkFont(family=MONO_FONT, size=14),
                text_color=TEXT_MUTED
            )
            lbl.grid(row=0, column=0, pady=20)
            self.profile_buttons.append(lbl)
            return

        for i, p in enumerate(profiles):
            btn = ctk.CTkButton(
                self.scrollable_list, text=p,
                fg_color="transparent", text_color=TEXT_LIST,
                hover_color=ELEM_BG, anchor="w",
                corner_radius=8, font=ctk.CTkFont(family=MONO_FONT, size=15),
                height=42, command=lambda name=p: self.on_profile_select(name)
            )
            btn.grid(row=i, column=0, sticky="ew", pady=2)
            self.profile_buttons.append(btn)

    # ─────────────────────────────────────────────────────────────────────────
    # Notifications
    # ─────────────────────────────────────────────────────────────────────────

    def show_error(self, msg):
        if not hasattr(self, 'lbl_error'):
            self.lbl_error = ctk.CTkLabel(
                self, text="",
                text_color=RED_TEXT,
                font=ctk.CTkFont(family=MONO_FONT, size=13, weight="bold")
            )
        self.lbl_error.configure(text=msg)
        self.lbl_error.grid(row=5, column=0, pady=(0, 10))
        self.after(4000, self.lbl_error.grid_forget)

    def show_info(self, msg):
        if not hasattr(self, 'lbl_info'):
            self.lbl_info = ctk.CTkLabel(
                self, text="",
                text_color=GREEN_BTN,
                font=ctk.CTkFont(family=MONO_FONT, size=13)
            )
        self.lbl_info.configure(text=msg)
        self.lbl_info.grid(row=5, column=0, pady=(0, 10))
        self.after(5000, self.lbl_info.grid_forget)

    # ─────────────────────────────────────────────────────────────────────────
    # macOS save-back button (shown after launch since we can't monitor `open`)
    # ─────────────────────────────────────────────────────────────────────────

    def _show_save_credentials_btn(self, profile_name):
        """Show a 'Save Credentials' button (macOS only, after launching app)."""
        if hasattr(self, '_save_creds_btn') and self._save_creds_btn.winfo_exists():
            self._save_creds_btn.destroy()

        profile_dir = AGY_ACCOUNTS_DIR / profile_name

        def do_save():
            try:
                _save_back(profile_dir)
                _clear_last_active()
                self.show_info(f"Credentials saved to '{profile_name}'.")
            except Exception as e:
                self.show_error(f"Save failed: {e}")
            finally:
                self._save_creds_btn.destroy()

        self._save_creds_btn = ctk.CTkButton(
            self, text=f"\u2193  Save Credentials \u2192 '{profile_name}'",
            font=ctk.CTkFont(family=MONO_FONT, size=13, weight="bold"),
            fg_color=YELLOW_BTN, hover_color=YELLOW_HOVER,
            text_color="white", corner_radius=10, height=38,
            command=do_save
        )
        self._save_creds_btn.grid(row=6, column=0, padx=30, pady=(0, 15), sticky="ew")

    # ─────────────────────────────────────────────────────────────────────────
    # Launch logic
    # ─────────────────────────────────────────────────────────────────────────

    def _prompt_for_custom_path(self):
        import tkinter.filedialog as fd
        
        filetypes = []
        if sys.platform == "win32":
            filetypes = [("Executable", "*.exe")]
        elif sys.platform == "darwin":
            filetypes = [("Application Bundle", "*.app")]
        else:
            filetypes = [("Executable", "*")]
            
        path = fd.askopenfilename(title="Locate Antigravity Desktop App", filetypes=filetypes)
        if path:
            set_custom_ide_path(path)
            self.show_info(f"Custom path saved:\n{path}")
        else:
            # If they cancel, they might just want to reset it
            set_custom_ide_path(None)
            self.show_info("Custom path reset to default.")

    def _kill_existing_ide(self):
        """Forcefully close any running Antigravity IDE instances so new tokens are read."""
        import time
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "Antigravity.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["taskkill", "/F", "/IM", "Antigravity IDE.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["taskkill", "/F", "/IM", "antigravity-ide.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.run(["killall", "Antigravity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["killall", "antigravity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["killall", "antigravity-ide"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["killall", "antigravity-desktop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    subprocess.run(["taskkill.exe", "/F", "/IM", "Antigravity.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["taskkill.exe", "/F", "/IM", "Antigravity IDE.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["taskkill.exe", "/F", "/IM", "antigravity-ide.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)

    def do_launch(self, profile_name):
        profile_dir = AGY_ACCOUNTS_DIR / profile_name
        profile_dir.mkdir(exist_ok=True)

        self._kill_existing_ide()

        # Migrate old tokens to new isolated HOME structure
        for _, filename in AUTH_FILES:
            old_path = profile_dir / filename
            if old_path.exists():
                new_path = profile_dir / ".gemini" / ("antigravity-cli/" + filename if "oauth-token" in filename else filename)
                new_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.move(str(old_path), str(new_path))

        env = os.environ.copy()
        env["HOME"] = str(profile_dir)
        for xdg in ["XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]:
            env.pop(xdg, None)

        if sys.platform == "win32":
            env["USERPROFILE"] = str(profile_dir)
            env["HOMEDRIVE"] = profile_dir.drive
            env["HOMEPATH"] = str(profile_dir)[len(profile_dir.drive):]
            appdata = profile_dir / "AppData" / "Roaming"
            localappdata = profile_dir / "AppData" / "Local"
            appdata.mkdir(parents=True, exist_ok=True)
            localappdata.mkdir(parents=True, exist_ok=True)
            env["APPDATA"] = str(appdata)
            env["LOCALAPPDATA"] = str(localappdata)

        if sys.platform == "darwin":
            try:
                custom = get_custom_ide_path()
                cmd = ["open", "-n", "-a", custom] if custom else ["open", "-n", "-a", "Antigravity"]
                result = subprocess.run(cmd, capture_output=True, env=env)
                if result.returncode != 0:
                    self.show_error("Antigravity not found. Click the ⚙ (Gear) icon above to locate it.")
                    return
            except Exception as e:
                self.show_error(f"Launch failed: {e}")
                return
        elif sys.platform == "win32":
            exe = _find_windows_exe()
            if exe:
                try:
                    subprocess.Popen([exe], env=env)
                except Exception as e:
                    self.show_error(f"Launch failed: {e}")
            else:
                self.show_error("Antigravity not found. Click the ⚙ (Gear) icon above to locate it.")
        else:
            valid_cmd = _find_linux_cmd()
            if valid_cmd:
                try:
                    subprocess.Popen([valid_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                except Exception as e:
                    self.show_error(f"Launch failed: {e}")
            else:
                self.show_error("Antigravity not found. Click the ⚙ (Gear) icon above to locate it.")

    def _monitor_process(self, proc, profile_name):
        """Watch process in background thread; save back tokens when it exits."""
        profile_dir = AGY_ACCOUNTS_DIR / profile_name

        def _watcher():
            try:
                proc.wait()
            except Exception:
                pass
            if _get_last_active() == profile_name:
                try:
                    _save_back(profile_dir)
                except Exception:
                    pass
                _clear_last_active()

        t = threading.Thread(target=_watcher, daemon=True)
        t.start()

    def launch_profile(self):
        p = self.selected_profile.get()
        if p:
            self.do_launch(p)

    # ─────────────────────────────────────────────────────────────────────────
    # Profile management
    # ─────────────────────────────────────────────────────────────────────────

    def sanitize_name(self, name: str):
        """Return a cleaned profile name or None if invalid."""
        name = name.strip()
        if not name:
            return None
        if '/' in name or '\\' in name or '..' in name:
            return None
        if name.startswith('.'):
            return None
        if re.search(r'[\x00-\x1f\x7f]', name):
            return None
        if not re.fullmatch(r'[A-Za-z0-9 _-]+', name):
            return None
        return name

    def create_profile(self):
        raw = self.entry_new.get().strip()
        p = self.sanitize_name(raw)
        if raw and p is None:
            self.show_error("Invalid profile name. Use only letters, numbers, spaces, hyphens, or underscores.")
            return
        if p:
            self.do_launch(p)
            self.entry_new.delete(0, 'end')
            self.refresh_list()
            self.on_profile_select(p)

    def delete_profile(self):
        p = self.selected_profile.get()
        if not p:
            return

        self.btn_launch.grid_forget()
        self.btn_delete.grid_forget()

        self.btn_confirm = ctk.CTkButton(
            self.action_frame, text=f"Confirm Delete '{p}'?",
            font=ctk.CTkFont(family=MONO_FONT, size=14, weight="bold"),
            fg_color=RED_BTN, hover_color=RED_HOVER, text_color="white",
            corner_radius=10, height=45, command=self.execute_delete
        )
        self.btn_confirm.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_cancel_del = ctk.CTkButton(
            self.action_frame, text="Cancel",
            font=ctk.CTkFont(family=MONO_FONT, size=14, weight="bold"),
            fg_color=ELEM_BG, text_color=TEXT_MAIN,
            hover_color=ELEM_HOVER, corner_radius=10, height=45,
            command=self.cancel_delete
        )
        self.btn_cancel_del.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def cancel_delete(self):
        if hasattr(self, 'btn_confirm') and self.btn_confirm.winfo_exists():
            self.btn_confirm.destroy()
            self.btn_cancel_del.destroy()
        self.btn_launch.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.btn_delete.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def execute_delete(self):
        p = self.selected_profile.get()
        if p:
            shutil.rmtree(AGY_ACCOUNTS_DIR / p, ignore_errors=True)
        self.cancel_delete()
        self.refresh_list()

    def on_close(self):
        """No save-back needed: HOME isolation means the IDE already wrote
        tokens directly into the profile directory during the session."""
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
