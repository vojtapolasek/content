# add_profile.py - SCAP Profile Creation Tool

## Overview

The `add_profile.py` script automates the creation of new SCAP profiles in the ComplianceAsCode project. It generates all necessary files and configurations while ensuring consistency and reducing manual errors.

## Features

### Core Functionality

1. **Profile File Creation**: Generates properly formatted `.profile` files with:
   - Metadata (version, SMEs)
   - Title and description
   - Reference URLs
   - Selections or extension configurations
   - Draft/complete documentation status

2. **Control File Validation**: Ensures the referenced control file exists before creating the profile (required for selection-based profiles)

3. **Product Configuration Updates**: Optionally updates `product.yml` with reference URIs while preserving original file formatting

4. **Profile Stability Test Setup**: Creates placeholder files for profile stability regression tests

5. **Kickstart File Generation**: Creates kickstart file templates for automated installations (when applicable)

6. **Profile Validation**: Validates existing profile files for correctness and completeness

## Usage

### Creating a Selection-Based Profile

Selection-based profiles reference control files and select specific controls, levels, or rules.

```bash
./utils/add_profile.py create \
  --product rhel9 \
  --name my_compliance_profile \
  --title "My Compliance Profile" \
  --description "This profile implements compliance requirements for XYZ standard" \
  --reference "https://example.com/standard" \
  --type selection \
  --control "my_control:all:high" \
  --version "1.0.0" \
  --smes "user1,user2" \
  --create-stability-test \
  --add-reference-uri mystandard=https://example.com/standard
```

**Options explained:**
- `--product`: Target product (rhel9, fedora, ol10, etc.)
- `--name`: Profile identifier (alphanumeric with underscores/hyphens)
- `--title`: Human-readable profile title
- `--description`: Detailed profile description
- `--reference`: URL to the benchmark or standard
- `--type selection`: Creates a selection-based profile
- `--control`: Control reference (format: control_name:selector:level)
- `--version`: Profile version number
- `--smes`: Comma-separated list of subject matter experts
- `--create-stability-test`: Creates profile stability test placeholder
- `--add-reference-uri`: Adds reference URI to product.yml

### Creating an Extension-Based Profile

Extension-based profiles inherit from an existing profile.

```bash
./utils/add_profile.py create \
  --product ol10 \
  --name hipaa_extended \
  --title "HIPAA Extended Profile" \
  --description "HIPAA profile with additional organization-specific requirements" \
  --reference "https://www.hhs.gov/hipaa" \
  --type extends \
  --extends hipaa \
  --version "2.0.0" \
  --smes "developer1"
```

### Creating a Draft Profile

Use `--draft` for profiles that are not yet complete:

```bash
./utils/add_profile.py create \
  --product ubuntu2404 \
  --name new_stig \
  --title "DRAFT - Ubuntu 24.04 STIG V1R1" \
  --description "Draft STIG profile for Ubuntu 24.04" \
  --reference "https://public.cyber.mil/stigs/" \
  --type selection \
  --control "stig_ubuntu2404:all" \
  --draft
```

### Advanced Selection Features

**Adding extra selections:**
```bash
--extra-selections "package_aide_installed,service_auditd_enabled,grub2_password"
```

**Excluding rules (unselections):**
```bash
--unselections "rule_to_skip,another_rule_to_skip"
```

These get added to the profile as `!rule_to_skip`.

### Creating Kickstart Files

For products that support kickstart (RHEL-based systems):

```bash
./utils/add_profile.py create \
  --product rhel10 \
  --name cis_server_l1 \
  --title "CIS RHEL 10 Server Level 1" \
  --description "CIS Server Level 1 benchmark" \
  --reference "https://www.cisecurity.org/" \
  --type selection \
  --control "cis_rhel10:all:l1_server" \
  --create-kickstart
```

### Validating Profiles

Validate an existing profile for correctness:

```bash
./utils/add_profile.py validate products/rhel9/profiles/cis.profile
```

The validator checks for:
- Valid YAML syntax
- Required fields (title, description)
- Proper structure (selections or extends)
- Metadata completeness
- Documentation status consistency

## File Structure

The script creates/modifies the following files:

```
products/<product>/
├── profiles/
│   └── <name>.profile              # Main profile file (created)
├── product.yml                      # Product configuration (optionally updated)
└── kickstart/
    └── ssg-<product>-<name>-ks.cfg # Kickstart file (optionally created)

tests/data/profile_stability/<product>/
└── <name>.profile                   # Stability test data (optionally created)
```

## Example Workflows

### Workflow 1: Complete CIS Profile

