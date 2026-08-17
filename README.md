<div align="center">

```
       ▄▀▀▄
      ▀▀▀▀▀▀
     ▀▀▀▀▀▀▀▀     Antigravity Profiles Suite
    ▄▀▀    ▀▀▄
   ▄▀▀      ▀▀▄
```

# Antigravity Profiles Suite

**Switch between multiple Antigravity accounts instantly — GUI or CLI.**  
Hit a limit? One click and you're on a fresh account, with your old history safe and waiting.

[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

</div>

---

## The Problem This Solves

Antigravity accounts have usage limits. When you hit one mid-project, you have two choices:

1. **Wait** for your limit to reset
2. **Switch accounts** instantly and keep working

This tool makes option 2 take **one click**.

Each profile is a completely separate Antigravity account — its own auth, its own session, its own server-side conversation history. Switching profiles is like handing off to a fresh colleague who has full access to their own history.

---

## How It Works

Each profile stores its own **auth credentials** in isolation:

```
~/.agyp-profiles/
├── work/        ← Account 1 auth tokens + local config
├── personal/    ← Account 2 auth tokens + local config
└── client/      ← Account 3 auth tokens + local config
```

When you launch a profile, Antigravity (CLI or Desktop App) starts using that account's credentials. Your **conversation history, projects, and `/resume`** are all tied to the account on Antigravity's servers — they're always there, whether you're using the CLI or the GUI app.

---

## The `/resume` Workflow

This is the real power. Your project history never dies — it's saved server-side per account.

**Scenario: You hit a limit mid-project**

```
Profile "work" hits limit
  → Open agyp, switch to "work-2"
  → Type /resume inside Antigravity
  → Pick up your project history and keep going
```

Each account's `/resume` shows only that account's conversations — perfectly organized by account, automatically.

**You never lose history.** Every conversation is saved server-side. Switch back to any profile at any time and `/resume` exactly where you left off — days or months later.

---

## Installation

### Linux

```bash
git clone https://github.com/yourusername/agyp-suite.git
cd agyp-suite
bash install.sh
```

The installer automatically:
- Detects your Python environment (including Arch Linux / Debian 12 managed Python)
- Installs `customtkinter` for the GUI
- Creates `agyp-cli` and `agyp-gui` commands in `~/.local/bin/`
- Adds a desktop shortcut to your app launcher

### macOS

```bash
git clone https://github.com/yourusername/agyp-suite.git
cd agyp-suite
bash install_mac.sh
```

Then add to your `~/.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Windows

1. Double-click **`install.bat`**
2. Use **`run-gui.bat`** to launch the GUI
3. Use **`run-cli.bat`** to launch the CLI

> **Requirements**: Python 3.8+ from [python.org](https://python.org)

---

## Usage

### GUI — `agyp-gui`

```bash
agyp-gui
```

- Click a profile → click **Launch** → Antigravity opens with that account
- **Add Profile** — type a name, press Enter or click the green button
- **Delete Profile** — select and click Delete, confirms inline
- **Toggle theme** — click the ☀ / ☽ button top right
- **Close** — ✕ button, Cmd+W (macOS), or native window close button

### CLI — `agyp` or `agyp-cli`

```bash
agyp
```

Or jump straight to a profile:

```bash
agyp work
agyp personal
agyp client
```

**Controls:**

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate |
| `Enter` | Select / confirm |
| `Ctrl+C` | Exit |

---

## Real-World Use Cases

| Profile | Use |
|---|---|
| `work` | Main account — daily work, projects |
| `work-2` | Backup — switch here when `work` hits limits |
| `personal` | Personal projects, separate history |
| `client-acme` | Dedicated account for a specific client |
| `testing` | Burn through limits here, keep main clean |

---

## Features

| Feature | CLI | GUI |
|---|---|---|
| Switch Antigravity accounts | ✅ | ✅ |
| Auth isolation per profile | ✅ | ✅ |
| Works with CLI (`agy`) | ✅ | — |
| Works with Desktop App | — | ✅ |
| Create / delete profiles | ✅ | ✅ |
| Dark / Light mode | — | ✅ |
| macOS native close (red dot + Cmd+W) | — | ✅ |
| Headless / SSH safe | ✅ | ✅ |
| Works without Nerd Font | ✅ | ✅ |
| Profile name security (no path traversal) | ✅ | ✅ |

---

## Project Structure

```
agyp-suite/
├── agyp_cli.py        # TUI — interactive arrow-key menu, cross-platform
├── agyp_gui.py        # GUI — iOS-inspired dark/light mode interface
├── install.sh         # Linux installer (Arch, Ubuntu, Fedora, Debian...)
├── install_mac.sh     # macOS installer
├── install.bat        # Windows installer
├── run-cli.bat        # Windows CLI launcher
└── run-gui.bat        # Windows GUI launcher
```

---

## Requirements

| | |
|---|---|
| Python | 3.8+ |
| Antigravity | CLI (`agy`) or Desktop App |
| GUI dep | `customtkinter` — auto-installed |
| Font | JetBrainsMono Nerd Font *(optional, for sharp icons)* |

---

## Contributing

PRs welcome. Keep CLI and GUI in sync, avoid hardcoded paths, test cross-platform.

---

## License

MIT — use freely, keep attribution.
