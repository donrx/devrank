#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║         DEV RARITY SCANNER v1.2 — "What Kind of Dev Are You?"    ║
║     Inspired by the sacred scrolls of r/ProgrammerHumor,         ║
║     r/unixporn, r/linux, and the deep lore of the internet.      ║
╚══════════════════════════════════════════════════════════════════╝

Scans your computer and ranks your developer rarity from:
  Common → Uncommon → Rare → Epic → Legendary → Mythical

No data leaves your machine. This is 100% local. We promise.
(Unlike that npm package you installed at 2am without reading.)
"""

from __future__ import annotations

import os
import re
import sys
import time
import json
import glob
import random
import shutil
import platform
import subprocess
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# ANSI COLOR CODES
# ─────────────────────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
ITALIC  = "\033[3m"

# Rank colors
C_COMMON    = "\033[37m"      # Gray/white
C_UNCOMMON  = "\033[32m"      # Green
C_RARE      = "\033[34m"      # Blue
C_EPIC      = "\033[35m"      # Purple
C_LEGENDARY = "\033[33m"      # Gold/Yellow
C_MYTHICAL  = "\033[91m"      # Bright Red / Orange

C_GREEN  = "\033[32m"
C_RED    = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN   = "\033[96m"
C_GRAY   = "\033[90m"
C_WHITE  = "\033[97m"

HOME = Path.home()
SYSTEM = platform.system()  # 'Windows', 'Darwin', 'Linux'


def _force_utf8_stdio() -> None:
    """Windows consoles default to cp1252, which mangles the emoji-heavy output.
    Force UTF-8 so the banner doesn't blow up on first print."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()


def is_windows() -> bool:
    return SYSTEM == "Windows"


def is_macos() -> bool:
    return SYSTEM == "Darwin"


def is_linux() -> bool:
    return SYSTEM == "Linux"


def is_wsl() -> bool:
    if not is_linux():
        return False

    if os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"):
        return True

    kernel_release = run("uname -r").lower()
    if "microsoft" in kernel_release or "wsl" in kernel_release:
        return True

    proc_version = read_file_safe("/proc/version").lower()
    return "microsoft" in proc_version or "wsl" in proc_version


def _within_depth(path: Path, root: Path, max_depth: int) -> bool:
    try:
        return len(path.relative_to(root).parts) <= max_depth
    except Exception:
        return False


def find_paths_under(root: Path, pattern: str, *, directories: Optional[bool] = None, max_depth: int = 5, limit: int = 50) -> List[str]:
    results: List[str] = []
    try:
        for path in root.rglob(pattern):
            if directories is True and not path.is_dir():
                continue
            if directories is False and not path.is_file():
                continue
            if not _within_depth(path, root, max_depth):
                continue

            results.append(str(path))
            if len(results) >= limit:
                break
    except Exception:
        pass
    return results


def find_node_modules(max_depth: int = 4, limit: int = 40, time_budget: float = 1.5) -> List[str]:
    """Find node_modules directories quickly without traversing huge trees forever."""
    results: List[str] = []
    skip_dirs = {
        ".git", ".cache", ".venv", "venv", "env", "dist", "build", "out",
        "Library", "Caches", "Temp", "tmp", "node_modules", "AppData",
    }

    start = time.monotonic()
    queue = deque([(HOME, 0)])

    while queue and len(results) < limit:
        if time.monotonic() - start > time_budget:
            break

        current, depth = queue.popleft()
        if depth > max_depth:
            continue

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.name in skip_dirs:
                        continue
                    try:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue

                    entry_path = Path(entry.path)
                    if entry.name == "node_modules":
                        results.append(str(entry_path))
                        if len(results) >= limit:
                            break
                        continue

                    if depth + 1 <= max_depth:
                        queue.append((entry_path, depth + 1))
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue

    return results


def scan_project_markers(max_depth: int = 5, time_budget: float = 1.5) -> Dict[str, int]:
    """Collect project-related files in one bounded walk instead of three separate scans."""
    counts = {
        "makefile": 0,
        "justfile": 0,
        "cargo_toml": 0,
        "nix": 0,
    }
    skip_dirs = {
        ".git", ".cache", ".venv", "venv", "env", "dist", "build", "out",
        "Library", "Caches", "Temp", "tmp", "node_modules", "AppData",
    }

    start = time.monotonic()
    queue = deque([(HOME, 0)])
    scanned_entries = 0

    while queue:
        if time.monotonic() - start > time_budget:
            break

        current, depth = queue.popleft()
        if depth > max_depth:
            continue

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    scanned_entries += 1
                    if scanned_entries > 4000:
                        return counts

                    name_lower = entry.name.lower()
                    if name_lower in skip_dirs:
                        continue

                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if depth + 1 <= max_depth:
                                queue.append((Path(entry.path), depth + 1))
                            continue
                    except OSError:
                        continue

                    if name_lower == "makefile":
                        counts["makefile"] += 1
                    elif name_lower == "justfile":
                        counts["justfile"] += 1
                    elif name_lower == "cargo.toml":
                        counts["cargo_toml"] += 1
                    elif name_lower.endswith(".nix"):
                        counts["nix"] += 1
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue

    return counts


def host_label() -> str:
    if is_wsl():
        return "WSL"
    return SYSTEM


