#!/usr/bin/env python3
# agyp — Antigravity Profiles
# Manage unlimited Antigravity (agy) accounts from a single terminal.
#
# Author:  pr4xh4r (https://github.com/pr4xh4r)
# License: MIT
# Community: https://x.com/buildx_main

import os
import sys
import io
import re
import tty
import json
import shutil
import atexit
import termios
import subprocess
import webbrowser
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

VERSION = "1.3.0"

# ── Brand Colors (Antigravity TrueColor ANSI) ──────────────────────────────────
C_BLUE   = "\033[38;2;66;133;244m"
C_GREEN  = "\033[38;2;52;168;83m"
C_RED    = "\033[38;2;234;67;53m"
C_YELLOW = "\033[38;2;251;188;5m"
C_WHITE  = "\033[37m"          # plain white — no bold, prevents icon size jump
C_GRAY   = "\033[38;5;245m"
C_RESET  = "\033[0m"
C_JOIN   = "\033[38;2;112;230;39m"   # bright lime green (X logo color)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROFILES_DIR    = _SYSTEM_HOME / "agyp-profiles"
CONFIG_FILE     = PROFILES_DIR / "config.json"
LAST_ACTIVE_FILE = PROFILES_DIR / ".last_active"

# Token files live at the same relative paths inside any HOME dir.
_TOKEN_RELPATHS = [
    Path(".gemini") / "antigravity-cli" / "antigravity-oauth-token",
    Path(".gemini") / "oauth_creds.json",
    Path(".gemini") / "google_accounts.json",
]


# ── Flicker-free terminal buffer ───────────────────────────────────────────────

class TerminalBuffer:
    """Render an entire screen frame in memory, then paint it in one shot."""
    def __init__(self):
        self.old_stdout = sys.stdout
        self.buf = io.StringIO()

    def write(self, s):
        # Append erase-to-EOL before every newline so leftover chars are wiped
        self.buf.write(s.replace('\n', '\033[K\n'))

    def flush(self):
        pass  # swallow intermediate flushes

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, *args):
        sys.stdout = self.old_stdout
        # Move to top-left, paint frame, erase anything below
        self.old_stdout.write('\033[H')
        self.old_stdout.write(self.buf.getvalue())
        self.old_stdout.write('\033[0J')
        self.old_stdout.flush()


# ── Terminal lifecycle ─────────────────────────────────────────────────────────

def _reset_terminal():
    """Restore terminal to a sane state — called automatically on exit."""
    try:
        sys.stdout.write("\033[?1049l")   # exit alternate screen buffer
        sys.stdout.write("\033[?25h")     # show cursor
        sys.stdout.write("\033[?1000l\033[?1002l\033[?1003l\033[?1015l\033[?1006l")
        sys.stdout.write("\033[?2004l")   # disable bracketed paste
        sys.stdout.flush()
    except Exception:
        pass

atexit.register(_reset_terminal)


# ── Helpers ────────────────────────────────────────────────────────────────────

def sanitize_name(name):
    """Sanitize profile name — prevents path traversal and shell injection."""
    name = name.strip()
    if not name:
        return None
    if '/' in name or '\\' in name or '..' in name or name.startswith('.'):
        return None
    if not re.match(r'^[A-Za-z0-9 _-]+$', name):
        return None
    return name


def get_profile_email(profile_name):
    """Return the last authenticated email for a profile, or None."""
    cli_log = PROFILES_DIR / profile_name / ".gemini" / "antigravity-cli" / "cli.log"
    if cli_log.exists():
        try:
            with open(cli_log, "r", encoding="utf-8", errors="ignore") as fh:
                for line in reversed(fh.readlines()):
                    m = re.search(r'email=([^,\s]+)', line)
                    if m:
                        return m.group(1).strip()
        except Exception:
            pass
    return None


