#!/usr/bin/env python3

"""
A tool for adding new SCAP profiles to the project.

This script automates the creation of new SCAP profiles by generating the necessary
files and configurations. It expects that the control file already exists before
creating a profile that references it.
"""

import argparse
import re
import sys
import textwrap
import yaml
from pathlib import Path


class LiteralString(str):
    """Custom string class for YAML literal block scalar representation."""
    pass


def literal_string_representer(dumper, data):
    """Represent strings using YAML literal block scalar style (|-)."""
    text = [line.rstrip() for line in data.splitlines()]
    sanitized = '\n'.join(text)
    return dumper.represent_scalar('tag:yaml.org,2002:str', sanitized, style='|-')


yaml.add_representer(LiteralString, literal_string_representer)


class ProfileCreator:
    """Handles the creation of SCAP profile files and related configurations."""

    def __init__(self, args):
        self.args = args
        self.repo_root = self._find_repo_root()
        self.product_dir = self.repo_root / "products" / args.product
        self.profile_path = self.product_dir / "profiles" / f"{args.name}.profile"
        self.errors = []
        self.warnings = []

    def _find_repo_root(self):
        """Find the repository root directory."""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / "CMakeLists.txt").exists() and (current / "products").exists():
                return current
            current = current.parent
        raise RuntimeError("Could not find repository root")

    def validate_inputs(self):
        """Validate all inputs before creating files."""
        # Check if product exists
        if not self.product_dir.exists():
            self.errors.append(f"Product '{self.args.product}' does not exist at {self.product_dir}")
            return False

        # Check if profiles directory exists
        profiles_dir = self.product_dir / "profiles"
        if not profiles_dir.exists():
            self.errors.append(f"Profiles directory does not exist at {profiles_dir}")
            return False

        # Check if profile already exists
        if self.profile_path.exists():
            self.errors.append(f"Profile '{self.args.name}' already exists at {self.profile_path}")
            return False

        # Validate profile name format
        if not self.args.name.replace('_', '').replace('-', '').isalnum():
            self.errors.append(f"Profile name '{self.args.name}' contains invalid characters. Use only alphanumeric, underscore, and hyphen.")
            return False

        # Check if control file exists (required for selection-based profiles)
        if self.args.type == 'selection':
            control_file = self._get_control_file_path()
            if not control_file.exists():
                self.errors.append(
                    f"Control file '{control_file.name}' does not exist at {control_file}\n"
                    f"Control files must be created before adding profiles that reference them."
                )
                return False
        elif self.args.type == 'extends':
            # Check if base profile exists
            base_profile_path = self.product_dir / "profiles" / f"{self.args.extends}.profile"
            if not base_profile_path.exists():
                self.errors.append(
                    f"Base profile '{self.args.extends}' does not exist at {base_profile_path}"
                )
                return False

        return len(self.errors) == 0

    def _get_control_file_path(self):
        """Extract control file name from control reference and return its path."""
        # Control reference format is typically: control_name:all:level or control_name:all
        control_name = self.args.control.split(':')[0] if self.args.control else None
        if control_name:
            return self.repo_root / "controls" / f"{control_name}.yml"
        return None

    def create_profile_file(self):
        """Create the main profile file."""
        profile_data = {
            'documentation_complete': not self.args.draft
        }

        # Add metadata if provided
        metadata = {}
        if self.args.version:
            metadata['version'] = self.args.version
        if self.args.smes:
            metadata['SMEs'] = self.args.smes.split(',')
        if metadata:
            profile_data['metadata'] = metadata

        # Add reference if provided
        if self.args.reference:
            profile_data['reference'] = self.args.reference

        # Add title
        profile_data['title'] = self.args.title

        # Add description
        if self.args.description:
            profile_data['description'] = LiteralString(self.args.description)

        # Add selections or extends
        if self.args.type == 'selection':
            # Parse control selections
            selections = [self.args.control]
            if self.args.extra_selections:
                selections.extend(self.args.extra_selections.split(','))
            if self.args.unselections:
                # Add unselections (rules to exclude)
                for unselection in self.args.unselections.split(','):
                    selections.append(f"!{unselection.strip()}")
            profile_data['selections'] = selections
        elif self.args.type == 'extends':
            profile_data['extends'] = self.args.extends

        # Write profile file
        with open(self.profile_path, 'w') as f:
            # Manual YAML formatting for better control
            f.write(yaml.dump(profile_data,
                            default_flow_style=False,
                            sort_keys=False,
                            allow_unicode=True,
                            width=1000))  # Prevent wrapping

        print(f"✓ Created profile file: {self.profile_path}")
        return True

    def update_product_yml(self):
        """Update product.yml with reference URI if specified."""
        if not self.args.add_reference_uri:
            return True

        product_yml = self.product_dir / "product.yml"
        if not product_yml.exists():
            self.warnings.append(f"product.yml not found at {product_yml}")
            return False

        # Parse reference URI
        try:
            ref_name, ref_url = self.args.add_reference_uri.split('=', 1)
        except ValueError:
            self.errors.append(
                "Invalid reference URI format. Use: --add-reference-uri name=https://..."
            )
            return False

        # Read product.yml content
        with open(product_yml, 'r') as f:
            content = f.read()
            f.seek(0)
            product_data = yaml.safe_load(f)

        # Check if reference URI already exists
        if 'reference_uris' in product_data and ref_name in product_data['reference_uris']:
            self.warnings.append(
                f"Reference URI '{ref_name}' already exists in product.yml. "
                f"Current value: {product_data['reference_uris'][ref_name]}"
            )
            return True

        # Add reference URI by appending to the file or inserting in reference_uris section
        ref_uris_match = re.search(r'^reference_uris:\s*$', content, re.MULTILINE)

        if ref_uris_match:
            # reference_uris section exists, add the new entry
            # Find the line after reference_uris and add the new entry with proper indentation
            lines = content.split('\n')
            new_lines = []
            in_ref_uris = False
            added = False

            for i, line in enumerate(lines):
                new_lines.append(line)
                if re.match(r'^reference_uris:\s*$', line):
                    in_ref_uris = True
                elif in_ref_uris and not added:
                    # Check if we're at a line that starts a new section (no indentation) or end of file
                    if i + 1 < len(lines) and (not lines[i + 1].startswith(' ') or lines[i + 1].strip() == ''):
                        # Add the new reference URI before the next section
                        new_lines.append(f"  {ref_name}: '{ref_url}'")
                        added = True
                        in_ref_uris = False
                    elif line.strip().startswith(ref_name.split()[0] if ' ' in ref_name else ref_name):
                        # Alphabetically insert if needed
                        pass

            if in_ref_uris and not added:
                # We're at the end, add it
                new_lines.append(f"  {ref_name}: '{ref_url}'")
                added = True

            content = '\n'.join(new_lines)
        else:
            # reference_uris section doesn't exist, create it at the end
            if not content.endswith('\n'):
                content += '\n'
            content += f"\nreference_uris:\n  {ref_name}: '{ref_url}'\n"

        # Write back to product.yml
        with open(product_yml, 'w') as f:
            f.write(content)

        print(f"✓ Updated product.yml with reference URI: {ref_name}={ref_url}")
        return True

    def create_profile_stability(self):
        """Create profile stability test placeholder."""
        if not self.args.create_stability_test:
            return True

        stability_dir = self.repo_root / "tests" / "data" / "profile_stability" / self.args.product
        stability_file = stability_dir / f"{self.args.name}.profile"

        # Create directory if it doesn't exist
        stability_dir.mkdir(parents=True, exist_ok=True)

        # Create placeholder file with instructions
        with open(stability_file, 'w') as f:
            f.write(textwrap.dedent(f"""\
                # Profile stability test data for {self.args.product}/{self.args.name}
                #
                # This file should contain a list of all rule IDs included in this profile,
                # one per line. It is used for regression testing to ensure the profile
                # remains stable across changes.
                #
                # To generate this file:
                # 1. Build the product: ./build_product {self.args.product}
                # 2. Extract profile rules from the built datastream
                # 3. Replace this file with the extracted rule list
                #
                # Placeholder - needs to be populated after building the profile
                """))

        print(f"✓ Created profile stability placeholder: {stability_file}")
        return True

    def create_kickstart_file(self):
        """Create kickstart file template."""
        if not self.args.create_kickstart:
            return True

        kickstart_dir = self.product_dir / "kickstart"
        if not kickstart_dir.exists():
            self.warnings.append(
                f"Kickstart directory does not exist at {kickstart_dir}. Skipping kickstart creation."
            )
            return True

        kickstart_file = kickstart_dir / f"ssg-{self.args.product}-{self.args.name}-ks.cfg"

        if kickstart_file.exists():
            self.warnings.append(f"Kickstart file already exists: {kickstart_file}")
            return True

        # Find an existing kickstart to use as template
        existing_kickstarts = list(kickstart_dir.glob("*.cfg"))
        if existing_kickstarts:
            template_file = existing_kickstarts[0]
            with open(template_file, 'r') as f:
                template_content = f.read()

            # Replace profile name in template
            template_name = template_file.stem.split('-')[-1].replace('-ks', '')
            content = template_content.replace(template_name, self.args.name)
            content = content.replace(template_name.upper(), self.args.name.upper())

            with open(kickstart_file, 'w') as f:
                f.write(content)

            print(f"✓ Created kickstart file: {kickstart_file}")
            print(f"  (based on template: {template_file.name})")
        else:
            with open(kickstart_file, 'w') as f:
                f.write(textwrap.dedent(f"""\
                    # SCAP Security Guide {self.args.title} kickstart for {self.args.product}
                    #
                    # This is a template kickstart file. Please customize it according to your needs.
                    # For more information, see the kickstart documentation for your product.

                    # TODO: Add kickstart configuration
                    """))
            print(f"✓ Created kickstart template: {kickstart_file}")

        return True

    def print_next_steps(self):
        """Print next steps for the user."""
        print("\n" + "="*70)
        print("Profile created successfully!")
        print("="*70)

        print("\nNext steps:")
        print("1. Review and edit the profile file:")
        print(f"   {self.profile_path.relative_to(self.repo_root)}")

        print("\n2. Build the product to test the profile:")
        print(f"   ./build_product {self.args.product}")

        if self.args.create_stability_test:
            print("\n3. Generate profile stability data:")
            print("   # After building, extract rules from the profile and update:")
            print(f"   tests/data/profile_stability/{self.args.product}/{self.args.name}.profile")

        print("\n4. Test the profile:")
        print("   # Use oscap or other testing tools to validate the profile")

        print("\n5. Review and commit your changes:")
        print(f"   git add {self.profile_path.relative_to(self.repo_root)}")

        if self.args.add_reference_uri:
            print(f"   git add products/{self.args.product}/product.yml")

        if self.args.create_stability_test:
            print(f"   git add tests/data/profile_stability/{self.args.product}/{self.args.name}.profile")

        if self.args.create_kickstart:
            print(f"   git add products/{self.args.product}/kickstart/ssg-{self.args.product}-{self.args.name}-ks.cfg")

        print(f"   git commit -m 'Add {self.args.name} profile for {self.args.product}'")

        print()

    def create(self):
        """Main method to create the profile and related files."""
        if not self.validate_inputs():
            return False

        steps = [
            ("Creating profile file", self.create_profile_file),
            ("Updating product.yml", self.update_product_yml),
            ("Creating profile stability test", self.create_profile_stability),
            ("Creating kickstart file", self.create_kickstart_file),
        ]

        for step_name, step_func in steps:
            if not step_func():
                self.errors.append(f"Failed at: {step_name}")
                return False

        return True


