import os
import sys

# === CONFIGURATION ===
COPYRIGHT_HOLDER = "TENKEI"
YEAR = "2025"
PROJECT_NAME = "PDSNO"
LICENSE_TAG = "SPDX-License-Identifier: AGPL-3.0-or-later"

# ---------------------------------------------------------------------------
# Comment style definitions
#
# Each entry maps a file extension to one of four style keys:
#   "hash"       →  # comment
#   "slash"      →  // comment
#   "block"      →  /* ... */ comment
#   "html"       →  <!-- ... --> comment
#   "dash_block" →  {- ... -} (Haskell)
#   "semicolon"  →  ; comment (assembly, some config formats)
# ---------------------------------------------------------------------------
COMMENT_STYLES: dict[str, str] = {
    # Hash-style
    ".py":      "hash",
    ".sh":      "hash",
    ".bash":    "hash",
    ".zsh":     "hash",
    ".rb":      "hash",
    ".pl":      "hash",
    ".r":       "hash",
    ".yaml":    "hash",
    ".yml":     "hash",
    ".toml":    "hash",
    ".tf":      "hash",       # Terraform
    ".tfvars":  "hash",
    ".cmake":   "hash",
    ".makefile": "hash",
    ".mk":      "hash",
    ".conf":    "hash",
    ".ini":     "hash",       # some .ini files support # comments
    ".dockerfile": "hash",    # bare Dockerfile
    "Dockerfile": "hash",     # exact filename match (handled separately)

    # Slash-style
    ".js":      "slash",
    ".ts":      "slash",
    ".jsx":     "slash",
    ".tsx":     "slash",
    ".go":      "slash",
    ".java":    "slash",
    ".c":       "slash",
    ".h":       "slash",
    ".cpp":     "slash",
    ".cc":      "slash",
    ".cxx":     "slash",
    ".cs":      "slash",
    ".swift":   "slash",
    ".kt":      "slash",
    ".kts":     "slash",
    ".rs":      "slash",      # Rust
    ".scala":   "slash",
    ".groovy":  "slash",
    ".gradle":  "slash",
    ".php":     "slash",

    # Block-style (/* */)
    ".css":     "block",
    ".scss":    "block",
    ".sass":    "block",
    ".less":    "block",

    # HTML-style (<!-- -->)
    ".html":    "html",
    ".htm":     "html",
    ".xml":     "html",
    ".svg":     "html",
    ".vue":     "html",
}

# Exact filename matches (no extension, or special names like Dockerfile)
EXACT_FILENAME_STYLES: dict[str, str] = {
    "Dockerfile":       "hash",
    "Makefile":         "hash",
    "Jenkinsfile":      "slash",
    ".gitattributes":   "hash",
    ".editorconfig":    "hash",
}

# Directories to never touch
EXCLUDE_DIRS: set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    "site",            # MkDocs output
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "migrations",      # DB migration files — usually auto-generated
    "vendor",
}

# Files to never touch regardless of extension
EXCLUDE_FILES: set[str] = {
    "LICENSE",
    "LICENSE.md",
    "CHANGELOG.md",
    "requirements.txt",
    "requirements-dev.txt",
    "poetry.lock",
    "package-lock.json",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
    "*.min.js",        # Note: glob patterns not supported here, handled below
    "*.min.css",
}


# ---------------------------------------------------------------------------
# Header templates
# ---------------------------------------------------------------------------

def make_hash_header() -> str:
    return (
        f"# Copyright (C) {YEAR} {COPYRIGHT_HOLDER}\n"
        f"# {LICENSE_TAG}\n"
        f"#\n"
        f"# This file is part of {PROJECT_NAME}.\n"
        f"# See the LICENSE file in the project root for license information.\n"
        f"\n"
    )

def make_slash_header() -> str:
    return (
        f"// Copyright (C) {YEAR} {COPYRIGHT_HOLDER}\n"
        f"// {LICENSE_TAG}\n"
        f"//\n"
        f"// This file is part of {PROJECT_NAME}.\n"
        f"// See the LICENSE file in the project root for license information.\n"
        f"\n"
    )

def make_block_header() -> str:
    return (
        f"/*\n"
        f" * Copyright (C) {YEAR} {COPYRIGHT_HOLDER}\n"
        f" * {LICENSE_TAG}\n"
        f" *\n"
        f" * This file is part of {PROJECT_NAME}.\n"
        f" * See the LICENSE file in the project root for license information.\n"
        f" */\n"
        f"\n"
    )

def make_html_header() -> str:
    return (
        f"<!--\n"
        f"  Copyright (C) {YEAR} {COPYRIGHT_HOLDER}\n"
        f"  {LICENSE_TAG}\n"
        f"\n"
        f"  This file is part of {PROJECT_NAME}.\n"
        f"  See the LICENSE file in the project root for license information.\n"
        f"-->\n"
        f"\n"
    )

