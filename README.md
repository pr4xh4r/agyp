<div align="center">

<img src="assets/logo.svg" width="170" alt="Antigravity Logo" />

# `agyp` — Antigravity Profiles Manager

**Never let a rate limit interrupt your flow.**  
Manage multiple Google Antigravity (`agy`) accounts seamlessly from a single lightweight terminal menu.

[![Version](https://img.shields.io/badge/version-1.6.4-orange?style=flat-square)](https://github.com/pr4xh4r/agyp)
[![Python](https://img.shields.io/badge/python-3.8+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Linux](https://img.shields.io/badge/linux-supported-green?style=flat-square&logo=linux&logoColor=white)](https://github.com/pr4xh4r/agyp)
[![macOS](https://img.shields.io/badge/macOS-supported-green?style=flat-square&logo=apple&logoColor=white)](https://github.com/pr4xh4r/agyp)
[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)

</div>

---

### The Problem
If you use Google Antigravity (`agy`) for daily coding, you've definitely run into this: you're right in the middle of building a feature, debugging a tricky bug, or iterating on a complex prompt, and suddenly — **you hit your 5-hour rolling limit or weekly quota.**

Normally, switching accounts is a headache:
1. You have to log out of `agy`.
2. Re-authenticate in your browser with a secondary Google account.
3. Deal with token conflicts and lost terminal state.
4. Repeat the whole dance again once the backup account runs low.

### The Solution: `agyp`
`agyp` lets you register as many backup Google accounts as you want. Each account lives in its own profile with saved authentication credentials. When one profile runs low on quota, just pop open `agyp`, switch to another account in one keystroke, and keep coding without missing a beat.

---

## 🖥️ What It Looks Like

```text
       ▄▀▀▄       
      ▀▀▀▀▀▀      
     ▀▀▀▀▀▀▀▀     Antigravity Profiles  v1.6.4
    ▄▀▀    ▀▀▄           (BETA)
   ▄▀▀      ▀▀▄   

─────────────────────────────────────────────────────

 Select a profile to launch:  mode: Unified

   p1   [work.lead@company.com]        G·5h: 100%   G·Wk: 100%   C·5h: 100%   C·Wk: 100%
   p2   [secondary.dev@gmail.com]      G·5h: 100%   G·Wk: 100%   C·5h: 100%   C·Wk:  50%
 ❯ p3   [personal.account@gmail.com]   G·5h: 100%   G·Wk: 100%   C·5h:  39%   C·Wk:  19%
   p4   [backup.testing@gmail.com]     G·5h:  97%   G·Wk: 100%   C·5h:   0%   C·Wk:   0%
   p5   [old.session@gmail.com]        [session expired — login on launch]
   + Add Profile
   ~ Rename Profile
   - Delete Profile
   ◆ Community
   ← Back
   ✕ Quit

 ↑/↓ or scroll to move · Enter or click to select
 ↻ p3 quota refreshes: C·5h in 3h 52m · C·Wk in 4d 11h
```

---

## ✨ Features That Make Life Easier

- **Live 4-Column Quota Tracking**: Shows both **Gemini** (5-Hour Rolling & Weekly) and **Claude / GPT** (5-Hour Rolling & Weekly) side-by-side in real-time.
- **Zero Ragged Lines**: Column widths are strictly aligned down to the character. No jagged tables or text hopping across the screen.
- **Dynamic Refresh Timers**: Active countdown timers (`↻ p3 quota refreshes: C·5h in 3h 52m · C·Wk in 4d 11h`) update dynamically in the footer when you highlight a profile, keeping the main table distraction-free.
- **Instant O(1) Navigation**: Pre-cached email lookups ensure scrolling and arrow-key movement remain instantaneous and buttery smooth, even with dozens of profiles.
- **Session Expiration Alerts**: If an OAuth token ever expires on Google's backend, `agyp` tags it immediately as `[session expired — login on launch]` instead of hanging or spinning forever.
- **Mouse & Keyboard Support**: Navigate with `↑` / `↓` arrow keys, or just click with your mouse and scroll with the wheel.
- **Two Launch Modes**:
  - **Isolated (Incognito)**: Completely separate sandbox for each profile (separate tokens, chat history, and cache).
  - **Unified Mode**: Keep your shared conversation history in `~/.gemini` while swapping only authentication tokens.
- **Token Pre-Seeding**: Tokens are automatically injected into `agy`'s internal account sandboxes before launch, so you don't get forced into browser login loops.
- **Zero Dependencies**: Pure Python 3 standard library. No `pip install`, no external bloat, and runs on any standard terminal.

---

## ⚡ Quick Installation

Clone and install with a single command:

### Linux
```bash
git clone https://github.com/pr4xh4r/agyp
cd agyp
bash install.sh
```

### macOS
```bash
git clone https://github.com/pr4xh4r/agyp
cd agyp
bash install_mac.sh
```

> **Note:** If `agyp` is not recognized after install, ensure `~/.local/bin` is in your `PATH`.  
> Add this to your `~/.bashrc` or `~/.zshrc` if needed:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

---

## 🚀 How to Use

### 1. Interactive TUI (Most Common)
Simply type:
```bash
agyp
```
This opens the interactive menu where you can:
- Choose between **Isolated** or **Unified** mode.
- View live quotas across all your accounts.
- Press **Enter** to launch Antigravity with your chosen profile.
- Add, rename, or delete profiles straight from the interface.

*When you launch a newly created profile for the first time, `agy` will prompt you to log into Google in your browser. Once done, `agyp` securely remembers that account forever.*

### 2. Direct Launch from Terminal
You can also launch any profile directly without going through the menu:
```bash
# Launch a specific profile directly
agyp p2

# Launch with extra flags passed directly to agy
agyp p2 --model gemini-3.8-flash-high

# Launch with a quick prompt
agyp p3 -p "Explain how asyncio tasks work in Python"
```

---

## 📖 Command Reference

| Command | What it does |
| :--- | :--- |
| `agyp` | Opens the interactive visual manager with live quotas |
| `agyp <profile>` | Launches a profile directly in isolated mode |
| `agyp <profile> [args...]` | Passes custom arguments directly to the underlying `agy` CLI |
| `agyp list` | Displays a clean summary table of all profiles and emails |
| `agyp quota` | Quick terminal readout of quota percentages and reset countdowns |
| `agyp info <profile>` | Shows metadata (email, token age, disk usage, creation date) |
| `agyp rename <old> <new>` | Renames an existing profile |
| `agyp delete <profile>` | Removes a profile folder and its saved credentials |
| `agyp duplicate <src> <dst>` | Clones an existing profile environment |
| `agyp reset-auth <profile>` | Wipes saved tokens to force a fresh Google OAuth login |
| `agyp --version` | Prints the installed `agyp` version |
| `agyp --help` | Displays command line usage and flags |

---

## 🔒 Isolated vs. Unified Mode

When you run `agyp`, you can pick how profiles run:

### 1. Isolated Mode (Incognito) — Recommended for Complete Separation
Each profile gets its own isolated home directory under `~/agyp-profiles/<name>/`.
- Completely separate chat history and scratchpad.
- Zero chance of personal or client work leaking between accounts.
- Best if you manage client projects, work accounts, and personal accounts.

### 2. Unified Mode — Best for Continuous Coding
Shares your global Antigravity workspace and history (`~/.gemini/`), but seamlessly swaps out the active Google authentication token.
- Keeps your previous conversation transcripts intact.
- Seamlessly lets you continue your coding flow on another account when one hits a limit.

---

## 🛠️ Frequently Asked Questions

<details>
<summary><b>Does agyp store my passwords?</b></summary>
No. <code>agyp</code> never sees or touches your Google password. It only manages official OAuth2 access and refresh tokens generated directly by Google's authentication flow, exactly the same way the official <code>agy</code> CLI does.
</details>

<details>
<summary><b>Where are my profiles saved?</b></summary>
All profile data is kept locally on your machine under <code>~/agyp-profiles/</code>.
</details>

<details>
<summary><b>How does quota fetching work?</b></summary>
<code>agyp</code> queries Google's internal Cloud Code service endpoints (<code>fetchAvailableModels</code> and <code>retrieveUserQuotaSummary</code>) using your saved OAuth tokens. Requests are cached in-memory and in lightweight JSON metadata, so the UI never lags or makes unnecessary network calls.
</details>

<details>
<summary><b>What does "[session expired — login on launch]" mean?</b></summary>
Google OAuth refresh tokens occasionally expire if an account has been inactive for a long time or permissions changed. When this happens, <code>agyp</code> lets you know right away. Just press Enter on that profile to launch it, and Google will prompt you to sign in again.
</details>

---

## 👥 Community & Support

`agyp` is built by **[pr4xh4r](https://github.com/pr4xh4r)** and supported by the **[Build x](https://x.com/buildx_main)** developer community.

Join us to share feedback, ask questions, or hang out:
- **X (Twitter)**: [@buildx_main](https://x.com/buildx_main)
- **Discord**: [Join our Discord](https://discord.gg/ShZRBUZ7AX)
- **Telegram**: [t.me/buildx_main](https://t.me/buildx_main)
- **Reddit**: [r/buildx_main](https://reddit.com/r/buildx_main)

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.  
Crafted with precision for developers who refuse to wait on rate limits.
