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
import time
import shutil
import atexit
import termios
import subprocess
import webbrowser
from datetime import datetime
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

VERSION = "1.5.0"

# ── Brand Colors (Antigravity TrueColor ANSI) ──────────────────────────────────
C_BLUE   = "\033[38;2;66;133;244m"
C_GREEN  = "\033[38;2;52;168;83m"
C_CYAN   = "\033[38;2;76;201;240m"
C_RED    = "\033[38;2;234;67;53m"
C_YELLOW = "\033[38;2;251;188;5m"
C_WHITE  = "\033[37m"          # plain white — no bold, prevents icon size jump
C_GRAY   = "\033[38;5;245m"
C_RESET  = "\033[0m"
C_JOIN   = "\033[38;2;112;230;39m"   # bright lime green (X logo color)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROFILES_DIR     = _SYSTEM_HOME / "agyp-profiles"
CONFIG_FILE      = PROFILES_DIR / "config.json"
LAST_ACTIVE_FILE = PROFILES_DIR / ".last_active"
# Metadata lives in a hidden sub-dir so it never appears in the profiles list.
META_DIR         = PROFILES_DIR / ".meta"

# Token files live at the same relative paths inside any HOME dir.
_TOKEN_RELPATHS = [
    Path(".gemini") / "antigravity-cli" / "antigravity-oauth-token",
    Path(".gemini") / "oauth_creds.json",
    Path(".gemini") / "google_accounts.json",
]

# Email regex — matches foo@bar.com across various log formats (key=val, JSON, plain)
_EMAIL_RE = re.compile(
    r'email[=:\s"\']+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
    re.IGNORECASE,
)


KEYRING_TOKEN_FILE = "keyring_token.json"


# ── System Keyring Token Manager ──────────────────────────────────────────────
# Antigravity (agy) stores its OAuth tokens in the system keyring
# (SecretService via DBus on Linux, Keychain on macOS) under service "gemini"
# and username "antigravity".  Because the keyring is system-wide, profile
# environments share the same credentials unless agyp actively manages the
# keyring item per profile.

class KeyringManager:
    SERVICE = "gemini"
    USERNAME = "antigravity"

    @classmethod
    def get_token(cls):
        """Read the raw OAuth JSON token string from the system keyring."""
        if sys.platform == "darwin":
            try:
                out = subprocess.check_output(
                    ["security", "find-generic-password", "-s", cls.SERVICE, "-a", cls.USERNAME, "-w"],
                    stderr=subprocess.DEVNULL
                )
                return out.decode("utf-8").strip()
            except Exception:
                return None
        elif sys.platform.startswith("linux"):
            try:
                import dbus
                bus = dbus.SessionBus()
                service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
                iface = dbus.Interface(service, "org.freedesktop.Secret.Service")
                res = iface.SearchItems({"service": cls.SERVICE, "username": cls.USERNAME})
                if not res[0]:
                    return None
                output, session_path = iface.OpenSession("plain", dbus.String("", variant_level=1))
                item_obj = bus.get_object("org.freedesktop.secrets", res[0][0])
                secret_struct = item_obj.GetSecret(session_path, dbus_interface="org.freedesktop.Secret.Item")
                return bytes(secret_struct[2]).decode("utf-8", errors="ignore")
            except Exception:
                return None
        return None

    @classmethod
    def set_token(cls, token_str):
        """Write the raw OAuth JSON token string into the system keyring."""
        if not token_str:
            return cls.delete_token()
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    ["security", "add-generic-password", "-U", "-s", cls.SERVICE, "-a", cls.USERNAME, "-w", token_str],
                    check=True, stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                return False
        elif sys.platform.startswith("linux"):
            try:
                import dbus
                bus = dbus.SessionBus()
                service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
                iface = dbus.Interface(service, "org.freedesktop.Secret.Service")
                output, session_path = iface.OpenSession("plain", dbus.String("", variant_level=1))

                # Delete existing item first to ensure clean overwrite
                res = iface.SearchItems({"service": cls.SERVICE, "username": cls.USERNAME})
                for p in res[0]:
                    try:
                        bus.get_object("org.freedesktop.secrets", p).Delete(dbus_interface="org.freedesktop.Secret.Item")
                    except Exception:
                        pass

                col_obj = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets/aliases/default")
                col_iface = dbus.Interface(col_obj, "org.freedesktop.Secret.Collection")
                props = {
                    "org.freedesktop.Secret.Item.Label": dbus.String(f"Password for \x27{cls.USERNAME}\x27 on \x27{cls.SERVICE}\x27"),
                    "org.freedesktop.Secret.Item.Attributes": dbus.Dictionary({
                        "service": cls.SERVICE,
                        "username": cls.USERNAME
                    }, signature="ss")
                }
                secret = dbus.Struct((
                    session_path,
                    dbus.ByteArray(b""),
                    dbus.ByteArray(token_str.encode("utf-8")),
                    dbus.String("text/plain")
                ))
                col_iface.CreateItem(props, secret, True)
                return True
            except Exception:
                return False
        return False

    @classmethod
    def delete_token(cls):
        """Delete the Antigravity OAuth token from the system keyring."""
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    ["security", "delete-generic-password", "-s", cls.SERVICE, "-a", cls.USERNAME],
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                return False
        elif sys.platform.startswith("linux"):
            try:
                import dbus
                bus = dbus.SessionBus()
                service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
                iface = dbus.Interface(service, "org.freedesktop.Secret.Service")
                res = iface.SearchItems({"service": cls.SERVICE, "username": cls.USERNAME})
                for p in res[0]:
                    try:
                        bus.get_object("org.freedesktop.secrets", p).Delete(dbus_interface="org.freedesktop.Secret.Item")
                    except Exception:
                        pass
                return True
            except Exception:
                return False
        return False

    @classmethod
    def extract_email(cls, token_str):
        """Extract user email from the JWT id_token inside the stored JSON token."""
        if not token_str:
            return None
        try:
            import base64
            data = json.loads(token_str)
            id_token = data.get("id_token")
            if id_token and isinstance(id_token, str) and "." in id_token:
                parts = id_token.split(".")
                if len(parts) >= 2:
                    p = parts[1] + "=" * (-len(parts[1]) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(p))
                    email = payload.get("email")
                    if email and "@" in email:
                        return email
        except Exception:
            pass
        return None


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