def get_key():
    """Read one keypress from raw stdin — handles arrow keys, Enter, Ctrl-C."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b'\x1b':
            # Switch to 100 ms timeout to read escape sequence tail
            esc = termios.tcgetattr(fd)
            esc[6][termios.VMIN]  = 0
            esc[6][termios.VTIME] = 1
            termios.tcsetattr(fd, termios.TCSANOW, esc)
            rest = os.read(fd, 6)
            if rest.startswith(b'[A'): return 'up'
            if rest.startswith(b'[B'): return 'down'
            return 'other'
        if ch in (b'\r', b'\n'): return 'enter'
        if ch == b'\x03':        return 'ctrl_c'
        if ch == b'\x7f':        return 'backspace'
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return 'other'


def clear_screen():
    """Full terminal clear (used only for input prompts)."""
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()


def draw_header():
    """Print the Antigravity logo and separator."""
    _brand = "Antigravity Profiles"
    _beta  = "(BETA)"
    _pad   = " " * ((len(_brand) - len(_beta)) // 2)
    print(f"       \033[38;2;237;125;49m▄\033[38;2;237;125;49m▀\033[38;2;225;85;53m▀\033[38;2;225;85;53m▄\033[0m       ")
    print(f"      \033[38;2;226;166;59m▀\033[38;2;232;134;54m▀\033[38;2;237;125;49m▀\033[38;2;225;85;53m▀\033[38;2;211;64;71m▀\033[38;2;211;64;71m▀\033[0m      ")
    print(f"     \033[38;2;125;180;82m▀\033[38;2;125;180;82m▀\033[38;2;161;179;71m▀\033[38;2;213;137;67m▀\033[38;2;225;85;53m▀\033[38;2;162;94;153m▀\033[38;2;162;94;153m▀\033[38;2;162;94;153m▀\033[0m     {C_WHITE}{_brand}  v{VERSION}{C_RESET}")
    print(f"    \033[38;2;108;190;90m▄\033[38;2;71;135;214m▀\033[38;2;71;135;214m▀    \033[38;2;104;113;200m▀\033[38;2;100;102;203m▀\033[38;2;100;102;203m▄\033[0m    {C_YELLOW}{_pad}{_beta}{C_RESET}")
    print(f"   \033[38;2;85;181;222m▄\033[38;2;71;135;214m▀\033[38;2;71;135;214m▀      \033[38;2;71;135;214m▀\033[38;2;71;135;214m▀\033[38;2;71;135;214m▄\033[0m   ")
    print(f"\n{C_GRAY}─────────────────────────────────────────────────────{C_RESET}\n")


# ── Community screen ───────────────────────────────────────────────────────────

def show_community():
    """Interactive Build x community links screen."""
    light = "\033[38;2;112;230;39m"
    mid   = "\033[38;2;71;200;50m"
    dark  = "\033[38;2;30;160;18m"

    logo = [
        f"     {light}█▄ ▄█{C_RESET}",
        f"      {mid}▀█▀{C_RESET}",
        f"     {dark}█▀ ▀█{C_RESET}",
    ]

    links = [
        ("\uf099 X (Twitter)", "https://x.com/buildx_main"),
        ("\uf2c6 Telegram",    "https://t.me/buildx_main"),
        ("\uf281 Reddit",      "https://reddit.com/r/buildx_main"),
        ("Go Back",            None),
    ]

    idx = 0
    while True:
        with TerminalBuffer():
            draw_header()
            for line in logo:
                print(line)
            print(f"\n {C_WHITE}Join the Build x Community!{C_RESET}\n")
            for i, (label, url) in enumerate(links):
                if i == idx:
                    if url:
                        print(f"  {C_BLUE}\u276f {label}{C_RESET}  \033[38;2;100;100;100m{url}\033[0m")
                    else:
                        print(f"  {C_BLUE}\u276f {C_GRAY}[x] {label}{C_RESET}")
                else:
                    if url:
                        print(f"    {C_GRAY}{label}{C_RESET}  \033[38;2;100;100;100m{url}\033[0m")
                    else:
                        print(f"    {C_GRAY}[x] {label}{C_RESET}")
            print(f"\n {C_GRAY}\u2191/\u2193 to move \u00b7 Enter to open \u00b7 Esc/Ctrl-C to go back{C_RESET}")

        key = get_key()
        if key == 'up':
            idx = (idx - 1) % len(links)
        elif key == 'down':
            idx = (idx + 1) % len(links)
        elif key == 'enter':
            url = links[idx][1]
            if url:
                webbrowser.open(url)
            else:
                return
        elif key in ('ctrl_c', 'other'):
            return


# ── Mode selection ─────────────────────────────────────────────────────────────

def ask_mode():
    """Ask isolated vs unified. Returns 'isolated', 'unified', or 'EXIT'."""
    options = [
        ("isolated", "Isolated", "[Each profile is fully separate]"),
        ("unified",  "Unified",  "[Shared history]"),
        ("join_us",  "",         ""),
        ("exit",     "",         ""),
    ]
    idx = 0
    while True:
        with TerminalBuffer():
            draw_header()
            print(f" {C_WHITE}Choose launch mode:{C_RESET}\n")
            for i, (label, tag, desc) in enumerate(options):
                if i == idx:
                    if label == "exit":
                        print(f"  {C_BLUE}\u276f {C_GRAY}[x] Exit{C_RESET}")
                    elif label == "join_us":
                        print(f"  {C_BLUE}\u276f {C_JOIN}[♥] Join Us{C_RESET}")
                    else:
                        print(f"  {C_BLUE}\u276f {C_WHITE}{tag}{C_RESET}  {C_GRAY}{desc}{C_RESET}")
                else:
                    if label == "exit":
                        print(f"    {C_GRAY}[x] Exit{C_RESET}")
                    elif label == "join_us":
                        print(f"    {C_JOIN}[♥] Join Us{C_RESET}")
                    else:
                        print(f"    {C_GRAY}{tag}{C_RESET}  {C_GRAY}{desc}{C_RESET}")
            print(f"\n {C_GRAY}\u2191/\u2193 to move \u00b7 Enter to confirm{C_RESET}")

        key = get_key()
        if key == 'up':
            idx = (idx - 1) % len(options)
        elif key == 'down':
            idx = (idx + 1) % len(options)
        elif key == 'enter':
            lbl = options[idx][0]
            if lbl == "exit":
                return "EXIT"
            elif lbl == "join_us":
                show_community()
            else:
                return lbl
        elif key == 'ctrl_c':
            return "EXIT"


# ── Interactive profile menu ───────────────────────────────────────────────────

def interactive_menu(profiles):
    """Full TUI for profile selection, creation, rename, delete."""
    mode = "main"
    current_idx = 0
    # Pre-build options so they're always defined before get_key() is called
    options = []

    def build_options():
        nonlocal options
        if mode == "main":
            options = profiles + [
                "[+] Add Profile",
                "[~] Rename Profile",
                "[-] Delete Profile",
                f"{C_JOIN}[♥] Join Us{C_RESET}",
                f"{C_GRAY}[x] Exit{C_RESET}",
            ]
        elif mode == "delete":
            options = profiles + [f"{C_GRAY}[<] Back{C_RESET}"]
        elif mode == "rename":
            options = profiles + [f"{C_GRAY}[<] Back{C_RESET}"]
        elif mode == "create":
            options = [f"{C_GREEN}[>] Enter Profile Name{C_RESET}", f"{C_GRAY}[<] Back{C_RESET}"]

    while True:
        build_options()

        with TerminalBuffer():
            draw_header()
            if mode == "main":
                print(f" {C_WHITE}Select a profile to launch:{C_RESET}\n")
            elif mode == "delete":
                print(f" {C_RED}Select a profile to delete:{C_RESET}\n")
                if not profiles:
                    print(f" {C_GRAY}  (No profiles exist yet.){C_RESET}\n")
            elif mode == "rename":
                print(f" {C_YELLOW}Select a profile to rename:{C_RESET}\n")
                if not profiles:
                    print(f" {C_GRAY}  (No profiles exist yet.){C_RESET}\n")
            elif mode == "create":
                print(f" {C_GREEN}Create New Profile:{C_RESET}\n")

            for i, opt in enumerate(options):
                suffix = ""
                plain = re.sub(r'\033\[[^m]*m', '', opt)   # strip ANSI for email lookup
                if mode == "main" and i < len(profiles):
                    email = get_profile_email(opt)
                    if email:
                        suffix = f"  {C_GRAY}[{email}]{C_RESET}"
                if i == current_idx:
                    print(f"  {C_BLUE}\u276f {opt}{suffix}{C_RESET}")
                else:
                    if not opt.startswith('\033'):
                        print(f"    {C_GRAY}{opt}{C_RESET}{suffix}")
                    else:
                        print(f"    {opt}{suffix}")

            print(f"\n {C_GRAY}\u2191/\u2193 to move \u00b7 Enter to select{C_RESET}")

        key = get_key()

        if key == 'up':
            current_idx = (current_idx - 1) % len(options)
        elif key == 'down':
            current_idx = (current_idx + 1) % len(options)
        elif key == 'ctrl_c':
            return "EXIT"
        elif key == 'enter':
            if mode == "main":
                n = len(profiles)
                if current_idx < n:
                    return profiles[current_idx]
                elif current_idx == n:        # Add Profile
                    mode = "create"
                    current_idx = 0
                elif current_idx == n + 1:    # Rename Profile
                    mode = "rename"
                    current_idx = 0
                elif current_idx == n + 2:    # Delete Profile
                    mode = "delete"
                    current_idx = 0
                elif current_idx == n + 3:    # Join Us
                    show_community()
                elif current_idx == n + 4:    # Exit
                    return "EXIT"

            elif mode == "create":
                if current_idx == 0:
                    # Exit alt-screen for input, then restore
                    sys.stdout.write("\033[?1049l\033[?25h")
                    sys.stdout.flush()
                    try:
                        clear_screen()
                        draw_header()
                        raw = input(f" {C_GREEN}New profile name:{C_RESET} ")
                    except (EOFError, KeyboardInterrupt):
                        raw = ""
                    sys.stdout.write("\033[?1049h\033[?25l")
                    sys.stdout.flush()
                    choice = sanitize_name(raw)
                    if not choice:
                        # flash error — will be overwritten on next render
                        import time; time.sleep(1.2)
                        continue
                    if (PROFILES_DIR / choice).exists():
                        import time; time.sleep(1.2)
                        continue
                    return choice
                else:
                    mode = "main"
                    current_idx = 0

            elif mode == "rename":
                if current_idx < len(profiles):
                    p_old = profiles[current_idx]
                    sys.stdout.write("\033[?1049l\033[?25h")
                    sys.stdout.flush()
                    try:
                        clear_screen()
                        draw_header()
                        raw = input(f" {C_YELLOW}Rename '{p_old}' to:{C_RESET} ").strip()
                    except (EOFError, KeyboardInterrupt):
                        raw = ""
                    sys.stdout.write("\033[?1049h\033[?25l")
                    sys.stdout.flush()
                    new_name = sanitize_name(raw)
                    if new_name and not (PROFILES_DIR / new_name).exists():
                        (PROFILES_DIR / p_old).rename(PROFILES_DIR / new_name)
                        profiles[profiles.index(p_old)] = new_name
                        profiles.sort()
                    mode = "main"
                    current_idx = 0
                else:
                    mode = "main"
                    current_idx = 0

            elif mode == "delete":
                if current_idx < len(profiles):
                    p_del = profiles[current_idx]
                    sys.stdout.write("\033[?1049l\033[?25h")
                    sys.stdout.flush()
                    try:
                        clear_screen()
                        draw_header()
                        ans = input(f" {C_RED}Permanently delete '{p_del}'? (y/N):{C_RESET} ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        ans = ""
                    sys.stdout.write("\033[?1049h\033[?25l")
                    sys.stdout.flush()
                    if ans == 'y':
                        target = PROFILES_DIR / p_del
                        if target.exists():
                            shutil.rmtree(target)
                        profiles.remove(p_del)
                        current_idx = min(current_idx, max(0, len(profiles) - 1))
                    mode = "main"
                    current_idx = 0
                else:
                    mode = "main"
                    current_idx = 0

    return None


# ── Auth file management ───────────────────────────────────────────────────────

def _migrate_old_tokens(profile_dir):
    """Move tokens from old flat layout to the .gemini mirror structure."""
    old_names = {
        "antigravity-oauth-token": _TOKEN_RELPATHS[0],
        "oauth_creds.json":        _TOKEN_RELPATHS[1],
        "google_accounts.json":    _TOKEN_RELPATHS[2],
    }
    for fname, rel in old_names.items():
        old = profile_dir / fname
        new = profile_dir / rel
        if old.exists() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(new))


def swap_in_profile(profile_dir):
    """Unified mode: copy profile tokens into live HOME."""
    for rel in _TOKEN_RELPATHS:
        src = profile_dir / rel
        dst = REAL_HOME / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".agyp-backup"))
            shutil.copy2(src, dst)
        else:
            if dst.exists():
                shutil.copy2(dst, dst.with_suffix(".agyp-backup"))
                dst.unlink()


def save_back_profile(profile_dir):
    """Unified mode: save updated tokens back into profile after session ends."""
    for rel in _TOKEN_RELPATHS:
        src = REAL_HOME / rel
        dst = profile_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)


def set_last_active(profile_name):
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
    """True if we're running inside an existing agy sandbox."""
    return ".agy_accounts" in os.environ.get("HOME", "")


