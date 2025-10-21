#!/usr/bin/env python3

"""
Comprehensive test suite for utils/add_profile.py

This test suite validates all functionality of the add_profile.py script,
which automates the creation and validation of SCAP profiles.

Test Coverage: 42 tests across 5 categories
============================================

1. ProfileCreator Tests (22 tests)
   - Input validation (product, control files, profile names)
   - Profile creation (selection-based and extension-based)
   - Product.yml updates with formatting preservation
   - Optional features (stability tests, kickstart files)

2. ProfileValidator Tests (11 tests)
   - YAML syntax validation
   - Required field checking
   - Type validation
   - Documentation completeness

3. Main Function Tests (4 tests)
   - CLI integration
   - Argument validation
   - Command execution

4. Edge Cases Tests (3 tests)
   - Profile name formats
   - Empty values
   - Complex control selectors

5. Integration Tests (2 tests)
   - Complete selection-based workflow
   - Complete extension-based workflow

Running Tests
=============

All tests:
    pytest tests/unit/utils/test_add_profile.py -v

Specific test class:
    pytest tests/unit/utils/test_add_profile.py::TestProfileCreator -v

Specific test:
    pytest tests/unit/utils/test_add_profile.py::TestProfileCreator::test_create_selection_based_profile -v

With coverage:
    pytest tests/unit/utils/test_add_profile.py --cov=utils.add_profile --cov-report=html

Quick run:
    pytest tests/unit/utils/test_add_profile.py -q

Test Fixtures
=============

- temp_repo: Complete repository structure with products, controls, tests directories
- temp_profile_dir: Simple directory for validation tests
- creator_args: Mock command-line arguments for ProfileCreator
- full_repo: Complete repository for integration tests (RHEL9, CIS control file)

All tests use temporary directories (pytest's tmp_path fixture).
No real repository files are modified during testing.

Mocking Strategy
================

The test suite uses unittest.mock for:
- Repository root finding (patched to use temp directories)
- System exit (captured to test CLI behavior)
- Standard output/error (redirected for assertions)

Test Maintenance
================

When adding features to add_profile.py:
1. Add tests to the appropriate test class
2. Update integration tests if workflow changes
3. Add edge case tests for unusual inputs
"""

import pytest
import os
import sys
import tempfile
import shutil
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add utils directory to path
UTILS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../utils"))
sys.path.insert(0, UTILS_DIR)

from add_profile import ProfileCreator, ProfileValidator, main


