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
import base64
import select
import shutil
import atexit
import termios
import subprocess
import webbrowser
import signal
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
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

VERSION = "1.6.1"

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

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def _visible_len(s):
    """Return visible character length of string without ANSI escape sequences."""
    return len(_ANSI_RE.sub("", s))

def pad_ansi(s, width):
    """Pad a string containing ANSI escape sequences to target visible width."""
    vis = _visible_len(s)
    return s + " " * max(0, width - vis)

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

# Email regex — matches foo@bar.com across various log formats (key=val, JSON, plain, OAuth lines)
_EMAIL_RE = re.compile(
    r'(?:email[=:\s"\']+|authenticated successfully as\s+)([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
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
            # 1. Native D-Bus SecretService (fastest, standard on desktop Linux)
            try:
                import dbus
                bus = dbus.SessionBus()
                service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
                iface = dbus.Interface(service, "org.freedesktop.Secret.Service")
                res = iface.SearchItems({"service": cls.SERVICE, "username": cls.USERNAME})
                if res and res[0]:
                    output, session_path = iface.OpenSession("plain", dbus.String("", variant_level=1))
                    item_obj = bus.get_object("org.freedesktop.secrets", res[0][0])
                    secret_struct = item_obj.GetSecret(session_path, dbus_interface="org.freedesktop.Secret.Item")
                    return bytes(secret_struct[2]).decode("utf-8", errors="ignore")
            except Exception:
                pass

            # 2. CLI secret-tool fallback (libsecret)
            if shutil.which("secret-tool"):
                try:
                    out = subprocess.check_output(
                        ["secret-tool", "lookup", "service", cls.SERVICE, "username", cls.USERNAME],
                        stderr=subprocess.DEVNULL, timeout=3
                    )
                    tok = out.decode("utf-8").strip()
                    if tok:
                        return tok
                except Exception:
                    pass

            # 3. python-keyring module fallback
            try:
                import keyring
                tok = keyring.get_password(cls.SERVICE, cls.USERNAME)
                if tok:
                    return tok
            except Exception:
                pass

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
            # 1. Native D-Bus SecretService
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
                pass

            # 2. CLI secret-tool fallback (libsecret)
            if shutil.which("secret-tool"):
                try:
                    subprocess.run(
                        ["secret-tool", "store", f"--label=Password for '{cls.USERNAME}' on '{cls.SERVICE}'", "service", cls.SERVICE, "username", cls.USERNAME],
                        input=token_str.encode("utf-8"),
                        check=True,
                        stderr=subprocess.DEVNULL,
                        timeout=3
                    )
                    return True
                except Exception:
                    pass

            # 3. python-keyring fallback
            try:
                import keyring
                keyring.set_password(cls.SERVICE, cls.USERNAME, token_str)
                return True
            except Exception:
                pass

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
            # 1. Native D-Bus SecretService
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
                pass

            # 2. CLI secret-tool fallback
            if shutil.which("secret-tool"):
                try:
                    subprocess.run(
                        ["secret-tool", "clear", "service", cls.SERVICE, "username", cls.USERNAME],
                        check=True,
                        stderr=subprocess.DEVNULL,
                        timeout=3
                    )
                    return True
                except Exception:
                    pass

            # 3. python-keyring fallback
            try:
                import keyring
                keyring.delete_password(cls.SERVICE, cls.USERNAME)
                return True
            except Exception:
                pass

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
                        return email.strip().lower()
        except Exception:
            pass
        return None

    @classmethod
    def extract_refresh_token(cls, token_str):
        """Extract refresh_token from the stored JSON token."""
        if not token_str:
            return None
        try:
            data = json.loads(token_str)
            return data.get("token", {}).get("refresh_token")
        except Exception:
            return None


def safe_merge_token(new_tok_str, existing_tok_str=None, bound_email=None):
    """Safely merges new OAuth token with existing token:
    1. If bound_email is provided, strictly rejects tokens belonging to different Google accounts.
    2. Preserves refresh_token from existing token if new token lacks it (preventing 4-5 day expiry).
    3. Preserves id_token from existing token if new token lacks it.
    4. Preserves auth_method from existing token if new token lacks it.
    Returns: (merged_tok_str, email_to_record, status_msg)
    """
    if not new_tok_str:
        return None, None, "empty_token"

    try:
        new_data = json.loads(new_tok_str)
    except Exception:
        return None, None, "invalid_json"

    if not isinstance(new_data, dict):
        return None, None, "not_a_dict"

    new_email = KeyringManager.extract_email(new_tok_str)

    # Enforce account ownership: A profile bound to an account MUST NEVER accept another account's token!
    if bound_email:
        bound_norm = bound_email.strip().lower()
        if new_email and new_email.strip().lower() != bound_norm:
            return None, None, f"mismatch: token is for {new_email}, profile is bound to {bound_email}"

    existing_data = {}
    if existing_tok_str:
        try:
            existing_data = json.loads(existing_tok_str)
            if not isinstance(existing_data, dict):
                existing_data = {}
        except Exception:
            existing_data = {}

    # Merge token object (access_token, refresh_token, expiry, token_type)
    new_tok_obj = new_data.get("token")
    if not isinstance(new_tok_obj, dict):
        new_tok_obj = {}

    existing_tok_obj = existing_data.get("token")
    if not isinstance(existing_tok_obj, dict):
        existing_tok_obj = {}

    # Critical: Google OAuth refresh calls often do NOT return a new refresh_token.
    # We MUST preserve the existing refresh_token so the account never expires!
    if not new_tok_obj.get("refresh_token") and existing_tok_obj.get("refresh_token"):
        new_tok_obj["refresh_token"] = existing_tok_obj["refresh_token"]

    new_data["token"] = new_tok_obj

    # Preserve id_token (which contains the email JWT) if new token doesn't include one
    if not new_data.get("id_token") and existing_data.get("id_token"):
        new_data["id_token"] = existing_data["id_token"]

    # Preserve auth_method
    if not new_data.get("auth_method") and existing_data.get("auth_method"):
        new_data["auth_method"] = existing_data["auth_method"]

    final_email = new_email or bound_email
    if not final_email:
        final_email = KeyringManager.extract_email(json.dumps(new_data))

    return json.dumps(new_data), final_email, "ok"


def _backup_profile_token(profile_dir):
    """Keep a redundant backup of keyring_token.json so it can never be lost."""
    src = profile_dir / KEYRING_TOKEN_FILE
    if src.exists() and src.stat().st_size > 10:
        try:
            shutil.copy2(src, profile_dir / (KEYRING_TOKEN_FILE + ".bak"))
        except Exception:
            pass


def _restore_token_from_backup(profile_dir):
    """Restore keyring_token.json from backup if missing or empty."""
    target = profile_dir / KEYRING_TOKEN_FILE
    bak = profile_dir / (KEYRING_TOKEN_FILE + ".bak")
    if (not target.exists() or target.stat().st_size < 10) and bak.exists() and bak.stat().st_size > 10:
        try:
            shutil.copy2(bak, target)
            return True
        except Exception:
            pass
    return False


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

_ORIG_TERMIOS = None
_IN_RAW_SESSION = False

try:
    if sys.stdin.isatty():
        _ORIG_TERMIOS = termios.tcgetattr(sys.stdin.fileno())
except Exception:
    pass


def _reset_terminal():
    """Restore terminal to a sane state — called automatically on exit."""
    try:
        if sys.stdin.isatty() and _ORIG_TERMIOS is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _ORIG_TERMIOS)
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
    """Persist key/value pairs into a profile's metadata file. Passing a key as None removes it."""
    meta = _load_meta(profile_name)
    for k, v in kwargs.items():
        if v is None:
            meta.pop(k, None)
        else:
            meta[k] = v
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