# ── agy binary resolution ──────────────────────────────────────────────────────

def _resolve_agy():
    """Return path to the agy binary, respecting custom config."""
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
    """Replace this process with bash running cmd_str (os.execvpe — never returns)."""
    bash = shutil.which("bash") or "/bin/bash"
    os.execvpe(bash, [bash, "-i", "-c", cmd_str], env)


def _bash_run(env, cmd_str):
    """Run cmd_str in a bash subprocess and wait for it to finish."""
    bash = shutil.which("bash") or "/bin/bash"
    return subprocess.call([bash, "-i", "-c", cmd_str], env=env)


def launch_isolated(profile, args):
    """Launch agy with a fully isolated HOME = profile directory."""
    agy_bin = _resolve_agy()
    if not agy_bin:
        print(f"{C_RED}Error: 'agy' not found in PATH. Is Antigravity installed?{C_RESET}")
        sys.exit(1)

    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    _migrate_old_tokens(profile_dir)

    print(f"\n{C_BLUE}Switching to profile '{profile}'  [{C_YELLOW}isolated{C_BLUE}]{C_RESET}")
    print(f"{C_GREEN}Launching isolated environment...{C_RESET}\n")

    env = os.environ.copy()
    env["HOME"] = str(profile_dir)
    for xdg in ["XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]:
        env.pop(xdg, None)

    extra = " ".join(f"'{a}'" for a in args) if args else ""
    _bash_exec(env, f"'{agy_bin}' {extra}".strip())
    # os.execvpe never returns


def launch_unified(profile, args):
    """Launch agy with shared HOME but this profile's auth tokens."""
    agy_bin = _resolve_agy()
    if not agy_bin:
        print(f"{C_RED}Error: 'agy' not found in PATH. Is Antigravity installed?{C_RESET}")
        sys.exit(1)

    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    _migrate_old_tokens(profile_dir)

    if inside_agy_session():
        print(f"\n{C_YELLOW}Warning: already inside an agy session. A conflict may occur.{C_RESET}")
        print(f"{C_GRAY}Consider using isolated mode instead.{C_RESET}\n")

    print(f"\n{C_BLUE}Switching to profile '{profile}'  [{C_YELLOW}unified{C_BLUE}]{C_RESET}")
    swap_in_profile(profile_dir)
    set_last_active(profile)
    print(f"{C_GREEN}Auth tokens swapped. Launching...{C_RESET}\n")

    extra = " ".join(f"'{a}'" for a in args) if args else ""
    try:
        _bash_run(os.environ.copy(), f"'{agy_bin}' {extra}".strip())
    finally:
        save_back_profile(profile_dir)
        clear_last_active()

    sys.exit(0)


# ── Non-interactive subcommands ────────────────────────────────────────────────

def _print_help():
    draw_header()
    print(f"{C_WHITE}Usage:{C_RESET}\n")
    print(f"  {C_WHITE}agyp{C_RESET}                       Launch interactive profile manager")
    print(f"  {C_WHITE}agyp <profile>{C_RESET}             Launch a named profile directly (isolated mode)")
    print(f"  {C_WHITE}agyp <profile> [args...]{C_RESET}   Pass extra args to agy")
    print(f"  {C_WHITE}agyp list{C_RESET}                  List all saved profiles")
    print(f"  {C_WHITE}agyp rename <old> <new>{C_RESET}    Rename a profile")
    print(f"  {C_WHITE}agyp --version{C_RESET}             Show version")
    print(f"  {C_WHITE}agyp --help{C_RESET}                Show this help")
    print(f"\n{C_GRAY}Profiles stored in: ~/agyp-profiles/{C_RESET}\n")


def _cmd_list():
    print()   # push past the shell prompt line
    if not PROFILES_DIR.exists():
        print(f"  {C_GRAY}No profiles yet. Run 'agyp' to create one.{C_RESET}\n")
        return
    profiles = sorted([d.name for d in PROFILES_DIR.iterdir() if d.is_dir()])
    if not profiles:
        print(f"  {C_GRAY}No profiles yet. Run 'agyp' to create one.{C_RESET}\n")
        return
    print(f"  {C_WHITE}Saved profiles:{C_RESET}\n")
    for p in profiles:
        email = get_profile_email(p)
        suffix = f"  {C_GRAY}[{email}]{C_RESET}" if email else ""
        print(f"  {C_BLUE}·{C_RESET} {p}{suffix}")
    print()


def _cmd_rename(old_name, new_name):
    old = sanitize_name(old_name)
    new = sanitize_name(new_name)
    if old is None:
        print(f"{C_RED}Error: Invalid name '{old_name}'.{C_RESET}"); sys.exit(1)
    if new is None:
        print(f"{C_RED}Error: Invalid name '{new_name}'.{C_RESET}"); sys.exit(1)
    src = PROFILES_DIR / old
    dst = PROFILES_DIR / new
    if not src.exists():
        print(f"{C_RED}Error: Profile '{old}' does not exist.{C_RESET}"); sys.exit(1)
    if dst.exists():
        print(f"{C_RED}Error: Profile '{new}' already exists.{C_RESET}"); sys.exit(1)
    src.rename(dst)
    print(f"{C_GREEN}✓ Renamed '{old}' → '{new}'{C_RESET}")


# ── Entry point ────────────────────────────────────────────────────────────────

def _goodbye():
    """Print the exit message cleanly after the alt-screen is closed."""
    sys.stdout.write(f"\r\n  {C_JOIN}♥ Thanks for using Antigravity Profiles!{C_RESET}\r\n\r\n")
    sys.stdout.flush()


def main():
    argv = sys.argv[1:]

    if argv and argv[0] in ("--version", "-v"):
        print(f"agyp v{VERSION}")
        sys.exit(0)

    if argv and argv[0] in ("--help", "-h"):
        _print_help()
        sys.exit(0)

    if argv and argv[0] == "list":
        _cmd_list()
        return

    if argv and argv[0] == "rename":
        if len(argv) != 3:
            print(f"{C_RED}Usage: agyp rename <old-name> <new-name>{C_RESET}")
            sys.exit(1)
        _cmd_rename(argv[1], argv[2])
        return

    # Direct profile launch: agyp <profile> [agy-args...]
    if argv:
        argv_profile = sanitize_name(argv[0])
        if argv_profile is None:
            print(f"{C_RED}Error: Invalid profile name '{argv[0]}'.{C_RESET}")
            sys.exit(1)
        launch_isolated(argv_profile, argv[1:])
        return

    # ── Interactive TUI ────────────────────────────────────────────────────────
    sys.stdout.write("\033[?1049h\033[?25l")   # enter alt-screen, hide cursor
    sys.stdout.flush()

    mode = None
    selected_profile = None

    try:
        mode = ask_mode()
        if mode == "EXIT":
            return  # falls through to finally → goodbye

        profiles = []
        if PROFILES_DIR.exists():
            profiles = sorted([d.name for d in PROFILES_DIR.iterdir() if d.is_dir()])

        selected_profile = interactive_menu(profiles)
        if selected_profile == "EXIT" or not selected_profile:
            return  # falls through to finally → goodbye

    finally:
        # Always restore terminal before doing ANYTHING else
        sys.stdout.write("\033[?1049l\033[?25h")
        sys.stdout.flush()

    # Print goodbye only on clean exit (not when launching a profile)
    if not selected_profile or selected_profile == "EXIT":
        _goodbye()
        os._exit(0)

    # Step 3: launch
    if mode == "isolated":
        launch_isolated(selected_profile, [])
    else:
        launch_unified(selected_profile, [])


if __name__ == "__main__":
    main()
