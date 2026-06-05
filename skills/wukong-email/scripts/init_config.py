#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Initialize the user-level configuration for wukong-email.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    return Path.home() / ".wukong-email"


def check_and_install_dependencies(skill_dir: Path) -> None:
    """Check and install markdown library"""
    try:
        import markdown
        print("[OK] markdown library installed")
    except ImportError:
        print("[!] markdown library not installed")
        print("[*] Attempting auto-install...")
        try:
            requirements_txt = skill_dir / "requirements.txt"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_txt)],
                check=True,
                capture_output=True
            )
            print("[OK] markdown library installed successfully")
        except (subprocess.CalledProcessError, PermissionError):
            print("[!] Auto-install failed, please run manually:")
            print(f"    pip install -r {requirements_txt}")


def init_config(skill_dir: Optional[Path] = None) -> Path:
    if skill_dir is None:
        skill_dir = Path(__file__).resolve().parents[1]

    source = skill_dir / "env.example"
    config_dir = get_config_dir()
    target = config_dir / ".env"

    if not source.exists():
        raise FileNotFoundError(f"Template not found: {source}")

    config_dir.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        shutil.copyfile(source, target)
        print(f"Created config file: {target}")
    else:
        print(f"Config file already exists, not overwritten: {target}")

    print(f"Edit this file and fill in your mailbox settings: {target}")
    return target


def main() -> int:
    skill_dir = Path(__file__).resolve().parents[1]
    init_config(skill_dir)
    check_and_install_dependencies(skill_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
