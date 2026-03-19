"""Bump the version in pyproject.toml."""

import argparse
import tomllib
from pathlib import Path

from packaging.version import Version

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def bump(bump_type: str) -> Version:
    with open(PYPROJECT, "rb") as f:
        current = Version(tomllib.load(f)["project"]["version"])

    if bump_type == "major":
        new = Version(f"{current.major + 1}.0.0")
    elif bump_type == "minor":
        new = Version(f"{current.major}.{current.minor + 1}.0")
    else:
        new = Version(f"{current.major}.{current.minor}.{current.micro + 1}")

    text = PYPROJECT.read_text()
    text = text.replace(f'version = "{current}"', f'version = "{new}"')
    PYPROJECT.write_text(text)
    return new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bump_type", choices=["major", "minor", "patch"])
    args = parser.parse_args()
    new = bump(args.bump_type)
    print(new)


if __name__ == "__main__":
    main()
