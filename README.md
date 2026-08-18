<div align="center">

<pre>
       ▄▀▀▄      
      ▀▀▀▀▀▀     
     ▀▀▀▀▀▀▀▀    
    ▄▀▀    ▀▀▄   
   ▄▀▀      ▀▀▄  
</pre>

# Antigravity Profiles

Manage multiple Antigravity accounts from one terminal — fully isolated or token-only swap.

![Linux](https://img.shields.io/badge/Linux-✓-blue?style=flat-square&logo=linux&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-✓-blue?style=flat-square&logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python&logoColor=white)
![CLI only](https://img.shields.io/badge/interface-CLI_only-blue?style=flat-square)

</div>

---

I built this because I kept hitting usage limits mid-project and the only option was to manually log out, log back in with a different account, and lose my place. That got old fast.

## What it does

Keeps separate credentials for each "profile" (account). On launch it asks you to pick a mode, then pick a profile — and drops you straight into `agy` under that account.

Typical setup:

- `main` — daily account
- `backup` — for when `main` hits limits
- `client` — separate account for client work

When `main` hits a rate limit, run `agyp`, pick `backup`, keep going. When you come back to `main` later, `/resume` picks up exactly where you left off.

---

## Modes

### Isolated *(recommended)*
The profile directory becomes `$HOME` for the entire `agy` session. Nothing leaks in or out — separate conversation history, config, and credentials. This is the correct mode to use when running `agyp` from inside an existing `agy` session.

### Unified
Only the three auth token files are swapped. Everything else (conversation history, config, cache) is shared. Use this from **outside** an `agy` session. After the session ends, updated tokens are automatically saved back to the profile.

> **Note:** Do not use Unified mode from inside an active `agy` session — launching a second `agy` with the same `$HOME` causes a session conflict. `agyp` will warn you if it detects this.

---

## Install

**Linux**
```bash
git clone https://github.com/pr4xh4r/agyp
cd agyp
bash install.sh
```

**macOS**
```bash
git clone https://github.com/pr4xh4r/agyp
cd agyp
bash install_mac.sh
```

Add `~/.local/bin` to your PATH if it isn't already:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Scripts are copied to `~/.local/share/agyp/` so the tool keeps working even if you move or delete the cloned repo. No dependencies beyond Python 3 stdlib.

---

## Usage

```bash
agyp
```

On launch you'll see two menus in sequence:

1. **Choose mode** — `isolated` or `unified` (arrow keys + Enter)
2. **Choose profile** — pick an existing profile or create a new one

Or jump straight to a profile (uses isolated mode):
```bash
agyp myprofile
agyp myprofile -- --some-agy-flag
```

**First time** you use a profile, `agy` asks you to log in — after that the credentials are saved and it just works.

---

## How it works

Antigravity stores its auth at these paths relative to `$HOME`:

```
.gemini/antigravity-cli/antigravity-oauth-token   ← CLI account token
.gemini/oauth_creds.json                          ← OAuth credentials
.gemini/google_accounts.json                      ← Active account info
```

Each profile stores its own copies of these files at the exact same relative paths inside `~/agyp-profiles/<name>/`.

**Isolated mode** sets `HOME=~/agyp-profiles/<name>` before launching `agy` — the binary reads and writes its tokens there naturally. No manual copying needed.

**Unified mode** copies the profile's token files into the real `$HOME/.gemini/...` before launch, then copies them back after `agy` exits.

---

## Requirements

- Python 3.8+ (stdlib only — no pip installs)
- `agy` (Antigravity CLI) in your `PATH`
- Linux or macOS

---

## Files

```
agyp_cli.py      — the entire tool (single file, no dependencies)
install.sh       — Linux installer
install_mac.sh   — macOS installer
assets/          — screenshots
```

---

## Notes

- Tested on Arch Linux, Ubuntu, Fedora, macOS Sonoma
- Safe to run over SSH
- Profile names are sanitized — path traversal and special characters blocked
- Your tokens stay in `~/agyp-profiles/` on your machine only — never uploaded anywhere
- After install, the script lives in `~/.local/share/agyp/` — moving the cloned repo won't break anything
- `agyp` automatically migrates profiles created by older versions of the tool


