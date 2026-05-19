#!/usr/bin/env python3
"""Fix yamllint line-length violations in ComplianceAsCode content files.

Processes rule.yml, group.yml, control files, and profiles. Lines exceeding
the maximum length are either broken at word boundaries or annotated with
a yamllint disable comment when breaking is not possible.
"""

import argparse
import difflib
import os
import re
import subprocess
import sys


MAX_LENGTH = 99
YAMLLINT_DISABLE = "  # yamllint disable-line rule:line-length"

CONTENT_FILE_PATTERNS = {"rule.yml", "group.yml"}
CONTROL_DIR_NAMES = {"controls"}
PROFILE_EXTENSION = ".profile"

DOUBLE_QUOTED_ESCAPE_RE = re.compile(r'^\s+description:\s+".*\\$')
BACKSLASH_CONTINUATION_RE = re.compile(r'^\s+\\ .*\\$')

BLOCK_SCALAR_RE = re.compile(
    r'^(\s*\S.*?):\s*(-?)([|>])(-?)\s*$'
)

JINJA2_STATEMENT_RE = re.compile(r'\{\{%')
JINJA2_EXPR_FULL_LINE_RE = re.compile(
    r'^\s*\{\{\{.*\}\}\}\s*$'
)
JINJA2_STMT_FULL_LINE_RE = re.compile(
    r'^\s*\{\{%.*%\}\}\s*$'
)
NO_BREAK_ZONE_RE = re.compile(
    r'\{\{\{.*?\}\}\}'
    r'|\{\{%.*?%\}\}'
    r'|<pre\b[^>]*>.*?</pre>',
    re.IGNORECASE,
)

REFERENCE_KEYS = {
    "isa-62443-2009", "isa-62443-2013", "cobit5", "nerc-cip",
    "hipaa", "iso27001-2013", "nist-csf", "srg", "nist",
    "cis-csc", "stigid", "stigref", "pcidss", "pcidss4",
    "anssi", "ospp", "cui", "disa", "isa-62443-2013",
}

INLINE_KEY_VALUE_RE = re.compile(
    r'^(\s*)(\S+)\s*:\s*(.*\S)\s*$'
)
LIST_ITEM_KEY_VALUE_RE = re.compile(
    r'^(\s*)-\s+(\S+)\s*:\s*(.*\S)\s*$'
)


def find_repo_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()