```bash
# 1. Create control file first (if not exists)
#    controls/cis_myproduct.yml

# 2. Create profile with all features
./utils/add_profile.py create \
  --product myproduct \
  --name cis \
  --title "CIS Benchmark for MyProduct" \
  --description "This profile aligns to the CIS Benchmark Level 2 for MyProduct" \
  --reference "https://www.cisecurity.org/benchmark/myproduct" \
  --type selection \
  --control "cis_myproduct:all:l2_server" \
  --version "2.0.0" \
  --smes "security_team" \
  --add-reference-uri cis=https://workbench.cisecurity.org/communities/101 \
  --create-stability-test \
  --create-kickstart

# 3. Build the product
./build_product myproduct

# 4. Generate and populate profile stability data
# (Extract rules from built datastream and update stability file)

# 5. Test the profile
# (Run compliance scans)

# 6. Commit changes
git add products/myproduct/profiles/cis.profile
git add products/myproduct/product.yml
git add tests/data/profile_stability/myproduct/cis.profile
git add products/myproduct/kickstart/ssg-myproduct-cis-ks.cfg
git commit -m "Add CIS profile for myproduct"
```

### Workflow 2: Simple Extension Profile

```bash
# Create a profile that extends an existing one
./utils/add_profile.py create \
  --product rhel9 \
  --name custom_hardening \
  --title "Custom Hardening Profile" \
  --description "Organization-specific hardening based on STIG" \
  --type extends \
  --extends stig

# Review and edit the profile
vi products/rhel9/profiles/custom_hardening.profile

# Add custom selections or unselections
# Then build and test
./build_product rhel9
```

## Validation Examples

### Valid Profile
```bash
$ ./utils/add_profile.py validate products/rhel9/profiles/cis.profile
Validating: products/rhel9/profiles/cis.profile
  ✓ Profile is valid!
```

### Profile with Warnings
```bash
$ ./utils/add_profile.py validate products/test/profiles/incomplete.profile
Validating: products/test/profiles/incomplete.profile

Warnings:
  ⚠ Missing 'documentation_complete' field
  ⚠ Documentation complete but missing 'reference' field

✓ Profile is valid (with warnings)
```

### Invalid Profile
```bash
$ ./utils/add_profile.py validate products/test/profiles/broken.profile
Validating: products/test/profiles/broken.profile

Errors found:
  ✗ Missing required field: title
  ✗ Profile must have either 'selections' or 'extends'
```

## Error Handling

The script provides clear error messages for common issues:

### Control File Not Found
```
Errors occurred:
  ✗ Control file 'nonexistent_control.yml' does not exist at /path/to/controls/nonexistent_control.yml
Control files must be created before adding profiles that reference them.
```

### Product Not Found
```
Errors occurred:
  ✗ Product 'invalid_product' does not exist at /path/to/products/invalid_product
```

### Profile Already Exists
```
Errors occurred:
  ✗ Profile 'cis' already exists at /path/to/products/rhel9/profiles/cis.profile
```

### Missing Required Arguments
```
Error: --control is required when --type is 'selection'
```

## Tips and Best Practices

1. **Always create control files first**: Selection-based profiles require the control file to exist

2. **Use meaningful profile names**: Follow the project's naming conventions (e.g., `cis`, `stig`, `hipaa`, not `profile1`)

3. **Set documentation_complete carefully**: Use `--draft` for work-in-progress profiles

4. **Add SMEs**: Include subject matter experts who can review and maintain the profile

5. **Create stability tests**: Use `--create-stability-test` for all production profiles to enable regression testing

6. **Review generated files**: Always review and edit the generated profile file before committing

7. **Test thoroughly**: Build and test the profile before creating a pull request

8. **Validate before committing**: Run the validate command to catch issues early

## Integration with Project Workflow

This script integrates with the standard ComplianceAsCode workflow:

```
1. Create control file (controls/*.yml)
   ↓
2. Run add_profile.py create (this script)
   ↓
3. Review and edit profile file
   ↓
4. Build product (./build_product)
   ↓
5. Generate stability data
   ↓
6. Test profile (oscap, compliance-operator, etc.)
   ↓
7. Commit and create PR
```

## Troubleshooting

### Kickstart Directory Not Found
If you see a warning about kickstart directory not existing, it's because the product doesn't have kickstart support. This is expected for non-RHEL products like Fedora, Ubuntu, etc.

### Reference URI Already Exists
If the reference URI already exists in product.yml, the script will warn you but continue. You can manually edit product.yml if needed.

### YAML Formatting Issues
The script preserves the original formatting of product.yml. If you encounter issues, you can manually edit the file after running the script.

## See Also

- `build_product` - Build script for products
- `utils/generate_profile.py` - Tool for converting benchmarks to control files
- `utils/build_control_from_reference.py` - Build control files from references
- Project documentation on profiles and controls
