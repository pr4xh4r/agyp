#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Antigravity isolates each account under HOME=/home/user/.agy_accounts/N
# so we MUST use the current $HOME env var (not the system passwd home)
# to find the correct token location that Antigravity reads from.
# We only fall back to pwd if HOME is somehow not set.
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

# Profiles are always stored in the REAL system home (/home/user)
# regardless of which .agy_accounts/N sandbox Antigravity activates.
if sys.platform != "win32":
    try:
        import pwd as _pwd
        _SYSTEM_HOME = Path(_pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError):
        _SYSTEM_HOME = REAL_HOME
else:
    _SYSTEM_HOME = REAL_HOME

VERSION = "1.1.0"

# Antigravity/Google Brand Colors (TrueColor ANSI)
C_BLUE   = "\033[38;2;66;133;244m"
C_GREEN  = "\033[38;2;52;168;83m"
C_RED    = "\033[38;2;234;67;53m"
C_YELLOW = "\033[38;2;251;188;5m"
C_WHITE  = "\033[1;37m"
C_GRAY   = "\033[38;5;245m"
C_RESET  = "\033[0m"

# Profile storage dir — always in real system home
PROFILES_DIR = _SYSTEM_HOME / "agyp-profiles"

# Auth files — always in REAL_HOME (the active Antigravity .agy_accounts/N dir)
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
        sys_path.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            if sys_path.exists():
                shutil.copy2(sys_path, sys_path.with_suffix(".agyp-backup"))
            shutil.copy2(src, sys_path)
            swapped += 1
        else:
            # CRITICAL: This profile is empty for this token.
            # We MUST delete the live system token so the app doesn't
            # reuse the previous user's login!
            if sys_path.exists():
                shutil.copy2(sys_path, sys_path.with_suffix(".agyp-backup"))
                sys_path.unlink()
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


def kill_existing_cli():
    """Forcefully close any background Antigravity CLI daemons so new tokens are read."""
    import time
    # On Windows, CREATE_NO_WINDOW stops CMD windows flashing open for each subprocess call
    _no_win = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "agy.exe", "/T"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=_no_win)
        elif sys.platform == "darwin":
            subprocess.run(["killall", "-9", "agy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["killall", "-9", "agy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                subprocess.run(["taskkill.exe", "/F", "/IM", "agy.exe", "/T"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=_no_win)
            except Exception:
                pass
    except Exception:
        pass
    time.sleep(0.5)

    # agy uses raw terminal mode for its interactive UI. If we kill it mid-session,
    # the terminal is left in a broken state printing "1u;1u;..." escape sequences.
    # stty sane resets all terminal settings back to a sane default.
    if sys.platform != "win32":
        try:
            subprocess.run(["stty", "sane"], stderr=subprocess.DEVNULL)
        except Exception:
            pass


def launch_profile(profile, args):
    """Launch agy in a completely isolated HOME environment."""
    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\\n{C_BLUE}Switching to profile '{profile}'...{C_RESET}")

    kill_existing_cli()

    # Migrate any old flat tokens to the isolated HOME structure
    for _, filename in AUTH_FILES:
        old_path = profile_dir / filename
        if old_path.exists():
            new_path = profile_dir / ".gemini" / ("antigravity-cli/" + filename if "oauth-token" in filename else filename)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.move(str(old_path), str(new_path))

    print(f"{C_GREEN}Launching in isolated environment...{C_RESET}\\n")

    import json
    CONFIG_FILE = PROFILES_DIR / "config.json"
    
    def get_custom_cli():
        try:
            if CONFIG_FILE.exists():
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("custom_cli_path")
        except: pass
        return None

    def set_custom_cli(path):
        try:
            data = {}
            if CONFIG_FILE.exists():
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            data["custom_cli_path"] = path
            CONFIG_FILE.write_text(json.dumps(data), encoding="utf-8")
        except: pass

    _custom = get_custom_cli()
    if _custom and os.path.isfile(_custom):
        cmd_path = _custom
    else:
        import shutil
        cmd_path = shutil.which("agy") or shutil.which("agy.exe") or shutil.which("agy.cmd")

    if not cmd_path:
        print(f"{C_RED}Error: 'agy' command not found in your PATH.{C_RESET}")
        sys.exit(1)

    use_shell = sys.platform == "win32" and not str(cmd_path).lower().endswith(".exe")
    
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

    try:
        import subprocess
        ret = subprocess.call([cmd_path] + args, shell=use_shell, env=env)
    except FileNotFoundError:
        print(f"{C_RED}Error: '{cmd_path}' not found.{C_RESET}")
        sys.exit(1)

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
