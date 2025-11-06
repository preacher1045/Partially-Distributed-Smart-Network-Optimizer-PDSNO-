import os

# === CONFIGURATION ===
COPYRIGHT_HOLDER = "Atlas Iris"
YEAR = "2025"
PROJECT_NAME = "PDSNO"
LICENSE_TAG = "SPDX-License-Identifier: AGPL-3.0-or-later"

# File extensions and their comment styles
COMMENT_STYLES = {
    # Hash-style comments
    ".py": "#",
    ".sh": "#",
    ".rb": "#",

    # Double-slash comments
    ".js": "//",
    ".ts": "//",
    ".go": "//",
    ".java": "//",
    ".c": "//",
    ".cpp": "//",
    ".cs": "//",
    ".swift": "//",

    # Block comments
    ".html": "/*",
    ".css": "/*"
}

EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", "venv", "dist", "build"}

def make_header(comment_symbol, block=False):
    """Generate a language-appropriate header."""
    if block and comment_symbol == "/*":
        return (
            f"/*\n"
            f" * Copyright (C) {YEAR} {COPYRIGHT_HOLDER}\n"
            f" * {LICENSE_TAG}\n"
            f" *\n"
            f" * This file is part of {PROJECT_NAME}.\n"
            f" * See the LICENSE file in the project root for license information.\n"
            f" */\n\n"
        )
    else:
        return (
            f"{comment_symbol} Copyright (C) {YEAR} {COPYRIGHT_HOLDER}\n"
            f"{comment_symbol} {LICENSE_TAG}\n"
            f"{comment_symbol}\n"
            f"{comment_symbol} This file is part of {PROJECT_NAME}.\n"
            f"{comment_symbol} See the LICENSE file in the project root for license information.\n\n"
        )

def has_header(content):
    """Check if file already contains SPDX tag."""
    return LICENSE_TAG in content[:300]

def add_header_to_file(filepath, comment_symbol):
    block = (comment_symbol == "/*")
    header = make_header(comment_symbol, block)
    with open(filepath, "r+", encoding="utf-8") as f:
        content = f.read()
        if has_header(content):
            return False
        f.seek(0)
        f.write(header + content)
    return True

def main():
    added = 0
    for root, _, files in os.walk("."):
        if any(excluded in root for excluded in EXCLUDE_DIRS):
            continue
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in COMMENT_STYLES:
                path = os.path.join(root, file)
                if add_header_to_file(path, COMMENT_STYLES[ext]):
                    added += 1
                    print(f"Added header to: {path}")
    print(f"\n✅ Done. Added headers to {added} file(s).")

if __name__ == "__main__":
    main()