class ProfileValidator:
    """Validates existing profile files."""

    def __init__(self, profile_path):
        self.profile_path = Path(profile_path)
        self.errors = []
        self.warnings = []

    def validate(self):
        """Validate a profile file."""
        if not self.profile_path.exists():
            self.errors.append(f"Profile file does not exist: {self.profile_path}")
            return False

        # Read and parse YAML
        try:
            with open(self.profile_path, 'r') as f:
                profile_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML syntax: {e}")
            return False

        # Check required fields
        required_fields = ['title', 'description']
        for field in required_fields:
            if field not in profile_data:
                self.errors.append(f"Missing required field: {field}")

        # Check for documentation_complete
        if 'documentation_complete' not in profile_data:
            self.warnings.append("Missing 'documentation_complete' field")
        elif profile_data['documentation_complete']:
            # If documentation is complete, check for additional requirements
            if 'reference' not in profile_data:
                self.warnings.append("Documentation complete but missing 'reference' field")

        # Check for selections or extends
        if 'selections' not in profile_data and 'extends' not in profile_data:
            self.errors.append("Profile must have either 'selections' or 'extends'")

        # Validate selections format
        if 'selections' in profile_data:
            if not isinstance(profile_data['selections'], list):
                self.errors.append("'selections' must be a list")

        # Check for metadata
        if 'metadata' in profile_data:
            metadata = profile_data['metadata']
            if 'version' in metadata:
                # Version should be a string or number
                if not isinstance(metadata['version'], (str, int, float)):
                    self.errors.append("metadata.version should be a string or number")

        # Print results
        print(f"Validating: {self.profile_path}")

        if self.errors:
            print("\nErrors found:")
            for error in self.errors:
                print(f"  ✗ {error}")

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")

        if not self.errors and not self.warnings:
            print("  ✓ Profile is valid!")
        elif not self.errors:
            print("\n✓ Profile is valid (with warnings)")

        return len(self.errors) == 0