def _parse_log_creation_time(log_path):
    """Extract creation timestamp from cli-YYYYMMDD_HHMMSS.log filename."""
    m = re.match(r"^cli-(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.log$", log_path.name)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6))
            )
            return dt.timestamp()
        except Exception:
            pass
    return None


def _search_email_in_log(log_path, session_start_ts=None):
    """Scan a single cli.log for the most-recently-authenticated email.
    If session_start_ts is provided, strictly ignores older logs and older auth events.
    """
    if not log_path.exists():
        return None

    if session_start_ts:
        # Check filename creation timestamp first
        log_created = _parse_log_creation_time(log_path)
        if log_created is not None and log_created < session_start_ts - 5:
            # File was created by an older session before this one started!
            return None
        try:
            if log_path.stat().st_mtime < session_start_ts - 5:
                return None
        except Exception:
            return None

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in reversed(fh.readlines()):
                m = _EMAIL_RE.search(line)
                if m:
                    if session_start_ts:
                        # Glog format: I1011 12:28:44.650999 ...
                        tm = re.match(r"^[IWEF](\d{2})(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", line)
                        if tm:
                            try:
                                now_dt = datetime.fromtimestamp(session_start_ts)
                                line_dt = datetime(
                                    now_dt.year,
                                    int(tm.group(1)), int(tm.group(2)),
                                    int(tm.group(3)), int(tm.group(4)), int(tm.group(5))
                                )
                                if line_dt.timestamp() < session_start_ts - 5:
                                    continue
                            except Exception:
                                pass
                    return m.group(1).strip()
    except Exception:
        pass
    return None


def get_profile_email(profile_name):
    """Return the authenticated email for a profile, or None.

    Priority:
      1. Profile's saved keyring_token.json (parses real Google id_token JWT - cryptographic ground truth).
      2. Backup token file (keyring_token.json.bak).
      3. Persistent metadata (.meta/<name>.json) ONLY IF token file or backup exists.
      4. Profile's local cli.log ONLY IF token file exists.
    """
    profile_dir = PROFILES_DIR / profile_name
    token_file = profile_dir / KEYRING_TOKEN_FILE
    bak_file = profile_dir / (KEYRING_TOKEN_FILE + ".bak")

    has_token_file = (
        (token_file.exists() and token_file.stat().st_size > 10)
        or (bak_file.exists() and bak_file.stat().st_size > 10)
        or any((profile_dir / rel).exists() for rel in _TOKEN_RELPATHS)
    )

    # A profile with no saved token files is not authenticated.
    if not has_token_file:
        return None

    # 1. Direct from profile's saved keyring token (cryptographic ground truth)
    if token_file.exists() and token_file.stat().st_size > 10:
        try:
            email = KeyringManager.extract_email(token_file.read_text(encoding="utf-8"))
            if email:
                _save_meta(profile_name, email=email)
                return email
        except Exception:
            pass

    # 2. Check backup token file
    if bak_file.exists() and bak_file.stat().st_size > 10:
        try:
            email = KeyringManager.extract_email(bak_file.read_text(encoding="utf-8"))
            if email:
                _save_meta(profile_name, email=email)
                return email
        except Exception:
            pass

    # 3. Persistent metadata
    meta = _load_meta(profile_name)
    if meta.get("email"):
        return meta["email"]

    # 4. Profile's own local cli.log
    email = _search_email_in_log(
        profile_dir / ".gemini" / "antigravity-cli" / "cli.log"
    )
    if email:
        _save_meta(profile_name, email=email)
        return email

    return None


