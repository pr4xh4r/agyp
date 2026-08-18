#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

# ── Platform guard ─────────────────────────────────────────────────────────────
if sys.platform == "win32":
    print("Error: agyp does not support Windows. Use Linux or macOS.")
    sys.exit(1)

# Antigravity isolates each account under HOME=/home/user/.agy_accounts/N
# so we MUST use the current $HOME env var (not the system passwd home)
# to find the correct token location that Antigravity reads from.
_env_home = os.environ.get("HOME")
if _env_home:
    REAL_HOME = Path(_env_home)
else:
    try:
        import pwd as _pwd
        REAL_HOME = Path(_pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError):
        REAL_HOME = Path(os.path.expanduser("~"))

# Profiles are always stored in the REAL system home (/home/user or /Users/user)
# regardless of which .agy_accounts/N sandbox Antigravity activates.
try:
    import pwd as _pwd
    _SYSTEM_HOME = Path(_pwd.getpwuid(os.getuid()).pw_dir)
except (ImportError, KeyError):
    _SYSTEM_HOME = REAL_HOME

VERSION = "1.2.0"

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

# ── Auth token paths ───────────────────────────────────────────────────────────
#
# Token files always live at the SAME relative paths inside any HOME dir.
# We store them at those same relative paths inside the profile dir too,
# so isolated mode (HOME=profile_dir) works with zero extra copying.
#
#   profile_dir/.gemini/antigravity-cli/antigravity-oauth-token
#   profile_dir/.gemini/oauth_creds.json
#   profile_dir/.gemini/google_accounts.json
#
# For unified mode we copy profile_dir/<rel> ↔ REAL_HOME/<rel>.

_TOKEN_RELPATHS = [
    Path(".gemini") / "antigravity-cli" / "antigravity-oauth-token",
    Path(".gemini") / "oauth_creds.json",
    Path(".gemini") / "google_accounts.json",
]

LAST_ACTIVE_FILE = PROFILES_DIR / ".last_active"
CONFIG_FILE      = PROFILES_DIR / "config.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

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
    """Reads a single keypress without echoing to the screen (arrow keys + enter)."""
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
    os.system("clear")


def draw_header():
    print(f"{C_BLUE}       ▄▀▀▄       {C_RESET}")
    print(f"{C_BLUE}      ▀▀▀▀▀▀      {C_RESET}")
    print(f"{C_BLUE}     ▀▀▀▀▀▀▀▀     {C_WHITE}Antigravity Profiles  v{VERSION}{C_RESET}")
    print(f"{C_BLUE}    ▄▀▀    ▀▀▄    {C_RESET}")
    print(f"{C_BLUE}   ▄▀▀      ▀▀▄   {C_RESET}")
    print(f"\n{C_GRAY}─────────────────────────────────────────────────────{C_RESET}\n")


# ── Mode selection ─────────────────────────────────────────────────────────────

def ask_mode():
    """
    Ask whether to run in isolated or unified mode.
      isolated → separate HOME per profile — no shared history or config.
      unified  → swap auth tokens only; history and config are shared.
    Returns 'isolated' or 'unified'.
    """
    options = [
        ("isolated", "separate HOME per profile — no shared history or config"),
        ("unified",  "swap auth tokens only — history and config are shared"),
    ]
    idx = 0
    sys.stdout.write("\033[?25l")
    try:
        while True:
            clear_screen()
            draw_header()
            print(f" {C_WHITE}Choose launch mode:{C_RESET}\n")
            for i, (label, desc) in enumerate(options):
                if i == idx:
                    print(f"  {C_BLUE}\u276f {C_WHITE}{label}{C_RESET}  {C_GRAY}{desc}{C_RESET}")
                else:
                    print(f"    {C_GRAY}{label}{C_RESET}  {C_GRAY}{desc}{C_RESET}")
            print(f"\n {C_GRAY}\u2191/\u2193 to move \u00b7 Enter to confirm{C_RESET}")

            key = get_key()
            if key == 'up':
                idx = max(0, idx - 1)
            elif key == 'down':
                idx = min(len(options) - 1, idx + 1)
            elif key == 'enter':
                return options[idx][0]
            elif key == 'ctrl_c':
                sys.stdout.write("\033[?25h")
                sys.exit(0)
    finally:
        sys.stdout.write("\033[?25h")


# ── Interactive profile menu ───────────────────────────────────────────────────

def interactive_menu(profiles):
    mode = "main"
    current_idx = 0

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


# ── Auth file management ───────────────────────────────────────────────────────

def _migrate_old_tokens(profile_dir):
    """
    One-time migration: move tokens from the old flat storage
    (profile_dir/antigravity-oauth-token) to the new mirror structure
    (profile_dir/.gemini/antigravity-cli/antigravity-oauth-token).
    Safe to call on every launch — no-ops if already migrated.
    """
    old_name_to_rel = {
        "antigravity-oauth-token": _TOKEN_RELPATHS[0],
        "oauth_creds.json":        _TOKEN_RELPATHS[1],
        "google_accounts.json":    _TOKEN_RELPATHS[2],
    }
    for old_name, rel in old_name_to_rel.items():
        old = profile_dir / old_name
        new = profile_dir / rel
        if old.exists() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(new))


def swap_in_profile(profile_dir):
    """
    Unified mode: copy this profile's tokens into the live HOME.
    Reads from profile_dir/.gemini/... → writes to REAL_HOME/.gemini/...
    Backs up whatever is currently live so it can be restored.
    """
    for rel in _TOKEN_RELPATHS:
        src = profile_dir / rel
        dst = REAL_HOME / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".agyp-backup"))
            shutil.copy2(src, dst)
        else:
            # Profile has no token for this file — remove the live copy so
            # agy doesn't reuse the previous account's credentials.
            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".agyp-backup"))
                dst.unlink()


