#!/usr/bin/env python3
"""
Remove empty 'rules:' sections from ITSAR control file.
An empty rules section is one that contains no actual rule items (lines starting with '-').
"""

import sys
import re
from pathlib import Path


def has_actual_rules(lines):
    """
    Check if a list of lines contains actual rule items.
    Rule items are lines that start with '-' (after whitespace), excluding comments.
    """
    for line in lines:
        stripped = line.lstrip()
        # Check if it's a list item (starts with '-') and not a comment
        if stripped.startswith('-') and not stripped.startswith('- #'):
            return True
    return False


def remove_empty_rules_sections(content):
    """
    Remove empty 'rules:' sections from YAML content.
    """
    lines = content.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line is a 'rules:' key
        if re.match(r'^(\s*)rules:\s*$', line):
            rules_indent = len(line) - len(line.lstrip())
            rules_line_idx = i

            # Collect all lines that belong to this rules section
            rules_content = []
            i += 1

            while i < len(lines):
                next_line = lines[i]

                # Empty line - include it for now
                if not next_line.strip():
                    rules_content.append(next_line)
                    i += 1
                    continue

                # Calculate indentation
                next_indent = len(next_line) - len(next_line.lstrip())

                # If indentation is less or equal to rules indent, we've left the rules section
                if next_indent <= rules_indent:
                    break

                # This line is part of the rules section
                rules_content.append(next_line)
                i += 1

            # Check if rules section has actual rules
            if has_actual_rules(rules_content):
                # Keep the rules section
                result.append(line)
                result.extend(rules_content)
            else:
                # Skip the rules section (don't add to result)
                # Also remove trailing empty lines from rules_content
                pass
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def main():
    if len(sys.argv) != 2:
        print("Usage: remove_empty_rules.py <yaml_file>")
        print("Example: remove_empty_rules.py controls/itsar.yml")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)

    # Read the file
    print(f"Reading {file_path}...")
    content = file_path.read_text()

    # Process the content
    print("Removing empty rules sections...")
    modified_content = remove_empty_rules_sections(content)

    # Write back
    print(f"Writing modified content to {file_path}...")
    file_path.write_text(modified_content)

    # Count how many rules sections were removed
    original_rules_count = content.count('\n    rules:\n') + content.count('\n    rules:')
    modified_rules_count = modified_content.count('\n    rules:\n') + modified_content.count('\n    rules:')
    removed_count = original_rules_count - modified_rules_count

    print(f"Done! Removed {removed_count} empty rules sections.")
    print(f"Remaining rules sections: {modified_rules_count}")


if __name__ == '__main__':
    main()