def _list_profiles():
    """Return sorted list of profile names, skipping hidden dirs like .meta."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(
        d.name for d in PROFILES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    )


# ── Profile metadata ───────────────────────────────────────────────────────────
# Each profile has a JSON file at .meta/<name>.json storing:
#   email, created_at, last_used
# This survives log rotation and does not depend on agy's internal log format.

def _load_meta(profile_name):
    """Load metadata dict for a profile, returning {} if absent or corrupt."""
    meta_file = META_DIR / f"{profile_name}.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_meta(profile_name, **kwargs):
    """Persist key/value pairs into a profile's metadata file."""
    meta = _load_meta(profile_name)
    meta.update({k: v for k, v in kwargs.items() if v is not None})
    META_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (META_DIR / f"{profile_name}.json").write_text(
            json.dumps(meta, indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass


def _rename_meta(old_name, new_name):
    """Rename a profile's metadata file when the profile itself is renamed."""
    old_file = META_DIR / f"{old_name}.json"
    new_file = META_DIR / f"{new_name}.json"
    if old_file.exists():
        try:
            old_file.rename(new_file)
        except Exception:
            pass


def _delete_meta(profile_name):
    """Remove a profile's metadata file when the profile is deleted."""
    meta_file = META_DIR / f"{profile_name}.json"
    if meta_file.exists():
        try:
            meta_file.unlink()
        except Exception:
            pass


# ── Email detection ────────────────────────────────────────────────────────────
# BUG FIX: agy writes its runtime logs inside .agy_accounts/<slot>/.gemini/…/cli.log,
# NOT at the top-level profile_dir/.gemini/…/cli.log.  Both locations are now
# searched, with the most-recently-modified slot checked first.

def _search_email_in_log(log_path):
    """Scan a single cli.log for the most-recently-authenticated email."""
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in reversed(fh.readlines()):
                m = _EMAIL_RE.search(line)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return None


def get_profile_email(profile_name):
    """Return the authenticated email for a profile, or None.

    Priority:
      1. Persistent metadata (.meta/<name>.json) — fastest.
      2. Profile's keyring_token.json (parses real Google id_token JWT).
      3. Top-level cli.log at profile_dir/.gemini/antigravity-cli/cli.log.
      4. cli.log inside .agy_accounts/<slot>/ sub-sandboxes (newest slot first).
    """
    # 1. Metadata (persisted after every session)
    meta = _load_meta(profile_name)
    if meta.get("email"):
        return meta["email"]

    profile_dir = PROFILES_DIR / profile_name

    # 2. Extract directly from profile's saved keyring token
    token_file = profile_dir / KEYRING_TOKEN_FILE
    if token_file.exists():
        try:
            email = KeyringManager.extract_email(token_file.read_text(encoding="utf-8"))
            if email:
                _save_meta(profile_name, email=email)
                return email
        except Exception:
            pass

    # 3. Top-level log (unified mode / some agy versions write here directly)
    email = _search_email_in_log(
        profile_dir / ".gemini" / "antigravity-cli" / "cli.log"
    )
    if email:
        return email

    # 3. Inside .agy_accounts/<slot>/ — search newest slot first
    agy_inner = profile_dir / ".agy_accounts"
    if agy_inner.exists():
        try:
            slots = sorted(
                (s for s in agy_inner.iterdir() if s.is_dir()),
                key=lambda s: s.stat().st_mtime,
                reverse=True,
            )
            for slot in slots:
                email = _search_email_in_log(
                    slot / ".gemini" / "antigravity-cli" / "cli.log"
                )
                if email:
                    return email
        except Exception:
            pass

    return None


def _scan_logs_for_email(profile_name):
    """Scan all log locations directly — bypasses the metadata cache.

    Used after a session to detect the CURRENT authenticated email, which
    may differ from a previously cached value (e.g. after switching accounts).
    Also checks the real HOME's cli.log because isolated mode now pre-swaps
    tokens into ~/.gemini/ before launch.
    """
    profile_dir = PROFILES_DIR / profile_name

    # Check real home first — agy writes here when it ignores the $HOME env var
    email = _search_email_in_log(
        REAL_HOME / ".gemini" / "antigravity-cli" / "cli.log"
    )
    if email:
        return email

    # Check profile-dir top-level log (agy versions that respect $HOME)
    email = _search_email_in_log(
        profile_dir / ".gemini" / "antigravity-cli" / "cli.log"
    )
    if email:
        return email

    # Check .agy_accounts/<slot>/ sub-sandboxes (newest slot first)
    agy_inner = profile_dir / ".agy_accounts"
    if agy_inner.exists():
        try:
            slots = sorted(
                (s for s in agy_inner.iterdir() if s.is_dir()),
                key=lambda s: s.stat().st_mtime,
                reverse=True,
            )
            for slot in slots:
                email = _search_email_in_log(
                    slot / ".gemini" / "antigravity-cli" / "cli.log"
                )
                if email:
                    return email
        except Exception:
            pass

    return None


def _persist_profile_email(profile_name):
    """After a session, scan logs fresh (never use cached metadata) and persist.

    Scanning fresh ensures we always capture the CURRENT account — important
    when the user switches to a different Google account in a new session.
    """
    email = _scan_logs_for_email(profile_name)
    updates = {"last_used": datetime.now().isoformat()}
    if email:
        updates["email"] = email
    _save_meta(profile_name, **updates)


# ── Token pre-seeding ──────────────────────────────────────────────────────────
# BUG FIX: In isolated mode (HOME=profile_dir) agy creates .agy_accounts/<slot>/
# and re-reads auth tokens from INSIDE that slot.  Fresh slots have no tokens,
# so agy demands re-authentication on every profile switch.  Pre-seeding copies
# the profile's saved canonical tokens into each existing slot before launch.

def _preseed_agy_slots(profile_dir):
    """Copy saved tokens into existing .agy_accounts/ slots before launching."""
    agy_inner = profile_dir / ".agy_accounts"
    if not agy_inner.exists():
        return
    try:
        for slot in agy_inner.iterdir():
            if not slot.is_dir():
                continue
            for rel in _TOKEN_RELPATHS:
                src = profile_dir / rel
                if src.exists():
                    dst = slot / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
    except Exception:
        pass



# ── Auth status helpers ────────────────────────────────────────────────────────

def _is_fresh_profile(profile_dir):
    """Return True if this profile has no saved auth tokens (first-time use)."""
    if (profile_dir / KEYRING_TOKEN_FILE).exists():
        return False
    return not any((profile_dir / rel).exists() for rel in _TOKEN_RELPATHS)


def _deep_clear_real_home_auth():
    """Aggressively clear ALL credential-related files from the real ~/.gemini/
    AND clear the system keyring before launching a fresh profile.

    This ensures agy cannot find any existing authentication state and is
    forced to trigger a clean OAuth flow.
    """
    # 1. Clear system keyring item
    KeyringManager.delete_token()

    # 2. Clear known file tokens
    for rel in _TOKEN_RELPATHS:
        p = REAL_HOME / rel
        if p.exists():
            try:
                shutil.copy2(p, p.with_suffix(".agyp-backup"))
                p.unlink()
            except Exception:
                pass

    # Broader sweep: any other .json files inside ~/.gemini/antigravity-cli/
    cli_dir = REAL_HOME / ".gemini" / "antigravity-cli"
    if cli_dir.exists():
        try:
            for f in cli_dir.iterdir():
                if f.suffix == ".json" and "agyp-backup" not in f.name:
                    try:
                        shutil.copy2(f, f.with_name(f.stem + ".agyp-backup"))
                        f.unlink()
                    except Exception:
                        pass
        except Exception:
            pass


def _get_private_browser_cmd():
    """Detect an installed browser and return a command that opens a private window.

    When agy does Google OAuth it calls the system browser via the BROWSER env
    var (or webbrowser module default).  If we set BROWSER to an incognito/private
    command, the OAuth page opens in a clean session with NO pre-logged-in Google
    account — forcing a genuine fresh sign-in where the user can pick any account.

    Returns a BROWSER-format string (with %s placeholder for the URL), or None
    if no supported browser is found.
    """
    candidates = [
        ("google-chrome",        "--incognito"),
        ("google-chrome-stable", "--incognito"),
        ("chromium-browser",     "--incognito"),
        ("chromium",             "--incognito"),
        ("brave-browser",        "--incognito"),
        ("brave",                "--incognito"),
        ("microsoft-edge",       "--inprivate"),
        ("firefox",              "--private-window"),
        ("firefox-esr",          "--private-window"),
    ]
    for browser, flag in candidates:
        if shutil.which(browser):
            return f"{browser} {flag} %s"
    return None


def _warn_browser_account_switch(profile_name, private_browser):
    """Print an unmissable warning before a profile's first-ever login."""
    border = C_YELLOW + "═" * 56 + C_RESET
    print(f"\n{border}")
    print(f"  {C_YELLOW}⚠  NEW PROFILE — FRESH GOOGLE SIGN-IN REQUIRED{C_RESET}")
    print(f"{border}")
    if private_browser:
        print(f"  {C_GREEN}✓ Opening a PRIVATE browser window automatically.{C_RESET}")
        print(f"  {C_GRAY}  (No cached Google account — you choose who to log in as.){C_RESET}\n")
    else:
        print(f"  A browser window will open for Google authentication.\n")
        print(f"  {C_WHITE}IMPORTANT — to use a DIFFERENT Google account:{C_RESET}")
        print(f"  {C_GREEN}1.{C_RESET} In the browser, click {C_WHITE}\"Use another account\"{C_RESET}")
        print(f"  {C_GREEN}2.{C_RESET} Sign in with a {C_GREEN}different{C_RESET} Google account\n")
    print(f"  {C_GRAY}No second Google account yet? Create one at accounts.google.com")
    print(f"  Signed in with the same account by accident?")
    print(f"  Run: agyp reset-auth {profile_name}{C_RESET}")
    print(f"{border}\n")


def _warn_duplicate_email(profile_name, email):
    """After a session, warn if this profile now shares an email with another."""
    if not email:
        return
    duplicates = [
        p for p in _list_profiles()
        if p != profile_name and get_profile_email(p) == email
    ]
    if not duplicates:
        return
    others = ", ".join(duplicates)
    print(f"\n{C_YELLOW}⚠  Same Google account in multiple profiles:{C_RESET}")
    print(f"   {C_WHITE}{profile_name}{C_RESET} and {C_WHITE}{others}{C_RESET} share {C_GRAY}[{email}]{C_RESET}")
    print(f"   {C_GRAY}Both profiles hit the same rate limits — defeating the purpose.{C_RESET}")
    print(f"   Fix: run  {C_WHITE}agyp reset-auth {profile_name}{C_RESET}  then re-launch")
    print(f"   and choose {C_GREEN}\"Use another account\"{C_RESET} in the browser.\n")


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


# ── Isolated-mode token persistence ───────────────────────────────────────────
# agy uses the $HOME env var for its AppDataDir (confirmed: when HOME=<profile_dir>,
# AppDataDir = <profile_dir>/.gemini/antigravity-cli/).  This means tokens written
# during a session land at:
#   <profile_dir>/.gemini/antigravity-cli/antigravity-oauth-token
# which is exactly where agyp expects to find them.
#
# HOWEVER, agy also creates .agy_accounts/<slot>/ sub-sandboxes and may write
# refreshed tokens there.  We run a broad post-session sweep to always find the
# newest token and persist it at the canonical location for the next launch.

def _collect_token_candidates(profile_dir):
    """Return all paths where agy may have written a token during the session."""
    candidates = []
    # Primary: directly inside the profile HOME
    for rel in _TOKEN_RELPATHS:
        candidates.append(profile_dir / rel)
    # Secondary: inside any .agy_accounts sub-sandbox
    agy_inner = profile_dir / ".agy_accounts"
    if agy_inner.exists():
        try:
            for slot in agy_inner.iterdir():
                if slot.is_dir():
                    for rel in _TOKEN_RELPATHS:
                        candidates.append(slot / rel)
        except Exception:
            pass
    return candidates


def _harvest_newest_token(profile_dir, session_start_ts):
    """After a session, find the newest written token and save to canonical paths.

    Scans all candidate locations (profile_dir and any .agy_accounts sub-dirs
    created inside it).  Only copies files modified AFTER session start so we
    never overwrite a good saved token with a stale one.
    """
    for rel in _TOKEN_RELPATHS:
        canonical  = profile_dir / rel
        best_src   = None
        best_mtime = session_start_ts  # only accept files newer than session start

        for candidate in _collect_token_candidates(profile_dir):
            if candidate.name != canonical.name:
                continue
            try:
                mtime = candidate.stat().st_mtime
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_src   = candidate
            except OSError:
                pass

        if best_src and best_src != canonical:
            canonical.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_src, canonical)


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
    """Launch agy with isolated HOME + token swap into the real ~/.gemini/.

    ROOT-CAUSE FIX (v1.4.1):
      agy may resolve its config dir via Path.home() / pwd.getpwuid() rather
      than the $HOME env var.  When it does, it always reads from the REAL
      system home — meaning the HOME override alone does not isolate tokens.
      Both profiles end up using the same ~/.gemini/antigravity-cli/ token,
      so the same Google account appears in every profile.

    Two-layer isolation strategy:
      1. Token swap (NEW): the profile's saved tokens are copied into the real
         ~/.gemini/ BEFORE launch, exactly as unified mode does.  This ensures
         agy starts authenticated as the correct account regardless of which
         path it uses to locate its config.
      2. HOME override (kept): HOME=profile_dir gives each profile its own
         workspace, history, and any files agy writes relative to $HOME.
      3. _preseed_agy_slots(): also copies tokens into existing .agy_accounts/
         sub-sandbox slots for agy versions that create inner sessions.

    After the session:
      • save_back_profile() — saves tokens from ~/.gemini/ (real home) back
        into the profile, capturing what agy updated via Path.home().
      • _harvest_newest_token() — also captures tokens written relative to
        the $HOME override (profile_dir) for good measure.
    """
    agy_bin = _resolve_agy()
    if not agy_bin:
        print(f"{C_RED}Error: 'agy' not found in PATH. Is Antigravity installed?{C_RESET}")
        sys.exit(1)

    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    _migrate_old_tokens(profile_dir)

    # Initialise metadata on first use of this profile
    if not _load_meta(profile).get("created_at"):
        _save_meta(profile, created_at=datetime.now().isoformat())

    fresh = _is_fresh_profile(profile_dir)
    p_email = get_profile_email(profile)
    email_tag = f"  [{C_CYAN}{p_email}{C_BLUE}]" if p_email else f"  [{C_YELLOW}login required{C_BLUE}]"

    print(f"\n{C_BLUE}Switching to profile '{C_WHITE}{profile}{C_BLUE}'{email_tag}  [{C_YELLOW}isolated{C_BLUE}]{C_RESET}")
    print(f"{C_GREEN}Launching isolated environment...{C_RESET}")

    private_browser = None
    if fresh:
        # Detect an incognito/private browser to force a clean Google sign-in.
        # Setting BROWSER in the env means agy's OAuth opens in a private window
        # where NO Google account is pre-logged-in — user chooses freely.
        private_browser = _get_private_browser_cmd()
        _warn_browser_account_switch(profile, private_browser)
        # Clear ALL real-home credentials so agy cannot reuse a cached account.
        _deep_clear_real_home_auth()
    else:
        print()

    session_start_ts = time.time()

    # ── Layer 0: Swap system keyring token (SecretService / Keychain) ───────────
    # agy reads/writes its primary OAuth token from the system keyring.
    # We must load this profile's token into the keyring, or clear it if fresh!
    keyring_file = profile_dir / KEYRING_TOKEN_FILE
    if keyring_file.exists():
        try:
            tok = keyring_file.read_text(encoding="utf-8").strip()
            if tok:
                KeyringManager.set_token(tok)
        except Exception:
            pass
    else:
        # Fresh or reset profile: CLEAR the keyring so agy is forced to prompt for login!
        KeyringManager.delete_token()

    # ── Layer 1: Swap profile tokens into the REAL home ────────────────────────
    swap_in_profile(profile_dir)
    set_last_active(profile)

    # ── Layer 2: Override $HOME for workspace isolation ────────────────────────
    env = os.environ.copy()
    env["HOME"] = str(profile_dir)
    for xdg in ["XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]:
        env.pop(xdg, None)

    # ── Layer 3: For fresh profiles, force private/incognito browser ───────────
    # This is the key fix: agy's OAuth opens in a clean browser session with
    # no pre-logged-in Google account, so the user MUST choose which account
    # to sign in with — no silent auto-selection of the "wrong" account.
    if private_browser:
        env["BROWSER"] = private_browser

    # ── Layer 4: Pre-seed any existing .agy_accounts/ slots ───────────────────
    _preseed_agy_slots(profile_dir)

    extra = " ".join(f"'{a}'" for a in args) if args else ""
    try:
        # subprocess.call (not os.execvpe) — this process survives to save tokens.
        _bash_run(env, f"'{agy_bin}' {extra}".strip())
    finally:
        # Capture token from system keyring and save to profile
        try:
            current_keyring_tok = KeyringManager.get_token()
            if current_keyring_tok:
                keyring_file.write_text(current_keyring_tok, encoding="utf-8")
                extracted = KeyringManager.extract_email(current_keyring_tok)
                if extracted:
                    _save_meta(profile, email=extracted)
        except Exception:
            pass

        # Save tokens from real home → profile (captures agy's Path.home() writes)
        save_back_profile(profile_dir)
        clear_last_active()
        # Also harvest tokens written relative to the $HOME override
        _harvest_newest_token(profile_dir, session_start_ts)
        # Persist email + timestamp; warn if same email found in another profile
        _persist_profile_email(profile)
        detected_email = get_profile_email(profile)
        _warn_duplicate_email(profile, detected_email)

    sys.exit(0)





def launch_unified(profile, args):
    """Launch agy with shared HOME but this profile's auth tokens."""
    agy_bin = _resolve_agy()
    if not agy_bin:
        print(f"{C_RED}Error: 'agy' not found in PATH. Is Antigravity installed?{C_RESET}")
        sys.exit(1)

    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    _migrate_old_tokens(profile_dir)

    # Initialise metadata on first use of this profile
    if not _load_meta(profile).get("created_at"):
        _save_meta(profile, created_at=datetime.now().isoformat())

    if inside_agy_session():
        print(f"\n{C_YELLOW}Warning: already inside an agy session. A conflict may occur.{C_RESET}")
        print(f"{C_GRAY}Consider using isolated mode instead.{C_RESET}\n")

    p_email = get_profile_email(profile)
    email_tag = f"  [{C_CYAN}{p_email}{C_BLUE}]" if p_email else f"  [{C_YELLOW}login required{C_BLUE}]"
    print(f"\n{C_BLUE}Switching to profile '{C_WHITE}{profile}{C_BLUE}'{email_tag}  [{C_YELLOW}unified{C_BLUE}]{C_RESET}")

    # Swap system keyring token
    keyring_file = profile_dir / KEYRING_TOKEN_FILE
    if keyring_file.exists():
        try:
            tok = keyring_file.read_text(encoding="utf-8").strip()
            if tok:
                KeyringManager.set_token(tok)
        except Exception:
            pass
    else:
        KeyringManager.delete_token()

    swap_in_profile(profile_dir)
    set_last_active(profile)
    print(f"{C_GREEN}Auth tokens swapped. Launching...{C_RESET}\n")

    extra = " ".join(f"'{a}'" for a in args) if args else ""
    try:
        _bash_run(os.environ.copy(), f"'{agy_bin}' {extra}".strip())
    finally:
        try:
            current_keyring_tok = KeyringManager.get_token()
            if current_keyring_tok:
                keyring_file.write_text(current_keyring_tok, encoding="utf-8")
                extracted = KeyringManager.extract_email(current_keyring_tok)
                if extracted:
                    _save_meta(profile, email=extracted)
        except Exception:
            pass

        save_back_profile(profile_dir)
        clear_last_active()
        _persist_profile_email(profile)

    sys.exit(0)


# ── Terminal I/O ───────────────────────────────────────────────────────────────

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
        ("\uf099 X (Twitter) ", "https://x.com/buildx_main"),
        ("\uf2c6 Telegram    ", "https://t.me/buildx_main"),
        ("\uf281 Reddit      ", "https://reddit.com/r/buildx_main"),
        ("\uf392 Discord     ", "https://discord.gg/ShZRBUZ7AX"),
        ("Go Back",             None),
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
        ("isolated", "Isolated", "[Each profile is fully separated]"),
        ("unified",  "Unified",  "[Shared history, token-only swap]"),
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

def interactive_menu(profiles, launch_mode="isolated"):
    """Full TUI for profile selection, creation, rename, delete."""
    mode = "main"
    current_idx = 0
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
                mode_label = (
                    f"\033[38;2;112;230;39mIsolated\033[0m"
                    if launch_mode == "isolated"
                    else f"{C_YELLOW}Unified{C_RESET}"
                )
                print(f" {C_WHITE}Select a profile to launch:{C_RESET}  {C_GRAY}mode:{C_RESET} {mode_label}\n")
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
                if i < len(profiles) and mode in ("main", "delete", "rename"):
                    email = get_profile_email(opt)
                    if email:
                        suffix = f"  {C_CYAN}[{email}]{C_RESET}"
                    else:
                        suffix = f"  {C_YELLOW}[no account — login on launch]{C_RESET}"
                if i == current_idx:
                    print(f"  {C_BLUE}\u276f {opt}{suffix}{C_RESET}")
                else:
                    if not opt.startswith('\033'):
                        print(f"    {C_WHITE}{opt}{C_RESET}{suffix}")
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
                        time.sleep(1.2)
                        continue
                    if (PROFILES_DIR / choice).exists():
                        time.sleep(1.2)
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
                        _rename_meta(p_old, new_name)          # FIX: keep metadata in sync
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
                        ans = input(
                            f" {C_RED}Permanently delete '{p_del}'? (y/N):{C_RESET} "
                        ).strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        ans = ""
                    sys.stdout.write("\033[?1049h\033[?25l")
                    sys.stdout.flush()
                    if ans == 'y':
                        target = PROFILES_DIR / p_del
                        if target.exists():
                            shutil.rmtree(target)
                        _delete_meta(p_del)                    # FIX: also remove metadata
                        profiles.remove(p_del)
                        current_idx = min(current_idx, max(0, len(profiles) - 1))
                    mode = "main"
                    current_idx = 0
                else:
                    mode = "main"
                    current_idx = 0

    return None


# ── Non-interactive subcommands ────────────────────────────────────────────────

def _print_help():
    draw_header()
    print(f"{C_WHITE}Usage:{C_RESET}\n")
    print(f"  {C_WHITE}agyp{C_RESET}                           Launch interactive profile manager")
    print(f"  {C_WHITE}agyp <profile>{C_RESET}                 Launch a named profile (isolated mode)")
    print(f"  {C_WHITE}agyp <profile> [args...]{C_RESET}       Pass extra args to agy")
    print(f"  {C_WHITE}agyp list{C_RESET}                      List all saved profiles")
    print(f"  {C_WHITE}agyp info <profile>{C_RESET}            Show detailed profile info")
    print(f"  {C_WHITE}agyp rename <old> <new>{C_RESET}        Rename a profile")
    print(f"  {C_WHITE}agyp delete <profile>{C_RESET}          Delete a profile")
    print(f"  {C_WHITE}agyp duplicate <src> <dst>{C_RESET}     Clone a profile (auth tokens stripped)")
    print(f"  {C_WHITE}agyp reset-auth <profile>{C_RESET}      {C_YELLOW}Clear saved tokens → force fresh login{C_RESET}")
    print(f"  {C_WHITE}agyp --version{C_RESET}                 Show version")
    print(f"  {C_WHITE}agyp --help{C_RESET}                    Show this help")
    print(f"\n{C_GRAY}Profiles stored in: ~/agyp-profiles/{C_RESET}\n")



def _cmd_list():
    print()
    profiles = _list_profiles()
    if not profiles:
        print(f"  {C_GRAY}No profiles yet. Run 'agyp' to create one.{C_RESET}\n")
        return
    print(f"  {C_WHITE}Saved profiles:{C_RESET}\n")
    for p in profiles:
        email     = get_profile_email(p)
        meta      = _load_meta(p)
        last_used = meta.get("last_used", "")
        created   = meta.get("created_at", "")

        if email:
            email_part = f"  {C_CYAN}[{email}]{C_RESET}"
        else:
            email_part = f"  {C_YELLOW}[no account — login on launch]{C_RESET}"
        date_part  = (
            f"  {C_GRAY}last: {last_used[:10]}{C_RESET}" if last_used else
            (f"  {C_GRAY}created: {created[:10]}{C_RESET}" if created else "")
        )
        print(f"  {C_BLUE}·{C_RESET} {C_WHITE}{p}{C_RESET}{email_part}{date_part}")
    print()


def _cmd_info(profile_name):
    """Print detailed information about a single profile."""
    name = sanitize_name(profile_name)
    if name is None:
        print(f"{C_RED}Error: Invalid profile name '{profile_name}'.{C_RESET}")
        sys.exit(1)
    target = PROFILES_DIR / name
    if not target.exists():
        print(f"{C_RED}Error: Profile '{name}' does not exist.{C_RESET}")
        sys.exit(1)

    meta      = _load_meta(name)
    email     = get_profile_email(name) or "—"
    created   = meta.get("created_at",  "—")
    last_used = meta.get("last_used",   "—")

    # Disk usage
    try:
        total = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
        size_str = (
            f"{total / 1024 / 1024:.1f} MB"
            if total >= 1024 * 1024
            else f"{total / 1024:.1f} KB"
        )
    except Exception:
        size_str = "—"

    # Auth token status
    has_token = (target / KEYRING_TOKEN_FILE).exists() or any((target / rel).exists() for rel in _TOKEN_RELPATHS)
    token_str = (
        f"{C_GREEN}saved{C_RESET}"
        if has_token
        else f"{C_YELLOW}not saved — login required on next launch{C_RESET}"
    )

    W = 14
    print(f"\n  {C_WHITE}Profile: {name}{C_RESET}")
    print(f"  {'Email:':<{W}} {email}")
    print(f"  {'Auth token:':<{W}} {token_str}")
    print(f"  {'Created:':<{W}} {created[:19] if created != '—' else created}")
    print(f"  {'Last used:':<{W}} {last_used[:19] if last_used != '—' else last_used}")
    print(f"  {'Disk usage:':<{W}} {size_str}")
    print(f"  {'Path:':<{W}} {target}\n")


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
    _rename_meta(old, new)
    print(f"{C_GREEN}✓ Renamed '{old}' → '{new}'{C_RESET}")


def _cmd_delete(profile_name):
    """Delete a profile after an interactive confirmation prompt."""
    name = sanitize_name(profile_name)
    if name is None:
        print(f"{C_RED}Error: Invalid profile name '{profile_name}'.{C_RESET}")
        sys.exit(1)
    target = PROFILES_DIR / name
    if not target.exists():
        print(f"{C_RED}Error: Profile '{name}' does not exist.{C_RESET}")
        sys.exit(1)
    try:
        ans = input(
            f"{C_RED}Permanently delete profile '{name}'?{C_RESET} (y/N): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{C_GRAY}Cancelled.{C_RESET}")
        return
    if ans == 'y':
        shutil.rmtree(target)
        _delete_meta(name)
        print(f"{C_GREEN}✓ Deleted profile '{name}'.{C_RESET}")
    else:
        print(f"{C_GRAY}Cancelled.{C_RESET}")


def _cmd_duplicate(src_name, dst_name):
    """Clone a profile's workspace — auth tokens are NOT copied.

    The clone starts with no saved credentials so that launching it triggers
    a fresh Google sign-in.  This is intentional: if tokens were inherited,
    both profiles would silently share the same Google account.
    """
    src = sanitize_name(src_name)
    dst = sanitize_name(dst_name)
    if src is None:
        print(f"{C_RED}Error: Invalid name '{src_name}'.{C_RESET}"); sys.exit(1)
    if dst is None:
        print(f"{C_RED}Error: Invalid name '{dst_name}'.{C_RESET}"); sys.exit(1)
    src_dir = PROFILES_DIR / src
    dst_dir = PROFILES_DIR / dst
    if not src_dir.exists():
        print(f"{C_RED}Error: Profile '{src}' does not exist.{C_RESET}"); sys.exit(1)
    if dst_dir.exists():
        print(f"{C_RED}Error: Profile '{dst}' already exists.{C_RESET}"); sys.exit(1)

    print(f"Duplicating '{src}' → '{dst}' (without auth tokens)...")
    try:
        shutil.copytree(src_dir, dst_dir)
    except Exception as e:
        print(f"{C_RED}Error: {e}{C_RESET}"); sys.exit(1)

    # Strip auth tokens from the clone — force a fresh login on first launch
    stripped = 0
    keyring_clone = dst_dir / KEYRING_TOKEN_FILE
    if keyring_clone.exists():
        keyring_clone.unlink()
        stripped += 1
    for rel in _TOKEN_RELPATHS:
        token_copy = dst_dir / rel
        if token_copy.exists():
            token_copy.unlink()
            stripped += 1
    # Also clear tokens inside any .agy_accounts sub-sandboxes
    agy_inner = dst_dir / ".agy_accounts"
    if agy_inner.exists():
        try:
            for slot in agy_inner.iterdir():
                if slot.is_dir():
                    for rel in _TOKEN_RELPATHS:
                        t = slot / rel
                        if t.exists():
                            t.unlink()
                            stripped += 1
        except Exception:
            pass

    # Fresh metadata — no email (different account expected), reset timestamps
    _save_meta(dst, created_at=datetime.now().isoformat())
    print(f"{C_GREEN}✓ Duplicated '{src}' → '{dst}'.{C_RESET}")
    print(
        f"{C_YELLOW}  Auth tokens removed from clone ({stripped} file(s) cleared).{C_RESET}\n"
        f"{C_GRAY}  Launch '{dst}' and sign in with a DIFFERENT Google account.{C_RESET}"
    )



def _cmd_reset_auth(profile_name):
    """Clear a profile's saved auth tokens — forces fresh login on next launch.

    Use this when a profile ended up with the wrong Google account.
    After resetting, launch the profile and choose 'Use another account'
    in the browser to authenticate with a different Google account.
    """
    name = sanitize_name(profile_name)
    if name is None:
        print(f"{C_RED}Error: Invalid profile name '{profile_name}'.{C_RESET}")
        sys.exit(1)
    target = PROFILES_DIR / name
    if not target.exists():
        print(f"{C_RED}Error: Profile '{name}' does not exist.{C_RESET}")
        sys.exit(1)

    old_email = get_profile_email(name) or "none"
    cleared = 0

    # Remove keyring token file
    kf = target / KEYRING_TOKEN_FILE
    if kf.exists():
        kf.unlink()
        cleared += 1

    # Clear system keyring item so next launch is guaranteed clean!
    KeyringManager.delete_token()

    # Remove known token files from the profile dir
    for rel in _TOKEN_RELPATHS:
        p = target / rel
        if p.exists():
            p.unlink()
            cleared += 1

    # Also sweep .agy_accounts sub-sandboxes
    agy_inner = target / ".agy_accounts"
    if agy_inner.exists():
        try:
            for slot in agy_inner.iterdir():
                if slot.is_dir():
                    for rel in _TOKEN_RELPATHS:
                        p = slot / rel
                        if p.exists():
                            p.unlink()
                            cleared += 1
        except Exception:
            pass

    # Remove the cached email from metadata so TUI shows no stale account
    meta = _load_meta(name)
    meta.pop("email", None)
    _save_meta(name, **{k: v for k, v in meta.items()})

    print(f"{C_GREEN}✓ Auth reset for profile '{name}'.{C_RESET}")
    print(f"  {C_GRAY}Removed {cleared} token file(s).  Previous account: {old_email}{C_RESET}")
    print(f"\n  Next launch will prompt for a fresh Google sign-in.")
    print(f"  {C_WHITE}In the browser → sign in with your DIFFERENT Google account.{C_RESET}\n")


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

    if argv and argv[0] == "info":
        if len(argv) != 2:
            print(f"{C_RED}Usage: agyp info <profile-name>{C_RESET}")
            sys.exit(1)
        _cmd_info(argv[1])
        return

    if argv and argv[0] == "rename":
        if len(argv) != 3:
            print(f"{C_RED}Usage: agyp rename <old-name> <new-name>{C_RESET}")
            sys.exit(1)
        _cmd_rename(argv[1], argv[2])
        return

    if argv and argv[0] == "delete":
        if len(argv) != 2:
            print(f"{C_RED}Usage: agyp delete <profile-name>{C_RESET}")
            sys.exit(1)
        _cmd_delete(argv[1])
        return

    if argv and argv[0] == "duplicate":
        if len(argv) != 3:
            print(f"{C_RED}Usage: agyp duplicate <src-name> <dst-name>{C_RESET}")
            sys.exit(1)
        _cmd_duplicate(argv[1], argv[2])
        return

    if argv and argv[0] == "reset-auth":
        if len(argv) != 2:
            print(f"{C_RED}Usage: agyp reset-auth <profile-name>{C_RESET}")
            sys.exit(1)
        _cmd_reset_auth(argv[1])
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

    exiting = False
    try:
        mode = ask_mode()
        if mode == "EXIT":
            exiting = True
            return

        profiles = _list_profiles()

        selected_profile = interactive_menu(profiles, launch_mode=mode)
        if selected_profile == "EXIT" or not selected_profile:
            exiting = True
            return

    finally:
        # Always restore terminal FIRST
        sys.stdout.write("\033[?1049l\033[?25h")
        sys.stdout.flush()
        if exiting:
            _goodbye()
            os._exit(0)

    # Launch the selected profile
    if mode == "isolated":
        launch_isolated(selected_profile, [])
    else:
        launch_unified(selected_profile, [])


if __name__ == "__main__":
    main()
