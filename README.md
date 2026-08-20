<div align="center">

<pre>
       ▄▀▀▄      
      ▀▀▀▀▀▀     
     ▀▀▀▀▀▀▀▀    
    ▄▀▀    ▀▀▄   
   ▄▀▀      ▀▀▄  
</pre>

# Antigravity Profiles

Switch between multiple Antigravity (`agy`) accounts instantly — no logging out, no lost history.

![Linux](https://img.shields.io/badge/Linux-✓-blue?style=flat-square&logo=linux&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-✓-blue?style=flat-square&logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python&logoColor=white)
![Accounts](https://img.shields.io/badge/accounts-unlimited-green?style=flat-square)

</div>

---

## Why?

When you hit a rate limit mid-project, the only option is to manually log out, log into a different Google account, and lose your place. This fixes that.

Run `agyp`, pick an account, keep going. Your history for each account is separate. When you switch back later, `/resume` picks up exactly where you left off.

---

## How many accounts?

**Unlimited.** Just create a new profile for each Google account. Each one is completely independent.

```
account1   → your main Google account
account2   → backup for when account1 hits limits  
work       → work Google account
client     → client's account
```

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

> If you see `agyp: command not found` after install, add this to your `~/.bashrc` or `~/.zshrc` and restart the terminal:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

---

## Usage

```bash
agyp
```

That's it. You'll get two simple menus:

**Step 1 — Pick a mode:**
```
❯ isolated   ← use this (fully separate session)
  unified    ← token swap only, shared history
```

**Step 2 — Pick a profile:**
```
  account1
❯ account2
  [+] Add Profile
```

First time you use a new profile, `agy` will ask you to log in with Google — after that it's saved and you never need to log in again for that account.

### Skip the menu — go straight to a profile

```bash
agyp myaccount
```

---

## Isolated vs Unified — which to use?

| | Isolated | Unified |
|---|---|---|
| Conversation history | Separate per profile | Shared |
| Config & settings | Separate per profile | Shared |
| Auth credentials | Separate per profile | Separate per profile |
| **When to use** | **Always (recommended)** | Outside an `agy` session only |

**Just use Isolated.** It's the safe default — each account is fully sandboxed, nothing leaks between sessions.

> ⚠️ If you run `agyp unified` from **inside** an existing `agy` session, it may conflict with your current session. `agyp` will warn you if this happens.

---

## Requirements

- `agy` (Antigravity CLI) — already installed if you're using Antigravity
- Python 3.8+ — already on your system
- Linux or macOS

No additional packages needed.

---

## Your data

- All profiles are stored locally in `~/agyp-profiles/` — nothing is uploaded anywhere
- Each profile's credentials are saved automatically after every session
- Profile names only allow letters, numbers, spaces, hyphens, underscores — no funny business

---

## Built by

Made by **[pr4xh4r](https://github.com/pr4xh4r)** — part of the **[Build x](https://x.com/buildx_main)** community.

Join us:
- X (Twitter): https://x.com/buildx_main
- Telegram: https://t.me/buildx_main
- Reddit: https://reddit.com/r/buildx_main

---

## License

MIT © [pr4xh4r](https://github.com/pr4xh4r)
