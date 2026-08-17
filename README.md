<div align="center">

```
       ▄▀▀▄
      ▀▀▀▀▀▀
     ▀▀▀▀▀▀▀▀     Antigravity Profiles Suite
    ▄▀▀    ▀▀▄
   ▄▀▀      ▀▀▄
```

# Antigravity Profiles Suite

**Manage multiple isolated Antigravity profiles — with a beautiful GUI or a blazing-fast CLI.**  
Keep your work, personal, and client sessions completely separate. Never lose a conversation again.

[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

</div>

---

## Why Use This?

Every Antigravity profile is a **fully isolated environment**. Each one has its own:

- 📜 **Conversation history** — your `/resume` conversations are safe and never mixed
- ⚙️ **Settings & preferences** — model selection, theme, tool policies per profile
- 📁 **Projects & workspaces** — separate project lists for each context
- 🔌 **Skills, Rules & MCP servers** — custom configs stay where they belong
- 🗂️ **Scheduled tasks** — your cron jobs and timers don't bleed across profiles

### Real-world use cases

| Profile | What it's for |
|---|---|
| `work` | Your main job — history, projects, and settings all in one place |
| `personal` | Side projects, experiments, personal tasks |
| `client-acme` | Dedicated session for a specific client — share nothing |
| `testing` | Try new models, risky settings, or destructive commands safely |
| `fresh` | Always a clean slate — no history, no baggage |

---

## The `/resume` Advantage

One of Antigravity's most powerful features is `/resume` — it lets you pick up any past conversation exactly where you left off. With profiles, this becomes even more powerful:

```
# Inside your "work" profile
/resume  →  shows ONLY your work conversations

# Inside your "client-acme" profile
/resume  →  shows ONLY that client's conversations
```

**Your history is never lost.** Each profile stores its own conversation database independently. You can always go back to any profile and `/resume` exactly where you left off — days, weeks, or months later.

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
- Creates `agyp-cli`, `agyp-gui` commands in `~/.local/bin/`
- Adds a desktop shortcut to your app launcher
- Creates `~/.agyp-profiles/` for your profile data

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

Launch from terminal or your app launcher:

```bash
agyp-gui
```

**What you can do:**
- **Select a profile** from the list and click **Launch** to open Antigravity bound to that profile
- **Add Profile** — type a name and press Enter or click the green button
- **Delete Profile** — select a profile and click Delete; confirms inline before removing anything
- **Toggle theme** — click the ☀ / ☽ circular button in the top right
- **Close** — click ✕ or press Cmd+W (macOS) / Alt+F4 (Windows)

### CLI — `agyp` or `agyp-cli`

Launch the interactive menu:

```bash
agyp
```

Or launch a specific profile directly (great for scripts and shortcuts):

```bash
agyp work
agyp personal
agyp client-acme
```

**Keyboard controls:**

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate the menu |
| `Enter` | Select / confirm |
| `Ctrl+C` | Exit cleanly |

---

## How Profile Isolation Works

Each profile is stored as a directory under `~/.agyp-profiles/`:

```
~/.agyp-profiles/
├── work/           ← All "work" data lives here
│   ├── .config/
│   ├── .local/
│   └── ...
├── personal/
└── client-acme/
```

When you launch a profile, the suite sets the Antigravity app's `--user-data-dir` to point exclusively at that profile's folder. The app sees it as a completely fresh, isolated home. **No data ever leaks between profiles.**

---

## Project Structure

```
agyp-suite/
├── agyp_cli.py        # TUI — interactive arrow-key menu, cross-platform
├── agyp_gui.py        # GUI — iOS-inspired dark/light mode interface
├── install.sh         # Linux installer (handles Arch, Ubuntu, Fedora, Debian...)
├── install_mac.sh     # macOS installer
├── install.bat        # Windows installer
├── run-cli.bat        # Windows CLI launcher
└── run-gui.bat        # Windows GUI launcher
```

---

## Features at a Glance

| Feature | CLI | GUI |
|---|---|---|
| Create / delete profiles | ✅ | ✅ |
| Launch isolated Antigravity session | ✅ | ✅ |
| Dark / Light mode | — | ✅ |
| Profile name sanitization (security) | ✅ | ✅ |
| Works without Nerd Font installed | ✅ | ✅ |
| macOS native close (red dot + Cmd+W) | — | ✅ |
| Headless / SSH safe | ✅ | ✅ |
| No data leaks between profiles | ✅ | ✅ |

---

## Requirements

| | Minimum |
|---|---|
| Python | 3.8+ |
| Antigravity | Any version with `--user-data-dir` support |
| GUI dependency | `customtkinter` (auto-installed) |
| Font (optional) | JetBrainsMono Nerd Font — for sharp icons in GUI |

---

## Contributing

Pull requests are welcome. Please:
- Keep the CLI and GUI in sync for all features
- Test on at least one of Linux / macOS / Windows before submitting
- Do not hardcode paths — use `Path.home()` and relative script paths

---

## License

MIT — do whatever you want, just keep the attribution.