def setup_argument_parser():
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:

        1. Create a CIS profile extending another profile:
            %(prog)s create \\
                --product rhel10 \\
                --name hipaa \\
                --title "HIPAA Security Profile" \\
                --description "This profile aligns with HIPAA requirements" \\
                --reference "https://www.hhs.gov/hipaa" \\
                --type extends \\
                --extends hipaa_base \\
                --smes user1,user2

        2. Create a profile with control selections:
            %(prog)s create \\
                --product fedora \\
                --name cis_server_l1 \\
                --title "CIS Fedora Server Level 1" \\
                --description "CIS benchmark Level 1 for servers" \\
                --reference "https://workbench.cisecurity.org/" \\
                --type selection \\
                --control "cis_fedora:all:l1_server" \\
                --add-reference-uri cis=https://workbench.cisecurity.org/communities/101 \\
                --create-stability-test \\
                --smes user1

        3. Create a draft profile:
            %(prog)s create \\
                --product ol10 \\
                --name ospp \\
                --title "DRAFT - Protection Profile for General Purpose Operating Systems" \\
                --description "Draft profile based on OSPP" \\
                --reference "https://www.niap-ccevs.org/Profile/Info.cfm" \\
                --type selection \\
                --control "ospp:all" \\
                --draft

        4. Validate an existing profile:
            %(prog)s validate products/rhel9/profiles/cis.profile
        """)
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new profile')
    create_parser.add_argument(
        '--product',
        required=True,
        help='Product name (e.g., rhel9, fedora, ol10)'
    )
    create_parser.add_argument(
        '--name',
        required=True,
        help='Profile name (e.g., cis, hipaa, ospp)'
    )
    create_parser.add_argument(
        '--title',
        required=True,
        help='Profile title'
    )
    create_parser.add_argument(
        '--description',
        required=True,
        help='Profile description'
    )
    create_parser.add_argument(
        '--reference',
        help='Reference URL for the profile'
    )
    create_parser.add_argument(
        '--type',
        required=True,
        choices=['selection', 'extends'],
        help='Profile type: selection (uses control selections) or extends (inherits from another profile)'
    )
    create_parser.add_argument(
        '--control',
        help='Control reference for selection-based profiles (e.g., cis_rhel9:all:l2_server)'
    )
    create_parser.add_argument(
        '--extends',
        help='Base profile name for extension-based profiles'
    )
    create_parser.add_argument(
        '--extra-selections',
        help='Additional selections (comma-separated)'
    )
    create_parser.add_argument(
        '--unselections',
        help='Rules to exclude/unselect (comma-separated, without ! prefix)'
    )
    create_parser.add_argument(
        '--version',
        help='Profile version'
    )
    create_parser.add_argument(
        '--smes',
        help='Subject Matter Experts (comma-separated usernames)'
    )
    create_parser.add_argument(
        '--draft',
        action='store_true',
        help='Mark profile as draft (documentation_complete: false)'
    )
    create_parser.add_argument(
        '--add-reference-uri',
        help='Add reference URI to product.yml (format: name=https://...)'
    )
    create_parser.add_argument(
        '--create-stability-test',
        action='store_true',
        help='Create profile stability test placeholder'
    )
    create_parser.add_argument(
        '--create-kickstart',
        action='store_true',
        help='Create kickstart file template'
    )

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate an existing profile')
    validate_parser.add_argument(
        'profile',
        help='Path to profile file to validate'
    )

    return parser


def main():
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'create':
        # Validate type-specific arguments
        if args.type == 'selection' and not args.control:
            print("Error: --control is required when --type is 'selection'", file=sys.stderr)
            return 1
        if args.type == 'extends' and not args.extends:
            print("Error: --extends is required when --type is 'extends'", file=sys.stderr)
            return 1

        creator = ProfileCreator(args)

        if creator.create():
            if creator.warnings:
                print("\nWarnings:")
                for warning in creator.warnings:
                    print(f"  ⚠ {warning}")

            creator.print_next_steps()
            return 0
        else:
            print("\nErrors occurred:", file=sys.stderr)
            for error in creator.errors:
                print(f"  ✗ {error}", file=sys.stderr)
            return 1

    elif args.command == 'validate':
        validator = ProfileValidator(args.profile)
        if validator.validate():
            return 0
        else:
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