HEADER_BUILDERS: dict[str, callable] = {
    "hash":  make_hash_header,
    "slash": make_slash_header,
    "block": make_block_header,
    "html":  make_html_header,
}


# ---------------------------------------------------------------------------
# Lines that must remain as the very first line of the file
# These are detected and preserved above the inserted header
# ---------------------------------------------------------------------------
MUST_BE_FIRST_LINE_PREFIXES: tuple[str, ...] = (
    "#!",               # Shebangs: #!/usr/bin/env python3
    "<?xml",            # XML declarations
    "<!DOCTYPE",        # HTML doctypes
)

YAML_DOC_SEPARATOR = "---"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def has_header(content: str) -> bool:
    """Return True if the file already contains the SPDX tag anywhere in the first 500 chars."""
    return LICENSE_TAG in content[:500]


def should_skip_file(filename: str) -> bool:
    """Return True if this file should never be touched."""
    if filename in EXCLUDE_FILES:
        return True
    # Skip minified files
    if filename.endswith(".min.js") or filename.endswith(".min.css"):
        return True
    return False


def is_excluded_dir(path_parts: list[str]) -> bool:
    """
    Return True if any component of the path is an excluded directory.
    Uses exact component matching — 'build_tools' will NOT match 'build'.
    """
    return any(part in EXCLUDE_DIRS for part in path_parts)


def get_style(filename: str) -> str | None:
    """
    Return the comment style key for this filename, or None if unknown.
    Checks exact filename matches first, then extension.
    """
    if filename in EXACT_FILENAME_STYLES:
        return EXACT_FILENAME_STYLES[filename]
    ext = os.path.splitext(filename)[1].lower()
    return COMMENT_STYLES.get(ext)


def split_preserved_prefix(content: str, ext: str) -> tuple[str, str]:
    """
    Split content into (prefix_to_keep_first, rest).

    For shebangs, XML declarations, and DOCTYPE lines: the first line must
    stay at position 0. We extract it and prepend it back after the header.

    For YAML files: the '---' document separator is treated the same way.
    """
    lines = content.splitlines(keepends=True)
    if not lines:
        return "", content

    first_line = lines[0]
    stripped = first_line.strip()

    # Shebang
    if stripped.startswith("#!"):
        return first_line, "".join(lines[1:])

    # XML / HTML preamble
    if stripped.startswith("<?xml") or stripped.startswith("<!DOCTYPE"):
        return first_line, "".join(lines[1:])

    # YAML document separator
    if ext in (".yaml", ".yml") and stripped == "---":
        return first_line, "".join(lines[1:])

    return "", content


def add_header_to_file(filepath: str, style: str) -> bool:
    """
    Add the copyright header to filepath if not already present.
    Returns True if the file was modified, False if skipped.
    Writes atomically: read → build new content → write.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError) as e:
        print(f"  SKIP (unreadable): {filepath} — {e}", file=sys.stderr)
        return False

    if has_header(content):
        return False

    ext = os.path.splitext(filepath)[1].lower()
    preserved_prefix, remainder = split_preserved_prefix(content, ext)

    header = HEADER_BUILDERS[style]()

    if preserved_prefix:
        # shebang / XML decl goes first, then a blank line, then header, then rest
        new_content = preserved_prefix + "\n" + header + remainder
    else:
        new_content = header + content

    # Atomic write: write to a temp file in the same directory, then replace
    dir_name = os.path.dirname(filepath) or "."
    tmp_path = filepath + ".tmp_header"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, filepath)   # atomic on POSIX; best-effort on Windows
    except Exception as e:
        print(f"  ERROR writing {filepath}: {e}", file=sys.stderr)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    added = 0
    skipped_unreadable = 0

    for root, dirs, files in os.walk("."):
        # Prune excluded directories in-place so os.walk doesn't descend into them
        # This is more efficient than checking root after the fact
        path_parts = root.replace("\\", "/").strip("/").split("/")
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE_DIRS
        ]

        if is_excluded_dir(path_parts):
            continue

        for filename in files:
            if should_skip_file(filename):
                continue

            style = get_style(filename)
            if style is None:
                continue

            filepath = os.path.join(root, filename)
            result = add_header_to_file(filepath, style)
            if result:
                added += 1
                print(f"  ✓  {filepath}")

    print(f"\n{'─' * 50}")
    print(f"  Done.  {added} file(s) updated.")
    if skipped_unreadable:
        print(f"  {skipped_unreadable} file(s) skipped (unreadable).")
    print(f"{'─' * 50}")


if __name__ == "__main__":
    main()