def _scan_logs_for_email(profile_name, session_start_ts=None):
    """Scan log locations directly, strictly scoped to this profile's session.
    NEVER reads older logs from other profiles or unrelated sessions.
    """
    profile_dir = PROFILES_DIR / profile_name

    # Check profile-dir top-level log (isolated mode)
    email = _search_email_in_log(
        profile_dir / ".gemini" / "antigravity-cli" / "cli.log",
        session_start_ts=session_start_ts,
    )
    if email:
        return email

    # Check profile-dir log sub-folder (isolated mode)
    prof_log_dir = profile_dir / ".gemini" / "antigravity-cli" / "log"
    if prof_log_dir.exists():
        try:
            logs = sorted(
                (f for f in prof_log_dir.iterdir() if f.name.endswith(".log")),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            for log_file in logs:
                email = _search_email_in_log(log_file, session_start_ts=session_start_ts)
                if email:
                    return email
        except Exception:
            pass

    # Only in unified mode (where logs write to REAL_HOME), check REAL_HOME logs
    # BUT ONLY files created during or after session_start_ts!
    if session_start_ts:
        log_dir = REAL_HOME / ".gemini" / "antigravity-cli" / "log"
        if log_dir.exists():
            try:
                logs = sorted(
                    (f for f in log_dir.iterdir() if f.name.endswith(".log")),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                for log_file in logs[:10]:
                    email = _search_email_in_log(log_file, session_start_ts=session_start_ts)
                    if email:
                        return email
            except Exception:
                pass

    return None


def _persist_profile_email(profile_name, session_start_ts=None):
    """After a session, persist profile email and last_used timestamp.
    Guarantees: An existing bound email is NEVER overwritten by an unverified log scan.
    """
    profile_dir = PROFILES_DIR / profile_name
    updates = {"last_used": datetime.now().isoformat()}

    existing_email = get_profile_email(profile_name)
    if existing_email:
        updates["email"] = existing_email
    elif session_start_ts:
        has_token = (
            (profile_dir / KEYRING_TOKEN_FILE).exists()
            or (profile_dir / (KEYRING_TOKEN_FILE + ".bak")).exists()
            or any((profile_dir / rel).exists() for rel in _TOKEN_RELPATHS)
        )
        if has_token:
            email = _scan_logs_for_email(profile_name, session_start_ts)
            if email:
                updates["email"] = email

    _save_meta(profile_name, **updates)


# ── Quota & Usage Manager ──────────────────────────────────────────────────────
# Antigravity CLI accounts query the internal Google Cloud models endpoint to
# track usage. Gemini models track a rolling 5-hour window quota (shared across
# flash and pro models). Claude models track their separate quota allocation.
# When an access token expires (1h lifetime), this module automatically refreshes
# it via Google OAuth2 token endpoint using the profile's saved refresh token.

_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
_MODELS_API_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
_QUOTA_CACHE_TTL = 120  # seconds

_MEM_QUOTA_CACHE = {}  # In-memory fast cache: {profile_name: quota_dict}
_AGY_OAUTH_CREDS = None


def _get_agy_oauth_creds():
    """Extract official Google OAuth client credentials dynamically from local agy binary."""
    global _AGY_OAUTH_CREDS
    if _AGY_OAUTH_CREDS:
        return _AGY_OAUTH_CREDS

    candidates = [
        shutil.which("agy"),
        str(REAL_HOME / ".local/bin/agy"),
        "/usr/local/bin/agy",
        "/usr/bin/agy",
    ]
    cid, sec = None, None
    for p in candidates:
        if p and Path(p).is_file():
            try:
                with open(p, "rb") as f:
                    data = f.read()
                m_ids = re.findall(rb"(1071006060591-[a-z0-9]+\.apps\.googleusercontent\.com)", data)
                if not m_ids:
                    m_ids = re.findall(rb"([0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com)", data)
                if m_ids:
                    cid = m_ids[0].decode("utf-8")
                m_sec = re.findall(rb"(GOCSPX-[A-Za-z0-9_-]{28})", data)
                if m_sec:
                    sec = m_sec[0].decode("utf-8")
                if cid and sec:
                    break
            except Exception:
                pass

    _AGY_OAUTH_CREDS = (cid, sec)
    return _AGY_OAUTH_CREDS


def format_reset_delta(reset_str):
    """Format an ISO 8601 reset timestamp into a concise relative duration (e.g. '14m', '4h 50m', '3d 22h')."""
    if not reset_str:
        return ""
    try:
        r_str = reset_str[:-1] + "+00:00" if reset_str.endswith("Z") else reset_str
        reset_dt = datetime.fromisoformat(r_str)
        diff = reset_dt - datetime.now(timezone.utc)
        total_seconds = int(diff.total_seconds())
        if total_seconds <= 0:
            return ""
        mins = total_seconds // 60
        hours = mins // 60
        days = hours // 24
        if days > 0:
            rem_h = hours % 24
            return f"{days}d {rem_h}h" if rem_h else f"{days}d"
        elif hours > 0:
            rem_m = mins % 60
            return f"{hours}h {rem_m}m" if rem_m else f"{hours}h"
        else:
            return f"{mins}m"
    except Exception:
        return ""


def _parse_model_quota(models_dict, prefix="gemini"):
    """Extract quota percentage and reset time for a model family (gemini or claude)."""
    if prefix == "gemini":
        preferred = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.1-pro-high", "gemini-3-flash"]
    else:
        preferred = ["claude-sonnet-4-6", "claude-opus-4-6-thinking"]

    target_info = None
    for k in preferred:
        if k in models_dict and isinstance(models_dict[k], dict) and "quotaInfo" in models_dict[k]:
            target_info = models_dict[k]["quotaInfo"]
            break

    if not target_info:
        for k, v in models_dict.items():
            if k.startswith(prefix) and isinstance(v, dict) and "quotaInfo" in v:
                target_info = v["quotaInfo"]
                break

    if not target_info:
        return None

    rem = target_info.get("remainingFraction")
    reset_time = target_info.get("resetTime")

    # If reset_time is in the past, quota has already refreshed to 100%
    if reset_time:
        try:
            r_str = reset_time[:-1] + "+00:00" if reset_time.endswith("Z") else reset_time
            r_dt = datetime.fromisoformat(r_str)
            if (r_dt - datetime.now(timezone.utc)).total_seconds() <= 0:
                return {"pct": 100, "reset_time": None}
        except Exception:
            pass

    if rem is not None:
        pct = max(0, min(100, int(round(rem * 100))))
    elif reset_time:
        pct = 0
    else:
        pct = 100

    return {"pct": pct, "reset_time": reset_time}


def _refresh_profile_token(profile_name, refresh_token):
    """Refresh an expired access token using Google OAuth2 endpoint, persisting update to disk."""
    if not refresh_token:
        return None
    cid, sec = _get_agy_oauth_creds()
    if not cid or not sec:
        return None
    try:
        payload = urllib.parse.urlencode({
            "client_id": cid,
            "client_secret": sec,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")
        req = urllib.request.Request(
            _OAUTH_TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            new_atk = data.get("access_token")
            if new_atk:
                p_dir = PROFILES_DIR / profile_name
                tok_file = p_dir / KEYRING_TOKEN_FILE
                if tok_file.exists():
                    try:
                        t_data = json.loads(tok_file.read_text(encoding="utf-8"))
                        if "token" in t_data and isinstance(t_data["token"], dict):
                            t_data["token"]["access_token"] = new_atk
                            if "expires_in" in data:
                                t_data["token"]["expiry"] = datetime.now(timezone.utc).isoformat()
                            tok_file.write_text(json.dumps(t_data, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                return new_atk
    except Exception:
        pass
    return None


def fetch_profile_quota(profile_name, force=False):
    """Fetch live or cached quota usage for a profile."""
    # 1. Fast in-memory cache check
    cached = _MEM_QUOTA_CACHE.get(profile_name)
    if not force and cached and (time.time() - cached.get("fetched_at", 0) < _QUOTA_CACHE_TTL):
        return cached

    # 2. Check persistent metadata
    if not force:
        meta = _load_meta(profile_name)
        m_quota = meta.get("quota")
        if m_quota and (time.time() - m_quota.get("fetched_at", 0) < _QUOTA_CACHE_TTL):
            _MEM_QUOTA_CACHE[profile_name] = m_quota
            return m_quota

    # 3. Read profile token
    p_dir = PROFILES_DIR / profile_name
    tok_file = p_dir / KEYRING_TOKEN_FILE
    if not tok_file.exists() or tok_file.stat().st_size <= 10:
        return None

    try:
        data = json.loads(tok_file.read_text(encoding="utf-8"))
        tok = data.get("token", {})
        access_token = tok.get("access_token")
        refresh_token = tok.get("refresh_token")
    except Exception:
        return None

    if not access_token:
        return None

    def _query_api(atk):
        req = urllib.request.Request(
            _MODELS_API_URL,
            headers={
                "Authorization": f"Bearer {atk}",
                "Content-Type": "application/json",
                "User-Agent": "antigravity-cli",
            },
            data=b"{}",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return json.loads(resp.read().decode("utf-8"))

    models_data = None
    try:
        models_data = _query_api(access_token)
    except urllib.error.HTTPError as e:
        if e.code == 401 and refresh_token:
            new_atk = _refresh_profile_token(profile_name, refresh_token)
            if new_atk:
                try:
                    models_data = _query_api(new_atk)
                except Exception:
                    pass
    except Exception:
        pass

    if not models_data or "models" not in models_data:
        meta = _load_meta(profile_name)
        return meta.get("quota")

    models = models_data.get("models", {})
    gemini_q = _parse_model_quota(models, "gemini")
    claude_q = _parse_model_quota(models, "claude")

    quota_dict = {
        "gemini": gemini_q,
        "claude": claude_q,
        "fetched_at": time.time(),
    }

    _MEM_QUOTA_CACHE[profile_name] = quota_dict
    _save_meta(profile_name, quota=quota_dict)
    return quota_dict


def batch_fetch_quotas(profiles, force=False, max_workers=10):
    """Fetch quotas in parallel for profiles that need refresh."""
    to_fetch = []
    now = time.time()
    for p in profiles:
        tok_file = PROFILES_DIR / p / KEYRING_TOKEN_FILE
        if not tok_file.exists() or tok_file.stat().st_size <= 10:
            continue
        cached = _MEM_QUOTA_CACHE.get(p)
        if not force and cached and (now - cached.get("fetched_at", 0) < _QUOTA_CACHE_TTL):
            continue
        if not force:
            meta = _load_meta(p)
            m_quota = meta.get("quota")
            if m_quota and (now - m_quota.get("fetched_at", 0) < _QUOTA_CACHE_TTL):
                _MEM_QUOTA_CACHE[p] = m_quota
                continue
        to_fetch.append(p)

    if not to_fetch:
        return

    workers = min(len(to_fetch), max_workers)
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda name: fetch_profile_quota(name, force=force), to_fetch))
    except Exception:
        pass


def _color_quota_pct(pct):
    if pct is None:
        return f"{C_GRAY}—{C_RESET}"
    if pct >= 75:
        c = C_GREEN
    elif pct >= 25:
        c = C_YELLOW
    else:
        c = C_RED
    return f"{c}{pct:>3}%{C_RESET}"


def format_quota_inline(quota_dict):
    """Format Gemini (5h limit) and Claude quotas into a single-row colored string."""
    if not quota_dict:
        return ""
    g_data = quota_dict.get("gemini")
    c_data = quota_dict.get("claude")
    if not g_data and not c_data:
        return ""

    parts = []
    if g_data:
        g_pct = g_data.get("pct")
        g_rst = format_reset_delta(g_data.get("reset_time"))
        g_rst_str = f" {C_GRAY}({g_rst}){C_RESET}" if (g_pct is not None and g_pct < 100 and g_rst) else ""
        parts.append(f"{C_WHITE}Gemini:{C_RESET} {_color_quota_pct(g_pct)}{g_rst_str}")

    if c_data:
        c_pct = c_data.get("pct")
        c_rst = format_reset_delta(c_data.get("reset_time"))
        c_rst_str = f" {C_GRAY}({c_rst}){C_RESET}" if (c_pct is not None and c_pct < 100 and c_rst) else ""
        parts.append(f"{C_WHITE}Claude:{C_RESET} {_color_quota_pct(c_pct)}{c_rst_str}")

    sep = f" {C_GRAY}│{C_RESET} "
    return sep.join(parts)


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
    """Return True if this profile has never been authenticated yet."""
    _restore_token_from_backup(profile_dir)
    tok = profile_dir / KEYRING_TOKEN_FILE
    if tok.exists() and tok.stat().st_size > 10:
        return False
    if any((profile_dir / rel).exists() for rel in _TOKEN_RELPATHS):
        return False
    return True


def _deep_clear_real_home_auth():
    """Clear system keyring before launching a fresh profile.
    Forces clean OAuth flow without touching or wiping user data from REAL_HOME.
    """
    KeyringManager.delete_token()


def _get_private_browser_cmd():
    """Detect an installed browser and return a command that opens a private window.

    When agy does Google OAuth it calls the system browser via the BROWSER env
    var (or webbrowser module default).  If we set BROWSER to an incognito/private
    command, the OAuth page opens in a clean session with NO pre-logged-in Google
    account — forcing a genuine fresh sign-in where the user can pick any account.

    Returns a BROWSER-format string (with %s placeholder for the URL), or None
    if no supported browser is found.
    """
    if sys.platform == "darwin":
        mac_apps = [
            ("/Applications/Google Chrome.app", 'open -na "Google Chrome" --args --incognito %s'),
            ("/Applications/Brave Browser.app", 'open -na "Brave Browser" --args --incognito %s'),
            ("/Applications/Microsoft Edge.app", 'open -na "Microsoft Edge" --args --inprivate %s'),
            ("/Applications/Firefox.app", 'open -na "Firefox" --args --private-window %s'),
            (os.path.expanduser("~/Applications/Google Chrome.app"), 'open -na "Google Chrome" --args --incognito %s'),
            (os.path.expanduser("~/Applications/Brave Browser.app"), 'open -na "Brave Browser" --args --incognito %s'),
        ]
        for app_path, cmd in mac_apps:
            if os.path.exists(app_path):
                return cmd

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
    """Restore profile's saved auth, config, and credentials into REAL_HOME."""
    prof_gemini = profile_dir / ".gemini"
    if prof_gemini.exists():
        try:
            # 1. Config directory (contains config.json, projects)
            src_cfg = prof_gemini / "config"
            if src_cfg.exists():
                dst_cfg = REAL_HOME / ".gemini" / "config"
                dst_cfg.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src_cfg, dst_cfg, dirs_exist_ok=True)

            # 2. Antigravity-cli state and cache
            src_cli = prof_gemini / "antigravity-cli"
            if src_cli.exists():
                dst_cli = REAL_HOME / ".gemini" / "antigravity-cli"
                dst_cli.mkdir(parents=True, exist_ok=True)
                for fname in ["jetski_state.pbtxt", "settings.json", "installation_id"]:
                    f = src_cli / fname
                    if f.exists():
                        shutil.copy2(f, dst_cli / fname)
                src_cache = src_cli / "cache"
                if src_cache.exists():
                    shutil.copytree(src_cache, dst_cli / "cache", dirs_exist_ok=True)
        except Exception:
            pass

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
    """Save updated auth, config, and credentials back into profile after session ends."""
    try:
        # 1. Sync config directory
        src_cfg = REAL_HOME / ".gemini" / "config"
        if src_cfg.exists():
            dst_cfg = profile_dir / ".gemini" / "config"
            dst_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_cfg, dst_cfg, dirs_exist_ok=True)

        # 2. Sync antigravity-cli state and cache
        cli_dir = REAL_HOME / ".gemini" / "antigravity-cli"
        if cli_dir.exists():
            dst_cli = profile_dir / ".gemini" / "antigravity-cli"
            dst_cli.mkdir(parents=True, exist_ok=True)
            for fname in ["jetski_state.pbtxt", "settings.json", "installation_id"]:
                f = cli_dir / fname
                if f.exists():
                    shutil.copy2(f, dst_cli / fname)
            src_cache = cli_dir / "cache"
            if src_cache.exists():
                shutil.copytree(src_cache, dst_cli / "cache", dirs_exist_ok=True)

        # 3. Mark authentication saved for this profile only if a token file exists
        has_token = (
            (profile_dir / KEYRING_TOKEN_FILE).exists()
            or (profile_dir / (KEYRING_TOKEN_FILE + ".bak")).exists()
            or any((profile_dir / rel).exists() for rel in _TOKEN_RELPATHS)
        )
        if has_token:
            (profile_dir / ".auth_saved").touch()
        elif (profile_dir / ".auth_saved").exists():
            (profile_dir / ".auth_saved").unlink()
    except Exception:
        pass

    for rel in _TOKEN_RELPATHS:
        src = REAL_HOME / rel
        dst = profile_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)


def set_last_active(profile_name):
    try:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        data = {"profile": profile_name, "pid": os.getpid(), "time": time.time()}
        LAST_ACTIVE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def clear_last_active():
    try:
        if LAST_ACTIVE_FILE.exists():
            LAST_ACTIVE_FILE.unlink()
    except OSError:
        pass


def _sync_profile_now(profile_name, profile_dir, session_start_ts=None):
    """Safely and immediately syncs live tokens into profile_dir.
    Guarantees:
      - Never overwrites a profile with a token from a different Google account.
      - Never loses refresh_token or id_token (prevents token expiry).
      - Automatically maintains backup token copy (.bak).
    """
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
        keyring_file = profile_dir / KEYRING_TOKEN_FILE

        existing_tok = None
        if keyring_file.exists() and keyring_file.stat().st_size > 10:
            try:
                existing_tok = keyring_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        if not existing_tok:
            bak = profile_dir / (KEYRING_TOKEN_FILE + ".bak")
            if bak.exists() and bak.stat().st_size > 10:
                try:
                    existing_tok = bak.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

        # Determine bound email:
        # A profile is bound ONLY if it has an existing saved token file!
        # If there is no existing token file, this is a fresh or reset profile:
        # it must NEVER reject a newly acquired token due to stale metadata!
        bound_email = None
        if existing_tok:
            bound_email = KeyringManager.extract_email(existing_tok)
            if not bound_email:
                meta = _load_meta(profile_name)
                bound_email = meta.get("email")

        # Capture token from system keyring and safely validate/merge
        tok = KeyringManager.get_token()
        if tok:
            merged_tok, email, status = safe_merge_token(tok, existing_tok, bound_email)
            if merged_tok:
                if merged_tok != existing_tok:
                    keyring_file.write_text(merged_tok, encoding="utf-8")
                    _backup_profile_token(profile_dir)

                if email:
                    _save_meta(profile_name, email=email, last_used=datetime.now().isoformat())
                    (profile_dir / ".auth_saved").touch()
            # If status == mismatch (token belongs to another Google account),
            # DO NOT TOUCH THIS PROFILE!
    except Exception:
        pass


def _start_autosync_watcher(profile_name, profile_dir, session_start_ts=None):
    """Start a background daemon thread that polls for newly acquired credentials
    and persists them immediately into profile_dir with strict account validation.
    """
    stop_event = threading.Event()

    def _watcher_loop():
        while not stop_event.is_set():
            _sync_profile_now(profile_name, profile_dir, session_start_ts)
            stop_event.wait(3.0)

    t = threading.Thread(target=_watcher_loop, name=f"agyp-sync-{profile_name}", daemon=True)
    t.start()
    return stop_event


def _auto_recover_interrupted():
    """If an earlier session was interrupted abruptly before closing,
    recover any acquired credentials for the last active profile.
    Only runs if that process is dead.
    """
    try:
        if LAST_ACTIVE_FILE.exists():
            content = LAST_ACTIVE_FILE.read_text(encoding="utf-8").strip()
            last_p = None
            pid = None
            if content.startswith("{"):
                try:
                    d = json.loads(content)
                    last_p = d.get("profile")
                    pid = d.get("pid")
                except Exception:
                    pass
            else:
                last_p = content

            is_running = False
            if pid:
                try:
                    os.kill(pid, 0)
                    is_running = True
                except (OSError, ProcessLookupError):
                    is_running = False

            if not is_running and last_p:
                p_dir = PROFILES_DIR / last_p
                if p_dir.exists():
                    _sync_profile_now(last_p, p_dir)
                clear_last_active()
    except Exception:
        pass


def inside_agy_session():
    """True if we're running inside an existing agy sandbox."""
    return ".agy_accounts" in os.environ.get("HOME", "")


# ── agy binary resolution ──────────────────────────────────────────────────────

def _resolve_agy():
    """Return path to the agy binary, respecting custom config and standard locations."""
    custom = None
    try:
        if CONFIG_FILE.exists():
            custom = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("custom_cli_path")
    except Exception:
        pass
    if custom and os.path.isfile(custom):
        return custom

    found = shutil.which("agy")
    if found:
        return found

    # Fallback search in standard paths across Linux and macOS
    fallbacks = [
        REAL_HOME / ".local" / "bin" / "agy",
        Path("/opt/homebrew/bin/agy"),       # macOS Apple Silicon
        Path("/usr/local/bin/agy"),         # macOS Intel / Linux
        REAL_HOME / ".gemini" / "antigravity-cli" / "bin" / "agy",
    ]
    for p in fallbacks:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    return None


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
    """Launch agy with 100% isolated HOME + per-profile token and workspace isolation.

    In isolated mode:
      • HOME=profile_dir gives each profile its own completely separate workspace,
        conversations, history, brain, SQLite database, and configs.
      • No files are leaked to or from the system REAL_HOME.
      • Keyring token is swapped cleanly before launch and restored on exit.
      • Token merging strictly enforces account ownership and preserves refresh tokens.
    """
    agy_bin = _resolve_agy()
    if not agy_bin:
        print(f"{C_RED}Error: 'agy' not found in PATH. Is Antigravity installed?{C_RESET}")
        sys.exit(1)

    profile_dir = PROFILES_DIR / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    _migrate_old_tokens(profile_dir)
    _restore_token_from_backup(profile_dir)

    # Initialise metadata on first use of this profile
    if not _load_meta(profile).get("created_at"):
        _save_meta(profile, created_at=datetime.now().isoformat())

    fresh = _is_fresh_profile(profile_dir)
    p_email = get_profile_email(profile)
    email_tag = f"  [{C_CYAN}{p_email}{C_BLUE}]" if p_email else f"  [{C_YELLOW}login required{C_BLUE}]"

    print(f"\n{C_BLUE}Switching to profile '{C_WHITE}{profile}{C_BLUE}'{email_tag}  [{C_GREEN}isolated{C_BLUE}]{C_RESET}")
    print(f"{C_GREEN}Launching isolated environment...{C_RESET}")

    private_browser = None
    if fresh:
        private_browser = _get_private_browser_cmd()
        _warn_browser_account_switch(profile, private_browser)
        _deep_clear_real_home_auth()
    else:
        print()

    session_start_ts = time.time()

    # ── Layer 0: Swap system keyring token (SecretService / Keychain) ───────────
    keyring_file = profile_dir / KEYRING_TOKEN_FILE
    if keyring_file.exists() and keyring_file.stat().st_size > 10:
        try:
            tok = keyring_file.read_text(encoding="utf-8").strip()
            if tok:
                KeyringManager.set_token(tok)
        except Exception:
            pass
    else:
        KeyringManager.delete_token()

    set_last_active(profile)

    # ── Layer 1: Override HOME and XDG for complete workspace isolation ─────────
    # Keeping HOME=profile_dir guarantees that agy writes all history, chats,
    # and settings inside profile_dir/.gemini/ without polluting REAL_HOME.
    env = os.environ.copy()
    env["HOME"] = str(profile_dir)
    env["XDG_CONFIG_HOME"] = str(profile_dir / ".config")
    env["XDG_DATA_HOME"]   = str(profile_dir / ".local" / "share")
    env["XDG_CACHE_HOME"]  = str(profile_dir / ".cache")
    env["XDG_STATE_HOME"]  = str(profile_dir / ".local" / "state")

    if private_browser:
        env["BROWSER"] = private_browser

    _preseed_agy_slots(profile_dir)

    extra = " ".join(f"'{a}'" for a in args) if args else ""

    # Start background autosync watcher with account safety
    stop_sync = _start_autosync_watcher(profile, profile_dir, session_start_ts)

    def _sig_handler(signum, frame):
        try:
            stop_sync.set()
            _sync_profile_now(profile, profile_dir, session_start_ts)
            clear_last_active()
        except Exception:
            pass
        sys.exit(128 + signum)

    old_handlers = {}
    for sig in [getattr(signal, s) for s in ("SIGHUP", "SIGTERM", "SIGINT") if hasattr(signal, s)]:
        try:
            old_handlers[sig] = signal.signal(sig, _sig_handler)
        except Exception:
            pass

    try:
        _bash_run(env, f"'{agy_bin}' {extra}".strip())
    finally:
        stop_sync.set()
        for sig, h in old_handlers.items():
            try:
                signal.signal(sig, h)
            except Exception:
                pass

        _sync_profile_now(profile, profile_dir, session_start_ts)
        clear_last_active()
        _harvest_newest_token(profile_dir, session_start_ts)
        _persist_profile_email(profile, session_start_ts)
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
    _restore_token_from_backup(profile_dir)

    # Initialise metadata on first use of this profile
    if not _load_meta(profile).get("created_at"):
        _save_meta(profile, created_at=datetime.now().isoformat())

    if inside_agy_session():
        print(f"\n{C_YELLOW}Warning: already inside an agy session. A conflict may occur.{C_RESET}")
        print(f"{C_GRAY}Consider using isolated mode instead.{C_RESET}\n")

    p_email = get_profile_email(profile)
    email_tag = f"  [{C_CYAN}{p_email}{C_BLUE}]" if p_email else f"  [{C_YELLOW}login required{C_BLUE}]"
    print(f"\n{C_BLUE}Switching to profile '{C_WHITE}{profile}{C_BLUE}'{email_tag}  [{C_YELLOW}unified{C_BLUE}]{C_RESET}")

    session_start_ts = time.time()

    # Swap system keyring token
    keyring_file = profile_dir / KEYRING_TOKEN_FILE
    if keyring_file.exists() and keyring_file.stat().st_size > 10:
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

    # Start background autosync watcher with session scoping
    stop_sync = _start_autosync_watcher(profile, profile_dir, session_start_ts)

    def _sig_handler_uni(signum, frame):
        try:
            stop_sync.set()
            _sync_profile_now(profile, profile_dir, session_start_ts)
            save_back_profile(profile_dir)
            clear_last_active()
        except Exception:
            pass
        sys.exit(128 + signum)

    old_handlers = {}
    for sig in [getattr(signal, s) for s in ("SIGHUP", "SIGTERM", "SIGINT") if hasattr(signal, s)]:
        try:
            old_handlers[sig] = signal.signal(sig, _sig_handler_uni)
        except Exception:
            pass

    try:
        _bash_run(os.environ.copy(), f"'{agy_bin}' {extra}".strip())
    finally:
        stop_sync.set()
        for sig, h in old_handlers.items():
            try:
                signal.signal(sig, h)
            except Exception:
                pass

        _sync_profile_now(profile, profile_dir, session_start_ts)
        save_back_profile(profile_dir)
        clear_last_active()
        _persist_profile_email(profile, session_start_ts)

    sys.exit(0)


# ── Terminal I/O & Raw Session ────────────────────────────────────────────────

class RawTerminalSession:
    """Keep terminal in cbreak/no-echo mode across the entire interactive session.
    Completely eliminates arrow key escape sequence leakage (^[[A, ^[[B, ^^AA, ^^BB).
    """
    def __init__(self):
        self.fd = sys.stdin.fileno() if sys.stdin.isatty() else None

    def __enter__(self):
        global _IN_RAW_SESSION
        if self.fd is not None:
            try:
                raw_attr = termios.tcgetattr(self.fd)
                raw_attr[3] &= ~(termios.ECHO | termios.ICANON)
                if hasattr(termios, "ECHOCTL"):
                    raw_attr[3] &= ~termios.ECHOCTL
                if hasattr(termios, "ECHONL"):
                    raw_attr[3] &= ~termios.ECHONL
                raw_attr[6][termios.VMIN] = 1
                raw_attr[6][termios.VTIME] = 0
                termios.tcsetattr(self.fd, termios.TCSADRAIN, raw_attr)
                _IN_RAW_SESSION = True
            except Exception:
                pass
        return self

    def __exit__(self, *args):
        global _IN_RAW_SESSION
        _IN_RAW_SESSION = False
        if self.fd is not None and _ORIG_TERMIOS is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, _ORIG_TERMIOS)
            except Exception:
                pass


def prompt_input(prompt_text):
    """Safely prompt for text input while temporarily restoring cooked/echo mode."""
    fd = sys.stdin.fileno() if sys.stdin.isatty() else None
    if fd is not None and _ORIG_TERMIOS is not None:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, _ORIG_TERMIOS)
        except Exception:
            pass
    try:
        return input(prompt_text)
    finally:
        if fd is not None and _IN_RAW_SESSION:
            try:
                raw_attr = termios.tcgetattr(fd)
                raw_attr[3] &= ~(termios.ECHO | termios.ICANON)
                if hasattr(termios, "ECHOCTL"):
                    raw_attr[3] &= ~termios.ECHOCTL
                if hasattr(termios, "ECHONL"):
                    raw_attr[3] &= ~termios.ECHONL
                raw_attr[6][termios.VMIN] = 1
                raw_attr[6][termios.VTIME] = 0
                termios.tcsetattr(fd, termios.TCSADRAIN, raw_attr)
            except Exception:
                pass


def get_key():
    """Read one keypress from raw stdin — handles ANSI/SS3 arrow keys, vim keys, Enter, Esc, Ctrl-C."""
    if not sys.stdin.isatty():
        return "other"

    fd = sys.stdin.fileno()
    must_restore = False
    saved = None

    if not _IN_RAW_SESSION:
        try:
            saved = termios.tcgetattr(fd)
            raw = termios.tcgetattr(fd)
            raw[3] &= ~(termios.ECHO | termios.ICANON)
            if hasattr(termios, "ECHOCTL"):
                raw[3] &= ~termios.ECHOCTL
            if hasattr(termios, "ECHONL"):
                raw[3] &= ~termios.ECHONL
            raw[6][termios.VMIN] = 1
            raw[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSADRAIN, raw)
            must_restore = True
        except Exception:
            pass

    try:
        try:
            ch = os.read(fd, 1)
        except Exception:
            return "other"

        if not ch:
            return "other"

        if ch == b"\x1b":
            # Check if more bytes follow immediately (part of escape sequence)
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                try:
                    rest = os.read(fd, 16)
                except Exception:
                    return "escape"

                # Up arrow (ANSI '\x1b[A', SS3 '\x1bOA', or modified '\x1b[1;2A')
                if rest.startswith(b"[A") or rest.startswith(b"OA") or b"[1;2A" in rest or b"[1;5A" in rest:
                    return "up"
                # Down arrow (ANSI '\x1b[B', SS3 '\x1bOB', or modified '\x1b[1;2B')
                if rest.startswith(b"[B") or rest.startswith(b"OB") or b"[1;2B" in rest or b"[1;5B" in rest:
                    return "down"
                if rest.startswith(b"[C") or rest.startswith(b"OC"):
                    return "right"
                if rest.startswith(b"[D") or rest.startswith(b"OD"):
                    return "left"
                if rest.startswith(b"[H") or rest == b"[1~":
                    return "home"
                if rest.startswith(b"[F") or rest == b"[4~":
                    return "end"
                return "other"
            return "escape"

        if ch in (b"\r", b"\n"):
            return "enter"
        if ch == b"\x03":
            return "ctrl_c"
        if ch in (b"\x7f", b"\x08"):
            return "backspace"
        if ch in (b"k", b"K"):
            return "up"
        if ch in (b"j", b"J"):
            return "down"
        if ch in (b"q", b"Q"):
            return "q"

        return "other"
    finally:
        if must_restore and saved is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, saved)
            except Exception:
                pass


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
        elif key in ('ctrl_c', 'escape', 'backspace', 'q'):
            return