def match_any(text: str, needles: Tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def read_linux_distro() -> str:
    try:
        distro_info = Path("/etc/os-release").read_text(errors="ignore")
        for line in distro_info.split("\n"):
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "Linux (unknown distro)"


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run(cmd: str, timeout: int = 5) -> str:
    """Run a shell command and return stdout, empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""

def file_exists(*paths) -> bool:
    return any(Path(p).exists() for p in paths)

def dir_exists(*paths) -> bool:
    return any(Path(p).is_dir() for p in paths)

def file_contains(path: str, *patterns: str) -> bool:
    try:
        content = Path(path).read_text(errors="ignore")
        return any(p.lower() in content.lower() for p in patterns)
    except Exception:
        return False

def count_files_in(path: str, pattern: str = "*") -> int:
    try:
        return len(list(Path(path).rglob(pattern)))
    except Exception:
        return 0

def get_shell_rc_files() -> List[Path]:
    if is_windows():
        candidates = [
            HOME / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
            HOME / "Documents" / "PowerShell" / "profile.ps1",
            HOME / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
            HOME / "Documents" / "WindowsPowerShell" / "profile.ps1",
        ]
    else:
        candidates = [
            HOME / ".bashrc", HOME / ".bash_profile", HOME / ".profile",
            HOME / ".zshrc", HOME / ".zprofile",
            HOME / ".fishrc", HOME / ".config" / "fish" / "config.fish",
            HOME / ".tcshrc", HOME / ".cshrc",
        ]
    return [p for p in candidates if p.exists()]

def read_file_safe(path) -> str:
    try:
        return Path(path).read_text(errors="ignore")
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class DevScanner:
    def __init__(self):
        self.score = 0
        self.findings: List[Tuple[int, str, str]] = []  # (points, emoji, message)
        self.warnings: List[str] = []
        self.profile: Dict[str, any] = {}
        # Tracks how many awards have been made per category for diminishing returns.
        # Each additional award in a category is scaled by 1/(1 + n*decay),
        # a hyperbolic decay that compresses bulk tool-stacking without hard caps.
        self._category_counts: Dict[str, int] = {}

    def award(self, points: int, emoji: str, msg: str):
        self.score += points
        self.findings.append((points, emoji, msg))
        
    def penalize(self, points: int, emoji: str, msg: str):
        self.score -= points
        self.findings.append((-points, emoji, msg))

    def category_award(self, category: str, points: int, emoji: str, msg: str, decay: float = 0.25):
        """Award points with hyperbolic diminishing returns within a category.

        The n-th award in *category* is multiplied by:
            factor(n) = 1 / (1 + n * decay)
        where n starts at 0.  This is a well-defined harmonic-series decay that
        asymptotically approaches zero, preventing any single bulk category from
        dominating the score regardless of how many tools a user has installed.

        Example with decay=0.25 and base=8:
            n=0 → 8  (100 %)
            n=1 → 6  ( 80 %)
            n=2 → 5  ( 67 %)
            n=4 → 4  ( 50 %)
            n=9 → 2  ( 29 %)
            n=19→ 1  ( 17 %)
        """
        n = self._category_counts.get(category, 0)
        factor = 1.0 / (1.0 + n * decay)
        effective = max(1, round(points * factor))
        self.award(effective, emoji, msg)
        self._category_counts[category] = n + 1

    def category_penalize(self, category: str, points: int, emoji: str, msg: str, decay: float = 0.25):
        """Penalize with the same hyperbolic diminishing returns."""
        n = self._category_counts.get(category, 0)
        factor = 1.0 / (1.0 + n * decay)
        effective = max(1, round(points * factor))
        self.penalize(effective, emoji, msg)
        self._category_counts[category] = n + 1

    def warn(self, msg: str):
        self.warnings.append(msg)

    def has(self, *commands: str) -> bool:
        return any(cmd_exists(command) for command in commands)

    def apply_rules(self, rules: List[Tuple[Tuple[str, ...], int, str, str]], collector: Optional[List[str]] = None,
                    category: Optional[str] = None, decay: float = 0.25):
        for commands, points, emoji, msg in rules:
            command_tuple = (commands,) if isinstance(commands, str) else commands
            if self.has(*command_tuple):
                if category:
                    if points >= 0:
                        self.category_award(category, points, emoji, msg, decay)
                    else:
                        self.category_penalize(category, abs(points), emoji, msg, decay)
                else:
                    if points >= 0:
                        self.award(points, emoji, msg)
                    else:
                        self.penalize(abs(points), emoji, msg)
                if collector is not None:
                    collector.append(command_tuple[0])

    def first_available(self, commands: Tuple[str, ...]) -> Optional[str]:
        for command in commands:
            if cmd_exists(command):
                return command
        return None

    # ── TIER 1: COMMON — Basic signs of life ──────────────────────────────

    def check_os(self):
        """OS choice is the OG developer personality test."""
        if is_windows():
            wsl = run("wsl.exe -l -q 2>&1") or run("wsl.exe --status 2>&1")
            if wsl.strip():
                self.award(8, "🪟", f"Windows detected... but at least you have WSL (Windows Suffering Layer). Respect.")
                self.profile["os"] = "windows_wsl"
            else:
                self.penalize(20, "🪟", f"Windows detected without WSL. Absolute proprietary slop.")
                self.profile["os"] = "windows"
                self.warn("Uses Windows without WSL. node_modules folder is basically a black hole.")
        elif is_macos():
            mac_ver = platform.mac_ver()[0]
            self.award(5, "🍎", f"macOS {mac_ver}. A developer OR a designer who opened Terminal once.")
            self.profile["os"] = "macos"
        elif is_linux():
            if is_wsl():
                self.award(8, "🪟", "WSL detected! Windows on the outside, Linux on the inside.")
                self.profile["os"] = "wsl"
                return

            distro = read_linux_distro()
            distro_lower = distro.lower()
            linux_rules = [
                (lambda: match_any(distro_lower, ("arch",)), 25, "🏹", "arch", f"Arch Linux! Don't worry, we already know. You've told everyone."),
                (lambda: match_any(distro_lower, ("gentoo",)), 30, "🔮", "gentoo", f"Gentoo! You compile everything from source including your morning coffee."),
                (lambda: match_any(distro_lower, ("nix",)) or file_exists("/etc/nixos"), 35, "❄️", "nixos", f"NixOS detected. Your system.nix is longer than most novels."),
                (lambda: match_any(distro_lower, ("bsd",)) or SYSTEM == "FreeBSD", 35, "🦌", "bsd", f"BSD! You are either very wise or very lost. Possibly both."),
                (lambda: match_any(distro_lower, ("ubuntu",)), 10, "🐧", "ubuntu", f"{distro}. The 'I use Linux btw' starter pack. Comfortable."),
                (lambda: match_any(distro_lower, ("debian",)), 12, "🌀", "debian", f"Debian. Stable. Boring. Like you. (Compliment.)"),
                (lambda: match_any(distro_lower, ("fedora",)), 14, "🎩", "fedora", f"Fedora. For people who want Arch clout but also want their GPU drivers to work."),
                (lambda: match_any(distro_lower, ("mint",)), 8, "🌿", "mint", f"Linux Mint. You showed your friend and said 'Linux is easy!'"),
                (lambda: match_any(distro_lower, ("kali",)), -10, "💀", "kali", f"Kali Linux as a daily driver. Peak script-kiddie cringe."),
                (lambda: match_any(distro_lower, ("pop",)), 11, "🚀", "pop_os", f"Pop!_OS. For gamers who want to feel like real developers."),
            ]

            for matches, pts, emoji, profile, msg in linux_rules:
                if matches():
                    if pts >= 0:
                        self.award(pts, emoji, msg)
                    else:
                        self.penalize(abs(pts), emoji, msg)
                    self.profile["os"] = profile
                    return

            self.award(15, "🐧", f"Linux ({distro}). Exotic taste. Respect.")
            self.profile["os"] = "linux_other"

    def check_shell(self):
        """Your shell is your personality."""
        shell = os.environ.get("SHELL", "")
        shell_lower = shell.lower()
        shell_rules = [
            (("fish",), 14, "🐟", "Fish shell! You love autocomplete more than you love documentation."),
            (("zsh",), 10, "⚡", "Zsh. The trendy shell. Instagram of shells."),
            (("bash",), 4, "💥", "Bash. Classic. Like cargo shorts. Functional, not fashionable."),
            (("dash",), 20, "⚡", "Dash! Minimal. POSIX purist. You probably hate bash for 'bloat'."),
            (("tcsh", "csh"), 8, "🦕", "C shell. You either work in academia or time-traveled from 1985."),
            (("pwsh", "powershell"), 3, "💙", "PowerShell. You're doing your best. We respect the hustle."),
            (("cmd",), -15, "☠️", "CMD.exe as primary shell. Pure, unfiltered suffering."),
        ]

        for needles, pts, emoji, msg in shell_rules:
            if match_any(shell_lower, needles):
                if pts >= 0:
                    self.award(pts, emoji, msg)
                else:
                    self.penalize(abs(pts), emoji, msg)
                    self.warn("CMD as primary shell. Sir, this is a Wendy's.")
                break
        else:
            if shell:
                self.award(12, "🔮", f"Custom shell: {shell}. Mysterious. We like it.")
        self.profile["shell"] = shell

    def check_editor_of_choice(self):
        """The editor wars. The eternal flame."""
        editors_found = []
        
        if cmd_exists("eclipse"):
            self.category_penalize("editors", 15, "☕", "Eclipse installed. Your RAM is crying. Peak enterprise slop.")
            editors_found.append("eclipse")

        if cmd_exists("nvim"):
            nvim_cfg_paths = [
                HOME / ".config" / "nvim" / "init.vim",
                HOME / ".config" / "nvim" / "init.lua",
                HOME / ".config" / "nvim" / "lua",
            ]
            has_real_config = any(Path(p).exists() for p in nvim_cfg_paths)
            if has_real_config:
                lazy = dir_exists(HOME / ".local" / "share" / "nvim" / "lazy")
                packer = dir_exists(HOME / ".local" / "share" / "nvim" / "site" / "pack" / "packer")
                plug = file_exists(HOME / ".local" / "share" / "nvim" / "site" / "autoload" / "plug.vim")
                if lazy or packer or plug:
                    self.category_award("editors", 28, "📝", "Neovim with plugins! You spent 3 days configuring and 1 hour coding.")
                    editors_found.append("nvim_configured")
                else:
                    self.category_award("editors", 20, "📝", "Neovim installed with config. You're on the path. The path hurts.")
                    editors_found.append("nvim_config")
            else:
                self.category_award("editors", 10, "📝", "Neovim installed but no real config. You're a vim poser. It's okay, we won't tell.")
                editors_found.append("nvim_bare")

        if cmd_exists("vim") or cmd_exists("vi"):
            if "nvim_configured" not in editors_found and "nvim_config" not in editors_found:
                vimrc = HOME / ".vimrc"
                vim_cfg = HOME / ".vim" / "vimrc"
                if vimrc.exists() or vim_cfg.exists():
                    content = read_file_safe(vimrc) + read_file_safe(vim_cfg)
                    line_count = len(content.splitlines())
                    if line_count > 100:
                        self.category_award("editors", 20, "🧙", f"Vim with {line_count}-line .vimrc. You are a wizard. A slightly unhinged one.")
                    else:
                        self.category_award("editors", 12, "🧙", "Vim with config. You know :wq without Googling. Respect.")
                else:
                    self.category_award("editors", 2, "🧙", "Vim installed but no .vimrc. Standard issue OS.")

        if cmd_exists("emacs"):
            emacs_cfg = [HOME / ".emacs", HOME / ".emacs.d" / "init.el", HOME / ".config" / "emacs" / "init.el"]
            doom = dir_exists(HOME / ".config" / "doom")
            spacemacs = dir_exists(HOME / ".spacemacs.d")
            if doom:
                self.category_award("editors", 25, "👿", "Doom Emacs. You use Emacs as an OS and Vim keybindings inside it. Maximum chaos.")
            elif spacemacs:
                self.category_award("editors", 20, "🚀", "Spacemacs. You wanted both Emacs and Vim and chose violence.")
            elif any(Path(p).exists() for p in emacs_cfg):
                self.category_award("editors", 22, "🧓", "Emacs with config. M-x butterfly. You are timeless.")
            else:
                self.category_award("editors", 5, "🧓", "Emacs installed. Did you run M-x doctor yet?")

        if cmd_exists("code"):
            self.category_award("editors", 4, "💙", "VSCode installed. You are not a programmer; you are a 'software engineer'.")
            ext_path = HOME / ".vscode" / "extensions"
            if ext_path.exists():
                n_ext = len([d for d in ext_path.iterdir() if d.is_dir()])
                if n_ext > 50:
                    self.category_penalize("editors", 5, "💙", f"VSCode with {n_ext} extensions! It's basically a full, bloated OS at this point.")
                elif n_ext > 20:
                    self.category_award("editors", 2, "💙", f"VSCode with {n_ext} extensions. Building a collection.")

        if cmd_exists("nano"):
            self.category_penalize("editors", 5, "🍌", "Nano is installed. The training wheels never came off.")

        if cmd_exists("hx"):
            self.category_award("editors", 18, "💎", "Helix editor! You're a trendsetter. Or you read too many Rust blogs.")

        if cmd_exists("micro"):
            self.category_award("editors", 3, "🔬", "Micro editor. Nano but you wanted more without committing to vim.")

    def check_package_managers(self):
        """Package managers: the measure of a developer's chaos."""
        pms = []
        self.apply_rules([
            (("snap",), -15, "🐌", "Snap daemon found. Canonical's sluggish proprietary slop."),
            (("flatpak",), 5, "📦", "Flatpak. The acceptable, modern way to sandbox desktop apps."),
            (("nix", "nix-env"), 20, "❄️", "Nix package manager! You hate state and love reproducing builds from 2019."),
            (("apt", "apt-get"), 2, "📦", "APT package manager (Debian/Ubuntu). Stable and standard."),
            (("pacman",), 10, "👻", "Pacman! You are one 'yay -Syu' away from an existential crisis."),
            (("yay", "paru"), 8, "🏹", "AUR helper detected! You install software that 3 people maintain from their basement."),
            (("emerge",), 20, "🔮", "Portage/emerge! You compile packages during lunch. You are Gentoo."),
            (("cargo",), 12, "🦀", "Cargo installed! You've mentioned Rust at least 7 times this week."),
        ], pms, category="pkgmgr", decay=0.30)

        if cmd_exists("brew"):
            pkgs = run("brew list --formula 2>/dev/null | wc -l").strip()
            try:
                n = int(pkgs)
                if n > 100:
                    self.award(8, "🍺", f"Homebrew with {n} packages. Your Mac is basically Linux now.")
                elif n > 30:
                    self.award(5,  "🍺", f"Homebrew with {n} packages. A solid loadout.")
                else:
                    self.award(3,  "🍺", "Homebrew with a few packages. Baby steps.")
            except Exception:
                self.award(3, "🍺", "Homebrew found. The gateway drug to Linux.")
            pms.append("brew")

        tools = [t for t in ["npm", "pnpm", "yarn", "bun"] if cmd_exists(t)]
        if tools:
            if len(tools) > 2:
                self.award(4,  "😵", f"Multiple JS package managers: {', '.join(tools)}. Pick a lane.")
            else:
                self.award(2,  "📦", f"JS package manager(s): {', '.join(tools)}.")
            pms.append("js_pm")

        self.profile["package_managers"] = pms

    # ── TIER 2: UNCOMMON — You've been around the block ──────────────────

    def check_languages(self):
        """Programming languages: your resume vs. reality."""
        # Note: Compilers and low level tools removed from this list to avoid double counting!
        langs = []
        
        self.apply_rules([
            (("php",), -10, "🐘", "PHP. The language of legacy WordPress slop. installed."),
            (("java",), -5, "☕", "Java. Enterprise boilerplate factory. installed."),
            (("matlab",), -15, "📉", "MATLAB. Paying for an array index that starts at 1. installed."),
            (("python3",), 2, "🐍", "Python 3. Standard issue. installed."),
            (("node",), 3, "💚", "Node.js installed."),
            (("deno",), 8, "🦕", "Deno (you said 'npm is too mainstream') installed."),
            (("bun",), 7, "🐢", "Bun.js (you're always chasing the next hotness) installed."),
            (("ruby",), 3, "💎", "Ruby. Found everywhere, loved by some. installed."),
            (("perl",), 2, "🔮", "Perl! It's preinstalled, but maybe you actually use it. installed."),
            (("kotlin",), 8, "🅺", "Kotlin. You graduated from Java and feel smug about it. installed."),
            (("scala",), 15, "⚡", "Scala. You work at a bank or a startup that thinks it's a bank. installed."),
            (("swift",), 8, "🍎", "Swift. You have $99/year opinions. installed."),
            (("rustc",), 15, "🦀", "Rust compiler! Memory safety AND superiority complex. installed."),
            (("go",), 10, "🐹", "Go. You value simplicity over expressiveness. installed."),
            (("elixir",), 18, "💧", "Elixir! Pattern matching and 'fault tolerant' everything. installed."),
            (("erlang",), 22, "📡", "Erlang! You were doing distributed computing before it was cool. installed."),
            (("clojure",), 20, "🧠", "Clojure! Lisp in the JVM. Peak smug. installed."),
            (("ocaml",), 22, "🐪", "OCaml! You either do formal verification or competitive programming. installed."),
            (("zig",), 25, "⚡", "Zig! You read the Zig docs for fun. On weekends. installed."),
            (("lua",), 10, "🌙", "Lua! Neovim plugin dev or game scripting. Respected. installed."),
            (("r",), 10, "📊", "R. You either do data science or biostatistics. Crying either way. installed."),
            (("julia",), 18, "📐", "Julia! Fast and beautiful. Nobody around you knows it exists. installed."),
            (("nim",), 25, "👁️", "Nim! 12 people use this and you're one of them. Elite club. installed."),
            (("crystal",), 22, "💎", "Crystal! Ruby vibes, C performance. Niche and proud. installed."),
            (("dart",), 8, "🎯", "Dart. Flutter dev or Google employee. installed."),
            (("groovy",), 8, "🎸", "Groovy. Jenkins pipeline victim. installed."),
            (("tcl",), 18, "🐍", "Tcl! You are from a different timeline entirely. installed."),
            (("sbcl",), 28, "λ", "Common Lisp (SBCL)! Parentheses all the way down. installed."),
            (("racket",), 20, "🎾", "Racket! You took a PL theory class and never recovered. installed."),
            (("fortran",), 25, "🦕", "Fortran! You are either 80 years old or doing numerical computing. installed."),
            (("cobol",), 30, "🏦", "COBOL! Banks pay you more than God. installed."),
            (("ada",), 30, "✈️", "Ada! Aviation? Defense? You care if planes stay in the sky. installed."),
            (("fpc",), 22, "🎠", "Pascal/FPC! Legendary. Nostalgic. Chaotic. installed."),
        ], langs, category="languages", decay=0.20)
        self.profile["languages"] = langs

    def check_git(self):
        """Git is the biography of your developer soul."""
        if not cmd_exists("git"):
            self.penalize(10, "📁", "Git not found. Are you zipping folders and emailing them to yourself?")
            self.warn("Git not found. You are either a genius or you're using FTP.")
            return

        self.award(2, "🌿", "Git installed. Basic requirement of civilization.")

        gitconfig = HOME / ".gitconfig"
        if gitconfig.exists():
            content = read_file_safe(gitconfig)
            if "name" in content and "email" in content:
                self.award(2, "🌿", "Git configured with name & email. You're not anonymous.")

            alias_count = content.lower().count("[alias]")
            raw_aliases = re.findall(r"^\s+\w+\s*=", content, re.MULTILINE)
            if len(raw_aliases) > 20:
                self.award(10, "🌿", f"Git with {len(raw_aliases)} aliases. Your aliases have aliases.")
            elif len(raw_aliases) > 5:
                self.award(5, "🌿", f"Git aliases: {len(raw_aliases)} shortcuts. Efficiency nerd.")

            if "signingkey" in content.lower():
                self.award(12, "🔐", "GPG-signed commits! You take cryptographic ownership of your disasters.")

            if "delta" in content or "difftastic" in content:
                self.award(8, "🔎", "Git pager configured (delta/difftastic). You care about diffs. Like, really care.")

        repos = run(f'find "{HOME}" -maxdepth 5 -name ".git" -type d 2>/dev/null', timeout=10)
        repo_count = len([r for r in repos.split("\n") if r.strip()]) if repos else 0
        if repo_count > 100:
            self.award(15, "📁", f"{repo_count} git repos! You are a hoarder of unfinished projects.")
        elif repo_count > 30:
            self.award(10, "📁", f"{repo_count} git repos. Many side projects, zero shipped.")
        elif repo_count > 10:
            self.award(5, "📁", f"{repo_count} git repos. Getting started.")
        self.profile["git_repos"] = repo_count

        for tool, pts, emoji, msg in [
            ("git-lfs",   5,  "📦", "git-lfs! Large files. Probably a ML person."),
            ("gh",        8,  "🐙", "GitHub CLI (gh). You live in the terminal and the terminal knows it."),
            ("hub",       5,  "🐙", "hub CLI. OG GitHub terminal user."),
            ("git-crypt", 15, "🔐", "git-crypt! Encrypted secrets in git. Paranoid in the best way."),
            ("tig",       10, "🌳", "tig — terminal git browser! You refuse to touch a GUI. Respected."),
        ]:
            if cmd_exists(tool):
                self.award(pts, emoji, msg)

    def check_docker_and_devops(self):
        """DevOps: because 'it works on my machine' wasn't good enough."""
        has_docker = cmd_exists("docker")
        if has_docker:
            self.award(8, "🐳", "Docker installed. 'It works on my machine' → 'It works in my container'.")
            if cmd_exists("docker-compose") or run("docker compose version 2>/dev/null"):
                self.award(5, "🐳", "Docker Compose. You orchestrate things. Locally. For now.")

        if cmd_exists("kubectl"):
            self.award(18, "☸️",  "kubectl! You manage clusters. Your YAML files have feelings.")
            if cmd_exists("helm"):
                self.award(10, "⛵", "Helm! You package your YAML inside more YAML. Beautiful.")
            if cmd_exists("k9s"):
                self.award(8,  "🐕", "k9s! Kubernetes TUI. You admin clusters from the couch.")
            if cmd_exists("kind") or cmd_exists("minikube"):
                self.award(8, "☸️", "Local Kubernetes. You run a cluster on your laptop. Your fan hates you.")

        if cmd_exists("terraform"):
            self.award(12, "🏗️",  "Terraform! Infrastructure as code. You destroy and recreate cloud resources for fun.")
        if cmd_exists("ansible"):
            self.award(10, "🤖", "Ansible! You automate server config. YAML all the way down.")
        if cmd_exists("pulumi"):
            self.award(12, "🏗️",  "Pulumi! Infra-as-code in a real language. You called Terraform 'too limiting'.")

        if cmd_exists("vagrant"):
            self.award(6, "🧳", "Vagrant. A relic. A classic. Like a flip phone in a smartphone world.")
            
        if cmd_exists("podman") and not has_docker:
            self.award(10, "🦭", "Podman! Rootless containers. You're worried about Docker's daemon and you're right.")

        if cmd_exists("act"):
            self.award(10, "🎬", "act! You run GitHub Actions locally. Debugging CI without pushing. Legendary.")

        clouds = []
        for cloud, pts, emoji, msg in [
            ("aws",    8,  "☁️",  "AWS CLI. Your billing alert emails are truly terrifying."),
            ("gcloud", 8,  "☁️",  "gcloud CLI. Google Cloud. You have BigQuery opinions."),
            ("az",     8,  "☁️",  "Azure CLI. You either work at Microsoft or a corporation that loves Microsoft."),
            ("fly",    8,  "🪰", "Fly.io CLI. You escaped Heroku and never looked back."),
            ("vercel", 6,  "▲",  "Vercel CLI. You ship frontends at the speed of hype."),
            ("wrangler",6, "☁️",  "Wrangler CLI. Cloudflare Workers. Edge computing evangelist."),
        ]:
            if cmd_exists(cloud):
                self.category_award("devops_cloud", pts, emoji, msg, decay=0.30)
                clouds.append(cloud)
        self.profile["clouds"] = clouds

    # ── TIER 3: RARE — Terminal native, unix philosopher ─────────────────

    def check_terminal_tools(self):
        """The sacred tools of the terminal warrior."""
        tools = [
            ("tmux",         15, "🪟", "tmux! You split your terminal and feel infinite power."),
            ("zellij",       12, "🪟", "Zellij! Modern tmux alternative. You have Rust opinions."),
            ("screen",       6,  "📺", "GNU screen. Ancient. Noble. Like a stone tablet."),
            ("fzf",          10, "🔍", "fzf! Fuzzy finder. You've remapped Ctrl+R and never looked back."),
            ("ripgrep",      10, "⚡", "ripgrep (rg)! grep but written in Rust."),
            ("fd",           8,  "⚡", "fd! find but sane. You hate Unix conventions but respect speed."),
            ("bat",          6,  "🦇", "bat! cat with wings. Syntax highlighting in the terminal. Fancy."),
            ("delta",        10, "🔎", "delta! Pretty diffs. You suffer more beautifully than most."),
            ("jq",           10, "🔧", "jq! JSON processor. You parse API responses at the speed of thought."),
            ("yq",           8,  "🔧", "yq! YAML processor. jq but sadder."),
            ("htop",         3,  "📊", "htop! You check CPU usage compulsively."),
            ("btop",         8,  "📊", "btop++! Beautiful system monitor. You care how your CPU load looks."),
            ("glances",      8,  "👀", "Glances! System monitor. Paranoid but stylish."),
            ("neofetch",     5,  "🖼️",  "neofetch! You screenshot your terminal and post it on r/unixporn."),
            ("fastfetch",    8,  "🖼️",  "fastfetch! neofetch but fast. You optimize even your flex."),
            ("onefetch",     10, "📊", "onefetch! git repo info display. You flex your git stats."),
            ("tokei",        10, "📏", "tokei! Code line counter. You know how many lines you've written. Probably lying."),
            ("hyperfine",    12, "⏱️",  "hyperfine! Benchmarking tool. You benchmark even your benchmarks."),
            ("tldr",         4,  "📚", "tldr! man pages for normal humans."),
            ("zoxide",       10, "⚡", "zoxide! Smart cd. You travel your filesystem like a ninja."),
            ("atuin",        12, "🔮", "atuin! Shell history in a database. You worship your past commands."),
            ("nnn",          12, "📁", "nnn! Terminal file manager. GUI is for cowards."),
            ("ranger",       12, "📁", "ranger! vim-inspired file manager. Everything must be vim."),
            ("lf",           10, "📁", "lf! File manager. Lightweight. Go-coded. Minimalist."),
            ("yazi",         12, "📁", "yazi! Blazingly fast file manager. Written in Rust because of course."),
            ("lazydocker",   8,  "🐳", "lazydocker! Docker TUI. You manage containers from a couch."),
            ("glow",         8,  "✨", "glow! Markdown in the terminal. Beautiful and pointless."),
            ("httpie",       8,  "🌐", "HTTPie! curl for humans. You value readability over portability."),
            ("xh",           10, "🌐", "xh! HTTPie clone in Rust. You're on brand."),
            ("nmap",         8,  "🗺️",  "nmap! Network scanner. Either sysadmin or CTF player."),
            ("mtr",          8,  "🌐", "mtr! traceroute meets ping. You debug network paths for fun."),
            ("netcat",       5,  "📡", "netcat! The Swiss Army knife of networking."),
            ("tcpdump",      10, "📡", "tcpdump! Packet capture. You read raw network traffic for fun."),
            ("tshark",       10, "🦈", "tshark! Wireshark in terminal. No GUI needed. Ever."),
            ("wireshark",    10, "🦈", "Wireshark! GUI packet sniffer. You're probably in security."),
            ("strace",       8,  "🔬", "strace! syscall tracer. You debug at the kernel interface."),
            ("ltrace",       8,  "🔬", "ltrace! Library call tracer. You go deeper than strace."),
            ("perf",         10, "⚡", "perf! Linux perf tool. You profile things no one else can see."),
            ("valgrind",     10, "🔬", "Valgrind! Memory debugger. Your C code doesn't leak. Usually."),
            ("gdb",          8,  "🐛", "GDB! GNU debugger. You debug in the raw. No IDE safety net."),
            ("lldb",         8,  "🐛", "LLDB! Apple's debugger. You debug things in assembly sometimes."),
            ("pwndbg",       15, "💀", "pwndbg! GDB extension for exploitation. You're either CTF or red team."),
            ("ghidra",       15, "👁️",  "Ghidra! NSA's reverse engineering tool. You decompile software for fun."),
            ("radare2",      15, "🔮", "Radare2! Hardcore reverse engineering framework. You read assembly like English."),
            ("binwalk",      12, "🔧", "binwalk! Firmware analysis. You extract filesystems from binaries."),
            ("objdump",      5,  "⚙️",  "objdump! You read ELF binaries directly. Based."),
            ("readelf",      5,  "⚙️",  "readelf! ELF inspector. You know your .text from your .bss."),
            ("hexdump",      3,  "🔢", "hexdump! You read hex for fun. Possible robot."),
            ("xxd",          3,  "🔢", "xxd! Hex dump tool. You speak bytes."),
        ]
        
        self.apply_rules([((cmd,), pts, emoji, msg) for cmd, pts, emoji, msg in tools], category="terminal_tools", decay=0.25)
                
        # Exclusive checks to prevent double-point bloat
        if self.has("eza"):
            self.category_award("terminal_tools", 8, "📁", "eza! ls replacement. Color, icons, git status. Maximum customization.")
        elif self.has("exa"):
            self.category_award("terminal_tools", 6, "📁", "exa (old eza)! You care about ls output. Respectable.")

        if self.has("curl"):
            self.category_award("terminal_tools", 2, "🌐", "curl. The original API tester.")
        if self.has("wget"):
            self.category_award("terminal_tools", 2, "📥", "wget. You download files like a person of culture.")

    def check_shell_customization(self):
        """How deep does the rabbit hole go?"""
        rc_files = get_shell_rc_files()
        total_aliases = 0
        total_functions = 0
        total_lines = 0
        all_content = ""

        for rc in rc_files:
            content = read_file_safe(rc)
            all_content += content
            total_lines += len(content.splitlines())
            total_aliases += content.count("alias ")
            total_aliases += len(re.findall(r"(?im)^\s*(?:Set|New)-Alias\b", content))
            total_functions += len(re.findall(r"^function\s+\w+|^\w+\s*\(\s*\)\s*\{", content, re.MULTILINE))

        if total_aliases > 50:
            self.award(15, "⚙️", f"{total_aliases} shell aliases! Your shell has more shortcuts than a Windows power user's desktop.")
        elif total_aliases > 20:
            self.award(8, "⚙️",  f"{total_aliases} aliases. Comfortable efficiency.")
        elif total_aliases > 5:
            self.award(4, "⚙️",  f"{total_aliases} aliases. Getting started.")

        if total_functions > 20:
            self.award(12, "⚙️", f"{total_functions} custom shell functions. You basically wrote a second shell.")
        elif total_functions > 5:
            self.award(6, "⚙️",  f"{total_functions} shell functions. Automation beginning.")

        if total_lines > 500:
            self.award(15, "📜", f"Shell configs total {total_lines} lines. Your .zshrc is a masterpiece and a warning.")
        elif total_lines > 200:
            self.award(8,  "📜", f"Shell configs: {total_lines} lines. Respectable.")

        if "oh-my-zsh" in all_content or dir_exists(HOME / ".oh-my-zsh"):
            self.award(8, "😱", "Oh My Zsh! You install themes that take 2 seconds to load. Worth it?")
        if "zinit" in all_content or "antibody" in all_content or "antigen" in all_content:
            self.award(10, "⚡", "Zinit/Antigen/Antibody! Managing zsh plugins with a plugin manager.")
        if "prezto" in all_content:
            self.award(10, "🎩", "Prezto! Oh My Zsh's refined sibling.")
        if "p10k" in all_content or file_exists(HOME / ".p10k.zsh"):
            self.award(10, "⚡", "Powerlevel10k! Your prompt renders a Nerd Font glyph for your git status. Iconic.")
        if "starship" in all_content or cmd_exists("starship"):
            self.award(10, "🚀", "Starship prompt config in shell! Cross-shell prompt. Truly unbiased.")

        if "pyenv" in all_content or cmd_exists("pyenv"):
            self.award(8, "🐍", "pyenv! Because python3 vs python is a war that never ends.")
        if "nvm" in all_content or cmd_exists("nvm") or dir_exists(HOME / ".nvm"):
            self.award(8, "💚", "nvm! Node version manager. Because breaking changes every 6 months.")
        if "rbenv" in all_content or cmd_exists("rbenv"):
            self.award(8, "💎", "rbenv! Ruby version manager. You fight rails compatibility issues.")
        if "asdf" in all_content or cmd_exists("asdf"):
            self.award(12, "🔧", "asdf! One version manager to rule them all. A developer of taste.")
        if "mise" in all_content or cmd_exists("mise"):
            self.award(12, "🔧", "mise! Modern asdf. Rust-based. On trend.")
        if "direnv" in all_content or cmd_exists("direnv"):
            self.award(10, "📁", "direnv! Per-directory env vars. Project isolation perfectionist.")

    def check_dotfiles(self):
        """The dotfiles: the developer's soul made visible."""
        if is_windows():
            return

        dotfile_dirs = [
            HOME / ".dotfiles",
            HOME / "dotfiles",
            HOME / ".config" / "dotfiles",
        ]
        for d in dotfile_dirs:
            if d.is_dir() and (d / ".git").is_dir():
                file_count = count_files_in(str(d), "*")
                self.award(20, "🗂️", f"Dotfiles git repo at {d} with ~{file_count} files! You could rebuild your environment from scratch. Impressive and sad.")
                break

        if cmd_exists("stow"):
            self.award(10, "🔗", "GNU Stow! You manage dotfiles with symlinks like a proper unix sorcerer.")
        if cmd_exists("chezmoi"):
            self.award(12, "🏠", "chezmoi! Dotfiles manager. You template your dotfiles. Your configs have conditionals.")
        if cmd_exists("yadm"):
            self.award(10, "🌳", "yadm! Git wrapper for dotfiles. Pure elegance.")

        ssh_dir = HOME / ".ssh"
        if ssh_dir.exists():
            keys = list(ssh_dir.glob("id_*"))
            priv_keys = [k for k in keys if not k.name.endswith(".pub")]
            if len(priv_keys) > 3:
                self.award(15, "🔑", f"{len(priv_keys)} SSH private keys! You manage many servers or have commitment issues.")
            elif len(priv_keys) > 0:
                self.award(5, "🔑", f"{len(priv_keys)} SSH key(s). You deploy things. Or try to.")

            ssh_config = ssh_dir / "config"
            if ssh_config.exists():
                content = read_file_safe(ssh_config)
                host_count = content.count("Host ")
                if host_count > 10:
                    self.award(12, "🔑", f"SSH config with {host_count} hosts! You're managing an empire.")
                elif host_count > 3:
                    self.award(6, "🔑",  f"SSH config with {host_count} hosts. You've got servers.")

        gpg_output = run("gpg --list-keys 2>/dev/null")
        if gpg_output and "pub" in gpg_output:
            key_count = gpg_output.count("pub")
            self.award(10, "🔐", f"GPG keyring with {key_count} key(s). You encrypt your emails. You send emails to 0 people but they're encrypted.")

    def check_node_modules(self):
        """The node_modules folder: a monument to dependency hell."""
        nm_dirs = find_node_modules()
        if len(nm_dirs) > 30:
            self.penalize(10, "📦", f"{len(nm_dirs)}+ node_modules directories found. Maximum JavaScript slop. Your SSD is begging for mercy.")
            self.warn(f"node_modules found in {len(nm_dirs)} locations. Your disk cries. Have you heard of pnpm?")
        elif len(nm_dirs) > 10:
            self.award(2, "📦", f"{len(nm_dirs)} node_modules dirs. Moderate dependency chaos.")
        elif len(nm_dirs) > 0:
            self.award(2, "📦", f"{len(nm_dirs)} node_modules dirs. You've touched JavaScript. That's okay.")
        self.profile["node_modules_count"] = len(nm_dirs)

    # ── TIER 4: EPIC — Power user, deep unix rabbit hole ─────────────────

    def check_tiling_wm_and_desktop(self):
        """Window managers: the final form of procrastination."""
        if is_linux() or is_wsl():
            wm_checks = [
                ("i3",       25, "🪟", "i3wm! Tiling window manager. You tile everything. Even your thoughts."),
                ("sway",     28, "🌊", "Sway! i3 for Wayland. You're on the bleeding edge. It occasionally cuts."),
                ("hyprland", 25, "💫", "Hyprland! Wayland compositor. Your animations are smoother than your social skills."),
                ("bspwm",    25, "🌳", "bspwm! Binary space partitioning. You organize windows like a BST."),
                ("dwm",      30, "⚙️",  "dwm! Dynamic window manager. You compiled your WM from source. On brand."),
                ("qtile",    22, "🐍", "Qtile! Tiling WM in Python. You configure your WM with code."),
                ("awesome",  25, "🌟", "Awesome WM! Lua-configured tiling. Dual name — ironically true."),
                ("xmonad",   30, "λ",  "XMonad! Haskell-configured WM. You write type-safe window tiling logic."),
                ("leftwm",   25, "🦀", "LeftWM! Rust-written tiling WM. Everything must be Rust."),
                ("herbstluftwm", 28, "🍃", "herbstluftwm! If you can spell it, you deserve points."),
                ("openbox",  10, "📦", "Openbox! Minimal floating WM. Lightweight and no-nonsense."),
                ("fluxbox",  12, "📦", "Fluxbox! Retro minimal WM. You've been doing Linux since 2003."),
            ]
            for cmd, pts, emoji, msg in wm_checks:
                if cmd_exists(cmd):
                    self.category_award("wm", pts, emoji, msg, decay=0.40)

            if os.environ.get("WAYLAND_DISPLAY"):
                self.award(10, "🌊", "Running Wayland! You've moved on from X11. Brave new world.")

        for term, pts, emoji, msg in [
            ("kitty",    12, "🐱", "Kitty terminal! GPU-accelerated. Your terminal renders faster than most webpages."),
            ("alacritty",12, "⚡", "Alacritty! Rust-written, GPU-accelerated terminal. Speed and ideology."),
            ("wezterm",  12, "✨", "WezTerm! Lua-configured terminal. More powerful than most IDEs."),
            ("foot",     10, "🦶", "Foot terminal! Minimal Wayland terminal. Purist."),
            ("urxvt",    15, "🦕", "URxvt! Ancient. Venerable. Your config file is older than some colleagues."),
            ("st",       20, "⚙️",  "st (simple terminal)! You compiled your own terminal. suckless philosophy detected."),
            ("xterm",    5,  "🖥️",  "xterm! The original. Respect for the classics."),
            ("rio",      10, "🌊", "Rio terminal! Blazingly fast. Written in Rust. Of course."),
            ("ghostty",  12, "👻", "Ghostty! The hottest new terminal. You read tech Twitter."),
        ]:
            if cmd_exists(term):
                self.category_award("terminal_emu", pts, emoji, msg, decay=0.40)

    def check_fonts_and_ricing(self):
        """r/unixporn would approve."""
        nerd_font_names = ["NerdFont", "Nerd Font", "JetBrainsMono", "FiraCode", "Hack", "Inconsolata", "CascadiaCode", "MesloLG", "SourceCodePro"]
        font_dirs = [
            HOME / ".local" / "share" / "fonts",
            HOME / ".fonts",
            Path("/usr/local/share/fonts"),
            Path("/usr/share/fonts"),
            HOME / "Library" / "Fonts",
        ]
        found_nerd = False
        for fd in font_dirs:
            if fd.is_dir():
                try:
                    for f in fd.rglob("*.ttf"):
                        for nf in nerd_font_names:
                            if nf.lower() in f.name.lower():
                                found_nerd = True
                                break
                        if found_nerd:
                            break
                except Exception:
                    pass
            if found_nerd:
                break

        if found_nerd:
            self.award(10, "🎨", "Nerd Fonts installed! Your terminal glyphs are works of art. r/unixporn approved.")

        if cmd_exists("picom") or cmd_exists("compton"):
            self.award(10, "✨", "Picom/Compton compositor! Transparency, shadows, blur. Peak aesthetics.")

        if cmd_exists("pywal") or cmd_exists("wal"):
            self.award(15, "🎨", "pywal! Your entire desktop color scheme changes with your wallpaper. Maximum rice.")
        elif cmd_exists("wpg") or cmd_exists("wpgtk"):
            self.award(12, "🎨", "wpgtk! Wallpaper-based theming. You're deep in the rice rabbit hole.")

        if cmd_exists("rofi"):
            self.award(10, "🚀", "Rofi launcher! Your app launcher is configured in CSS and it's beautiful.")
        elif cmd_exists("dmenu"):
            self.award(8, "⚙️", "dmenu! Minimalist launcher. Suckless philosophy. Your menu has no rounded corners.")
        
        if cmd_exists("wofi") or cmd_exists("fuzzel"):
            self.award(10, "🌊", "Wayland launcher (wofi/fuzzel). You've fully committed to Wayland.")

        if cmd_exists("polybar"):
            self.award(12, "📊", "Polybar! Custom status bar. Your taskbar is a work of art that nobody sees but you.")
        if cmd_exists("waybar"):
            self.award(12, "🌊", "Waybar! Wayland status bar. Modern and configurable.")
        if cmd_exists("eww"):
            self.award(18, "🔮", "eww (Elkowar's Wacky Widgets)! You build desktop widgets in Yuck (a Lisp-like DSL). Certified maniac.")

    def check_programming_indicators(self):
        """The sacred scrolls of code on your disk."""
        script_dirs = [HOME / "scripts", HOME / "bin", HOME / ".local" / "bin", HOME / ".bin"]
        for d in script_dirs:
            if d.is_dir():
                scripts = list(d.glob("*"))
                n = len(scripts)
                if n > 20:
                    self.award(15, "📜", f"{n} personal scripts in {d.name}/. You automate everything, including brewing coffee.")
                elif n > 5:
                    self.award(8, "📜",  f"{n} scripts in {d.name}/. Automation in progress.")
                elif n > 0:
                    self.award(4, "📜",  f"{n} scripts in {d.name}/.")

        crontab = run("crontab -l 2>/dev/null")
        if (is_linux() or is_wsl()) and crontab and "#" not in crontab[:5]:
            job_count = len([l for l in crontab.splitlines() if l.strip() and not l.startswith("#")])
            if job_count > 0:
                self.award(12, "⏰", f"{job_count} cron job(s)! Your computer does things while you sleep. Possibly mine crypto.")

        if is_linux() or is_wsl():
            systemd_user = HOME / ".config" / "systemd" / "user"
            if systemd_user.is_dir():
                services = list(systemd_user.glob("*.service"))
                if services:
                    self.award(18, "⚙️", f"{len(services)} systemd user service(s). You write services for your personal projects. Unhinged. Respect.")

        project_counts = scan_project_markers(max_depth=5, time_budget=1.5)
        make_count = project_counts["makefile"] + project_counts["justfile"]
        if make_count > 10:
            self.award(10, "⚙️", f"{make_count} Makefiles/Justfiles. You automate your automation.")
        elif make_count > 3:
            self.award(5, "⚙️",  f"{make_count} Makefiles/Justfiles.")

        rust_projects = project_counts["cargo_toml"]
        if rust_projects > 5:
            self.award(15, "🦀", f"{rust_projects} Rust projects. You believe in memory safety and you're not shy about it.")
        elif rust_projects > 0:
            self.award(8, "🦀",  f"{rust_projects} Rust project(s). The journey begins.")

        nix_files = project_counts["nix"]
        if nix_files > 10:
            self.award(20, "❄️", f"{nix_files} Nix expression files! Your system is reproducible. Unlike your sleep schedule.")
        elif nix_files > 0:
            self.award(10, "❄️", f"{nix_files} Nix file(s). You're on the path to purity.")

    # ── TIER 5: LEGENDARY — Elite signals ────────────────────────────────

    def check_compilers_and_low_level(self):
        """The deep lore. The C programmers. The kernel hackers."""
        self.apply_rules([
            ("gcc",     3,  "⚙️",  "GCC installed. You compile C. Respect."),
            ("clang",   5,  "⚙️",  "Clang! LLVM-based. You care about error messages."),
            ("llc",     15, "⚙️",  "llc! LLVM compiler backend. You work with IR. Not human."),
            ("nasm",    15, "🔩", "NASM assembler! You write x86 assembly. You are the machine."),
            ("as",      5,  "🔩", "GNU Assembler! You assemble things. From bits."),
            ("ld",      5,  "🔗", "GNU linker! You link things manually. You understand the ELF format."),
            ("make",    3,  "🔨", "make! You orchestrate builds. Makefile syntax is your second language."),
            ("cmake",   5,  "🔨", "CMake! C/C++ project generator. Your CMakeLists.txt is 800 lines."),
            ("meson",   10, "🔨", "Meson build system! You escaped CMake and have opinions about it."),
            ("ninja",   10, "⚡", "Ninja build tool! Fast builds. You work on large codebases."),
            ("bazel",   15, "🏗️",  "Bazel! Google-style build system. Your monorepo is a lifestyle."),
            ("buck2",   15, "🏗️",  "Buck2! Meta's build system. Speed is your religion."),
            ("gfortran",15, "🦕", "GFortran! Fortran compiler. Numerical computing or pure nostalgia."),
            ("ocamlfind",20,"🐪", "OCamlfind! OCaml package finder. Functional and formal."),
            ("ghc",     28, "λ",  "GHC! Haskell compiler. You think in monads. Casually."),
            ("idris2",  25, "🔮", "Idris 2! Dependently typed. Your types are theorems. You are insane (genius)."),
        ])

        if is_linux() or is_wsl():
            if self.has("dkms"):
                self.award(15, "⚙️", "DKMS! Dynamic Kernel Module Support. You manage out-of-tree kernel modules.")
            modules_dir = Path("/lib/modules")
            if modules_dir.is_dir():
                kernels = [d for d in modules_dir.iterdir() if d.is_dir()]
                if len(kernels) > 3:
                    self.award(15, "🐧", f"{len(kernels)} kernel versions installed! You keep old kernels 'just in case'. Hoarder. Hero.")
                    self.warn("Multiple kernel versions found. You've been 'just in case' boot-loop-proofing since 2018.")

        cross_tools = ["arm-linux-gnueabi-gcc", "aarch64-linux-gnu-gcc", "mips-linux-gnu-gcc", "riscv64-linux-gnu-gcc"]
        cross_found = [t for t in cross_tools if self.has(t)]
        if cross_found:
            self.award(30, "🔩", f"Cross-compiler(s) found: {', '.join(cross_found)}! You compile for architectures your laptop can't run. Based.")

        if self.has("avr-gcc", "avrdude"):
            self.award(25, "🤖", "AVR toolchain! You program microcontrollers. Byte-level everything.")
        if self.has("arm-none-eabi-gcc"):
            self.award(25, "🤖", "ARM bare-metal toolchain! Embedded systems. You write code that runs on PCBs.")
        if self.has("pio"):
            self.award(15, "🤖", "PlatformIO! Embedded dev. Arduino grown up.")
        if self.has("qemu", "qemu-system-x86_64"):
            self.award(20, "🖥️",  "QEMU! Virtual machines from the terminal. You run operating systems as a hobby.")
        if self.has("bochs"):
            self.award(30, "🖥️",  "Bochs! x86 emulator. You debug OS kernels and boot sectors.")

    def check_security_tools(self):
        """For the defenders and the 'researchers'."""
        sec_tools = [
            ("burpsuite",    12, "🕷️",  "Burp Suite! Web app pentesting. You intercept HTTP for fun."),
            ("zaproxy",      12, "🕷️",  "OWASP ZAP! Web security scanner. Defender or attacker?"),
            ("sqlmap",       12, "💉", "sqlmap! Automated SQL injection. Your queries have subqueries."),
            ("hashcat",      15, "🔐", "Hashcat! Password cracking. You own it. Probably yours."),
            ("john",         12, "🔐", "John the Ripper! Password cracker classic. Old school."),
            ("aircrack-ng",  15, "📡", "Aircrack-ng! WiFi hacking toolkit. Your neighbors should change passwords."),
            ("hydra",        15, "🐍", "Hydra! Brute forcer. You have multi-headed attack patterns."),
            ("nikto",        10, "🔍", "Nikto! Web server scanner. You probe things."),
            ("gobuster",     10, "👻", "Gobuster! Directory brute-forcer. You find hidden paths."),
            ("ffuf",         10, "⚡", "ffuf! Fuzzing web apps at the speed of Go."),
            ("ncrack",       10, "🔐", "ncrack! Network authentication cracker."),
            ("openssl",      5,  "🔒", "OpenSSL! You generate certs and question CA trust."),
            ("fail2ban",     12, "🛡️",  "Fail2ban! You protect servers. Someone keeps knocking."),
            ("snort",        15, "🐽", "Snort! IDS/IPS. You monitor network traffic like a hawk."),
            ("suricata",     18, "🐯", "Suricata! High-performance IDS. Serious network security."),
            ("yara",         20, "🦟", "YARA! Malware pattern matching. Malware analyst or researcher."),
            ("volatility",   15, "🧠", "Volatility! Memory forensics framework. You examine RAM dumps."),
        ]
        self.apply_rules([((cmd,), pts, emoji, msg) for cmd, pts, emoji, msg in sec_tools])

        # Handle MSF without double-counting
        if self.has("msfconsole"):
            self.award(15, "💀", "msfconsole! Metasploit console. Pentest credentials confirmed.")
        elif self.has("metasploit-framework"):
            self.award(15, "💀", "Metasploit! You find exploits or you find exploits. Red team detected.")

        sshd_config = "/etc/ssh/sshd_config"
        if (is_linux() or is_wsl()) and file_exists(sshd_config):
            content = read_file_safe(sshd_config)
            if "PermitRootLogin no" in content:
                self.award(10, "🔒", "SSH configured to deny root login. Basic sysadmin hygiene. Appreciated.")
            if "PasswordAuthentication no" in content:
                self.award(15, "🔒", "SSH password authentication disabled! Keys only. You don't trust passwords.")

    def check_ai_ml_tools(self):
        """The new hotness. The thing that's definitely not replacing us."""
        ml_tools = [
            ("ollama",     10, "🤖", "Ollama! Running LLMs locally. You run AI models so you can ask them why your code doesn't work."),
            ("llama.cpp",  12, "🦙", "llama.cpp! You compile and run LLMs from source. C++ ML enjoyer."),
            ("nvtop",      8,  "🎮", "nvtop! GPU monitoring. You train models and watch VRAM like a hawk."),
            ("nvidia-smi", 8,  "🎮", "nvidia-smi! You have a GPU and you know its utilization at all times."),
            ("rocm-smi",   8,  "🎮", "ROCm tools! AMD GPU compute. You support the underdog."),
            ("jupyter",    5,  "📓", "Jupyter! You write code in cells and call it a notebook."),
            ("ipython",    5,  "🐍", "IPython! Interactive Python. REPL for the discerning Pythonista."),
            ("mlflow",     15, "📈", "MLflow! ML experiment tracking. You track your model metrics religiously."),
            ("wandb",      12, "🔮", "Weights & Biases! You log experiments to the cloud and watch graphs."),
            ("dvc",        12, "📦", "DVC! Data version control. git for data. You're serious about ML."),
        ]
        self.apply_rules([((cmd,), pts, emoji, msg) for cmd, pts, emoji, msg in ml_tools])

        if self.has("nvcc"):
            self.award(20, "⚡", "NVCC! CUDA compiler! You write GPU kernels. Your code runs on silicon at scale.")
        if self.has("rocminfo", "clinfo"):
            self.award(15, "⚡", "GPU compute tools (ROCm/OpenCL) installed. Heterogeneous computing enjoyer.")

        if self.has("huggingface-cli"):
            self.award(10, "🤗", "Hugging Face CLI! You download models like normal people download songs.")

    # ── TIER 6: MYTHICAL ─────────────────────────────────────────────────

    def check_legendary_stuff(self):
        """Signs of transcendence."""
        if is_linux() or is_wsl():
            kernel_conf = run("ls /boot/config-* 2>/dev/null")
            if kernel_conf:
                proc_config = run("zcat /proc/config.gz 2>/dev/null | wc -l")
                try:
                    if int(proc_config) > 0:
                        self.award(35, "🐧", "Custom kernel config accessible via /proc! You compile Linux kernels. You are Linux.")
                except Exception:
                    pass

        self.apply_rules([
            ("latex",    15, "📄", "LaTeX installed! You typeset mathematics and hate Word users."),
            ("pdflatex", 15, "📄", "pdflatex! You write papers in LaTeX and compile them manually."),
            ("xelatex",  18, "📄", "XeLaTeX! Unicode and custom fonts in LaTeX. Typesetting perfectionist."),
            ("lualatex", 18, "📄", "LuaLaTeX! LaTeX with Lua scripting. Over-engineer even your documents."),
            ("bibtex",   12, "📚", "BibTeX! You manage references in plaintext files. Academic detected."),
        ])

        lex_tools = ["flex", "bison", "antlr4", "yacc"]
        found_lex = [t for t in lex_tools if self.has(t)]
        if found_lex:
            self.award(30, "🔮", f"Lexer/parser tools found: {', '.join(found_lex)}! You write compilers for fun. Or class. Either way, you suffer beautifully.")

        self.apply_rules([
            ("lean",     45, "🧮", "Lean theorem prover! You write mathematical proofs as programs. You are beyond programming."),
            ("coq",      45, "🧮", "Coq proof assistant! 'My code doesn't have bugs' — proven by type theory."),
            ("agda",     45, "🧮", "Agda! Dependent types as a lifestyle. You are not a software engineer. You are a mathematician."),
            ("isabelle", 45, "🧮", "Isabelle! Interactive theorem prover. Your hobby is formally verifying software."),
        ])

        self.apply_rules([
            ("tcc",      20, "⚡", "TinyCC! Minimal C compiler. You like your tools small and fast."),
            ("musl-gcc", 25, "⚙️",  "musl-libc gcc! Minimal C library. You link against musl for purity."),
            ("plan9port", 40, "🔮", "Plan 9 from Bell Labs tools! You are a UNIX philosopher and archaeologist."),
            ("9",        35, "🔮", "Plan 9's shell! You have transcended Unix into the realm of Bell Labs lore."),
            ("sam",      35, "📝", "Sam editor (Plan 9)! Rob Pike's editor. You have strong opinions on text editing."),
            ("acme",     35, "📝", "Acme editor! Plan 9 editor. Mouse-driven. Non-modal. Controversial."),
            ("factor",   30, "🧮", "Factor language! Stack-based concatenative language. Postfix everything."),
            ("j",        35, "📊", "J language! Array programming. You write entire algorithms in 3 characters."),
            ("apl",      40, "🔣", "APL! Array programming with special symbols. You type with a different keyboard layout. Omega chad."),
            ("k",        38, "📊", "K language! Financial array programming. 3 characters, 40 operations."),
            ("q",        35, "💹", "Q/KDB+! Financial databases. You work in finance or academic research."),
            ("forth",    35, "🔩", "Forth! Stack-based language. Compact. Powerful. For embedded and minimalists."),
        ])

        for irc_tool in ["weechat", "irssi", "hexchat", "catgirl"]:
            if self.has(irc_tool):
                self.award(15, "📡", f"{irc_tool}! IRC client. You use chat protocols from 1988. Timeless.")
                break

        if file_exists(HOME / "flake.nix") or file_exists(HOME / ".config" / "home-manager" / "flake.nix"):
            self.award(35, "❄️", "Nix Flake in home/config! Your entire system is reproducible and your friends don't understand why.")

        if self.has("home-manager"):
            self.award(30, "❄️", "home-manager! You manage your user environment with Nix. Fully declarative. Fully committed.")

        if self.has("guix"):
            self.award(40, "🐃", "GNU Guix! Purely functional package manager. You follow Richard Stallman's path but make it Haskell-adjacent.")

    # ── EXTENDED CHECKS — Modern stack signals ────────────────────────────

    def check_databases(self):
        """Databases on disk are a confident signal of a real backend developer."""
        confirmed: List[str] = []
        rules = [
            (("psql", "postgres"),    14, "🐘", "PostgreSQL client. The database for people who care about correctness."),
            (("mysql",),               6, "🐬", "MySQL client. Pragmatic, scarred, employed."),
            (("mariadb",),             8, "🦭", "MariaDB. You picked the fork. You read licensing news."),
            (("sqlite3",),             6, "📄", "sqlite3. The most-deployed database on Earth lives on your disk."),
            (("redis-cli",),          10, "🟥", "redis-cli. Cache, queue, lock, leaderboard. Swiss-army key/value store."),
            (("mongosh", "mongo"),     6, "🍃", "MongoDB shell. Documents schemas at runtime. We forgive you."),
            (("duckdb",),             18, "🦆", "DuckDB. Analytical SQL on a laptop. Peak modern data engineering taste."),
            (("clickhouse-client",),  18, "📊", "ClickHouse. Columnar OLAP at terrifying speed. You eat petabytes for breakfast."),
            (("cockroach",),          20, "🪳", "CockroachDB. Distributed SQL. Resilient like its namesake."),
            (("surreal",),            18, "🌀", "SurrealDB. Multi-model. You read product launches the day they ship."),
            (("influx",),             10, "📈", "InfluxDB. Time-series specialist. You graph everything, including your sleep."),
            (("etcdctl",),            14, "🗝️",  "etcdctl. Distributed consensus storage. Kubernetes-adjacent power user."),
            (("cqlsh",),              16, "🌌", "Cassandra (cqlsh). Wide-column, eventual-consistency lifestyle."),
            (("scylla",),             18, "🐉", "ScyllaDB. C++ Cassandra. You measure latency in microseconds."),
            (("neo4j",),              16, "🕸️",  "Neo4j. Graphs everywhere. Your data model has edges and feelings."),
            (("dgraph",),             18, "🕸️",  "Dgraph. Distributed graph DB. You picked the niche fork of niche."),
            (("rqlite",),             18, "🪨", "rqlite. Distributed SQLite. You like contradictions."),
            (("timescaledb-tune",),   16, "⏳", "TimescaleDB tuner. Postgres for time-series. Refined taste."),
            (("pgcli",),              10, "🐘", "pgcli. Autocompleting Postgres shell. You don't tolerate raw psql."),
            (("mycli",),               6, "🐬", "mycli. Autocompleting MySQL shell. Civilised."),
            (("litecli",),             8, "📄", "litecli. Autocompleting SQLite shell. You polish even the small things."),
            (("usql",),               14, "🔌", "usql. Universal SQL CLI. You speak every dialect."),
        ]
        self.apply_rules(rules, confirmed)
        self.profile["databases"] = confirmed

    def check_web_servers_and_proxies(self):
        """Reverse proxies, load balancers, real-deal HTTP daemons."""
        servers: List[str] = []
        rules = [
            (("nginx",),     8,  "🌐", "nginx. The reverse proxy of the modern web."),
            (("apache2", "httpd"), 4, "🪶", "Apache. Battle-tested, .htaccess-cursed, still serving."),
            (("caddy",),    14, "🍬", "Caddy. Automatic HTTPS by default. You demand sane defaults."),
            (("lighttpd",), 12, "🪶", "lighttpd. Embedded-grade web server. Minimalist."),
            (("traefik",),  14, "🚦", "Traefik. Service-discovery reverse proxy. Container-native router."),
            (("envoy",),    18, "✉️",  "Envoy. The proxy that runs the modern service mesh."),
            (("haproxy",),  12, "🧭", "HAProxy. Layer-4/7 load balancing without compromise."),
            (("varnish", "varnishd"), 14, "🪞", "Varnish. HTTP caching at scale. You speak VCL."),
            (("consul",),   14, "🗺️",  "HashiCorp Consul. Service discovery and KV. Networking nerd."),
            (("nomad",),    16, "🪖", "Nomad. Workload orchestration without Kubernetes ceremony."),
            (("vault",),    16, "🏦", "HashiCorp Vault. Secrets-as-a-service. You take leakage seriously."),
            (("nats", "nats-server"), 14, "📨", "NATS. Tiny, fast pub/sub messaging. Distributed-systems builder."),
            (("step",),     12, "🪪", "step CLI. Internal PKI. You issue your own certificates."),
            (("mkcert",),    8, "🔏", "mkcert. Local trusted dev certs. No more SSL warnings in dev."),
        ]
        self.apply_rules(rules, servers)
        self.profile["web_servers"] = servers

    def check_observability(self):
        """Metrics, traces, logs — the holy trinity of production maturity."""
        signals: List[str] = []
        rules = [
            (("prometheus",),         14, "🔥", "Prometheus. Pull-based metrics. Production-grade observability."),
            (("promtool",),           10, "🔥", "promtool. You lint your alerting rules."),
            (("grafana-server",),     12, "📊", "Grafana server installed. Your dashboards have dashboards."),
            (("loki",),               14, "🪵", "Loki. Log aggregation, Prometheus-style. Modern logging stack."),
            (("tempo",),              14, "⏱️",  "Tempo. Distributed tracing storage. Span-curious."),
            (("jaeger",),             14, "🔭", "Jaeger. Distributed tracing. You've debugged across services."),
            (("otelcol", "otelcol-contrib"), 16, "🛰️",  "OpenTelemetry Collector. Vendor-neutral telemetry pipeline."),
            (("vector",),             16, "🌊", "Vector. High-performance log/metric pipeline in Rust."),
            (("fluent-bit", "fluentd"), 12, "🪡", "Fluent forwarder. Log shipping, properly."),
            (("datadog-agent",),      10, "🐶", "Datadog Agent. Your billing department weeps. Quietly."),
            (("newrelic-cli",),        8, "🆕", "New Relic CLI. APM enthusiast."),
            (("sentry-cli",),         10, "🛡️",  "Sentry CLI. You ship release tracking with your deploys."),
            (("uptime",),              4, "⏲️",  "uptime. System monitoring basic literacy."),
        ]
        self.apply_rules(rules, signals)
        self.profile["observability"] = signals

    def check_testing_and_quality(self):
        """Test runners, fuzzers, linters — the difference between code and software."""
        tests: List[str] = []
        rules = [
            (("pytest",),         8,  "🧪", "pytest. The Python test runner of taste."),
            (("tox",),            8,  "📦", "tox. Multi-env Python testing. You test the matrix."),
            (("nox",),            8,  "🦊", "nox. tox in Python. You picked the modern fork."),
            (("hypothesis",),    14,  "🎲", "hypothesis. Property-based testing in Python. You think in invariants."),
            (("jest",),           6,  "🃏", "jest. JS testing default. Reliable."),
            (("vitest",),         8,  "⚡", "vitest. Vite-era test runner. You like fast feedback loops."),
            (("mocha",),          6,  "☕", "mocha. Classic JS test runner. Old guard."),
            (("playwright",),    14,  "🎭", "Playwright. End-to-end browser testing. You actually test the UI."),
            (("cypress",),       12,  "🌲", "Cypress. Browser test runner. You ship E2E with confidence."),
            (("selenium-side-runner",), 8, "🧭", "Selenium. Veteran browser automation."),
            (("k6",),            14,  "🏋️",  "k6. Load testing in JavaScript. You break things deliberately."),
            (("locust",),        12,  "🦗", "Locust. Load testing in Python. Performance-curious."),
            (("ab",),             4,  "📈", "ab (ApacheBench). Simple, brutal, effective."),
            (("wrk",),           10,  "💪", "wrk. Modern HTTP benchmarking. You measure tail latency."),
            (("siege",),          8,  "🏰", "siege. HTTP load testing classic."),
            (("afl-fuzz", "afl-clang"), 22, "🧬", "AFL fuzzer. You feed random bytes to programs and watch them die."),
            (("honggfuzz",),     22,  "🧬", "honggfuzz. Coverage-guided fuzzing. Memory-safety crusader."),
            (("libfuzzer",),     20,  "🧬", "libfuzzer. In-process fuzzing. Defensive-programming maximalist."),
            # Linters / formatters
            (("ruff",),          10,  "🦊", "ruff. The Python linter that broke the speed sound barrier."),
            (("black",),          5,  "⚫", "black. Opinionated Python formatter. You stopped arguing about commas."),
            (("isort",),          4,  "🔤", "isort. Sorted imports. Order matters."),
            (("mypy",),          10,  "🔠", "mypy. Static types in Python. You disagree with duck typing."),
            (("pyright",),       12,  "🔠", "pyright. Microsoft's faster mypy. You picked correctness over consensus."),
            (("eslint",),         5,  "🛡️",  "ESLint. The JS linter you can't escape."),
            (("biome",),         12,  "🌿", "Biome. Rust-powered JS toolchain. You said goodbye to ESLint+Prettier."),
            (("prettier",),       4,  "💅", "Prettier. Auto-formatted JS. The arguments stopped years ago."),
            (("clippy-driver",), 10,  "📎", "clippy. Rust's brutal linter. You take its advice."),
            (("golangci-lint",), 12,  "🐹", "golangci-lint. The Go meta-linter. Idiomatic Go enforcer."),
            (("rubocop",),        6,  "🚓", "RuboCop. Ruby style police. Officer present."),
            (("hlint",),         12,  "λ", "hlint. Haskell linter. You refactor pointful into pointfree on sight."),
            (("shellcheck",),    10,  "🐚", "ShellCheck. Static analysis for shell scripts. Bash bug hunter."),
            (("shfmt",),          6,  "🐚", "shfmt. Formatted shell. Even your scripts have taste."),
            (("semgrep",),       14,  "🔬", "Semgrep. Pattern-based static analysis. AppSec literate."),
            (("codeql",),        16,  "🔍", "CodeQL. GitHub's query engine. You write queries about codebases."),
            (("sonar-scanner",), 10,  "📡", "SonarQube scanner. Enterprise quality gate operator."),
            (("scc", "cloc"),     6,  "📏", "Code line counter (scc/cloc). You quantify your output."),
            (("tokei",),          0,  "",   ""),  # Already counted in terminal tools.
        ]
        # Filter out empty placeholder rules
        self.apply_rules([r for r in rules if r[2]], tests)
        self.profile["testing"] = tests

    def check_documentation_tools(self):
        """Documentation engines — the mark of someone who actually ships."""
        rules = [
            (("pandoc",),       12, "📝", "pandoc. Universal document converter. You weaponize markdown."),
            (("typst",),        18, "📐", "Typst. The modern LaTeX. You read HN the day it landed."),
            (("asciidoctor",),  12, "📜", "AsciiDoctor. You picked AsciiDoc over Markdown. Refined choice."),
            (("sphinx-build",), 12, "🦁", "Sphinx. Python docs at industrial scale. You document properly."),
            (("mkdocs",),        8, "📖", "MkDocs. Python-flavored static docs. Sensible default."),
            (("hugo",),         10, "⚡", "Hugo. Go static site generator. Sub-second builds."),
            (("zola",),         12, "🦀", "Zola. Rust static site generator. Single-binary purity."),
            (("jekyll",),        6, "💎", "Jekyll. The OG static site engine. GitHub Pages compatible."),
            (("eleventy", "@11ty/eleventy"), 10, "🟢", "Eleventy. Zero-config JS static site gen. You like quiet tools."),
            (("docusaurus",),   10, "🦖", "Docusaurus. React documentation. You document like Meta."),
            (("mdbook",),       12, "📕", "mdbook. Rust-style book generator. The Rust Book vibes."),
            (("vitepress", "vuepress"), 8, "🟩", "VitePress/VuePress. Vue-flavored docs."),
            (("tldr",),          0, "",   ""),  # Already counted.
        ]
        self.apply_rules([r for r in rules if r[2]])

    def check_alternative_vcs(self):
        """Anyone using non-Git VCS in 2026 is making a deliberate, expert choice."""
        if cmd_exists("hg"):
            self.award(20, "💧", "Mercurial (hg). You use the VCS Facebook and Mozilla actually deploy.")
        if cmd_exists("fossil"):
            self.award(28, "🦴", "Fossil. Single-file VCS with built-in wiki and bug tracker. SQLite-author taste.")
        if cmd_exists("jj"):
            self.award(30, "🪼", "Jujutsu (jj). The next-gen Git frontend. You read changelogs of changelogs.")
        if cmd_exists("pijul"):
            self.award(32, "🌲", "Pijul. Patch-theory VCS. You read papers about version control.")
        if cmd_exists("darcs"):
            self.award(28, "🎯", "darcs. Patch-based VCS. You've been doing this since before git existed.")
        if cmd_exists("bzr") or cmd_exists("brz"):
            self.award(15, "🐝", "Bazaar/Breezy. You maintain Ubuntu packages or remember Launchpad fondly.")
        if cmd_exists("svn"):
            self.award(4, "🗄️",  "Subversion. Real software still uses this. You probably maintain some.")
        if cmd_exists("cvs"):
            self.award(20, "🪦", "CVS. You time-traveled here from 1999. We have questions.")

    def check_more_languages(self):
        """The long tail of languages — niche, modern, esoteric, or all three."""
        confirmed: List[str] = []
        rules = [
            (("ghc", "ghcup"),    0, "",   ""),  # Already counted.
            (("cabal", "stack"), 14, "🐫", "Haskell build tool (cabal/stack). You ship Haskell, not just admire it."),
            (("purs",),          22, "💜", "PureScript. Strongly-typed JS. You believe in type safety on the frontend."),
            (("rescript",),      18, "🎨", "ReScript. OCaml on JS. You miss F#."),
            (("gleam",),         24, "✨", "Gleam. Typed BEAM language. You read every issue of the Gleam newsletter."),
            (("roc",),           28, "🦜", "Roc. Pure functional, fast. You back niche compilers on GitHub Sponsors."),
            (("grain",),         24, "🌾", "Grain. WebAssembly-first ML-family language. Bleeding edge."),
            (("hare",),          28, "🐇", "Hare. Drew DeVault's systems language. You hand-roll philosophy."),
            (("odin",),          22, "🪶", "Odin. C alternative for game/system devs. Aesthetic and pragmatic."),
            (("v",),             18, "📐", "V. Promised everything, delivered some of it. You watch the journey."),
            (("zls",),           14, "⚡", "Zig language server. You actively develop in Zig, not just dabble."),
            (("mojo",),          22, "🔥", "Mojo. Modular's Python-superset for AI. You bet on the future."),
            (("raku",),          22, "🦋", "Raku (Perl 6). Sigils, grammars, junctions. Beautiful. Niche."),
            (("io",),            26, "🌀", "Io language. Prototype-based. You read 'Seven Languages in Seven Weeks' and committed."),
            (("janet",),         24, "🌿", "Janet. Embeddable Lisp dialect. You write tools for yourself."),
            (("wren",),          22, "🐦", "Wren. Tiny scripting language. Game-engine adjacent."),
            (("hy",),            18, "🐍", "Hy. Lisp on Python's runtime. Why pick one paradigm?"),
            (("pony",),          24, "🐴", "Pony. Capabilities-secure actor language. You read research papers for fun."),
            (("nelua",),         24, "🌙", "Nelua. Statically-typed Lua. Niche of niche."),
            (("crystal",),        0, "",   ""),  # Already counted.
            (("smalltalk", "gst"), 26, "🟦", "GNU Smalltalk. Object-orientation, the original. You know what 'image-based' means."),
            (("swipl",),         22, "🔮", "SWI-Prolog. Declarative logic programming. Your code unifies."),
            (("scheme", "guile", "chicken", "racket"), 0, "", ""),  # racket counted.
            (("io",),             0, "",   ""),  # dup
            (("dhall",),         22, "🪶", "Dhall. Total functional config language. JSON without footguns."),
            (("cue",),           18, "🟦", "CUE. Constraints-based configuration. You hate YAML and have proof."),
            (("nickel",),        20, "🪙", "Nickel. Functional config language. Nix-adjacent."),
        ]
        self.apply_rules([r for r in rules if r[2]], confirmed)
        if confirmed:
            self.profile.setdefault("languages", []).extend(confirmed)

    def check_messaging_and_streaming(self):
        """Brokers and queues — backbone of the modern distributed system."""
        rules = [
            (("kafka-topics", "kafka-console-producer"), 18, "🌊", "Kafka tools. Event-streaming at scale. Distributed-log adept."),
            (("rabbitmqctl", "rabbitmq-server"),         14, "🐰", "RabbitMQ. AMQP. The reliable veteran of message brokers."),
            (("mosquitto",),                             12, "📡", "Mosquitto. MQTT broker. IoT or home-automation builder."),
            (("nsqd",),                                  14, "📬", "NSQ. Distributed messaging. You read engineering blogs from 2014."),
            (("pulsar-admin",),                          18, "🌌", "Apache Pulsar. Multi-tenant streaming. You compared it to Kafka and chose this."),
            (("redpanda",),                              18, "🐼", "Redpanda. Kafka-compatible C++ broker. Latency obsessive."),
        ]
        self.apply_rules(rules)

    def check_mobile_and_game_dev(self):
        """Mobile + game dev — verifiable, confident signals."""
        if is_macos() and (Path("/Applications/Xcode.app").exists() or cmd_exists("xcodebuild")):
            self.award(10, "📱", "Xcode toolchain. iOS/macOS native development confirmed.")
        if cmd_exists("xcrun"):
            self.award(4, "🍏", "xcrun present. Apple developer environment configured.")
        if cmd_exists("adb"):
            self.award(8, "🤖", "Android Debug Bridge. You sideload, debug, and own your phone properly.")
        if cmd_exists("fastboot"):
            self.award(10, "🔓", "fastboot. You unlock bootloaders. Custom-ROM territory.")
        if cmd_exists("gradle"):
            self.award(6, "🐘", "Gradle. JVM build tool. Android or Kotlin shipper.")
        if cmd_exists("fastlane"):
            self.award(12, "🚄", "fastlane. Mobile release automation. You ship to App Store from CLI.")
        if cmd_exists("expo"):
            self.award(8, "📲", "Expo. React Native shipping made bearable.")
        if cmd_exists("flutter"):
            self.award(10, "🦋", "Flutter. Cross-platform UI. Dart-curious mobile builder.")
        if cmd_exists("godot") or cmd_exists("godot4"):
            self.award(15, "🎮", "Godot engine. Open-source game development. Independent and proud.")
        if cmd_exists("love"):
            self.award(14, "❤️",  "LÖVE 2D. Lua game framework. Game-jam veteran energy.")
        if cmd_exists("raylib") or cmd_exists("rlpkg"):
            self.award(15, "🎮", "raylib. Tiny C game library. From-scratch game programmer.")
        if cmd_exists("sdl2-config") or cmd_exists("sdl-config"):
            self.award(8, "🎯", "SDL development files. You build games or emulators in C/C++.")
        if cmd_exists("blender"):
            self.award(8, "🟧", "Blender. 3D modeling and rendering. Asset pipeline literate.")

    def check_data_engineering(self):
        """Modern data stack — the rise of analytics engineers."""
        rules = [
            (("dbt",),         14, "🔧", "dbt. SQL transformations done right. Analytics engineer detected."),
            (("airflow",),     14, "💨", "Apache Airflow. DAGs for everything. Workflow orchestration veteran."),
            (("prefect",),     14, "🪄", "Prefect. Modern Python orchestration. You picked the friendly fork."),
            (("dagster",),     14, "✨", "Dagster. Asset-centric pipelines. Data engineering future-thinker."),
            (("spark-shell", "pyspark"), 12, "⚡", "Apache Spark. Big-data processing. JVM ML pipelines."),
            (("flink",),       16, "🪶", "Apache Flink. Stream processing. You think in unbounded datasets."),
            (("trino", "presto"), 16, "🚂", "Trino/Presto. Federated SQL. You query everything from one shell."),
            (("clickhouse-local",), 18, "📊", "clickhouse-local. Single-binary OLAP CLI. Power user."),
            (("duckdb",),       0, "", ""),  # already counted
            (("polars",),      14, "🐻‍❄️", "Polars CLI tools. Rust-powered dataframes. pandas pretender no longer."),
        ]
        self.apply_rules([r for r in rules if r[2]])

    def check_advanced_networking(self):
        """Beyond ping — power-user network tooling."""
        rules = [
            (("iperf3", "iperf"),  10, "📡", "iperf. Network throughput testing. You measure your LAN scientifically."),
            (("iftop",),            8, "📊", "iftop. Live bandwidth visualization. You watch packets like TV."),
            (("nethogs",),         10, "🐗", "nethogs. Per-process bandwidth. You hunt the noisy neighbor."),
            (("vnstat",),           6, "📈", "vnstat. Bandwidth statistics over time. Quietly tracking everything."),
            (("nload",),            6, "📉", "nload. Real-time network load. Sysadmin habit."),
            (("ngrep",),           10, "🔍", "ngrep. grep on packets. You debug protocols at the byte level."),
            (("socat",),           14, "🔗", "socat. The universal socket relay. You build network plumbing on the fly."),
            (("ipcalc", "sipcalc"), 6, "🧮", "ipcalc. Subnet math without paper. Network engineer hygiene."),
            (("dig",),              4, "🔎", "dig. The right way to query DNS."),
            (("dog",),             10, "🐕", "dog. Modern dig in Rust. You prefer color and JSON."),
            (("doggo",),           10, "🐶", "doggo. Modern dig in Go. You picked the friendly DNS client."),
            (("whois",),            4, "📇", "whois. Domain forensics. You investigate before you trust."),
            (("rsync",),            6, "🔄", "rsync. The safest way to move bytes between machines."),
            (("croc",),            10, "🐊", "croc. Encrypted P2P file transfer. You moved on from scp."),
            (("magic-wormhole",),  12, "🌀", "magic-wormhole. Codeword-based file transfer. You pick beautiful tools."),
            (("ssh-audit",),       12, "🔐", "ssh-audit. SSH server hardening. You verify, not assume."),
            (("nuclei",),          14, "💥", "nuclei. Template-based vulnerability scanner. AppSec engineer."),
        ]
        self.apply_rules(rules)

    def check_privacy_and_vpn(self):
        """Privacy stack — strong opinions about the network."""
        rules = [
            (("wg", "wg-quick"),       12, "🛡️",  "WireGuard. Modern VPN. You picked the right protocol."),
            (("openvpn",),              6, "🔐", "OpenVPN. The veteran. Configurable to a fault."),
            (("tailscale",),           14, "🪢", "Tailscale. Mesh networking that just works. Pragmatic privacy."),
            (("headscale",),           18, "🐙", "Headscale. Self-hosted Tailscale control plane. Sovereignty maximalist."),
            (("mullvad",),             14, "🦊", "Mullvad CLI. Privacy-first VPN. You pay in Monero for fun."),
            (("protonvpn-cli", "protonvpn"), 12, "🛡️",  "ProtonVPN CLI. Privacy by Geneva default."),
            (("tor", "torbrowser-launcher"), 12, "🧅", "Tor. Onion routing. You actually understand threat models."),
            (("i2prouter",),           18, "🌐", "I2P router. Anonymity network deeper than Tor. Operator-grade privacy."),
            (("yt-dlp",),               8, "📹", "yt-dlp. The download tool that respects your machine. yt-dlp gang."),
            (("aria2c",),               8, "📥", "aria2c. Multi-source download accelerator. Old-school power user."),
            (("syncthing",),           14, "🔄", "Syncthing. P2P file sync. You don't trust Dropbox."),
            (("rclone",),              10, "☁️", "rclone. Cloud-storage power tool. You orchestrate buckets from CLI."),
            (("restic",),              14, "🛟", "restic. Encrypted, deduplicated backups. You sleep well."),
            (("borgbackup", "borg"),   14, "🐻", "Borg backups. Tested, reliable, paranoid. The right call."),
        ]
        self.apply_rules(rules)

    def check_note_taking_and_productivity(self):
        """The 'I take my second brain seriously' stack."""
        rules = [
            (("taskwarrior", "task"), 10, "✅", "Taskwarrior. CLI todo list with a UDA system. Productivity hacker."),
            (("timew",),               10, "⏱️",  "Timewarrior. CLI time tracking. You measure your focus."),
            (("zk",),                  14, "🗒️",  "zk. CLI Zettelkasten. You actually maintain your notes."),
            (("obsidian",),             6, "🪨", "Obsidian. Local-first markdown vault. You own your notes."),
            (("logseq",),              10, "🧱", "Logseq. Outliner-style PKM. You think in graphs."),
            (("joplin",),               6, "📓", "Joplin. End-to-end encrypted notes. Privacy-aware notetaker."),
            (("vimwiki",),             14, "📓", "vimwiki. Notes in vim. You never leave the editor."),
            (("orgmode", "emacs-org"), 16, "📅", "Org mode. The PKM that runs your life. Emacs-adjacent saint."),
            (("calcurse",),            12, "📅", "calcurse. CLI calendar. You schedule from the terminal."),
            (("khal",),                12, "📆", "khal. CLI CalDAV calendar. Server-side power user."),
            (("vdirsyncer",),          12, "🔄", "vdirsyncer. Contacts/calendar sync. CalDAV operator."),
            (("pass",),                12, "🔑", "pass. The standard Unix password manager. GPG-backed and beautiful."),
            (("gopass",),              12, "🔑", "gopass. pass in Go with extras. Team-secret literate."),
            (("bitwarden", "bw"),       8, "🔒", "Bitwarden CLI. You manage secrets from scripts."),
            (("rbw",),                 12, "🔒", "rbw. Unofficial Rust Bitwarden CLI. You like fast and small."),
            (("age",),                 14, "🔐", "age. Modern file encryption. The right replacement for GPG-for-files."),
            (("rage",),                14, "🦀", "rage. age in Rust. You collect Rust ports of Go tools."),
        ]
        self.apply_rules(rules)

    def check_browsers_and_web_stack(self):
        """Browser choice and modern web tooling."""
        rules = [
            (("qutebrowser",), 16, "🦖", "qutebrowser. Vim-keybindings browser. You browse with hjkl."),
            (("nyxt",),        20, "🦊", "Nyxt. Lisp-extensible browser. Power-user territory."),
            (("lynx",),        12, "📜", "Lynx. Text-mode browser. You read the web like Plato did."),
            (("w3m",),         12, "📜", "w3m. Text browser with images. You read HN inside Emacs."),
            (("browsh",),      14, "🌐", "browsh. Real browser, terminal-rendered. You break conventions."),
            (("chromium",),     2, "🌍", "Chromium. The honest version of Chrome."),
            (("firefox-developer-edition",), 8, "🦊", "Firefox Developer Edition. Web platform engineer signal."),
            # Modern web build tools — only counted here, not in package managers.
            (("vite",),         8, "⚡", "Vite. Modern dev server. You moved on from webpack and you're happy."),
            (("esbuild",),      8, "🥇", "esbuild. Go-powered bundling at the speed of thought."),
            (("swc",),         10, "🦀", "swc. Rust-powered JS toolchain. You measure build times in milliseconds."),
            (("turbo",),       10, "🌀", "Turborepo. Monorepo task runner. You manage multiple packages."),
            (("nx",),          10, "🅰️",  "Nx. Monorepo orchestrator. Enterprise-scale frontend."),
            (("rome",),         8, "🏛️",  "Rome (legacy). You were early to Biome's predecessor."),
        ]
        self.apply_rules(rules)

    def check_release_and_packaging(self):
        """Distribution craftsmanship — anyone who packages software properly is rare."""
        rules = [
            (("goreleaser",),       16, "📦", "GoReleaser. Multi-arch release pipelines. You ship binaries professionally."),
            (("cargo-release",),    14, "🦀", "cargo-release. Reliable Rust crate publishing."),
            (("cargo-dist",),       14, "🦀", "cargo-dist. Multi-platform Rust binary releases. Modern."),
            (("dpkg-buildpackage",), 14, "📦", "Debian package builder. You actually maintain .deb packages. Distro-grade."),
            (("rpmbuild",),         14, "📦", "rpmbuild. Red Hat package builder. Enterprise-distro literacy."),
            (("fpm",),              14, "📦", "fpm. Universal package builder. Pragmatic packaging maximalist."),
            (("nfpm",),             12, "📦", "nfpm. Go package builder. Modern."),
            (("pkgbuild",),         16, "🏹", "pkgbuild. Arch package builder. AUR contributor energy."),
            (("conan",),            12, "🏛️",  "Conan. C/C++ package manager. You wrangle native deps for a living."),
            (("vcpkg",),            10, "🪟", "vcpkg. Microsoft's C/C++ package manager. Cross-platform native dev."),
            (("docker-buildx",),    10, "🐳", "docker buildx. Multi-arch image builds. ARM64 ready."),
            (("ko",),               14, "🥷", "ko. Container images for Go without Dockerfiles. Minimalist DevOps."),
            (("buildah",),          14, "🛠️",  "buildah. Daemonless container builds. You moved past Docker daemon."),
            (("skopeo",),           12, "🚚", "skopeo. Container image transfer. Registry power user."),
            (("dive",),             10, "🤿", "dive. Container layer explorer. You audit your images."),
        ]
        self.apply_rules(rules)

    def check_extended_editor_signals(self):
        """Plugin managers and editor depth — distinguishes posers from power users."""
        # tmux plugin manager
        if dir_exists(HOME / ".tmux" / "plugins" / "tpm"):
            self.award(10, "🪟", "tmux plugin manager (tpm). You configure tmux beyond defaults.")
        if file_exists(HOME / ".tmux.conf"):
            content = read_file_safe(HOME / ".tmux.conf")
            lines = len(content.splitlines())
            if lines > 100:
                self.award(12, "🪟", f"tmux.conf with {lines} lines. Your prefix isn't C-b. Power user.")
            elif lines > 20:
                self.award(6, "🪟", f"tmux.conf with {lines} lines. Customized.")

        # Neovim plugin manager depth
        nvim_share = HOME / ".local" / "share" / "nvim"
        nvim_data = HOME / ".local" / "state" / "nvim"
        plugin_signals = [
            (nvim_share / "lazy",   "lazy.nvim"),
            (nvim_share / "site" / "pack" / "packer", "packer.nvim"),
            (nvim_share / "site" / "autoload" / "plug.vim", "vim-plug"),
            (HOME / ".config" / "nvim" / "lazy-lock.json", "lazy.nvim lockfile"),
        ]
        for path, name in plugin_signals:
            if path.exists():
                self.award(8, "📝", f"Neovim with {name}. Plugin-managed, lockfile-aware.")
                break

        # LSPs configured
        mason_dir = HOME / ".local" / "share" / "nvim" / "mason"
        if mason_dir.is_dir():
            servers = [d for d in (mason_dir / "packages").glob("*") if d.is_dir()] if (mason_dir / "packages").is_dir() else []
            if len(servers) > 5:
                self.award(14, "🧰", f"Mason-managed LSP/DAP servers: {len(servers)}. You wired up real IDE features in nvim.")

        # VSCode workspaces
        vsc_settings = HOME / ".vscode" / "settings.json"
        if vsc_settings.exists():
            self.award(2, "💙", "VSCode settings.json present. Configured beyond defaults.")

        # JetBrains family
        jb_dirs = list(HOME.glob(".config/JetBrains/*")) + list(HOME.glob("Library/Application Support/JetBrains/*"))
        if jb_dirs:
            self.award(4, "🧠", f"JetBrains IDE detected ({len(jb_dirs)} profile(s)). Pragmatic, well-resourced developer.")

        # Sublime Text
        if cmd_exists("subl"):
            self.award(4, "🟧", "Sublime Text. Quietly fast editor. Veteran-tier choice.")
        # Zed
        if cmd_exists("zed"):
            self.award(12, "🌌", "Zed. Modern Rust-based editor. You actually try new things.")
        # Cursor / Windsurf
        if cmd_exists("cursor"):
            self.award(6, "🤖", "Cursor. AI-first editor. You collaborate with the model.")
        if cmd_exists("windsurf"):
            self.award(6, "🌬️",  "Windsurf. AI editor. You're testing the future.")

        # Lazygit / lazy* family
        if cmd_exists("lazygit"):
            self.award(10, "🌳", "lazygit. Git TUI. You commit faster than you think.")
        if cmd_exists("gitui"):
            self.award(10, "🌲", "gitui. Rust git TUI. You picked the speed-first option.")

    def check_hardware_and_environment(self):
        """The machine itself — workstation-class signals."""
        cpu_count = os.cpu_count() or 0
        if cpu_count >= 32:
            self.award(15, "🧠", f"{cpu_count} logical CPUs. Workstation-class hardware. You compile for a living.")
        elif cpu_count >= 16:
            self.award(8, "🧠", f"{cpu_count} logical CPUs. Beefy dev machine.")
        elif cpu_count >= 8:
            self.award(3, "🧠", f"{cpu_count} logical CPUs. Solid baseline.")
        self.profile["cpu_count"] = cpu_count

        # RAM — best-effort cross-platform
        ram_gb = self._detect_ram_gb()
        if ram_gb:
            if ram_gb >= 64:
                self.award(15, "💾", f"~{ram_gb} GB RAM. Your IDE has elbow room. ML or VM workloads suspected.")
            elif ram_gb >= 32:
                self.award(8, "💾", f"~{ram_gb} GB RAM. Comfortable for modern dev.")
            self.profile["ram_gb"] = ram_gb

        # GPU presence — confident detection
        gpu_signals = []
        if cmd_exists("nvidia-smi"):
            out = run("nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null", timeout=4)
            if out:
                gpus = [g.strip() for g in out.splitlines() if g.strip()]
                if gpus:
                    self.award(12, "🎮", f"NVIDIA GPU(s) detected: {', '.join(gpus[:2])}. CUDA-capable workstation.")
                    gpu_signals.extend(gpus)
        if is_macos():
            mac_chip = run("sysctl -n machdep.cpu.brand_string 2>/dev/null", timeout=2)
            if "apple" in mac_chip.lower():
                self.award(8, "🍏", f"{mac_chip.strip()}. Apple Silicon. Metal-capable, MLX-curious.")
                gpu_signals.append(mac_chip.strip())
        if is_linux() and cmd_exists("lspci"):
            lspci = run("lspci 2>/dev/null", timeout=3).lower()
            if "amd" in lspci and ("radeon" in lspci or "rdna" in lspci):
                self.award(10, "🎮", "AMD discrete GPU detected. ROCm-curious or gamer-developer.")
                gpu_signals.append("amd-gpu")
        self.profile["gpu_signals"] = gpu_signals

        # Multiple displays env hint (Linux)
        if is_linux() and cmd_exists("xrandr"):
            out = run("xrandr --listmonitors 2>/dev/null", timeout=3)
            if out:
                m = re.search(r"Monitors:\s*(\d+)", out)
                if m and int(m.group(1)) >= 2:
                    self.award(6, "🖥️",  f"{m.group(1)} monitors connected. Multi-display productivity setup.")

        # Battery → laptop signal
        bat_dir = Path("/sys/class/power_supply")
        if bat_dir.is_dir():
            if any(p.name.startswith("BAT") for p in bat_dir.iterdir()):
                self.profile["form_factor"] = "laptop"

    def _detect_ram_gb(self) -> Optional[int]:
        try:
            if is_linux() or is_wsl():
                meminfo = read_file_safe("/proc/meminfo")
                m = re.search(r"MemTotal:\s+(\d+)\s+kB", meminfo)
                if m:
                    return int(m.group(1)) // (1024 * 1024)
            if is_macos():
                bytes_str = run("sysctl -n hw.memsize 2>/dev/null", timeout=2)
                if bytes_str.isdigit():
                    return int(bytes_str) // (1024 ** 3)
            if is_windows():
                out = run('powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"', timeout=4)
                if out.strip().isdigit():
                    return int(out.strip()) // (1024 ** 3)
        except Exception:
            return None
        return None

    def check_ai_dev_workflow(self):
        """AI-assisted development — modern workflow signals."""
        if cmd_exists("claude"):
            self.award(14, "🤖", "Claude Code CLI. AI-pair-programming, terminal-native. Modern workflow confirmed.")
        if cmd_exists("gh-copilot") or cmd_exists("github-copilot-cli"):
            self.award(8, "🤖", "GitHub Copilot CLI. AI-assisted shell.")
        if cmd_exists("aider"):
            self.award(12, "🛠️",  "aider. Terminal AI pair programmer. You ship with the model.")
        if cmd_exists("cody"):
            self.award(8, "🤖", "Cody (Sourcegraph). Code-aware AI assistant.")
        if cmd_exists("continue"):
            self.award(8, "↪️",  "Continue. Open-source AI coding agent. You self-host your assistant.")
        if cmd_exists("codex"):
            self.award(10, "📜", "OpenAI Codex CLI. Terminal AI agent.")

    def check_combo_bonuses(self):
        """Cross-cutting bonuses — proves the system is greater than its parts."""
        prof = self.profile

        langs = set(prof.get("languages", []))
        if "rustc" in langs and prof.get("os") in ("nixos", "arch"):
            self.award(10, "🦀", "Rust + (Arch | NixOS) combo. Peak modern hacker stack. Quiet flex confirmed.")
        if "ghc" in langs and "nix" in prof.get("package_managers", []):
            self.award(15, "λ", "Haskell + Nix. Reproducible functional programming pipeline. You read POPL papers.")
        if {"ocaml", "rustc"} <= langs:
            self.award(8, "🐪", "OCaml + Rust. Compiler-construction enthusiast.")
        if {"go", "rustc"} <= langs:
            self.award(5, "🐹", "Go + Rust. Pragmatist and purist living in the same body.")
        if "ollama" in (prof.get("databases", []) + list(langs)) or cmd_exists("ollama"):
            if any(cmd_exists(c) for c in ("nvidia-smi", "rocm-smi")):
                self.award(10, "🤖", "Local LLMs + GPU detected. Self-hosted AI stack.")
        if prof.get("os") == "nixos" and cmd_exists("home-manager"):
            self.award(15, "❄️", "NixOS + home-manager. End-to-end declarative system. You can rebuild from a flake.")
        if cmd_exists("nvim") and cmd_exists("tmux") and cmd_exists("fzf"):
            self.award(8, "🧙", "nvim + tmux + fzf trifecta. The terminal-native developer's loadout.")
        if cmd_exists("git") and cmd_exists("gh") and cmd_exists("lazygit"):
            self.award(6, "🐙", "git + gh + lazygit. PR workflow without leaving the terminal.")

    def check_2026_meta(self):
        """The current year energy. Fresh off r/ProgrammerHumor, still warm."""

        # Zed editor — the 2025-26 "I switched from VSCode" flex
        if cmd_exists("zed") or dir_exists(HOME / ".config" / "zed"):
            self.award(18, "⚡", "Zed editor! GPU-accelerated, Rust-native, Electron-free. You read the benchmarks and felt something.")

        # uv — Astral's Python package manager that replaced pip+poetry+pyenv in one shot
        if cmd_exists("uv"):
            self.award(15, "🚀", "uv! Astral's Rust-based Python tool. You replaced pip, virtualenv, AND pyenv with one binary. Correct.")

        # ruff — Astral's linter/formatter, killed black+flake8 overnight
        if cmd_exists("ruff"):
            self.award(10, "🦀", "ruff! Rust-based Python linter. 100x faster than flake8. You didn't debate it, you just switched.")

        # atuin — shell history with sync, search, and stats. The 2025 upgrade everyone made
        if cmd_exists("atuin"):
            self.award(12, "🔍", "atuin! Shell history that actually works — synced, searchable, and stats. Ctrl+R was a crime before this.")

        # opencode — terminal-based AI coding agent (the serious alternative to cursor)
        if cmd_exists("opencode"):
            self.award(14, "🤖", "opencode! Terminal AI coding agent. You run your AI assistant in the CLI like a person of culture.")

        # The "Coding Monk" 2026 bonus — can you still code without AI?
        has_any_ai_tool = any(cmd_exists(c) for c in ("cursor", "aider", "opencode", "claude", "copilot"))
        has_real_tools  = sum([
            cmd_exists("nvim") or cmd_exists("vim"),
            cmd_exists("gdb") or cmd_exists("lldb"),
            cmd_exists("valgrind") or cmd_exists("heaptrack"),
            cmd_exists("make") or cmd_exists("cmake"),
            cmd_exists("rustc") or cmd_exists("gcc") or cmd_exists("clang"),
        ])
        if not has_any_ai_tool and has_real_tools >= 3:
            self.award(20, "🧘", "No AI coding tools detected. In 2026 that's either a lifestyle choice or an achievement. "
                               "r/ProgrammerHumor calls your kind 'coding monks'. Rare. Possibly feral.")

        # The "localhost:3000 deployer" — vibe coder with no actual infra knowledge
        has_infra = any(cmd_exists(c) for c in ("kubectl", "terraform", "ansible", "docker", "fly", "wrangler", "vercel"))
        has_cursor = dir_exists(HOME / ".cursor") or dir_exists(HOME / ".config" / "Cursor")
        if has_cursor and not has_infra:
            self.penalize(8, "🌐", "Cursor installed but zero deployment tools found. "
                                   "Your app works on localhost:3000. Ship it sometime.")
            self.warn("localhost:3000 deployer detected. The world cannot access your masterpiece.")

    def check_vibe_coding(self):
        """The 2025 meme that broke r/ProgrammerHumor."""
        # Detect vibe-coding tools
        has_cursor   = dir_exists(HOME / ".cursor") or dir_exists(HOME / ".config" / "Cursor")
        has_copilot  = cmd_exists("gh") and file_exists(HOME / ".config" / "gh" / "hosts.yml") and \
                       file_contains(str(HOME / ".config" / "gh" / "hosts.yml"), "github.com")
        has_claude_code = cmd_exists("claude")
        has_aider    = cmd_exists("aider")
        has_continue = dir_exists(HOME / ".continue")

        if has_cursor:
            self.award(3, "🖱️",  "Cursor IDE detected. Welcome to vibe coding. Your LLM does the typing; you do the vibing.")
        if has_aider:
            self.award(12, "🤖", "aider! Terminal-based AI pair programmer. You AI-assist without leaving the CLI. Respectable.")
        if has_continue:
            self.award(8,  "⚡", ".continue config found! Continue.dev in your editor. You have AI autocomplete and you're not ashamed.")
        if has_claude_code:
            self.award(15, "🟣", "claude (Claude Code) detected! You let an AI agent run commands on your machine. Either genius or brave.")

        # Penalise pure vibe coder: has Cursor but zero terminal AI tooling
        if has_cursor and not (has_aider or has_claude_code or has_continue):
            self.penalize(5, "😴", "Cursor-only vibe coder. No terminal AI tooling at all. You click buttons and call it engineering.")
            self.warn("Pure Cursor user with no CLI AI tools. r/ProgrammerHumor is watching.")

    def check_modern_ricing(self):
        """2025 r/unixporn meta: Niri, Quickshell, swww, and color scheme theology."""
        # Niri — the scrollable-tiling Wayland compositor blowing up in 2025-26
        if cmd_exists("niri"):
            self.award(30, "📜", "Niri compositor! Scrollable tiling for Wayland. PaperWM energy. r/unixporn's new darling.")

        # Quickshell — QML-based shell framework replacing eww/AGS
        if cmd_exists("quickshell") or dir_exists(HOME / ".config" / "quickshell"):
            self.award(22, "⚡", "Quickshell config detected! QML-based desktop shell. You replaced waybar with a framework. Certified ricer.")

        # swww — animated Wayland wallpaper daemon
        if cmd_exists("swww") or cmd_exists("swww-daemon"):
            self.award(10, "🖼️", "swww! Smooth animated wallpapers on Wayland. Your desktop transitions are silkier than your git history.")

        # wallust — colorscheme generator from wallpapers (newer pywal)
        if cmd_exists("wallust"):
            self.award(14, "🎨", "wallust! Next-gen pywal. Your colorscheme is auto-generated from your wallpaper. Peak rice autonomy.")

        # matugen — Material You color generator
        if cmd_exists("matugen"):
            self.award(12, "🎨", "matugen! Material You theming from wallpaper. Your desktop looks like a Google Pixel. Intentionally.")

        # Color scheme theology — check dotfiles for the holy grails
        rc_contents = ""
        for rc in get_shell_rc_files():
            rc_contents += read_file_safe(rc)
        cfg_dir = HOME / ".config"
        for cfg_file in ["hypr/hyprland.conf", "waybar/style.css", "kitty/kitty.conf",
                         "alacritty/alacritty.toml", "alacritty/alacritty.yml",
                         "nvim/init.lua", "nvim/init.vim"]:
            rc_contents += read_file_safe(cfg_dir / cfg_file)

        theme_hits = []
        for theme, emoji in [
            ("catppuccin", "🐈"), ("gruvbox", "🟤"), ("nord", "❄️"),
            ("dracula", "🧛"), ("tokyo", "🌃"), ("rose-pine", "🌹"),
            ("everforest", "🌲"), ("kanagawa", "🎐"), ("onedark", "🔵"),
        ]:
            if theme in rc_contents.lower():
                theme_hits.append(f"{emoji} {theme.title()}")

        if len(theme_hits) >= 3:
            self.award(15, "🎨", f"Multi-theme dotfiles: {', '.join(theme_hits[:3])} — and more. You have opinions. Strong ones.")
        elif len(theme_hits) == 2:
            self.award(10, "🎨", f"Color scheme devotion: {', '.join(theme_hits)}. You pick your editor theme like a religion.")
        elif len(theme_hits) == 1:
            self.award(6,  "🎨", f"Color scheme: {theme_hits[0]}. You have taste. Singular, but taste.")

    def run_all(self):
        """Run all checks."""
        checks = [
            ("🖥️  Operating System",           self.check_os),
            ("🐚  Shell",                       self.check_shell),
            ("📝  Code Editors",                self.check_editor_of_choice),
            ("📦  Package Managers",            self.check_package_managers),
            ("💻  Programming Languages",       self.check_languages),
            ("🌿  Git & Version Control",       self.check_git),
            ("🪼  Alt VCS",                      self.check_alternative_vcs),
            ("🐳  Docker & DevOps",             self.check_docker_and_devops),
            ("🔧  Terminal Tools",              self.check_terminal_tools),
            ("⚙️   Shell Customization",        self.check_shell_customization),
            ("🗂️   Dotfiles & Config",          self.check_dotfiles),
            ("📦  Node Modules & JS",           self.check_node_modules),
            ("🪟  Tiling WMs & Desktop",        self.check_tiling_wm_and_desktop),
            ("🎨  Fonts & Ricing",              self.check_fonts_and_ricing),
            ("📜  Code & Projects",             self.check_programming_indicators),
            ("⚙️   Compilers & Low Level",      self.check_compilers_and_low_level),
            ("🔐  Security Tools",              self.check_security_tools),
            ("🤖  AI & ML Tools",               self.check_ai_ml_tools),
            ("🤖  AI Dev Workflow",             self.check_ai_dev_workflow),
            ("🐘  Databases",                   self.check_databases),
            ("🌐  Web Servers & Proxies",        self.check_web_servers_and_proxies),
            ("🔭  Observability",                self.check_observability),
            ("🧪  Testing & Quality",            self.check_testing_and_quality),
            ("📝  Documentation Tools",          self.check_documentation_tools),
            ("🌌  Niche Languages",              self.check_more_languages),
            ("📡  Messaging & Streaming",        self.check_messaging_and_streaming),
            ("📱  Mobile & Game Dev",            self.check_mobile_and_game_dev),
            ("🌊  Data Engineering",             self.check_data_engineering),
            ("🛰️   Advanced Networking",         self.check_advanced_networking),
            ("🛡️   Privacy & VPN",               self.check_privacy_and_vpn),
            ("🗒️   Note-taking & Productivity",  self.check_note_taking_and_productivity),
            ("🦖  Browsers & Web Stack",         self.check_browsers_and_web_stack),
            ("📦  Release & Packaging",          self.check_release_and_packaging),
            ("🧰  Editor Plugins & Depth",       self.check_extended_editor_signals),
            ("🧠  Hardware & Environment",       self.check_hardware_and_environment),
            ("🔮  Legendary & Mythical",        self.check_legendary_stuff),
            ("✨  Combo Bonuses",                self.check_combo_bonuses),
            ("🤖  Vibe Coding",                 self.check_vibe_coding),
            ("🍚  Modern Ricing (2025)",        self.check_modern_ricing),
            ("📅  2026 Meta",                   self.check_2026_meta),
        ]

        print(f"\n{C_CYAN}{BOLD}{'─' * 60}{RESET}")
        for label, fn in checks:
            print(f"  {C_GRAY}Scanning{RESET} {label}...", end="\r", flush=True)
            fn()
            time.sleep(0.05)
            print(f"  {C_GREEN}✓{RESET}      {label}      ", flush=True)

        print(f"{C_CYAN}{BOLD}{'─' * 60}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# RANKING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

RANKS = [
    # (min_score, name, color, subtitle, description, ascii_art)
    (0,   "COMMON",    C_COMMON,
     "💀 The Muggle Developer",
     "You exist. You code. You Google everything. Stack Overflow is your pair-programmer.\n"
     "   Your code works and you don't know why. So does most production code. Welcome.",
     """
   ╔════════════╗
   ║   COMMON   ║
   ║  ░░░░░░░░  ║
   ║  ░  💻  ░  ║
   ║  ░░░░░░░░  ║
   ╚════════════╝"""),

    (60,  "UNCOMMON",  C_UNCOMMON,
     "🐣 The Aspiring Nerd",
     "You've installed a real package manager. You have opinions about text editors.\n"
     "   You've told someone 'have you tried Linux?' at least once this year.",
     """
   ╔══════════════╗
   ║   UNCOMMON   ║
   ║  ▒▒▒▒▒▒▒▒▒▒  ║
   ║  ▒   🐧   ▒  ║
   ║  ▒▒▒▒▒▒▒▒▒▒  ║
   ╚══════════════╝"""),

    (180, "RARE",      C_RARE,
     "🧙 The Terminal Dweller",
     "You live in the terminal. Your dotfiles have their own GitHub repo.\n"
     "   You've configured vim. You know what tmux is. Your peers fear your knowledge.",
     """
   ╔══════════════╗
   ║     RARE     ║
   ║  ▓▓▓▓▓▓▓▓▓▓  ║
   ║  ▓   🧙‍♂️   ▓  ║
   ║  ▓▓▓▓▓▓▓▓▓▓  ║
   ╚══════════════╝"""),

    (350, "EPIC",      C_EPIC,
     "🔮 The Unix Philosopher",
     "You have a tiling window manager. Your prompt shows git branch AND battery level.\n"
     "   You've written shell scripts that write shell scripts. Minimalism is not bloat.",
     """
   ╔══════════════╗
   ║     EPIC     ║
   ║  ██████████  ║
   ║  █   🔮   █  ║
   ║  ██████████  ║
   ╚══════════════╝"""),

    (600, "LEGENDARY", C_LEGENDARY,
     "⚡ The 10x Myth, Made Real",
     "You compile things from source. You have cross-compilers for chips you don't own.\n"
     "   Your .zshrc is longer than most novels. You've written a kernel module.\n"
     "   People ask you for advice and you reply with man-page citations.",
     """
   ╔══════════════════╗
   ║    LEGENDARY     ║
   ║  ██████████████  ║
   ║  ██  ⚡🦅⚡    ██  ║
   ║  ██████████████  ║
   ╚══════════════════╝"""),

    (900, "MYTHICAL",  C_MYTHICAL,
     "🌌 The Ascended Being",
     "You write theorem provers as a hobby. You use APL or J. You compile your own compilers.\n"
     "   You run Gentoo, BSD, or Plan 9. You've proven your software correct in Coq.\n"
     "   The kernel mailing list knows your name.",
     """
   ╔══════════════════════╗
   ║    ✨ MYTHICAL ✨    ║
   ║  ▓░▒█▓░▒█▓░▒█▓░▒█▓░  ║
   ║  ░  🌌 BEYOND 🌌  ▓  ║
   ║  ▓░▒█▓░▒█▓░▒█▓░▒█▓░  ║
   ╚══════════════════════╝"""),

]

def get_rank(score: int):
    rank = RANKS[0]
    for r in RANKS:
        if score >= r[0]:
            rank = r
    return rank


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def print_banner():
    banner = f"""
{C_CYAN}{BOLD}
 ██████╗ ███████╗██╗   ██╗    ██████╗  █████╗ ███╗   ██╗██╗  ██╗
 ██╔══██╗██╔════╝██║   ██║    ██╔══██╗██╔══██╗████╗  ██║██║ ██╔╝
 ██║  ██║█████╗  ██║   ██║    ██████╔╝███████║██╔██╗ ██║█████╔╝ 
 ██║  ██║██╔══╝  ╚██╗ ██╔╝    ██╔══██╗██╔══██║██║╚██╗██║██╔═██╗ 
 ██████╔╝███████╗ ╚████╔╝     ██║  ██║██║  ██║██║ ╚████║██║  ██╗
 ╚═════╝ ╚══════╝  ╚═══╝      ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
                                                                   
     ██████╗  ██████╗ █████╗ ███╗   ██╗███╗   ██╗███████╗██████╗ 
     ██╔════╝██╔════╝██╔══██╗████╗  ██║████╗  ██║██╔════╝██╔══██╗
     ███████╗██║     ███████║██╔██╗ ██║██╔██╗ ██║█████╗  ██████╔╝
     ╚════██║██║     ██╔══██║██║╚██╗██║██║╚██╗██║██╔══╝  ██╔══██╗
     ███████║╚██████╗██║  ██║██║ ╚████║██║ ╚████║███████╗██║  ██║
     ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
{RESET}
{C_GRAY}       "What kind of developer are you? Let the machine judge you."{RESET}
{C_GRAY}              Inspired by: r/ProgrammerHumor · r/unixporn · r/linux{RESET}
"""
    print(banner)

def print_findings(findings: List[Tuple[int, str, str]]):
    print(f"\n{BOLD}{C_CYAN}══════════════════ SCAN RESULTS ══════════════════{RESET}\n")
    for pts, emoji, msg in findings:
        if pts > 0:
            bar = "+" * min(pts // 2, 20)
            color = C_GREEN if pts >= 15 else (C_YELLOW if pts >= 8 else C_GRAY)
            sign = "+"
            display_pts = pts
        else:
            bar = "-" * min(abs(pts) // 2, 20)
            color = C_RED
            sign = ""
            display_pts = pts # Already negative

        print(f"  {emoji}  {msg}")
        print(f"     {color}{bar}{RESET} {C_GRAY}[{sign}{display_pts} pts]{RESET}\n")

def print_warnings(warnings: List[str]):
    if not warnings:
        return
    print(f"\n{BOLD}{C_YELLOW}══════════════════ HALL OF SHAME ══════════════════{RESET}\n")
    for w in warnings:
        print(f"  {C_YELLOW}⚠️  {w}{RESET}")

def print_score_bar(score: int, max_score: int = 2000):
    width = 50
    # Clamp negatives to 0 so the bar renders sanely.
    filled = max(0, min(int((score / max_score) * width), width))
    empty = width - filled
    _, name, color, *_ = get_rank(score)
    bar = f"{color}{'█' * filled}{C_GRAY}{'░' * empty}{RESET}"
    print(f"\n  Score: {C_WHITE}{BOLD}{score}{RESET} pts")
    print(f"  [{bar}] {color}{BOLD}{name}{RESET}")

def print_final_rank(score: int, findings_count: int):
    min_s, name, color, subtitle, desc, art = get_rank(score)

    print(f"\n\n{color}{BOLD}")
    print("  " + "═" * 58)
    print(f"  ✦  FINAL VERDICT  ✦".center(60))
    print("  " + "═" * 58)
    print(f"{RESET}")

    # ASCII art
    for line in art.split("\n"):
        print(f"  {color}{BOLD}{line}{RESET}")

    print(f"\n  {color}{BOLD}[ {name} ]  {subtitle}{RESET}")
    print(f"\n  {C_WHITE}{desc}{RESET}")
    print(f"\n  {C_GRAY}Total score: {score} pts  •  Signals detected: {findings_count}{RESET}")

    # Roast / encouragement
    roasts = {
        "COMMON": [
            "bro opened terminal once by accident and now he's here. actual skill issue 💀",
            "king of downloading vscode and calling yourself a dev. we see you. we judge you.",
            "you have python installed because a tutorial told you to. respect the journey. (it's a short journey.)",
            "ngl this is kinda rough. like we've seen worse but it's close.",
        ],
        "UNCOMMON": [
            "ok so you installed homebrew. do you want a trophy or something?? 😭",
            "you're the guy who reinstalls linux every weekend and still hasn't shipped anything lmaooo",
            "you told someone 'have you tried linux' this week. we both know it. they haven't texted back.",
            "participation trophy dev. not in a mean way. well. a little.",
        ],
        "RARE": [
            "dotfiles repo has 3 stars and two of them are you on alt accounts. we respect the commitment tho.",
            "unironically spends more time ricing than coding 😭 based and also concerning",
            "you said btw i use arch and it wasn't even a joke was it. it wasn't.",
            "your zshrc is longer than your last relationship and you care about it more too.",
        ],
        "EPIC": [
            "no titlebar havers rise up. also touch grass once in a while it's free.",
            "bro wrote a shell script that generates shell scripts. we're not the same. genuinely not the same.",
            "you explained your window manager to someone who didn't ask. they smiled and nodded. they were scared.",
            "rice so hard you forgot to ship anything. the ricing was the product all along 🙏",
        ],
        "LEGENDARY": [
            "your dotfiles have their own CI/CD pipeline. your plants do not. they are deceased.",
            "compiled your terminal emulator FROM SOURCE. on purpose. with custom flags. we're in awe and also worried.",
            "man page citations as advice to friends. they stopped asking. you kept citing. based.",
            "your .zshrc has comments explaining the comments. this is a medical condition.",
        ],
        "MYTHICAL": [
            "you are not a developer. you are a cautionary tale AND a deity. coexisting. somehow.",
            "linus replied to your email once. you framed it. it's above your monitor. you eat dinner looking at it.",
            "bro writes theorem provers for FUN. for FUN. sir what is wrong with you. (nothing. everything. both.)",
            "the kernel mailing list knows your name and emails you to ask questions. this is canon.",
        ],
    }

    print(f"\n  {C_CYAN}{ITALIC}» {random.choice(roasts.get(name, ['You are unique. The scanner doesn\'t know what to say.']))}{RESET}")
    print(f"\n  {color}{BOLD}{'═' * 58}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print_banner()

    print(f"  {C_GRAY}System: {host_label()} {platform.machine()} | Python {platform.python_version()}{RESET}")
    print(f"  {C_GRAY}Home: {HOME}{RESET}")
    print(f"\n  {C_YELLOW}Starting deep scan of your developer soul...{RESET}")
    print(f"  {C_GRAY}(No data leaves your machine. Unlike that npm package you installed yesterday.){RESET}")
    time.sleep(1)

    scanner = DevScanner()
    scanner.run_all()

    # Sort findings by points descending
    scanner.findings.sort(key=lambda x: x[0], reverse=True)

    # Print top findings — show more now that there are many more checks.
    top_findings = scanner.findings[:100]
    print_findings(top_findings)

    # Warnings
    print_warnings(scanner.warnings)

    # Score bar
    print_score_bar(scanner.score)

    # Final rank
    print_final_rank(scanner.score, len(scanner.findings))

    # Bonus breakdown
    print(f"\n{C_GRAY}  ── RANK THRESHOLDS ──")
    for min_s, name, color, subtitle, *_ in RANKS:
        indicator = "◀ YOU ARE HERE" if get_rank(scanner.score)[1] == name else ""
        print(f"    {color}{name:12}{RESET}  {min_s:4}+ pts  {C_CYAN}{indicator}{RESET}")
    print(f"{RESET}\n")

    print(f"  {C_GRAY}Made with caffeine and copious amounts of Reddit browsing.{RESET}")
    print(f"  {C_GRAY}Share your result on r/ProgrammerHumor with your rank.{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {C_YELLOW}Scan interrupted. Classic developer. Ctrl+C before the process finishes.{RESET}\n")
        sys.exit(0)