def discover_files(root):
    """Find content files to process."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        skip_dirs = ("build", "tests", ".git", ".github", ".tox",
                      ".claude", "logs", "docs", ".vscode")
        if any(rel == d or rel.startswith(d + os.sep) for d in skip_dirs):
            dirnames.clear()
            continue

        for fname in filenames:
            full_path = os.path.join(dirpath, fname)

            if fname in CONTENT_FILE_PATTERNS:
                files.append(full_path)
                continue

            if fname.endswith(PROFILE_EXTENSION):
                files.append(full_path)
                continue

            if fname.endswith(".yml") or fname.endswith(".yaml"):
                parts = rel.split(os.sep)
                if any(p == "controls" for p in parts):
                    files.append(full_path)
                    continue

    return sorted(files)


def has_double_quoted_escapes(lines):
    """Detect files using double-quoted \\n/\\ continuation pattern."""
    for line in lines:
        if DOUBLE_QUOTED_ESCAPE_RE.match(line):
            return True
        if BACKSLASH_CONTINUATION_RE.match(line):
            return True
    return False


def get_indent(line):
    """Return the number of leading spaces."""
    return len(line) - len(line.lstrip(" "))


class LineClassification:
    SKIP = "skip"
    UNBREAKABLE = "unbreakable"
    UNFIXABLE = "unfixable"  # inside block scalar, can't add comments
    BREAKABLE_INLINE = "breakable_inline"
    BREAKABLE_BLOCK = "breakable_block"


class YamlContext:
    """Track YAML parsing context for line classification."""

    def __init__(self):
        self.in_block_scalar = False
        self.block_scalar_indent = 0
        self.block_scalar_type = None
        self.block_scalar_pending = False
        self.in_references = False
        self.references_indent = 0
        self.references_key_indent = 0
        self.references_pending = False

    def update(self, line):
        """Update state based on current line, called BEFORE classifying."""
        stripped = line.strip()

        if not stripped:
            return

        indent = get_indent(line)

        if self.block_scalar_pending:
            if stripped:
                self.in_block_scalar = True
                self.block_scalar_indent = indent
                self.block_scalar_pending = False
            return

        if self.in_block_scalar:
            if indent < self.block_scalar_indent and stripped:
                self.in_block_scalar = False
                self.block_scalar_type = None
            else:
                return

        if self.references_pending:
            if stripped:
                self.in_references = True
                self.references_indent = indent
                self.references_pending = False

        if self.in_references:
            if indent <= self.references_key_indent and stripped:
                if not stripped.startswith("references:"):
                    self.in_references = False
                    self.references_pending = False

        m = BLOCK_SCALAR_RE.match(line)
        if m:
            self.block_scalar_type = m.group(3)
            self.block_scalar_pending = True

        if stripped == "references:":
            self.references_key_indent = indent
            self.references_pending = True


def classify_line(line, ctx):
    """Classify a long line (>max_length) into a handling category."""
    stripped = line.strip()

    if stripped.startswith("#"):
        return LineClassification.SKIP

    if ctx.in_block_scalar:
        if JINJA2_EXPR_FULL_LINE_RE.match(line):
            return LineClassification.UNFIXABLE

        if "{{{" in stripped and "}}}" in stripped:
            if stripped.startswith("{{{") and stripped.endswith("}}}"):
                return LineClassification.UNFIXABLE

        if JINJA2_STMT_FULL_LINE_RE.match(line):
            return LineClassification.UNFIXABLE

        return LineClassification.BREAKABLE_BLOCK

    if JINJA2_STATEMENT_RE.search(line):
        return LineClassification.UNBREAKABLE

    if ctx.in_references:
        return LineClassification.UNBREAKABLE

    m = INLINE_KEY_VALUE_RE.match(line)
    if m:
        key = m.group(2)

        if key in ("filepath", "filepath:"):
            return LineClassification.UNBREAKABLE
        if key == "source" or key == "source:":
            return LineClassification.UNBREAKABLE

        value = m.group(3)
        clean = re.sub(
            r'\s*#\s*yamllint disable-line\b.*$', '', value,
        )
        if '  # ' in clean or clean.endswith('  #'):
            return LineClassification.UNBREAKABLE

        if clean.startswith('[') or clean.startswith('{'):
            return LineClassification.UNBREAKABLE

        return LineClassification.BREAKABLE_INLINE

    if LIST_ITEM_KEY_VALUE_RE.match(line):
        return LineClassification.UNBREAKABLE

    return LineClassification.UNFIXABLE


def add_yamllint_disable(line):
    """Add yamllint disable comment if not already present."""
    if "yamllint disable-line" in line:
        return line
    return line.rstrip() + YAMLLINT_DISABLE


def break_line_at_width(text, max_width):
    """Find the last space position where text fits within max_width chars.

    Returns the index to split at, or -1 if no break point found.
    """
    if len(text) <= max_width:
        return -1

    last_space = -1
    for i in range(min(max_width, len(text)) - 1, 0, -1):
        if text[i] == " ":
            last_space = i
            break

    return last_space


def _inside_html_tag(text, pos):
    """Check if position is between an unclosed '<' and its '>'."""
    last_open = text.rfind('<', 0, pos)
    if last_open == -1:
        return False
    close_after_open = text.find('>', last_open, pos)
    return close_after_open == -1


def _find_no_break_zones(text):
    """Find regions in text where line breaks cannot be placed.

    Covers Jinja2 expressions ({{{ }}}), Jinja2 statements ({{% %}}),
    and <pre>...</pre> blocks.
    """
    return [(m.start(), m.end()) for m in NO_BREAK_ZONE_RE.finditer(text)]


def _in_no_break_zone(zones, pos):
    """Check if position falls inside any no-break zone."""
    for start, end in zones:
        if start < pos < end:
            return True
    return False


def _find_valid_break(text, max_width, min_pos, zones):
    """Find the rightmost space within max_width that avoids no-break zones."""
    for i in range(min(max_width, len(text)) - 1, min_pos, -1):
        if (text[i] == " "
                and not _in_no_break_zone(zones, i)
                and not _inside_html_tag(text, i)):
            return i
    return -1


def split_block_scalar_line(line, max_length):
    """Split a long line inside a block scalar at word boundaries.

    Returns None if any resulting fragment would still exceed max_length
    with no further break point (can't be fixed by splitting).
    """
    indent = get_indent(line)
    indent_str = " " * indent

    result_lines = []
    remaining = line.rstrip()

    while len(remaining) > max_length:
        zones = _find_no_break_zones(remaining)
        break_pos = _find_valid_break(
            remaining, max_length, indent, zones,
        )
        if break_pos < 0:
            return None

        result_lines.append(remaining[:break_pos].rstrip())
        remaining = indent_str + remaining[break_pos + 1:]

    if remaining.strip():
        result_lines.append(remaining)

    return result_lines


def collect_inline_continuation(lines, start_idx):
    """Collect continuation lines for an inline scalar starting at start_idx.

    Returns (full_value_text, number_of_continuation_lines_consumed).
    """
    m = INLINE_KEY_VALUE_RE.match(lines[start_idx].rstrip("\n").rstrip("\r"))
    if not m:
        return None, 0

    key_indent = len(m.group(1))
    value_part = m.group(3)

    min_continuation_indent = key_indent + 1
    parts = [value_part]
    consumed = 0

    for j in range(start_idx + 1, len(lines)):
        next_line = lines[j].rstrip("\n").rstrip("\r")
        if not next_line.strip():
            break
        next_indent = get_indent(next_line)
        if next_indent <= key_indent:
            break
        if next_indent < min_continuation_indent:
            break
        parts.append(next_line.strip())
        consumed += 1

    full_value = " ".join(parts)
    return full_value, consumed


def split_inline_scalar(indent_str, key, full_value, max_length):
    """Split a full inline scalar value using YAML plain continuation."""
    key_prefix = f"{indent_str}{key}: "
    key_indent = len(indent_str)
    continuation_indent = " " * (key_indent + 4)

    first_line_text = key_prefix + full_value
    if len(first_line_text) <= max_length:
        return [first_line_text]

    available_first = max_length - len(key_prefix)
    if available_first <= 0:
        return None

    break_pos = -1
    for i in range(min(available_first, len(full_value)) - 1, 0, -1):
        if full_value[i] == " ":
            break_pos = i
            break

    if break_pos <= 0:
        return None

    first_part = full_value[:break_pos].rstrip()
    rest = full_value[break_pos + 1:]

    result_lines = [f"{key_prefix}{first_part}"]

    remaining = f"{continuation_indent}{rest}"
    while len(remaining) > max_length:
        break_pos = break_line_at_width(remaining, max_length)
        cont_len = len(continuation_indent)
        if break_pos <= cont_len:
            result_lines.append(
                add_yamllint_disable(remaining))
            remaining = ""
            break

        result_lines.append(remaining[:break_pos].rstrip())
        remaining = continuation_indent + remaining[break_pos + 1:]

    if remaining and remaining.strip():
        result_lines.append(remaining)

    return result_lines


def process_file(filepath, max_length, dry_run):
    """Process a single file. Returns (changed, stats_dict)."""
    stats = {"lines_broken": 0, "lines_disabled": 0, "lines_unfixable": 0}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original_lines = f.readlines()
    except (UnicodeDecodeError, OSError) as e:
        print(f"  SKIP {filepath}: {e}", file=sys.stderr)
        return False, stats

    if has_double_quoted_escapes(original_lines):
        print(f"  SKIP {filepath}: double-quoted escape pattern detected")
        return False, stats

    ctx = YamlContext()
    new_lines = []
    changed = False

    i = 0
    while i < len(original_lines):
        line = original_lines[i].rstrip("\n").rstrip("\r")

        ctx.update(line)

        if len(line) <= max_length:
            new_lines.append(line)
            i += 1
            continue

        classification = classify_line(line, ctx)

        if classification == LineClassification.SKIP:
            new_lines.append(line)
            i += 1
            continue

        if classification == LineClassification.UNFIXABLE:
            new_lines.append(line)
            stats["lines_unfixable"] += 1
            i += 1
            continue

        if classification == LineClassification.UNBREAKABLE:
            new_line = add_yamllint_disable(line)
            if new_line != line:
                changed = True
                stats["lines_disabled"] += 1
            new_lines.append(new_line)
            i += 1
            continue

        if classification == LineClassification.BREAKABLE_BLOCK:
            result = split_block_scalar_line(line, max_length)
            if result is None:
                new_lines.append(line)
                stats["lines_unfixable"] += 1
            elif len(result) > 1:
                new_lines.extend(result)
                changed = True
                stats["lines_broken"] += 1
            else:
                new_lines.append(line)
            i += 1
            continue

        if classification == LineClassification.BREAKABLE_INLINE:
            m = INLINE_KEY_VALUE_RE.match(line)
            if not m:
                new_lines.append(line)
                i += 1
                continue

            full_value, consumed = collect_inline_continuation(
                original_lines, i,
            )
            if full_value is None:
                new_lines.append(line)
                i += 1
                continue

            result = split_inline_scalar(
                m.group(1), m.group(2), full_value, max_length,
            )
            if result is None:
                new_line = add_yamllint_disable(line)
                if new_line != line:
                    changed = True
                    stats["lines_disabled"] += 1
                new_lines.append(new_line)
                i += 1
            elif len(result) > 1 or consumed > 0:
                new_lines.extend(result)
                changed = True
                stats["lines_broken"] += 1
                i += 1 + consumed
            else:
                new_lines.append(result[0])
                i += 1
            continue

        new_lines.append(line)
        i += 1

    if not changed:
        return False, stats

    new_content = "\n".join(new_lines) + "\n"

    if dry_run:
        original_content_lines = [l.rstrip("\n").rstrip("\r") + "\n"
                                  for l in original_lines]
        new_content_lines = [l + "\n" for l in new_lines]
        diff = difflib.unified_diff(
            original_content_lines,
            new_content_lines,
            fromfile=filepath,
            tofile=filepath,
        )
        diff_text = "".join(diff)
        if diff_text:
            print(diff_text)
    else:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    return True, stats


def main():
    parser = argparse.ArgumentParser(
        description="Fix yamllint line-length violations "
                    "in ComplianceAsCode content files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root (default: auto-detect via git)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=MAX_LENGTH,
        help=f"Maximum line length (default: {MAX_LENGTH})",
    )
    args = parser.parse_args()

    root = args.root or find_repo_root()
    if not os.path.isdir(root):
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    files = discover_files(root)
    print(f"Found {len(files)} content files to process")

    total_changed = 0
    total_broken = 0
    total_disabled = 0
    total_unfixable = 0

    for filepath in files:
        file_changed, stats = process_file(filepath, args.max_length, args.dry_run)
        if file_changed:
            total_changed += 1
        total_broken += stats["lines_broken"]
        total_disabled += stats["lines_disabled"]
        total_unfixable += stats["lines_unfixable"]

    action = "would change" if args.dry_run else "changed"
    print(f"\nSummary: {action} {total_changed} files")
    print(f"  Lines broken at word boundaries: {total_broken}")
    print(f"  Lines marked yamllint-disable: {total_disabled}")
    if total_unfixable:
        print(f"  Lines unfixable (inside block scalars): {total_unfixable}")


if __name__ == "__main__":
    main()