# ── Mode selection ─────────────────────────────────────────────────────────────

def ask_mode():
    """Ask isolated vs unified. Returns 'isolated', 'unified', or 'EXIT'."""
    options = [
        ("isolated", "Isolated (Recommended)", "[Each profile 100% separate - clean history & tokens]"),
        ("unified",  "Unified",                "[Shared history in ~/.gemini, token-only swap]"),
        ("join_us",  "",                       ""),
        ("exit",     "",                       ""),
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
        elif key in ('ctrl_c', 'escape', 'q'):
            return "EXIT"


# ── Interactive profile menu ───────────────────────────────────────────────────

def interactive_menu(profiles, launch_mode="isolated"):
    """Full TUI for profile selection, creation, rename, delete."""
    mode = "main"
    current_idx = 0
    options = []
    max_email_len = max((len(get_profile_email(p) or "") for p in profiles), default=0)

    # Background prefetch quotas so navigation remains completely fluid
    threading.Thread(target=batch_fetch_quotas, args=(profiles,), daemon=True).start()

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
                is_prof = i < len(profiles) and mode in ("main", "delete", "rename")
                if is_prof:
                    email = get_profile_email(opt)
                    if email:
                        is_dupe = any(p != opt and get_profile_email(p) == email for p in profiles)
                        dupe_tag = f" {C_YELLOW}(duplicate){C_RESET}" if is_dupe else ""
                        email_pad = " " * max(0, max_email_len - len(email))
                        q = fetch_profile_quota(opt)
                        q_inline = format_quota_inline(q)
                        q_part = f"  {q_inline}" if q_inline else ""
                        suffix = f"  {C_CYAN}[{email}]{C_RESET}{email_pad}{dupe_tag}{q_part}"
                    else:
                        suffix = f"  {C_YELLOW}[no account — login on launch]{C_RESET}"

                p_disp = f"{opt:<4}" if is_prof else opt
                if i == current_idx:
                    print(f"  {C_BLUE}\u276f {p_disp}{suffix}{C_RESET}")
                else:
                    if not opt.startswith('\033'):
                        print(f"    {C_WHITE}{p_disp}{C_RESET}{suffix}")
                    else:
                        print(f"    {p_disp}{suffix}")

            print(f"\n {C_GRAY}\u2191/\u2193 to move \u00b7 Enter to select{C_RESET}")

        key = get_key()

        if key == 'up':
            current_idx = (current_idx - 1) % len(options)
        elif key == 'down':
            current_idx = (current_idx + 1) % len(options)
        elif key in ('ctrl_c', 'q', 'escape'):
            if mode == "main":
                return "EXIT"
            mode = "main"
            current_idx = 0
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
                        raw = prompt_input(f" {C_GREEN}New profile name:{C_RESET} ")
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
                        raw = prompt_input(f" {C_YELLOW}Rename '{p_old}' to:{C_RESET} ").strip()
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
    print(f"  {C_WHITE}agyp list{C_RESET}                      List all saved profiles and quotas")
    print(f"  {C_WHITE}agyp quota{C_RESET}                     Show account limits and remaining quota")
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

    # Parallel prefetch to ensure displayed quotas are up-to-date
    batch_fetch_quotas(profiles, force=False)
    max_email_len = max((len(get_profile_email(p) or "") for p in profiles), default=0)

    for p in profiles:
        email     = get_profile_email(p)
        meta      = _load_meta(p)
        last_used = meta.get("last_used", "")
        created   = meta.get("created_at", "")

        if email:
            is_dupe = any(other != p and get_profile_email(other) == email for other in profiles)
            dupe_tag = f" {C_YELLOW}(duplicate){C_RESET}" if is_dupe else ""
            email_pad = " " * max(0, max_email_len - len(email))
            email_part = f"  {C_CYAN}[{email}]{C_RESET}{email_pad}{dupe_tag}"
            q = fetch_profile_quota(p)
            q_inline = format_quota_inline(q)
            quota_part = f"  {q_inline}" if q_inline else ""
        else:
            email_part = f"  {C_YELLOW}[no account — login on launch]{C_RESET}"
            quota_part = ""

        date_part  = (
            f"  {C_GRAY}last: {last_used[:10]}{C_RESET}" if last_used else
            (f"  {C_GRAY}created: {created[:10]}{C_RESET}" if created else "")
        )
        print(f"  {C_BLUE}·{C_RESET} {C_WHITE}{p:<4}{C_RESET}{email_part}{quota_part}{date_part}")
    print()


def _cmd_quota():
    """Print a clean, aligned table of account quotas and reset limits."""
    profiles = _list_profiles()
    if not profiles:
        print(f"\n  {C_GRAY}No profiles yet. Run 'agyp' to create one.{C_RESET}\n")
        return

    sys.stdout.write(f"\r\033[K  {C_BLUE}Fetching quotas...{C_RESET}")
    sys.stdout.flush()
    batch_fetch_quotas(profiles, force=False)
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

    print(f"\n  {C_WHITE}Account Limits & Quota Usage:{C_RESET}\n")
    max_p = max(len(p) for p in profiles)
    p_w = max(8, max_p + 2)
    emails = [get_profile_email(p) or "—" for p in profiles]
    e_w = max(24, max(len(e) for e in emails) + 2)

    header = f"  {'Profile':<{p_w}} {'Email':<{e_w}} {'Gemini (5h Limit)':<24} {'Claude (Weekly)':<24} {'Last Used'}"
    print(f"{C_GRAY}{header}{C_RESET}")
    print(f"  {C_GRAY}{'─' * (p_w + e_w + 62)}{C_RESET}")

    for p in profiles:
        email = get_profile_email(p) or "—"
        meta = _load_meta(p)
        last_used = meta.get("last_used", "")
        last_str = last_used[:10] if last_used else "—"

        q = fetch_profile_quota(p)
        if not q or (not q.get("gemini") and not q.get("claude")):
            if email == "—":
                g_str = f"{C_YELLOW}login required{C_RESET}"
                c_str = f"{C_GRAY}—{C_RESET}"
            else:
                g_str = f"{C_GRAY}unavailable{C_RESET}"
                c_str = f"{C_GRAY}unavailable{C_RESET}"
        else:
            g = q.get("gemini", {})
            g_pct = g.get("pct")
            g_rst = format_reset_delta(g.get("reset_time"))
            g_col = _color_quota_pct(g_pct)
            g_rst_info = f" {C_GRAY}(in {g_rst}){C_RESET}" if (g_pct is not None and g_pct < 100 and g_rst) else ""
            g_str = f"{g_col}{g_rst_info}"

            c = q.get("claude", {})
            c_pct = c.get("pct")
            c_rst = format_reset_delta(c.get("reset_time"))
            c_col = _color_quota_pct(c_pct)
            c_rst_info = f" {C_GRAY}(in {c_rst}){C_RESET}" if (c_pct is not None and c_pct < 100 and c_rst) else ""
            c_str = f"{c_col}{c_rst_info}"

        p_padded = pad_ansi(f"{C_WHITE}{p}{C_RESET}", p_w)
        e_padded = pad_ansi(f"{C_CYAN}{email}{C_RESET}", e_w)
        g_padded = pad_ansi(g_str, 24)
        c_padded = pad_ansi(c_str, 24)

        print(f"  {p_padded} {e_padded} {g_padded} {c_padded} {C_GRAY}{last_str}{C_RESET}")
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
    has_token = (
        (target / KEYRING_TOKEN_FILE).exists()
        or (target / (KEYRING_TOKEN_FILE + ".bak")).exists()
        or any((target / rel).exists() for rel in _TOKEN_RELPATHS)
    )
    token_str = (
        f"{C_GREEN}saved{C_RESET}"
        if has_token
        else f"{C_YELLOW}not saved — login required on next launch{C_RESET}"
    )

    W = 15
    print(f"\n  {C_WHITE}Profile: {name}{C_RESET}")
    print(f"  {'Email:':<{W}} {email}")
    print(f"  {'Auth token:':<{W}} {token_str}")

    # Live Quota info
    q = fetch_profile_quota(name)
    if q:
        g = q.get("gemini")
        if g:
            g_pct = g.get("pct")
            g_rst = format_reset_delta(g.get("reset_time"))
            g_rst_str = f" {C_GRAY}(resets in {g_rst}){C_RESET}" if (g_pct is not None and g_pct < 100 and g_rst) else ""
            print(f"  {'Gemini quota:':<{W}} {_color_quota_pct(g_pct)}{g_rst_str} {C_GRAY}[5h rolling limit]{C_RESET}")
        c = q.get("claude")
        if c:
            c_pct = c.get("pct")
            c_rst = format_reset_delta(c.get("reset_time"))
            c_rst_str = f" {C_GRAY}(resets in {c_rst}){C_RESET}" if (c_pct is not None and c_pct < 100 and c_rst) else ""
            print(f"  {'Claude quota:':<{W}} {_color_quota_pct(c_pct)}{c_rst_str} {C_GRAY}[weekly limit]{C_RESET}")

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
    for f in [
        dst_dir / KEYRING_TOKEN_FILE,
        dst_dir / (KEYRING_TOKEN_FILE + ".bak"),
        dst_dir / (KEYRING_TOKEN_FILE + ".bak2"),
        dst_dir / ".auth_saved",
    ]:
        if f.exists():
            f.unlink()
            stripped += 1
    dst_gemini = dst_dir / ".gemini"
    if dst_gemini.exists():
        shutil.rmtree(dst_gemini, ignore_errors=True)
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

    # Remove keyring token file, backups, and auth_saved marker
    for f in [
        target / KEYRING_TOKEN_FILE,
        target / (KEYRING_TOKEN_FILE + ".bak"),
        target / (KEYRING_TOKEN_FILE + ".bak2"),
        target / ".auth_saved",
    ]:
        if f.exists():
            f.unlink()
            cleared += 1

    # Remove saved .gemini state
    prof_gemini = target / ".gemini"
    if prof_gemini.exists():
        shutil.rmtree(prof_gemini, ignore_errors=True)
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
    _save_meta(name, email=None)

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
    _auto_recover_interrupted()
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

    if argv and argv[0] in ("quota", "limits", "usage"):
        _cmd_quota()
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
        with RawTerminalSession():
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
