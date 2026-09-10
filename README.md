<div align="center">

<pre>
       ▄▀▀▄      
      ▀▀▀▀▀▀     
     ▀▀▀▀▀▀▀▀    
    ▄▀▀    ▀▀▄   
   ▄▀▀      ▀▀▄  
</pre>

# Antigravity Profiles (`agyp`) **BETA**

**Manage unlimited Antigravity (`agy`) accounts from a single terminal.**

![Linux](https://img.shields.io/badge/Linux-✓-blue?style=flat-square&logo=linux&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-✓-blue?style=flat-square&logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Version](https://img.shields.io/badge/version-1.5.0-orange?style=flat-square)

<img src="assets/mainpage.png" width="48%"> <img src="assets/profilepage.png" width="48%">

</div>

---

## Why does this exist?

You are deep into a coding session with Antigravity (`agy`) and suddenly... **you hit the rate limit.**  
Normally, you'd have to log out, log into a different Google account, and lose your entire conversation history and context.

**Not anymore.**

With `agyp`, you can create **unlimited profiles**. Hit a limit? Just open `agyp`, switch to your backup account, and keep coding.

## Features

- ⚡ **Instant Account Switching:** Jump between work, personal, or backup accounts in seconds.
- 🔒 **True Keyring & Session Isolation:** Handles Antigravity's OS Keyring (SecretService / macOS Keychain) token swaps so multiple Google accounts never conflict.
- 🔄 **Unified Mode:** Want to share your conversation history across different accounts? Unified mode swaps only the auth tokens.
- 🎨 **Beautiful Interactive TUI:** Flicker-free, arrow-key navigation. Add, rename, and delete profiles right from the terminal.
- 🏷️ **Smart Labels:** Automatically detects and persistently stores the authenticated Google email next to each profile — even across log rotations.
- 🔁 **Token Pre-seeding:** Saved tokens are injected into agy's internal sandbox slots before launch, so you never have to re-authenticate when switching between existing profiles.
- 📋 **Persistent Metadata:** Email address and last-used timestamps are stored in a lightweight `.meta/` store — reliable across agy updates and log format changes.
- 🔧 **Zero Dependencies:** Built in pure Python. Extremely lightweight and fast (~150ms startup).

---

## Installation

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

> **Note:** If you see `agyp: command not found` after installing, ensure `~/.local/bin` is in your PATH. Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc` or `~/.zshrc`.

---

## Usage

Just run:
```bash
agyp
```
You'll be greeted by an interactive menu to choose your launch mode and select a profile. The first time you use a new profile, `agy` will ask you to log in. After that, it remembers you!

### All Commands

| Command | Description |
|---|---|
| `agyp` | Launch the interactive profile manager |
| `agyp <profile>` | Launch a named profile directly (isolated mode) |
| `agyp <profile> [args...]` | Launch a profile and pass extra args to `agy` |
| `agyp list` | List all profiles with email and last-used date |
| `agyp info <profile>` | Show detailed info: email, token status, disk usage, dates |
| `agyp rename <old> <new>` | Rename a profile |
| `agyp delete <profile>` | Delete a profile (with confirmation prompt) |
| `agyp duplicate <src> <dst>` | Clone a profile including its saved auth tokens |
| `agyp --version` | Show version |
| `agyp --help` | Show help |

### Example Workflow

```bash
# See all your profiles and which accounts they're using
agyp list

# Inspect a specific profile
agyp info work

# Jump straight into a profile (no TUI)
agyp personal

# Hit the rate limit? Switch instantly
agyp backup

# Clone your work profile to start a second work account
agyp duplicate work work2

# Clean up an old profile
agyp delete old-profile
```

---

## How It Works

### Isolated Mode (default)
Each profile is a completely separate `HOME` directory under `~/agyp-profiles/<name>/`. When you launch a profile, `agy` runs with `HOME` pointed at that directory, giving it a totally independent auth store, history, and workspace.

After every session, `agyp` automatically:
1. Scans all possible token locations (including `agy`'s internal `.agy_accounts/` sub-sandboxes)
2. Saves the newest token back to the canonical profile path
3. Detects and persistently stores your authenticated email in `~/agyp-profiles/.meta/<name>.json`

### Unified Mode
Tokens from the selected profile are swapped into your real `~/.gemini/` directory before `agy` starts, and saved back when the session ends. History and workspace are shared across profiles.

---

## Built by

Made by **[pr4xh4r](https://github.com/pr4xh4r)** — proud member of the **[Build x](https://x.com/buildx_main)** community.

Join us:
- ❯ X (Twitter): [x.com/buildx_main](https://x.com/buildx_main)
- ❯ Telegram: [t.me/buildx_main](https://t.me/buildx_main)
- ❯ Reddit: [r/buildx_main](https://reddit.com/r/buildx_main)
- ❯ Discord: [discord.gg/ShZRBUZ7AX](https://discord.gg/ShZRBUZ7AX)

## License

MIT © [pr4xh4r](https://github.com/pr4xh4r)
