#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║         DEV RARITY SCANNER v1.2 — "What Kind of Dev Are You?"  ║
║     Inspired by the sacred scrolls of r/ProgrammerHumor,        ║
║     r/unixporn, r/linux, and the deep lore of the internet.     ║
╚══════════════════════════════════════════════════════════════════╝

Scans your computer and ranks your developer rarity from:
  Slop → Common → Uncommon → Rare → Epic → Legendary → Mythical

No data leaves your machine. This is 100% local. We promise.
(Unlike that npm package you installed at 2am without reading.)
"""

import os
import sys
import shutil
import platform
import subprocess
import glob
import re
import time
import random
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# ─────────────────────────────────────────────────────────────────────────────
# ANSI COLOR CODES
# ─────────────────────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
ITALIC  = "\033[3m"

# Rank colors
C_SLOP      = "\033[31m"      # Red
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


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

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

def find_node_modules() -> List[str]:
    """Find node_modules directories under home (limit scan depth to 5)."""
    found = []
    try:
        result = run(f'find "{HOME}" -maxdepth 5 -name "node_modules" -type d 2>/dev/null', timeout=10)
        if result:
            found = [l for l in result.split("\n") if l.strip()]
    except Exception:
        pass
    return found[:50]  # cap at 50 results

def get_shell_rc_files() -> List[Path]:
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

    def award(self, points: int, emoji: str, msg: str):
        self.score += points
        self.findings.append((points, emoji, msg))
        
    def penalize(self, points: int, emoji: str, msg: str):
        self.score -= points
        self.findings.append((-points, emoji, msg))

    def warn(self, msg: str):
        self.warnings.append(msg)

    # ── TIER 1: COMMON — Basic signs of life ──────────────────────────────

    def check_os(self):
        """OS choice is the OG developer personality test."""
        distro = ""
        if SYSTEM == "Windows":
            wsl = run("wsl --list 2>/dev/null")
            if wsl:
                self.award(8, "🪟", f"Windows detected... but at least you have WSL (Windows Suffering Layer). Respect.")
                self.profile["os"] = "windows_wsl"
            else:
                self.penalize(20, "🪟", f"Windows detected without WSL. Absolute proprietary slop.")
                self.profile["os"] = "windows"
                self.warn("Uses Windows without WSL. node_modules folder is basically a black hole.")
        elif SYSTEM == "Darwin":
            mac_ver = platform.mac_ver()[0]
            self.award(5, "🍎", f"macOS {mac_ver}. A developer OR a designer who opened Terminal once.")
            self.profile["os"] = "macos"
        elif SYSTEM == "Linux":
            kernel_release = run("uname -r").lower()
            if "microsoft" in kernel_release or "wsl" in kernel_release:
                self.award(8, "🪟", "WSL detected! Windows on the outside, Linux on the inside.")
                self.profile["os"] = "wsl"
                return

            try:
                distro_info = Path("/etc/os-release").read_text(errors="ignore")
                for line in distro_info.split("\n"):
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip().strip('"')
                        break
            except Exception:
                distro = "Linux (unknown distro)"

            distro_lower = distro.lower()
            if "arch" in distro_lower:
                self.award(25, "🏹", f"Arch Linux! Don't worry, we already know. You've told everyone.")
                self.profile["os"] = "arch"
            elif "gentoo" in distro_lower:
                self.award(40, "🔮", f"Gentoo! You compile everything from source including your morning coffee.")
                self.profile["os"] = "gentoo"
            elif "nix" in distro_lower or file_exists("/etc/nixos"):
                self.award(35, "❄️",  f"NixOS detected. Your system.nix is longer than most novels.")
                self.profile["os"] = "nixos"
            elif "bsd" in distro_lower or SYSTEM == "FreeBSD":
                self.award(45, "🦌", f"BSD! You are either very wise or very lost. Possibly both.")
                self.profile["os"] = "bsd"
            elif "ubuntu" in distro_lower:
                self.award(10, "🐧", f"{distro}. The 'I use Linux btw' starter pack. Comfortable.")
                self.profile["os"] = "ubuntu"
            elif "debian" in distro_lower:
                self.award(12, "🌀", f"Debian. Stable. Boring. Like you. (Compliment.)")
                self.profile["os"] = "debian"
            elif "fedora" in distro_lower:
                self.award(14, "🎩", f"Fedora. For people who want Arch clout but also want their GPU drivers to work.")
                self.profile["os"] = "fedora"
            elif "mint" in distro_lower:
                self.award(8,  "🌿", f"Linux Mint. You showed your friend and said 'Linux is easy!'")
                self.profile["os"] = "mint"
            elif "kali" in distro_lower:
                self.penalize(10, "💀", f"Kali Linux as a daily driver. Peak script-kiddie cringe.")
                self.profile["os"] = "kali"
            elif "pop" in distro_lower:
                self.award(11, "🚀", f"Pop!_OS. For gamers who want to feel like real developers.")
                self.profile["os"] = "pop_os"
            else:
                self.award(15, "🐧", f"Linux ({distro}). Exotic taste. Respect.")
                self.profile["os"] = "linux_other"

    def check_shell(self):
        """Your shell is your personality."""
        shell = os.environ.get("SHELL", "")
        shell_lower = shell.lower()
        if "fish" in shell_lower:
            self.award(14, "🐟", "Fish shell! You love autocomplete more than you love documentation.")
        elif "zsh" in shell_lower:
            self.award(10, "⚡", "Zsh. The trendy shell. Instagram of shells.")
        elif "bash" in shell_lower:
            self.award(4,  "💥", "Bash. Classic. Like cargo shorts. Functional, not fashionable.")
        elif "dash" in shell_lower:
            self.award(20, "⚡", "Dash! Minimal. POSIX purist. You probably hate bash for 'bloat'.")
        elif "tcsh" in shell_lower or "csh" in shell_lower:
            self.award(8,  "🦕", "C shell. You either work in academia or time-traveled from 1985.")
        elif "pwsh" in shell_lower or "powershell" in shell_lower:
            self.award(3,  "💙", "PowerShell. You're doing your best. We respect the hustle.")
        elif "cmd" in shell_lower:
            self.penalize(15, "☠️",  "CMD.exe as primary shell. Pure, unfiltered suffering.")
            self.warn("CMD as primary shell. Sir, this is a Wendy's.")
        elif shell:
            self.award(12, "🔮", f"Custom shell: {shell}. Mysterious. We like it.")
        self.profile["shell"] = shell

    def check_editor_of_choice(self):
        """The editor wars. The eternal flame."""
        editors_found = []
        
        if cmd_exists("eclipse"):
            self.penalize(15, "☕", "Eclipse installed. Your RAM is crying. Peak enterprise slop.")
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
                    self.award(28, "📝", "Neovim with plugins! You spent 3 days configuring and 1 hour coding.")
                    editors_found.append("nvim_configured")
                else:
                    self.award(20, "📝", "Neovim installed with config. You're on the path. The path hurts.")
                    editors_found.append("nvim_config")
            else:
                self.award(10, "📝", "Neovim installed but no real config. You're a vim poser. It's okay, we won't tell.")
                editors_found.append("nvim_bare")

        if cmd_exists("vim") or cmd_exists("vi"):
            if "nvim_configured" not in editors_found and "nvim_config" not in editors_found:
                vimrc = HOME / ".vimrc"
                vim_cfg = HOME / ".vim" / "vimrc"
                if vimrc.exists() or vim_cfg.exists():
                    content = read_file_safe(vimrc) + read_file_safe(vim_cfg)
                    line_count = len(content.splitlines())
                    if line_count > 100:
                        self.award(20, "🧙", f"Vim with {line_count}-line .vimrc. You are a wizard. A slightly unhinged one.")
                    else:
                        self.award(12, "🧙", "Vim with config. You know :wq without Googling. Respect.")
                else:
                    self.award(2,  "🧙", "Vim installed but no .vimrc. Standard issue OS.")

        if cmd_exists("emacs"):
            emacs_cfg = [HOME / ".emacs", HOME / ".emacs.d" / "init.el", HOME / ".config" / "emacs" / "init.el"]
            doom = dir_exists(HOME / ".config" / "doom")
            spacemacs = dir_exists(HOME / ".spacemacs.d")
            if doom:
                self.award(30, "👿", "Doom Emacs. You use Emacs as an OS and Vim keybindings inside it. Maximum chaos.")
            elif spacemacs:
                self.award(25, "🚀", "Spacemacs. You wanted both Emacs and Vim and chose violence.")
            elif any(Path(p).exists() for p in emacs_cfg):
                self.award(22, "🧓", "Emacs with config. M-x butterfly. You are timeless.")
            else:
                self.award(5,  "🧓", "Emacs installed. Did you run M-x doctor yet?")

        if cmd_exists("code"):
            self.award(4, "💙", "VSCode installed. You are not a programmer; you are a 'software engineer'.")
            ext_path = HOME / ".vscode" / "extensions"
            if ext_path.exists():
                n_ext = len([d for d in ext_path.iterdir() if d.is_dir()])
                if n_ext > 50:
                    self.penalize(5, "💙", f"VSCode with {n_ext} extensions! It's basically a full, bloated OS at this point.")
                elif n_ext > 20:
                    self.award(2, "💙", f"VSCode with {n_ext} extensions. Building a collection.")

        if cmd_exists("nano"):
            self.penalize(5, "🍌", "Nano is installed. The training wheels never came off.")

        if cmd_exists("hx"):
            self.award(18, "💎", "Helix editor! You're a trendsetter. Or you read too many Rust blogs.")

        if cmd_exists("micro"):
            self.award(3, "🔬", "Micro editor. Nano but you wanted more without committing to vim.")

    def check_package_managers(self):
        """Package managers: the measure of a developer's chaos."""
        pms = []
        
        if cmd_exists("snap"):
            self.penalize(15, "🐌", "Snap daemon found. Canonical's sluggish proprietary slop.")
            pms.append("snap")
            
        if cmd_exists("flatpak"):
            self.award(5, "📦", "Flatpak. The acceptable, modern way to sandbox desktop apps.")
            pms.append("flatpak")

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

        if cmd_exists("nix") or cmd_exists("nix-env"):
            self.award(20, "❄️",  "Nix package manager! You hate state and love reproducing builds from 2019.")
            pms.append("nix")

        if cmd_exists("apt") or cmd_exists("apt-get"):
            self.award(2,  "📦", "APT package manager (Debian/Ubuntu). Stable and standard.")
            pms.append("apt")

        if cmd_exists("pacman"):
            self.award(10, "👻", "Pacman! You are one 'yay -Syu' away from an existential crisis.")
            pms.append("pacman")

        if cmd_exists("yay") or cmd_exists("paru"):
            self.award(8, "🏹", "AUR helper detected! You install software that 3 people maintain from their basement.")
            pms.append("aur_helper")

        if cmd_exists("emerge"):
            self.award(30, "🔮", "Portage/emerge! You compile packages during lunch. You are Gentoo.")
            pms.append("portage")

        if cmd_exists("cargo"):
            self.award(12, "🦀", "Cargo installed! You've mentioned Rust at least 7 times this week.")
            pms.append("cargo")

        if cmd_exists("npm") or cmd_exists("pnpm") or cmd_exists("yarn") or cmd_exists("bun"):
            tools = [t for t in ["npm", "pnpm", "yarn", "bun"] if cmd_exists(t)]
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
        
        # Penalties for slop languages
        bad_langs = {
            "php":    (10, "🐘", "PHP. The language of legacy WordPress slop."),
            "java":   (5,  "☕", "Java. Enterprise boilerplate factory."),
            "matlab": (15, "📉", "MATLAB. Paying for an array index that starts at 1."),
        }
        for cmd, (pts, emoji, label) in bad_langs.items():
            if cmd_exists(cmd):
                self.penalize(pts, emoji, f"{label} installed.")
                langs.append(cmd)
                
        # Good/Neutral languages
        lang_checks = {
            "python3":    (2,  "🐍", "Python 3. Standard issue."),
            "node":       (3,  "💚", "Node.js"),
            "deno":       (8,  "🦕", "Deno (you said 'npm is too mainstream')"),
            "bun":        (7,  "🐢", "Bun.js (you're always chasing the next hotness)"),
            "ruby":       (3,  "💎", "Ruby. Found everywhere, loved by some."),
            "perl":       (2,  "🔮", "Perl! It's preinstalled, but maybe you actually use it."),
            "kotlin":     (8,  "🅺", "Kotlin. You graduated from Java and feel smug about it."),
            "scala":      (15, "⚡", "Scala. You work at a bank or a startup that thinks it's a bank."),
            "swift":      (8,  "🍎", "Swift. You have $99/year opinions."),
            "rustc":      (15, "🦀", "Rust compiler! Memory safety AND superiority complex."),
            "go":         (10, "🐹", "Go. You value simplicity over expressiveness."),
            "elixir":     (18, "💧", "Elixir! Pattern matching and 'fault tolerant' everything."),
            "erlang":     (22, "📡", "Erlang! You were doing distributed computing before it was cool."),
            "clojure":    (20, "🧠", "Clojure! Lisp in the JVM. Peak smug."),
            "ocaml":      (22, "🐪", "OCaml! You either do formal verification or competitive programming."),
            "zig":        (25, "⚡", "Zig! You read the Zig docs for fun. On weekends."),
            "lua":        (10, "🌙", "Lua! Neovim plugin dev or game scripting. Respected."),
            "r":          (10, "📊", "R. You either do data science or biostatistics. Crying either way."),
            "julia":      (18, "📐", "Julia! Fast and beautiful. Nobody around you knows it exists."),
            "nim":        (25, "👁️",  "Nim! 12 people use this and you're one of them. Elite club."),
            "crystal":    (22, "💎", "Crystal! Ruby vibes, C performance. Niche and proud."),
            "dart":       (8,  "🎯", "Dart. Flutter dev or Google employee."),
            "groovy":     (8,  "🎸", "Groovy. Jenkins pipeline victim."),
            "tcl":        (18, "🐍", "Tcl! You are from a different timeline entirely."),
            "sbcl":       (28, "λ",  "Common Lisp (SBCL)! Parentheses all the way down."),
            "racket":     (20, "🎾", "Racket! You took a PL theory class and never recovered."),
            "fortran":    (30, "🦕", "Fortran! You are either 80 years old or doing numerical computing."),
            "cobol":      (35, "🏦", "COBOL! Banks pay you more than God."),
            "ada":        (30, "✈️",  "Ada! Aviation? Defense? You care if planes stay in the sky."),
            "fpc":        (22, "🎠", "Pascal/FPC! Legendary. Nostalgic. Chaotic."),
        }
        for cmd, (pts, emoji, label) in lang_checks.items():
            if cmd_exists(cmd):
                self.award(pts, emoji, f"{label} installed.")
                langs.append(cmd)
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
                self.award(pts, emoji, msg)
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
        
        for cmd, pts, emoji, msg in tools:
            if cmd_exists(cmd):
                self.award(pts, emoji, msg)
                
        # Exclusive checks to prevent double-point bloat
        if cmd_exists("eza"):
            self.award(8, "📁", "eza! ls replacement. Color, icons, git status. Maximum customization.")
        elif cmd_exists("exa"):
            self.award(6, "📁", "exa (old eza)! You care about ls output. Respectable.")

        if cmd_exists("curl"):
            self.award(2, "🌐", "curl. The original API tester.")
        if cmd_exists("wget"):
            self.award(2, "📥", "wget. You download files like a person of culture.")

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
        wm_checks = [
            ("i3",       25, "🪟", "i3wm! Tiling window manager. You tile everything. Even your thoughts."),
            ("sway",     28, "🌊", "Sway! i3 for Wayland. You're on the bleeding edge. It occasionally cuts."),
            ("hyprland", 30, "💫", "Hyprland! Wayland compositor. Your animations are smoother than your social skills."),
            ("bspwm",    25, "🌳", "bspwm! Binary space partitioning. You organize windows like a BST."),
            ("dwm",      35, "⚙️",  "dwm! Dynamic window manager. You compiled your WM from source. On brand."),
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
                self.award(pts, emoji, msg)

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
                self.award(pts, emoji, msg)

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
        if crontab and "#" not in crontab[:5]:
            job_count = len([l for l in crontab.splitlines() if l.strip() and not l.startswith("#")])
            if job_count > 0:
                self.award(12, "⏰", f"{job_count} cron job(s)! Your computer does things while you sleep. Possibly mine crypto.")

        if SYSTEM == "Linux":
            systemd_user = HOME / ".config" / "systemd" / "user"
            if systemd_user.is_dir():
                services = list(systemd_user.glob("*.service"))
                if services:
                    self.award(18, "⚙️", f"{len(services)} systemd user service(s). You write services for your personal projects. Unhinged. Respect.")

        make_count = 0
        try:
            res = run(f'find "{HOME}" -maxdepth 5 -name "Makefile" -o -name "justfile" -o -name "Justfile" 2>/dev/null', timeout=10)
            make_count = len([l for l in res.split("\n") if l.strip()])
        except Exception:
            pass
        if make_count > 10:
            self.award(10, "⚙️", f"{make_count} Makefiles/Justfiles. You automate your automation.")
        elif make_count > 3:
            self.award(5, "⚙️",  f"{make_count} Makefiles/Justfiles.")

        rust_projects = []
        try:
            res = run(f'find "{HOME}" -maxdepth 5 -name "Cargo.toml" 2>/dev/null', timeout=10)
            rust_projects = [l for l in res.split("\n") if l.strip()]
        except Exception:
            pass
        if len(rust_projects) > 5:
            self.award(15, "🦀", f"{len(rust_projects)} Rust projects. You believe in memory safety and you're not shy about it.")
        elif len(rust_projects) > 0:
            self.award(8, "🦀",  f"{len(rust_projects)} Rust project(s). The journey begins.")

        nix_files = []
        try:
            res = run(f'find "{HOME}" -maxdepth 5 -name "*.nix" 2>/dev/null', timeout=8)
            nix_files = [l for l in res.split("\n") if l.strip()]
        except Exception:
            pass
        if len(nix_files) > 10:
            self.award(20, "❄️", f"{len(nix_files)} Nix expression files! Your system is reproducible. Unlike your sleep schedule.")
        elif len(nix_files) > 0:
            self.award(10, "❄️", f"{len(nix_files)} Nix file(s). You're on the path to purity.")

    # ── TIER 5: LEGENDARY — Elite signals ────────────────────────────────

    def check_compilers_and_low_level(self):
        """The deep lore. The C programmers. The kernel hackers."""
        for cmd, pts, emoji, msg in [
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
        ]:
            if cmd_exists(cmd):
                self.award(pts, emoji, msg)

        if SYSTEM == "Linux":
            if cmd_exists("dkms"):
                self.award(15, "⚙️", "DKMS! Dynamic Kernel Module Support. You manage out-of-tree kernel modules.")
            modules_dir = Path("/lib/modules")
            if modules_dir.is_dir():
                kernels = [d for d in modules_dir.iterdir() if d.is_dir()]
                if len(kernels) > 3:
                    self.award(15, "🐧", f"{len(kernels)} kernel versions installed! You keep old kernels 'just in case'. Hoarder. Hero.")
                    self.warn("Multiple kernel versions found. You've been 'just in case' boot-loop-proofing since 2018.")

        cross_tools = ["arm-linux-gnueabi-gcc", "aarch64-linux-gnu-gcc", "mips-linux-gnu-gcc", "riscv64-linux-gnu-gcc"]
        cross_found = [t for t in cross_tools if cmd_exists(t)]
        if cross_found:
            self.award(30, "🔩", f"Cross-compiler(s) found: {', '.join(cross_found)}! You compile for architectures your laptop can't run. Based.")

        if cmd_exists("avr-gcc") or cmd_exists("avrdude"):
            self.award(25, "🤖", "AVR toolchain! You program microcontrollers. Byte-level everything.")
        if cmd_exists("arm-none-eabi-gcc"):
            self.award(25, "🤖", "ARM bare-metal toolchain! Embedded systems. You write code that runs on PCBs.")
        if cmd_exists("pio"):
            self.award(15, "🤖", "PlatformIO! Embedded dev. Arduino grown up.")
        if cmd_exists("qemu") or cmd_exists("qemu-system-x86_64"):
            self.award(20, "🖥️",  "QEMU! Virtual machines from the terminal. You run operating systems as a hobby.")
        if cmd_exists("bochs"):
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
        for cmd, pts, emoji, msg in sec_tools:
            if cmd_exists(cmd):
                self.award(pts, emoji, msg)

        # Handle MSF without double-counting
        if cmd_exists("msfconsole"):
            self.award(15, "💀", "msfconsole! Metasploit console. Pentest credentials confirmed.")
        elif cmd_exists("metasploit-framework"):
            self.award(15, "💀", "Metasploit! You find exploits or you find exploits. Red team detected.")

        sshd_config = "/etc/ssh/sshd_config"
        if file_exists(sshd_config):
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
        for cmd, pts, emoji, msg in ml_tools:
            if cmd_exists(cmd):
                self.award(pts, emoji, msg)

        if cmd_exists("nvcc"):
            self.award(20, "⚡", "NVCC! CUDA compiler! You write GPU kernels. Your code runs on silicon at scale.")
        if cmd_exists("rocminfo") or cmd_exists("clinfo"):
            self.award(15, "⚡", "GPU compute tools (ROCm/OpenCL) installed. Heterogeneous computing enjoyer.")

        if cmd_exists("huggingface-cli"):
            self.award(10, "🤗", "Hugging Face CLI! You download models like normal people download songs.")

    # ── TIER 6: MYTHICAL ─────────────────────────────────────────────────

    def check_legendary_stuff(self):
        """Signs of transcendence."""
        if SYSTEM == "Linux":
            kernel_conf = run("ls /boot/config-* 2>/dev/null")
            if kernel_conf:
                proc_config = run("zcat /proc/config.gz 2>/dev/null | wc -l")
                try:
                    if int(proc_config) > 0:
                        self.award(35, "🐧", "Custom kernel config accessible via /proc! You compile Linux kernels. You are Linux.")
                except Exception:
                    pass

        for latex_cmd, pts, emoji, msg in [
            ("latex",    15, "📄", "LaTeX installed! You typeset mathematics and hate Word users."),
            ("pdflatex", 15, "📄", "pdflatex! You write papers in LaTeX and compile them manually."),
            ("xelatex",  18, "📄", "XeLaTeX! Unicode and custom fonts in LaTeX. Typesetting perfectionist."),
            ("lualatex", 18, "📄", "LuaLaTeX! LaTeX with Lua scripting. Over-engineer even your documents."),
            ("bibtex",   12, "📚", "BibTeX! You manage references in plaintext files. Academic detected."),
        ]:
            if cmd_exists(latex_cmd):
                self.award(pts, emoji, msg)

        lex_tools = ["flex", "bison", "antlr4", "yacc"]
        found_lex = [t for t in lex_tools if cmd_exists(t)]
        if found_lex:
            self.award(30, "🔮", f"Lexer/parser tools found: {', '.join(found_lex)}! You write compilers for fun. Or class. Either way, you suffer beautifully.")

        for tool, pts, emoji, msg in [
            ("lean",     45, "🧮", "Lean theorem prover! You write mathematical proofs as programs. You are beyond programming."),
            ("coq",      45, "🧮", "Coq proof assistant! 'My code doesn't have bugs' — proven by type theory."),
            ("agda",     45, "🧮", "Agda! Dependent types as a lifestyle. You are not a software engineer. You are a mathematician."),
            ("isabelle", 45, "🧮", "Isabelle! Interactive theorem prover. Your hobby is formally verifying software."),
        ]:
            if cmd_exists(tool):
                self.award(pts, emoji, msg)

        for tool, pts, emoji, msg in [
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
        ]:
            if cmd_exists(tool):
                self.award(pts, emoji, msg)

        for irc_tool in ["weechat", "irssi", "hexchat", "catgirl"]:
            if cmd_exists(irc_tool):
                self.award(15, "📡", f"{irc_tool}! IRC client. You use chat protocols from 1988. Timeless.")
                break

        if file_exists(HOME / "flake.nix") or file_exists(HOME / ".config" / "home-manager" / "flake.nix"):
            self.award(35, "❄️", "Nix Flake in home/config! Your entire system is reproducible and your friends don't understand why.")

        if cmd_exists("home-manager"):
            self.award(30, "❄️", "home-manager! You manage your user environment with Nix. Fully declarative. Fully committed.")

        if cmd_exists("guix"):
            self.award(40, "🐃", "GNU Guix! Purely functional package manager. You follow Richard Stallman's path but make it Haskell-adjacent.")

    def run_all(self):
        """Run all checks."""
        checks = [
            ("🖥️  Operating System",           self.check_os),
            ("🐚  Shell",                       self.check_shell),
            ("📝  Code Editors",                self.check_editor_of_choice),
            ("📦  Package Managers",            self.check_package_managers),
            ("💻  Programming Languages",       self.check_languages),
            ("🌿  Git & Version Control",       self.check_git),
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
            ("🔮  Legendary & Mythical",        self.check_legendary_stuff),
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
    (-999, "SLOP",     C_SLOP,
     "🗑️ The Bloatware Enthusiast",
     "You have more telemetry than code. Your system is purely corporate slop.\n"
     "   Please, install a package manager that isn't built by an ad agency.",
     """
   ╔═══════════╗
   ║   SLOP    ║
   ║  🗑️🗑️🗑️  ║
   ║  🔥📉🔥  ║
   ║  🗑️🗑️🗑️  ║
   ╚═══════════╝"""),

    (0,   "COMMON",    C_COMMON,
     "💀 The Muggle Developer",
     "You exist. You code. You Google everything. Stack Overflow is your pair-programmer.\n"
     "   Your code works, but you don't know why. That's fine. Most production code is like that.",
     """
   ╔═══════════╗
   ║  COMMON   ║
   ║  ░░░░░░░  ║
   ║  ░ 💻 ░  ║
   ║  ░░░░░░░  ║
   ╚═══════════╝"""),

    (50,  "UNCOMMON",  C_UNCOMMON,
     "🐣 The Aspiring Nerd",
     "You've installed a real package manager. You have opinions about text editors.\n"
     "   You've told someone 'have you tried Linux?' at least once this year.",
     """
   ╔══════════════╗
   ║  UNCOMMON    ║
   ║  ▒▒▒▒▒▒▒▒▒  ║
   ║  ▒  🐧  ▒  ║
   ║  ▒▒▒▒▒▒▒▒▒  ║
   ╚══════════════╝"""),

    (150, "RARE",      C_RARE,
     "🧙 The Terminal Dweller",
     "You live in the terminal. Your dotfiles have their own GitHub repo.\n"
     "   You've configured vim. You know what tmux is. Your peers fear your knowledge.",
     """
   ╔═══════════════╗
   ║     RARE      ║
   ║  ▓▓▓▓▓▓▓▓▓▓  ║
   ║  ▓  🧙‍♂️  ▓  ║
   ║  ▓▓▓▓▓▓▓▓▓▓  ║
   ╚═══════════════╝"""),

    (300, "EPIC",      C_EPIC,
     "🔮 The Unix Philosopher",
     "You have a tiling window manager. Your prompt shows your git branch AND battery level.\n"
     "   You've built your own shell scripts. 'It's not bloat, it's minimalism.' — You, probably.",
     """
   ╔═══════════════╗
   ║     EPIC      ║
   ║  ████████████ ║
   ║  █   🔮   █  ║
   ║  ████████████ ║
   ╚═══════════════╝"""),

    (500, "LEGENDARY", C_LEGENDARY,
     "⚡ The 10x Myth, Made Real",
     "You compile things from source. You have multiple cross-compilers. Your .zshrc is longer\n"
     "   than most novels. You've written a custom kernel module. People ask you for advice\n"
     "   and you speak in cryptic profundities. You are the wizard the legends spoke of.",
     """
   ╔════════════════╗
   ║  LEGENDARY ⚡  ║
   ║  ██████████████║
   ║  ██  ⚡🦅⚡  ██║
   ║  ██████████████║
   ╚════════════════╝"""),

    (800, "MYTHICAL",  C_MYTHICAL,
     "🌌 The Ascended Being",
     "You are beyond human classification. You write theorem provers as a hobby.\n"
     "   You use APL or J. You compile your own compilers. You run Gentoo or BSD or Plan 9.\n"
     "   You have proven the correctness of your software with Coq.\n"
     "   NASA has considered hiring you. The kernel mailing list knows your name.",
     """
   ╔══════════════════════╗
   ║  ✨ MYTHICAL ✨       ║
   ║  ▓░▒█▓░▒█▓░▒█▓░▒█▓  ║
   ║  ░  🌌 BEYOND 🌌  ░  ║
   ║  ▓░▒█▓░▒█▓░▒█▓░▒█▓  ║
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

def print_score_bar(score: int, max_score: int = 1000):
    width = 50
    # Clamping the bar visual to 0 even if the score is negative to prevent weird rendering
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
        "SLOP": [
            "We detected more bloat on your system than actual code.",
            "Please uninstall Eclipse and try again.",
            "Sir, this is a proprietary disaster.",
        ],
        "COMMON": [
            "Your terminal is black. That's the one good thing you've done.",
            "Keep going. The vim tutorial is waiting.",
            "Everyone starts somewhere. You started here. Godspeed.",
        ],
        "UNCOMMON": [
            "You've installed Homebrew. You've tasted freedom. There's no going back.",
            "You're on the path. The path involves compiling things for no reason.",
            "You installed Linux once. You reinstalled it six times. Progress.",
        ],
        "RARE": [
            "Your .zshrc is longer than your relationships.",
            "You've customized your terminal prompt. You've peaked. And also just begun.",
            "You said 'have you tried Linux?' to someone this week. I can tell.",
        ],
        "EPIC": [
            "Your window manager has no title bars and you call it efficiency.",
            "You've written a shell script that makes other shell scripts. Inception.",
            "People ask you for advice. You give them man pages. Correct.",
        ],
        "LEGENDARY": [
            "You understand why the kernel is written in C. You have opinions about it.",
            "Your dotfiles have their own CI/CD pipeline.",
            "You compiled your terminal emulator from source. On purpose.",
        ],
        "MYTHICAL": [
            "Linus Torvalds has responded to your email. Once. You saved it.",
            "You don't write code. You write proofs that happen to be executable.",
            "The machine knows your name. The machine fears you.",
        ],
    }

    print(f"\n  {C_CYAN}{ITALIC}» {random.choice(roasts.get(name, ['You are unique. The scanner doesn\'t know what to say.']))}{RESET}")
    print(f"\n  {color}{BOLD}{'═' * 58}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print_banner()

    print(f"  {C_GRAY}System: {platform.system()} {platform.machine()} | Python {platform.python_version()}{RESET}")
    print(f"  {C_GRAY}Home: {HOME}{RESET}")
    print(f"\n  {C_YELLOW}Starting deep scan of your developer soul...{RESET}")
    print(f"  {C_GRAY}(No data leaves your machine. Unlike that npm package you installed yesterday.){RESET}")
    time.sleep(1)

    scanner = DevScanner()
    scanner.run_all()

    # Sort findings by points descending
    scanner.findings.sort(key=lambda x: x[0], reverse=True)

    # Print findings (top 40 most interesting)
    top_findings = scanner.findings[:60]
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