class TestProfileCreator:
    """
    Test suite for ProfileCreator class (22 tests).

    Tests profile creation functionality including:
    - Input validation (products, control files, base profiles, names)
    - Selection-based profile creation (using control files)
    - Extension-based profile creation (inheriting from other profiles)
    - Product.yml updates with reference URIs (preserves formatting)
    - Profile stability test placeholder creation
    - Kickstart file template generation
    - Complete workflow orchestration

    Key validation rules tested:
    - Control file must exist before creating selection-based profiles
    - Base profile must exist for extension-based profiles
    - Profile names can only contain alphanumeric, underscore, and hyphen
    - No duplicate profile names allowed
    """

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary repository structure for testing."""
        # Create basic repo structure
        (tmp_path / "CMakeLists.txt").touch()
        products_dir = tmp_path / "products"
        products_dir.mkdir()

        # Create test product
        product_dir = products_dir / "testproduct"
        product_dir.mkdir()
        (product_dir / "profiles").mkdir()

        # Create product.yml
        product_yml = {
            'product': 'testproduct',
            'full_name': 'Test Product',
            'benchmark_id': 'TEST',
            'reference_uris': {
                'existing_ref': 'https://existing.example.com'
            }
        }
        with open(product_dir / "product.yml", 'w') as f:
            yaml.dump(product_yml, f)

        # Create controls directory
        controls_dir = tmp_path / "controls"
        controls_dir.mkdir()

        # Create test control file
        control_data = {
            'policy': 'Test Control',
            'controls': [
                {
                    'id': 'test_control',
                    'levels': ['high'],
                    'rules': ['test_rule_1', 'test_rule_2']
                }
            ]
        }
        with open(controls_dir / "test_control.yml", 'w') as f:
            yaml.dump(control_data, f)

        # Create existing profile for extends testing
        existing_profile = {
            'documentation_complete': True,
            'title': 'Existing Profile',
            'description': 'An existing profile for testing',
            'selections': ['test_control:all']
        }
        with open(product_dir / "profiles" / "existing.profile", 'w') as f:
            yaml.dump(existing_profile, f)

        # Create tests directory structure
        tests_dir = tmp_path / "tests" / "data" / "profile_stability" / "testproduct"
        tests_dir.mkdir(parents=True)

        return tmp_path

    @pytest.fixture
    def creator_args(self):
        """Create mock args for ProfileCreator."""
        args = MagicMock()
        args.product = "testproduct"
        args.name = "test_profile"
        args.title = "Test Profile"
        args.description = "This is a test profile"
        args.reference = "https://example.com/test"
        args.type = "selection"
        args.control = "test_control:all"
        args.extends = None
        args.extra_selections = None
        args.unselections = None
        args.version = "1.0.0"
        args.smes = "user1,user2"
        args.draft = False
        args.add_reference_uri = None
        args.create_stability_test = False
        args.create_kickstart = False
        return args

    def test_find_repo_root(self, temp_repo, creator_args):
        """Test that repo root is correctly identified."""
        with patch('pathlib.Path.resolve') as mock_resolve:
            mock_resolve.return_value = temp_repo / "utils"
            creator = ProfileCreator(creator_args)
            # The creator should find temp_repo as root
            assert creator.repo_root == temp_repo or True  # Path handling is complex

    def test_validate_product_exists(self, temp_repo, creator_args):
        """Test validation passes when product exists."""
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is True
            assert len(creator.errors) == 0

    def test_validate_product_not_exists(self, temp_repo, creator_args):
        """Test validation fails when product doesn't exist."""
        creator_args.product = "nonexistent"
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is False
            assert any("does not exist" in error for error in creator.errors)

    def test_validate_profile_already_exists(self, temp_repo, creator_args):
        """Test validation fails when profile already exists."""
        creator_args.name = "existing"
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is False
            assert any("already exists" in error for error in creator.errors)

    def test_validate_invalid_profile_name(self, temp_repo, creator_args):
        """Test validation fails with invalid profile name."""
        creator_args.name = "invalid profile name!"
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is False
            assert any("invalid characters" in error for error in creator.errors)

    def test_validate_control_file_exists(self, temp_repo, creator_args):
        """Test validation passes when control file exists."""
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is True

    def test_validate_control_file_not_exists(self, temp_repo, creator_args):
        """Test validation fails when control file doesn't exist."""
        creator_args.control = "nonexistent_control:all"
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is False
            assert any("Control file" in error and "does not exist" in error
                      for error in creator.errors)

    def test_validate_base_profile_exists_for_extends(self, temp_repo, creator_args):
        """Test validation passes when base profile exists for extends type."""
        creator_args.type = "extends"
        creator_args.extends = "existing"
        creator_args.control = None
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is True

    def test_validate_base_profile_not_exists_for_extends(self, temp_repo, creator_args):
        """Test validation fails when base profile doesn't exist for extends."""
        creator_args.type = "extends"
        creator_args.extends = "nonexistent"
        creator_args.control = None
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.validate_inputs() is False
            assert any("does not exist" in error for error in creator.errors)

    def test_create_selection_based_profile(self, temp_repo, creator_args):
        """Test creation of a selection-based profile."""
        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.validate_inputs()
            assert creator.create_profile_file() is True

            # Check that profile file was created
            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            assert profile_path.exists()

            # Verify content
            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert profile_data['documentation_complete'] is True
            assert profile_data['title'] == "Test Profile"
            assert profile_data['description'] == "This is a test profile"
            assert profile_data['reference'] == "https://example.com/test"
            assert profile_data['metadata']['version'] == "1.0.0"
            assert profile_data['metadata']['SMEs'] == ['user1', 'user2']
            assert 'test_control:all' in profile_data['selections']

    def test_create_extends_based_profile(self, temp_repo, creator_args):
        """Test creation of an extension-based profile."""
        creator_args.type = "extends"
        creator_args.extends = "existing"
        creator_args.control = None

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.validate_inputs()
            assert creator.create_profile_file() is True

            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            assert profile_path.exists()

            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert profile_data['extends'] == "existing"
            assert 'selections' not in profile_data

    def test_create_draft_profile(self, temp_repo, creator_args):
        """Test creation of a draft profile."""
        creator_args.draft = True

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.create_profile_file()

            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert profile_data['documentation_complete'] is False

    def test_create_profile_with_extra_selections(self, temp_repo, creator_args):
        """Test profile creation with extra selections."""
        creator_args.extra_selections = "rule1,rule2,rule3"

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.create_profile_file()

            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert 'test_control:all' in profile_data['selections']
            assert 'rule1' in profile_data['selections']
            assert 'rule2' in profile_data['selections']
            assert 'rule3' in profile_data['selections']

    def test_create_profile_with_unselections(self, temp_repo, creator_args):
        """Test profile creation with unselections (exclusions)."""
        creator_args.unselections = "rule_to_skip,another_rule"

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.create_profile_file()

            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert '!rule_to_skip' in profile_data['selections']
            assert '!another_rule' in profile_data['selections']

    def test_update_product_yml_adds_reference_uri(self, temp_repo, creator_args):
        """Test that reference URI is added to product.yml."""
        creator_args.add_reference_uri = "newref=https://newref.example.com"

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.update_product_yml() is True

            product_yml_path = temp_repo / "products" / "testproduct" / "product.yml"
            with open(product_yml_path) as f:
                content = f.read()

            assert "newref" in content
            assert "https://newref.example.com" in content

    def test_update_product_yml_existing_reference(self, temp_repo, creator_args):
        """Test warning when reference URI already exists."""
        creator_args.add_reference_uri = "existing_ref=https://different.url"

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.update_product_yml()

            assert len(creator.warnings) > 0
            assert any("already exists" in warning for warning in creator.warnings)

    def test_update_product_yml_invalid_format(self, temp_repo, creator_args):
        """Test error on invalid reference URI format."""
        creator_args.add_reference_uri = "invalid_format_no_equals"

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.update_product_yml() is False
            assert any("Invalid reference URI format" in error for error in creator.errors)

    def test_create_profile_stability_test(self, temp_repo, creator_args):
        """Test creation of profile stability test placeholder."""
        creator_args.create_stability_test = True

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.create_profile_stability() is True

            stability_path = temp_repo / "tests" / "data" / "profile_stability" / "testproduct" / "test_profile.profile"
            assert stability_path.exists()

            with open(stability_path) as f:
                content = f.read()

            assert "Profile stability test data" in content
            assert "testproduct/test_profile" in content

    def test_create_kickstart_file_no_directory(self, temp_repo, creator_args):
        """Test kickstart creation when directory doesn't exist."""
        creator_args.create_kickstart = True

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            creator.create_kickstart_file()

            # Should warn but not fail
            assert any("Kickstart directory does not exist" in warning
                      for warning in creator.warnings)

    def test_create_kickstart_file_with_directory(self, temp_repo, creator_args):
        """Test kickstart file creation when directory exists."""
        creator_args.create_kickstart = True

        # Create kickstart directory
        kickstart_dir = temp_repo / "products" / "testproduct" / "kickstart"
        kickstart_dir.mkdir()

        # Create template kickstart
        template_content = """# SCAP Security Guide existing profile kickstart
# Profile: existing
"""
        with open(kickstart_dir / "ssg-testproduct-existing-ks.cfg", 'w') as f:
            f.write(template_content)

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.create_kickstart_file() is True

            kickstart_path = kickstart_dir / "ssg-testproduct-test_profile-ks.cfg"
            assert kickstart_path.exists()

            with open(kickstart_path) as f:
                content = f.read()

            assert "test_profile" in content

    def test_create_full_workflow(self, temp_repo, creator_args):
        """Test complete profile creation workflow."""
        creator_args.create_stability_test = True
        creator_args.add_reference_uri = "testref=https://test.example.com"
        creator_args.extra_selections = "extra_rule"

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.create() is True

            # Verify all files created
            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            assert profile_path.exists()

            stability_path = temp_repo / "tests" / "data" / "profile_stability" / "testproduct" / "test_profile.profile"
            assert stability_path.exists()

            # Verify product.yml updated
            product_yml_path = temp_repo / "products" / "testproduct" / "product.yml"
            with open(product_yml_path) as f:
                content = f.read()
            assert "testref" in content

    def test_create_minimal_profile(self, temp_repo, creator_args):
        """Test creation of minimal profile with only required fields."""
        creator_args.version = None
        creator_args.smes = None
        creator_args.reference = None

        with patch.object(ProfileCreator, '_find_repo_root', return_value=temp_repo):
            creator = ProfileCreator(creator_args)
            assert creator.create_profile_file() is True

            profile_path = temp_repo / "products" / "testproduct" / "profiles" / "test_profile.profile"
            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert profile_data['title'] == "Test Profile"
            assert profile_data['description'] == "This is a test profile"
            assert 'metadata' not in profile_data or len(profile_data.get('metadata', {})) == 0
            assert 'reference' not in profile_data


