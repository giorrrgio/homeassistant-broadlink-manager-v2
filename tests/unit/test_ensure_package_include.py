"""
Unit tests for _ensure_package_include logic
Verifies that configuration.yaml is automatically updated to include
the broadlink_manager package so generated entities appear in HA.

Tests the logic directly without importing web_server (which requires Flask).
"""

import pytest
import tempfile
import os
import re
from pathlib import Path
from unittest.mock import Mock


def ensure_package_include(config_path: Path) -> dict:
    """
    Standalone copy of the _ensure_package_include logic for testing.
    This mirrors WebServer._ensure_package_include exactly.
    """
    result = {
        "added": False,
        "already_present": False,
        "error": None,
        "instructions": None,
    }

    try:
        config_file = config_path / "configuration.yaml"

        if not config_file.exists():
            result["error"] = "configuration.yaml not found"
            result["instructions"] = (
                "Add the following to your configuration.yaml:\n"
                "homeassistant:\n"
                "  packages:\n"
                "    broadlink_manager: !include broadlink_manager/package.yaml"
            )
            return result

        content = config_file.read_text(encoding="utf-8")

        include_pattern = re.compile(
            r"broadlink_manager\s*:\s*!include.*broadlink_manager",
            re.IGNORECASE,
        )
        if include_pattern.search(content):
            result["already_present"] = True
            return result

        include_dir_pattern = re.compile(
            r"packages\s*:\s*!include_dir_named", re.IGNORECASE
        )
        if include_dir_pattern.search(content):
            result["instructions"] = (
                "Your configuration.yaml uses !include_dir_named for packages. "
                "Set the 'package_output_path' option to write package.yaml "
                "to your packages directory, or manually add:\n"
                "homeassistant:\n"
                "  packages:\n"
                "    broadlink_manager: !include broadlink_manager/package.yaml"
            )
            return result

        lines = content.split("\n")
        ha_section_idx = None
        packages_idx = None

        for i, line in enumerate(lines):
            if re.match(r"^homeassistant\s*:", line):
                ha_section_idx = i
            if ha_section_idx is not None and re.match(
                r"^\s+packages\s*:", line
            ):
                packages_idx = i
                break

        if packages_idx is not None:
            indent = "    "
            for j in range(packages_idx + 1, len(lines)):
                line = lines[j]
                if line.strip() == "":
                    continue
                if re.match(r"^\s+\S", line):
                    indent = line[: len(line) - len(line.lstrip())]
                    break
                if re.match(r"^\S", line):
                    break

            insert_idx = packages_idx + 1
            while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                insert_idx += 1

            lines.insert(
                insert_idx,
                f"{indent}broadlink_manager: !include broadlink_manager/package.yaml",
            )
        elif ha_section_idx is not None:
            indent = "  "
            for j in range(ha_section_idx + 1, len(lines)):
                line = lines[j]
                if line.strip() == "":
                    continue
                if re.match(r"^\s+\S", line):
                    indent = line[: len(line) - len(line.lstrip())]
                    break
                if re.match(r"^\S", line):
                    break

            insert_idx = ha_section_idx + 1
            lines.insert(insert_idx, "")
            lines.insert(insert_idx + 1, f"{indent}packages:")
            lines.insert(
                insert_idx + 2,
                f"{indent}  broadlink_manager: !include broadlink_manager/package.yaml",
            )
        else:
            if content and not content.endswith("\n"):
                lines.append("")
            lines.append("")
            lines.append("homeassistant:")
            lines.append("  packages:")
            lines.append(
                "    broadlink_manager: !include broadlink_manager/package.yaml"
            )

        new_content = "\n".join(lines)
        config_file.write_text(new_content, encoding="utf-8")
        result["added"] = True
        return result

    except Exception as e:
        result["error"] = str(e)
        result["instructions"] = (
            "Could not automatically update configuration.yaml. "
            "Please manually add:\n"
            "homeassistant:\n"
            "  packages:\n"
            "    broadlink_manager: !include broadlink_manager/package.yaml"
        )
        return result


class TestEnsurePackageInclude:
    """Test _ensure_package_include method"""

    def test_already_present(self):
        """Test that existing include is detected"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yaml"
            config_file.write_text(
                "homeassistant:\n"
                "  packages:\n"
                "    broadlink_manager: !include broadlink_manager/package.yaml\n"
            )

            result = ensure_package_include(Path(tmpdir))

            assert result["already_present"] is True
            assert result["added"] is False
            # File should be unchanged
            assert "broadlink_manager: !include broadlink_manager/package.yaml" in config_file.read_text()

    def test_add_to_existing_homeassistant_section(self):
        """Test adding include to existing homeassistant: section without packages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yaml"
            config_file.write_text(
                "homeassistant:\n"
                "  name: My Home\n"
                "  latitude: 45.0\n"
                "  longitude: -90.0\n"
            )

            result = ensure_package_include(Path(tmpdir))

            assert result["added"] is True
            content = config_file.read_text()
            assert "packages:" in content
            assert "broadlink_manager: !include broadlink_manager/package.yaml" in content
            # Original content should be preserved
            assert "name: My Home" in content
            assert "latitude: 45.0" in content

    def test_add_to_existing_packages_section(self):
        """Test adding include to existing packages: section"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yaml"
            config_file.write_text(
                "homeassistant:\n"
                "  packages:\n"
                "    other_package: !include other_package.yaml\n"
            )

            result = ensure_package_include(Path(tmpdir))

            assert result["added"] is True
            content = config_file.read_text()
            assert "broadlink_manager: !include broadlink_manager/package.yaml" in content
            # Other package should still be there
            assert "other_package: !include other_package.yaml" in content

    def test_add_new_homeassistant_section(self):
        """Test adding homeassistant: section when none exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yaml"
            config_file.write_text(
                "default_config:\n"
                "frontend:\n"
            )

            result = ensure_package_include(Path(tmpdir))

            assert result["added"] is True
            content = config_file.read_text()
            assert "homeassistant:" in content
            assert "packages:" in content
            assert "broadlink_manager: !include broadlink_manager/package.yaml" in content
            # Original content should be preserved
            assert "default_config:" in content
            assert "frontend:" in content

    def test_config_file_not_found(self):
        """Test when configuration.yaml doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_package_include(Path(tmpdir))

            assert result["added"] is False
            assert result["already_present"] is False
            assert result["error"] is not None
            assert result["instructions"] is not None

    def test_include_dir_named_detected(self):
        """Test detection of !include_dir_named packages setup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yaml"
            config_file.write_text(
                "homeassistant:\n"
                "  packages: !include_dir_named packages/\n"
            )

            result = ensure_package_include(Path(tmpdir))

            assert result["added"] is False
            assert result["already_present"] is False
            assert result["instructions"] is not None
            assert "include_dir_named" in result["instructions"].lower() or "package_output_path" in result["instructions"].lower()

    def test_idempotent_multiple_calls(self):
        """Test that calling multiple times doesn't duplicate the include"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yaml"
            config_file.write_text("default_config:\n")

            # First call should add
            result1 = ensure_package_include(Path(tmpdir))
            assert result1["added"] is True

            # Second call should detect already present
            result2 = ensure_package_include(Path(tmpdir))
            assert result2["already_present"] is True
            assert result2["added"] is False

            # Verify only one include in file
            content = config_file.read_text()
            assert content.count("broadlink_manager: !include broadlink_manager/package.yaml") == 1
