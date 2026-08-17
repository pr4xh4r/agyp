#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Cross-platform real home detection
# pwd is Unix-only; Windows uses USERPROFILE/HOMEDRIVE+HOMEPATH
if sys.platform == "win32":
    REAL_HOME = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
else:
    try:
        import pwd as _pwd
        REAL_HOME = Path(_pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError):
        REAL_HOME = Path(os.path.expanduser("~"))

VERSION = "1.1.0"

# Antigravity/Google Brand Colors (TrueColor ANSI)
C_BLUE   = "\033[38;2;66;133;244m"
C_GREEN  = "\033[38;2;52;168;83m"
C_RED    = "\033[38;2;234;67;53m"
C_YELLOW = "\033[38;2;251;188;5m"
C_WHITE  = "\033[1;37m"
C_GRAY   = "\033[38;5;245m"
C_RESET  = "\033[0m"

# Profile storage dir (no leading dot — visible folder)
PROFILES_DIR = REAL_HOME / "agyp-profiles"

# Auth files — CLI token + Desktop App credentials
OAUTH_TOKEN_PATH = REAL_HOME / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
DESKTOP_CREDS    = REAL_HOME / ".gemini" / "oauth_creds.json"
DESKTOP_ACCOUNTS = REAL_HOME / ".gemini" / "google_accounts.json"

AUTH_FILES = [
    (OAUTH_TOKEN_PATH, "antigravity-oauth-token"),
    (DESKTOP_CREDS,    "oauth_creds.json"),
    (DESKTOP_ACCOUNTS, "google_accounts.json"),
]

LAST_ACTIVE_FILE = PROFILES_DIR / ".last_active"


def sanitize_name(name):
    """Sanitize profile name to prevent path traversal attacks."""
    import re
    name = name.strip()
    if not name:
        return None
    if '/' in name or '\\' in name or '..' in name or name.startswith('.'):
        return None
    if not re.match(r'^[A-Za-z0-9 _-]+$', name):
        return None
    return name


def get_key():
    """Reads a single keypress cross-platform without echoing to the screen."""
    if sys.platform == "win32":
        import msvcrt
        key = msvcrt.getch()
        if key in (b'\xe0', b'\x00'):
            key = msvcrt.getch()
            if key == b'H': return 'up'
            if key == b'P': return 'down'
        if key == b'\r': return 'enter'
        if key == b'\x03': return 'ctrl_c'
        return 'other'
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(2)
                if ch2 == '[A': return 'up'
                if ch2 == '[B': return 'down'
            if ch in ('\r', '\n'): return 'enter'
            if ch == '\x03': return 'ctrl_c'
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return 'other'


def clear_screen():
    os.system("cls" if sys.platform == "win32" else "clear")


def draw_header():
    print(f"{C_BLUE}       ▄▀▀▄       {C_RESET}")
    print(f"{C_BLUE}      ▀▀▀▀▀▀      {C_RESET}")
    print(f"{C_BLUE}     ▀▀▀▀▀▀▀▀     {C_WHITE}Antigravity Profiles (BETA){C_RESET}")
    print(f"{C_BLUE}    ▄▀▀    ▀▀▄    {C_RESET}")
    print(f"{C_BLUE}   ▄▀▀      ▀▀▄   {C_RESET}")
    print(f"\n{C_GRAY}─────────────────────────────────────────────────────{C_RESET}\n")


