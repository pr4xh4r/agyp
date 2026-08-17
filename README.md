<div align="center">

<pre>
       ▄▀▀▄      
      ▀▀▀▀▀▀     
     ▀▀▀▀▀▀▀▀    
    ▄▀▀    ▀▀▄   
   ▄▀▀      ▀▀▄  
</pre>

# Antigravity Profiles

Manage multiple Antigravity accounts from one place — GUI and CLI both included.

![Linux](https://img.shields.io/badge/Linux-✓-blue?style=flat-square&logo=linux&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-✓-blue?style=flat-square&logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-✓-blue?style=flat-square&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python&logoColor=white)

</div>

---

I built this because I kept hitting usage limits mid-project and the only option was to manually log out, log back in with a different account, and lose my place. That got old fast.

## What it does

Keeps separate OAuth tokens for each "profile" (account). When you switch profiles, it swaps in that account's token and opens Antigravity — same app, same CLI, just a different login. Your history and `/resume` are tied to each account on Antigravity's servers, so nothing gets mixed up and nothing is lost.

Typical setup:

- `agy1` — main account, daily use
- `agy2` — backup for when agy1 hits limits
- `client` — separate account for client work

When agy1 hits a rate limit, open the tool, switch to agy2, keep going. When you come back to agy1 later, `/resume` picks up exactly where you left off.

---

## Install

**Linux**
```bash
git clone https://github.com/yourusername/agyp-suite
cd agyp-suite
bash install.sh
```

Handles Python environments including Arch/Debian where pip is restricted — creates a small venv if needed.

**macOS**
```bash
bash install_mac.sh
```

Add `~/.local/bin` to your PATH if it isn't already:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

**Windows**

Double-click `install.bat`, then use `run-gui.bat` or `run-cli.bat` to launch. Requires Python 3.8+ from python.org.

---

## Usage

**GUI**
```bash
agyp-gui
```

Pick a profile from the list, hit Launch. Add new profiles with the text box at the bottom. First time you use a new profile, Antigravity asks you to log in — after that the token is saved and it just works.

**CLI**
```bash
agyp
```

Arrow keys to navigate, Enter to select. Or go straight to a profile:
```bash
agyp agy1
agyp agy2
```

---

## How it works

Antigravity stores its OAuth token at:
```
~/.gemini/antigravity-cli/antigravity-oauth-token
```

When you switch profiles, this tool:
1. Backs up the current token
2. Copies the selected profile's token into that path
3. Launches Antigravity (app or CLI)
4. When the session ends, saves the refreshed token back to the profile

Everything else — history, projects, `/resume` — lives on Antigravity's servers per account. The tool doesn't touch any of that.

Profiles are stored in `~/.agyp-profiles/`, one folder per profile, each containing just the OAuth token for that account.

---

## Requirements

- Python 3.8+
- `customtkinter` — installed automatically by the install script
- Antigravity CLI (`agy`) or Desktop App installed

The GUI works without Nerd Font — falls back to standard Unicode symbols automatically.

---

## Files

```
agyp_cli.py      — terminal interface
agyp_gui.py      — GUI (customtkinter, dark/light mode)
install.sh       — Linux installer
install_mac.sh   — macOS installer
install.bat      — Windows installer
run-cli.bat      — Windows CLI launcher
run-gui.bat      — Windows GUI launcher
```

---

## Notes

- Tested on Arch Linux, Ubuntu, Fedora, macOS Sonoma, Windows 11
- Safe to run over SSH — detects headless environments and won't crash
- Profile names are sanitized — path traversal and special characters blocked