def save_back_profile(profile_dir):
    """
    Unified mode: copy updated tokens from the live HOME back into the profile.
    Called after the agy session ends so the profile stays up-to-date.
    """
    for rel in _TOKEN_RELPATHS:
        src = REAL_HOME / rel
        dst = profile_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)


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


def inside_agy_session():
    """
    Return True if agyp is being run from inside an existing agy session.
    agy sets HOME to ~/.agy_accounts/N before launching, so we check for that.
    """
    home = os.environ.get("HOME", "")
    return ".agy_accounts" in home


# ── agy binary resolution ──────────────────────────────────────────────────────

def _resolve_agy():
    """Return path to the agy binary, honoring a custom CLI path config."""
    import json
    custom = None
    try:
        if CONFIG_FILE.exists():
            custom = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("custom_cli_path")
    except Exception:
        pass
    if custom and os.path.isfile(custom):
        return custom
    return shutil.which("agy")



# ── Launch helpers ─────────────────────────────────────────────────────────────

def _bash_exec(env, cmd_str):
    """
    Replace this process with bash -i sourcing .bashrc, then running cmd_str.
    os.execvpe means agyp's PID is gone — no Python parent left to conflict with agy.
    """
    bash = shutil.which("bash") or "/bin/bash"
    os.execvpe(bash, [bash, "-i", "-c", cmd_str], env)


def _bash_run(env, cmd_str):
    """
    Run cmd_str in a bash -i subprocess and WAIT for it to finish.
    Used for unified mode so we can call save_back_profile after agy exits.
    """
    bash = shutil.which("bash") or "/bin/bash"
    return subprocess.call([bash, "-i", "-c", cmd_str], env=env)


def launch_isolated(profile, args):
    """
    Launch agy with a completely isolated HOME environment.
    The profile directory IS $HOME — no shared history, config, or credentials.
    Tokens live at profile_dir/.gemini/... naturally (agy writes them there).
    """
    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Migrate any old flat-stored tokens to the .gemini mirror structure
    _migrate_old_tokens(profile_dir)

    print(f"\n{C_BLUE}Switching to profile '{profile}'  [{C_YELLOW}isolated{C_BLUE}]{C_RESET}")
    print(f"{C_GREEN}Launching isolated environment...{C_RESET}\n")

    # Set isolated HOME; clear XDG so nothing leaks from the real home
    env = os.environ.copy()
    env["HOME"] = str(profile_dir)
    for xdg in ["XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]:
        env.pop(xdg, None)

    extra = " ".join(f"'{a}'" for a in args) if args else ""
    # 'command agy' calls the binary directly (not the bash wrapper function).
    # HOME is already set in env to the isolated profile_dir.
    cmd_str = f"command agy {extra}".strip()

    _bash_exec(env, cmd_str)
    # os.execvpe never returns


def launch_unified(profile, args):
    """
    Launch agy using the real HOME but with this profile's auth tokens.
    History, config, and cache are shared. Only credentials are swapped.

    NOTE: Unified mode should be used from OUTSIDE an agy session.
    If run from inside agy, launching a second agy with the same HOME
    may cause a session conflict — use isolated mode instead.
    """
    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Migrate any old flat-stored tokens first
    _migrate_old_tokens(profile_dir)

    if inside_agy_session():
        print(f"\n{C_YELLOW}Warning: you are inside an existing agy session.{C_RESET}")
        print(f"{C_GRAY}Launching a second agy with the same HOME may cause a session conflict.")
        print(f"Consider using isolated mode instead.{C_RESET}")
        print()

    print(f"\n{C_BLUE}Switching to profile '{profile}'  [{C_YELLOW}unified{C_BLUE}]{C_RESET}")

    # Copy this profile's tokens into the live HOME
    swap_in_profile(profile_dir)
    set_last_active(profile)

    print(f"{C_GREEN}Auth tokens swapped. Launching...{C_RESET}\n")

    extra = " ".join(f"'{a}'" for a in args) if args else ""
    cmd_str = f"command agy {extra}".strip()

    # Use subprocess (not exec) so we can save tokens back after agy exits
    try:
        _bash_run(os.environ.copy(), cmd_str)
    finally:
        # Always save updated tokens back regardless of how agy exits
        save_back_profile(profile_dir)
        clear_last_active()

    sys.exit(0)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    # Allow direct non-interactive launch: agyp <profile> [agy-args...]
    # Defaults to isolated mode when called this way.
    if len(sys.argv) >= 2:
        argv_profile = sanitize_name(sys.argv[1])
        if argv_profile is None:
            print(f"{C_RED}Error: Invalid profile name '{sys.argv[1]}'. "
                  f"Use only letters, digits, spaces, hyphens, underscores.{C_RESET}")
            sys.exit(1)
        launch_isolated(argv_profile, sys.argv[2:])
        return

    # Step 1: Ask isolated or unified
    mode = ask_mode()

    # Step 2: Pick / create profile
    profiles = []
    if PROFILES_DIR.exists():
        profiles = sorted([d.name for d in PROFILES_DIR.iterdir() if d.is_dir()])

    selected_profile = interactive_menu(profiles)
    if not selected_profile:
        sys.exit(0)

    # Step 3: Launch in chosen mode
    if mode == "isolated":
        launch_isolated(selected_profile, [])
    else:
        launch_unified(selected_profile, [])


if __name__ == "__main__":
    main()
