"""Tests for JSON file validation in the integration.

Ensures all JSON files used in the integration are valid and parseable.
This catches syntax errors like missing commas, unclosed braces, etc.
"""

import json
import os
from pathlib import Path


class TestJSONValidation:
    """Validate JSON files in the integration."""

    def test_strings_json_valid(self) -> None:
        """Test that strings.json is valid JSON."""
        strings_path = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "strings.json"
        assert strings_path.exists(), f"strings.json not found at {strings_path}"
        
        with open(strings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Verify it has expected structure
        assert "title" in data
        assert "config" in data or "options" in data

    def test_translation_json_files_valid(self) -> None:
        """Test that all translation JSON files are valid JSON."""
        translations_dir = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "translations"
        assert translations_dir.exists(), f"translations directory not found at {translations_dir}"
        
        json_files = list(translations_dir.glob("*.json"))
        assert len(json_files) > 0, "No JSON files found in translations directory"
        
        for json_file in json_files:
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    raise AssertionError(f"Invalid JSON in {json_file.name}: {e}") from e

    def test_manifest_json_valid(self) -> None:
        """Test that manifest.json is valid JSON."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "hangar_assistant" / "manifest.json"
        assert manifest_path.exists(), f"manifest.json not found at {manifest_path}"
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Verify it has expected Home Assistant manifest structure
        assert "domain" in data
        assert data["domain"] == "hangar_assistant"
