#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Antigravity/Google Brand Colors (TrueColor ANSI)
C_BLUE = "\033[38;2;66;133;244m"
C_GREEN = "\033[38;2;52;168;83m"
C_RED = "\033[38;2;234;67;53m"
C_YELLOW = "\033[38;2;251;188;5m"
C_WHITE = "\033[1;37m"
C_GRAY = "\033[38;5;245m"
C_RESET = "\033[0m"

def get_key():
    """Reads a single keypress cross-platform without echoing to the screen."""
    if sys.platform == "win32":
        import msvcrt
        key = msvcrt.getch()
        if key in (b'\xe0', b'\x00'): 
            key = msvcrt.getch()
            if key == b'H': return 'up'
            if key == b'P': return 'down'
        if key == b'\r': return 'enter'
        if key == b'\x03': return 'ctrl_c'
        return 'other'
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(2)
                if ch2 == '[A': return 'up'
                if ch2 == '[B': return 'down'
            if ch in ('\r', '\n'): return 'enter'
            if ch == '\x03': return 'ctrl_c'
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return 'other'

def clear_screen():
    os.system("cls" if sys.platform == "win32" else "clear")

def draw_header():
    # Authentic Antigravity ASCII Art Header in Official Blue
    print(f"{C_BLUE}       ▄▀▀▄       {C_RESET}")
    print(f"{C_BLUE}      ▀▀▀▀▀▀      {C_RESET}")
    print(f"{C_BLUE}     ▀▀▀▀▀▀▀▀     {C_WHITE}Antigravity Profiles (BETA){C_RESET}")
    print(f"{C_BLUE}    ▄▀▀    ▀▀▄    {C_RESET}")
    print(f"{C_BLUE}   ▄▀▀      ▀▀▄   {C_RESET}")
    print(f"\n{C_GRAY}─────────────────────────────────────────────────────{C_RESET}\n")

def interactive_menu(profiles):
    mode = "main"
    current_idx = 0
    
    # Enable ANSI escape codes on Windows 10+
    if sys.platform == "win32":
        os.system("") 
        
    sys.stdout.write("\033[?25l") # Hide cursor
    try:
        while True:
            clear_screen()
            draw_header()

            if mode == "main":
                options = profiles + [f"{C_GREEN}[+] Add Profile{C_RESET}", f"{C_RED}[-] Delete Profile{C_RESET}", f"{C_GRAY}[x] Exit{C_RESET}"]
                print(f" {C_WHITE}Select a profile to launch:{C_RESET}\n")
            elif mode == "delete":
                options = profiles + [f"{C_GRAY}[<] Back{C_RESET}"]
                print(f" {C_RED}Select a profile to delete:{C_RESET}\n")
                if not profiles:
                    print(f" {C_GRAY}  (No profiles exist yet.){C_RESET}\n")
            elif mode == "create":
                options = [f"{C_GREEN}[>] Enter Profile Name{C_RESET}", f"{C_GRAY}[<] Back{C_RESET}"]
                print(f" {C_GREEN}Create New Profile:{C_RESET}\n")

            # Render Options
            for i, opt in enumerate(options):
                if i == current_idx:
                    print(f"  {C_BLUE}❯ {opt}{C_RESET}")
                else:
                    print(f"    {opt}")
            
            # Key Handling
            key = get_key()
            if key == 'up':
                current_idx = max(0, current_idx - 1)
            elif key == 'down':
                current_idx = min(len(options) - 1, current_idx + 1)
            elif key == 'enter':
                if mode == "main":
                    if current_idx < len(profiles):
                        return profiles[current_idx]
                    elif current_idx == len(profiles): # Create
                        mode = "create"
                        current_idx = 0
                    elif current_idx == len(profiles) + 1: # Delete
                        mode = "delete"
                        current_idx = 0
                    elif current_idx == len(profiles) + 2: # Exit
                        sys.exit(0)
                elif mode == "create":
                    if current_idx == 0: # Enter Name
                        sys.stdout.write("\033[?25h")
                        choice = input(f"\n {C_WHITE}Name:{C_RESET} ").strip()
                        if not choice: 
                            sys.stdout.write("\033[?25l")
                            continue # Go back to menu
                        return choice
                    else: # Back
                        mode = "main"
                        current_idx = 0
                elif mode == "delete":
                    if current_idx < len(profiles):
                        p_to_delete = profiles[current_idx]
                        sys.stdout.write("\033[?25h")
                        clear_screen()
                        draw_header()
                        ans = input(f" {C_RED}Permanently delete '{p_to_delete}'? (y/N): {C_RESET}").strip().lower()
                        if ans == 'y':
                            target = Path.home() / ".agy_accounts" / p_to_delete
                            if target.exists():
                                shutil.rmtree(target)
                            profiles.remove(p_to_delete)
                        sys.stdout.write("\033[?25l")
                        mode = "main"
                        current_idx = 0
                    else: # Back
                        mode = "main"
                        current_idx = 0
            elif key == 'ctrl_c':
                sys.stdout.write("\033[?25h")
                sys.exit(0)
    finally:
        sys.stdout.write("\033[?25h") # Show cursor
        clear_screen()
        
    return None

def launch_profile(profile, args):
    profile_dir = Path.home() / ".agy_accounts" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    env = os.environ.copy()
    env["HOME"] = str(profile_dir)
    
    print(f"\n{C_BLUE}🚀 Launching profile '{profile}'...{C_RESET}\n")
    
    if sys.platform == "win32":
        try:
            sys.exit(subprocess.call(["agy"] + args, env=env, shell=True))
        except FileNotFoundError:
            print(f"{C_RED}Error: 'agy' command not found. Ensure Antigravity CLI is installed.{C_RESET}")
            sys.exit(1)
    else:
        try:
            os.execvpe("agy", ["agy"] + args, env)
        except FileNotFoundError:
            print(f"{C_RED}Error: 'agy' command not found. Ensure Antigravity CLI is installed.{C_RESET}")
            sys.exit(1)

def main():
    accounts_dir = Path.home() / ".agy_accounts"
    
    if len(sys.argv) >= 2:
        launch_profile(sys.argv[1], sys.argv[2:])
        return

    profiles = []
    if accounts_dir.exists():
        profiles = sorted([d.name for d in accounts_dir.iterdir() if d.is_dir()])
        
    selected_profile = interactive_menu(profiles)
    if selected_profile:
        launch_profile(selected_profile, [])

if __name__ == "__main__":
    main()