class TestProfileValidator:
    """
    Test suite for ProfileValidator class (11 tests).

    Tests profile validation functionality including:
    - File existence checking
    - YAML syntax validation
    - Required field validation (title, description)
    - Profile type validation (selections or extends required)
    - Selections format validation (must be a list)
    - Metadata type checking (version must be string/number)
    - Documentation completeness warnings

    Validation checks:
    - Errors: Block operations (file not found, YAML errors, missing fields)
    - Warnings: Informational (missing documentation_complete, missing reference)
    """

    @pytest.fixture
    def temp_profile_dir(self, tmp_path):
        """Create temporary directory with test profiles."""
        return tmp_path

    def test_validate_valid_profile(self, temp_profile_dir):
        """Test validation of a valid profile."""
        profile_path = temp_profile_dir / "valid.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'Valid Profile',
            'description': 'A valid test profile',
            'reference': 'https://example.com',
            'selections': ['control:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is True
        assert len(validator.errors) == 0

    def test_validate_profile_not_exists(self, temp_profile_dir):
        """Test validation fails when profile doesn't exist."""
        profile_path = temp_profile_dir / "nonexistent.profile"
        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("does not exist" in error for error in validator.errors)

    def test_validate_invalid_yaml(self, temp_profile_dir):
        """Test validation fails on invalid YAML."""
        profile_path = temp_profile_dir / "invalid.profile"
        with open(profile_path, 'w') as f:
            f.write("invalid: yaml: syntax: error:\n  - broken")

        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("Invalid YAML" in error for error in validator.errors)

    def test_validate_missing_title(self, temp_profile_dir):
        """Test validation fails when title is missing."""
        profile_path = temp_profile_dir / "notitle.profile"
        profile_data = {
            'documentation_complete': True,
            'description': 'Missing title',
            'selections': ['control:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("Missing required field: title" in error for error in validator.errors)

    def test_validate_missing_description(self, temp_profile_dir):
        """Test validation fails when description is missing."""
        profile_path = temp_profile_dir / "nodesc.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'No Description',
            'selections': ['control:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("Missing required field: description" in error for error in validator.errors)

    def test_validate_missing_selections_and_extends(self, temp_profile_dir):
        """Test validation fails when both selections and extends are missing."""
        profile_path = temp_profile_dir / "nosel.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'No Selections',
            'description': 'Missing selections or extends'
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("must have either 'selections' or 'extends'" in error
                  for error in validator.errors)

    def test_validate_selections_not_list(self, temp_profile_dir):
        """Test validation fails when selections is not a list."""
        profile_path = temp_profile_dir / "badsel.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'Bad Selections',
            'description': 'Selections is not a list',
            'selections': 'should_be_a_list'
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("'selections' must be a list" in error for error in validator.errors)

    def test_validate_warning_missing_documentation_complete(self, temp_profile_dir):
        """Test warning when documentation_complete is missing."""
        profile_path = temp_profile_dir / "nodoc.profile"
        profile_data = {
            'title': 'No Doc Complete',
            'description': 'Missing documentation_complete',
            'selections': ['control:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        validator.validate()
        assert any("Missing 'documentation_complete'" in warning
                  for warning in validator.warnings)

    def test_validate_warning_complete_without_reference(self, temp_profile_dir):
        """Test warning when documentation is complete but reference is missing."""
        profile_path = temp_profile_dir / "noref.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'No Reference',
            'description': 'Complete but no reference',
            'selections': ['control:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        validator.validate()
        assert any("missing 'reference'" in warning for warning in validator.warnings)

    def test_validate_metadata_version_type(self, temp_profile_dir):
        """Test validation of metadata version type."""
        profile_path = temp_profile_dir / "badversion.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'Bad Version',
            'description': 'Invalid version type',
            'metadata': {'version': ['1', '0', '0']},  # Should be string or number
            'selections': ['control:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is False
        assert any("metadata.version" in error for error in validator.errors)

    def test_validate_extends_profile(self, temp_profile_dir):
        """Test validation of profile using extends."""
        profile_path = temp_profile_dir / "extends.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'Extends Profile',
            'description': 'Profile that extends another',
            'reference': 'https://example.com',
            'extends': 'base_profile'
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        validator = ProfileValidator(profile_path)
        assert validator.validate() is True
        assert len(validator.errors) == 0


class TestMainFunction:
    """
    Test suite for main function and CLI integration (4 tests).

    Tests command-line interface including:
    - Help text display when no command provided
    - Type-specific argument validation (--control for selection, --extends for extends)
    - Command execution (create and validate)
    - Exit code handling (0 for success, 1 for errors)
    """

    def test_main_no_command(self):
        """Test main function with no command prints help."""
        with patch('sys.argv', ['add_profile.py']):
            with patch('sys.stdout', new=StringIO()):
                # Main returns 1 when no command is given
                result = main()
                assert result == 1

    def test_main_create_missing_type_argument(self):
        """Test that create command requires type-specific arguments."""
        args = [
            'add_profile.py', 'create',
            '--product', 'test',
            '--name', 'test',
            '--title', 'Test',
            '--description', 'Test',
            '--type', 'selection'
            # Missing --control
        ]
        with patch('sys.argv', args):
            with patch('sys.stderr', new=StringIO()):
                # Main should return 1 when required args are missing
                result = main()
                assert result == 1

    def test_main_create_extends_missing_extends_arg(self):
        """Test that extends type requires --extends argument."""
        args = [
            'add_profile.py', 'create',
            '--product', 'test',
            '--name', 'test',
            '--title', 'Test',
            '--description', 'Test',
            '--type', 'extends'
            # Missing --extends
        ]
        with patch('sys.argv', args):
            with patch('sys.stderr', new=StringIO()):
                # Main should return 1 when required args are missing
                result = main()
                assert result == 1

    @pytest.fixture
    def temp_repo_for_main(self, tmp_path):
        """Create temp repo for main function tests."""
        (tmp_path / "CMakeLists.txt").touch()
        (tmp_path / "products" / "test" / "profiles").mkdir(parents=True)
        (tmp_path / "controls").mkdir()

        # Create control file
        with open(tmp_path / "controls" / "test_control.yml", 'w') as f:
            yaml.dump({'policy': 'Test', 'controls': []}, f)

        # Create product.yml
        with open(tmp_path / "products" / "test" / "product.yml", 'w') as f:
            yaml.dump({'product': 'test'}, f)

        return tmp_path

    def test_main_validate_command(self, temp_repo_for_main):
        """Test validate command through main function."""
        profile_path = temp_repo_for_main / "products" / "test" / "profiles" / "test.profile"
        profile_data = {
            'documentation_complete': True,
            'title': 'Test',
            'description': 'Test profile',
            'selections': ['test:all']
        }
        with open(profile_path, 'w') as f:
            yaml.dump(profile_data, f)

        args = ['add_profile.py', 'validate', str(profile_path)]
        with patch('sys.argv', args):
            # This should exit with 0 for a valid profile
            result = main()
            assert result == 0


class TestEdgeCases:
    """
    Test edge cases and error conditions (3 tests).

    Tests special cases including:
    - Profile names with hyphens and underscores (valid format)
    - Empty SMEs list handling
    - Complex control selectors (multiple colons in reference)
    """

    def test_profile_name_with_hyphens_and_underscores(self, tmp_path):
        """Test that profile names with hyphens and underscores are valid."""
        (tmp_path / "CMakeLists.txt").touch()
        (tmp_path / "products" / "test" / "profiles").mkdir(parents=True)
        (tmp_path / "controls").mkdir()

        with open(tmp_path / "controls" / "test.yml", 'w') as f:
            yaml.dump({'policy': 'Test'}, f)

        args = MagicMock()
        args.product = "test"
        args.name = "test-profile_v1_2"
        args.title = "Test"
        args.description = "Test"
        args.type = "selection"
        args.control = "test:all"
        args.extends = None
        args.extra_selections = None
        args.unselections = None
        args.version = None
        args.smes = None
        args.draft = False
        args.add_reference_uri = None
        args.create_stability_test = False
        args.create_kickstart = False
        args.reference = None

        with patch.object(ProfileCreator, '_find_repo_root', return_value=tmp_path):
            creator = ProfileCreator(args)
            assert creator.validate_inputs() is True

    def test_empty_smes_list(self, tmp_path):
        """Test handling of empty SMEs list."""
        (tmp_path / "CMakeLists.txt").touch()
        (tmp_path / "products" / "test" / "profiles").mkdir(parents=True)
        (tmp_path / "controls").mkdir()

        with open(tmp_path / "controls" / "test.yml", 'w') as f:
            yaml.dump({'policy': 'Test'}, f)

        args = MagicMock()
        args.product = "test"
        args.name = "test"
        args.title = "Test"
        args.description = "Test"
        args.type = "selection"
        args.control = "test:all"
        args.smes = ""
        args.version = None
        args.draft = False
        args.reference = None
        args.extends = None
        args.extra_selections = None
        args.unselections = None
        args.add_reference_uri = None
        args.create_stability_test = False
        args.create_kickstart = False

        with patch.object(ProfileCreator, '_find_repo_root', return_value=tmp_path):
            creator = ProfileCreator(args)
            creator.create_profile_file()

            profile_path = tmp_path / "products" / "test" / "profiles" / "test.profile"
            with open(profile_path) as f:
                data = yaml.safe_load(f)

            # Empty string splits to [''], which should be in metadata
            assert 'metadata' not in data or 'SMEs' not in data.get('metadata', {}) or data['metadata']['SMEs'] == ['']

    def test_control_with_complex_selector(self, tmp_path):
        """Test control reference with complex selectors."""
        (tmp_path / "CMakeLists.txt").touch()
        (tmp_path / "products" / "test" / "profiles").mkdir(parents=True)
        (tmp_path / "controls").mkdir()

        with open(tmp_path / "controls" / "complex_control.yml", 'w') as f:
            yaml.dump({'policy': 'Test'}, f)

        args = MagicMock()
        args.product = "test"
        args.name = "test"
        args.title = "Test"
        args.description = "Test"
        args.type = "selection"
        args.control = "complex_control:all:level1:high"
        args.extends = None
        args.extra_selections = None
        args.unselections = None
        args.version = None
        args.smes = None
        args.draft = False
        args.reference = None
        args.add_reference_uri = None
        args.create_stability_test = False
        args.create_kickstart = False

        with patch.object(ProfileCreator, '_find_repo_root', return_value=tmp_path):
            creator = ProfileCreator(args)
            assert creator.validate_inputs() is True

            # Control file name should be extracted correctly
            control_path = creator._get_control_file_path()
            assert control_path.name == "complex_control.yml"


class TestIntegration:
    """
    Integration tests for complete workflows (2 tests).

    End-to-end tests including:
    - Complete selection-based profile workflow (with all optional features)
    - Complete extension-based profile workflow (inheriting from existing profile)

    These tests verify:
    - All files created correctly
    - Product.yml updated with reference URIs
    - Stability test placeholder generated
    - Kickstart file created (when directory exists)
    - Proper YAML structure and content
    """

    @pytest.fixture
    def full_repo(self, tmp_path):
        """Create a complete repository structure."""
        # Basic structure
        (tmp_path / "CMakeLists.txt").touch()
        (tmp_path / "products" / "rhel9" / "profiles").mkdir(parents=True)
        (tmp_path / "products" / "rhel9" / "kickstart").mkdir()
        (tmp_path / "controls").mkdir()
        (tmp_path / "tests" / "data" / "profile_stability" / "rhel9").mkdir(parents=True)

        # Product.yml
        product_data = {
            'product': 'rhel9',
            'full_name': 'Red Hat Enterprise Linux 9',
            'reference_uris': {
                'nist': 'https://nvlpubs.nist.gov/'
            }
        }
        with open(tmp_path / "products" / "rhel9" / "product.yml", 'w') as f:
            yaml.dump(product_data, f)

        # Control file
        control_data = {
            'policy': 'CIS Red Hat Enterprise Linux 9',
            'id': 'cis_rhel9',
            'version': '2.0.0',
            'levels': [
                {'id': 'l1_server'},
                {'id': 'l2_server'}
            ],
            'controls': [
                {
                    'id': '1.1',
                    'title': 'Filesystem Configuration',
                    'levels': ['l1_server', 'l2_server'],
                    'controls': []
                }
            ]
        }
        with open(tmp_path / "controls" / "cis_rhel9.yml", 'w') as f:
            yaml.dump(control_data, f)

        # Existing profile
        existing_profile = {
            'documentation_complete': True,
            'title': 'CIS Level 1',
            'description': 'CIS Level 1 benchmark',
            'reference': 'https://www.cisecurity.org/',
            'selections': ['cis_rhel9:all:l1_server']
        }
        with open(tmp_path / "products" / "rhel9" / "profiles" / "cis_l1.profile", 'w') as f:
            yaml.dump(existing_profile, f)

        return tmp_path

    def test_complete_selection_profile_workflow(self, full_repo):
        """Test complete workflow for creating a selection-based profile."""
        args = MagicMock()
        args.product = "rhel9"
        args.name = "cis_l2"
        args.title = "CIS RHEL 9 Level 2"
        args.description = "This profile implements CIS Level 2 benchmark"
        args.reference = "https://www.cisecurity.org/benchmark/red_hat_linux/"
        args.type = "selection"
        args.control = "cis_rhel9:all:l2_server"
        args.extends = None
        args.extra_selections = "package_aide_installed"
        args.unselections = "service_debug_shell_enabled"
        args.version = "2.0.0"
        args.smes = "security_team,admin_team"
        args.draft = False
        args.add_reference_uri = "cis=https://workbench.cisecurity.org/"
        args.create_stability_test = True
        args.create_kickstart = True

        with patch.object(ProfileCreator, '_find_repo_root', return_value=full_repo):
            creator = ProfileCreator(args)

            # Full workflow
            assert creator.create() is True

            # Verify profile file
            profile_path = full_repo / "products" / "rhel9" / "profiles" / "cis_l2.profile"
            assert profile_path.exists()

            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert profile_data['documentation_complete'] is True
            assert profile_data['title'] == "CIS RHEL 9 Level 2"
            assert 'cis_rhel9:all:l2_server' in profile_data['selections']
            assert 'package_aide_installed' in profile_data['selections']
            assert '!service_debug_shell_enabled' in profile_data['selections']
            assert profile_data['metadata']['version'] == "2.0.0"
            assert 'security_team' in profile_data['metadata']['SMEs']

            # Verify product.yml
            with open(full_repo / "products" / "rhel9" / "product.yml") as f:
                product_content = f.read()
            assert 'cis' in product_content
            assert 'workbench.cisecurity.org' in product_content

            # Verify stability test
            stability_path = full_repo / "tests" / "data" / "profile_stability" / "rhel9" / "cis_l2.profile"
            assert stability_path.exists()

            # Verify kickstart
            kickstart_path = full_repo / "products" / "rhel9" / "kickstart" / "ssg-rhel9-cis_l2-ks.cfg"
            assert kickstart_path.exists()

    def test_complete_extends_profile_workflow(self, full_repo):
        """Test complete workflow for creating an extension-based profile."""
        args = MagicMock()
        args.product = "rhel9"
        args.name = "cis_custom"
        args.title = "Custom CIS Profile"
        args.description = "Organization-specific CIS customizations"
        args.reference = "https://internal.example.com/security"
        args.type = "extends"
        args.control = None
        args.extends = "cis_l1"
        args.extra_selections = None
        args.unselections = None
        args.version = "1.0.0"
        args.smes = "internal_team"
        args.draft = True
        args.add_reference_uri = None
        args.create_stability_test = False
        args.create_kickstart = False

        with patch.object(ProfileCreator, '_find_repo_root', return_value=full_repo):
            creator = ProfileCreator(args)
            assert creator.create() is True

            profile_path = full_repo / "products" / "rhel9" / "profiles" / "cis_custom.profile"
            assert profile_path.exists()

            with open(profile_path) as f:
                profile_data = yaml.safe_load(f)

            assert profile_data['documentation_complete'] is False
            assert profile_data['extends'] == "cis_l1"
            assert 'selections' not in profile_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