def interactive_menu(profiles):
    mode = "main"
    current_idx = 0

    if sys.platform == "win32":
        os.system("")

    sys.stdout.write("\033[?25l")
    try:
        while True:
            clear_screen()
            draw_header()

            if mode == "main":
                options = profiles + [
                    f"{C_GREEN}[+] Add Profile{C_RESET}",
                    f"{C_RED}[-] Delete Profile{C_RESET}",
                    f"{C_GRAY}[x] Exit{C_RESET}",
                ]
                print(f" {C_WHITE}Select a profile to launch:{C_RESET}\n")
            elif mode == "delete":
                options = profiles + [f"{C_GRAY}[<] Back{C_RESET}"]
                print(f" {C_RED}Select a profile to delete:{C_RESET}\n")
                if not profiles:
                    print(f" {C_GRAY}  (No profiles exist yet.){C_RESET}\n")
            elif mode == "create":
                options = [f"{C_GREEN}[>] Enter Profile Name{C_RESET}", f"{C_GRAY}[<] Back{C_RESET}"]
                print(f" {C_GREEN}Create New Profile:{C_RESET}\n")

            for i, opt in enumerate(options):
                if i == current_idx:
                    print(f"  {C_BLUE}\u276f {opt}{C_RESET}")
                else:
                    print(f"    {opt}")

            key = get_key()
            if key == 'up':
                current_idx = max(0, current_idx - 1)
            elif key == 'down':
                current_idx = min(len(options) - 1, current_idx + 1)
            elif key == 'enter':
                if mode == "main":
                    if current_idx < len(profiles):
                        return profiles[current_idx]
                    elif current_idx == len(profiles):
                        mode = "create"
                        current_idx = 0
                    elif current_idx == len(profiles) + 1:
                        mode = "delete"
                        current_idx = 0
                    elif current_idx == len(profiles) + 2:
                        sys.exit(0)
                elif mode == "create":
                    if current_idx == 0:
                        sys.stdout.write("\033[?25h")
                        raw = input(f"\n {C_WHITE}Name:{C_RESET} ")
                        choice = sanitize_name(raw)
                        if choice is None:
                            print(f"\n {C_RED}Invalid name. Use only letters, digits, spaces, hyphens, underscores.{C_RESET}")
                            import time; time.sleep(1.5)
                            sys.stdout.write("\033[?25l")
                            continue
                        return choice
                    else:
                        mode = "main"
                        current_idx = 0
                elif mode == "delete":
                    if current_idx < len(profiles):
                        p_to_delete = profiles[current_idx]
                        sys.stdout.write("\033[?25h")
                        clear_screen()
                        draw_header()
                        ans = input(f" {C_RED}Permanently delete '{p_to_delete}'? (y/N): {C_RESET}").strip().lower()
                        if ans == 'y':
                            target = PROFILES_DIR / p_to_delete
                            if target.exists():
                                shutil.rmtree(target)
                            profiles.remove(p_to_delete)
                        sys.stdout.write("\033[?25l")
                        mode = "main"
                        current_idx = 0
                    else:
                        mode = "main"
                        current_idx = 0
            elif key == 'ctrl_c':
                sys.stdout.write("\033[?25h")
                sys.exit(0)
    finally:
        sys.stdout.write("\033[?25h")
        clear_screen()

    return None


def swap_in_profile(profile_dir):
    """Copy this profile's saved auth files into the live system locations."""
    swapped = 0
    for sys_path, filename in AUTH_FILES:
        src = profile_dir / filename
        if src.exists():
            sys_path.parent.mkdir(parents=True, exist_ok=True)
            if sys_path.exists():
                shutil.copy2(sys_path, sys_path.with_suffix(".agyp-backup"))
            shutil.copy2(src, sys_path)
            swapped += 1
    return swapped


def save_back_profile(profile_dir):
    """Copy current live auth files back into the profile dir (after session ends)."""
    for sys_path, filename in AUTH_FILES:
        if sys_path.exists():
            shutil.copy2(sys_path, profile_dir / filename)


def set_last_active(profile_name):
    """Persist which profile is currently active."""
    try:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        LAST_ACTIVE_FILE.write_text(profile_name, encoding="utf-8")
    except OSError:
        pass


def clear_last_active():
    try:
        if LAST_ACTIVE_FILE.exists():
            LAST_ACTIVE_FILE.unlink()
    except OSError:
        pass


def launch_profile(profile, args):
    """Switch to a profile then launch agy, saving tokens back after exit."""
    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{C_BLUE}Switching to profile '{profile}'...{C_RESET}")

    swapped = swap_in_profile(profile_dir)
    if swapped > 0:
        print(f"{C_GREEN}Account loaded ({swapped} auth file(s) swapped). Launching...{C_RESET}\n")
    else:
        print(f"{C_YELLOW}New profile — you will be asked to log in.{C_RESET}")
        print(f"{C_GRAY}After logging in, your credentials are saved to this profile automatically.{C_RESET}\n")

    set_last_active(profile)

    # Verify CLI exists before trying to run it
    if not shutil.which("agy"):
        print(f"{C_RED}Error: 'agy' command not found. Ensure Antigravity CLI is installed.{C_RESET}")
        clear_last_active()
        sys.exit(1)

    try:
        ret = subprocess.call(["agy"] + args, shell=(sys.platform == "win32"))
    except FileNotFoundError:
        print(f"{C_RED}Error: 'agy' command not found. Ensure Antigravity CLI is installed.{C_RESET}")
        sys.exit(1)

    save_back_profile(profile_dir)
    clear_last_active()
    sys.exit(ret)


def main():
    if len(sys.argv) >= 2:
        argv_profile = sanitize_name(sys.argv[1])
        if argv_profile is None:
            print(f"{C_RED}Error: Invalid profile name '{sys.argv[1]}'. "
                  f"Use only letters, digits, spaces, hyphens, underscores.{C_RESET}")
            sys.exit(1)
        launch_profile(argv_profile, sys.argv[2:])
        return

    profiles = []
    if PROFILES_DIR.exists():
        profiles = sorted([d.name for d in PROFILES_DIR.iterdir() if d.is_dir()])

    selected_profile = interactive_menu(profiles)
    if selected_profile:
        launch_profile(selected_profile, [])


if __name__ == "__main__":
    main()
