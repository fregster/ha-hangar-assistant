"""Test NOTAM fixtures and real-world data validation."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from custom_components.hangar_assistant.utils.notam import NOTAMClient


FIXTURES_DIR = Path(__file__).parent / "fixtures"
REAL_NOTAM_XML = FIXTURES_DIR / "notam_sample_real.xml"
REAL_NOTAM_METADATA = FIXTURES_DIR / "notam_sample_real.json"


class TestNOTAMFixtureFreshness:
    """Test that NOTAM test fixtures are up-to-date."""

    def test_real_notam_fixture_exists(self):
        """Test that real NOTAM XML fixture file exists."""
        assert REAL_NOTAM_XML.exists(), (
            f"Real NOTAM fixture missing: {REAL_NOTAM_XML}. "
            "Run: curl -o tests/fixtures/notam_sample_real.xml "
            "https://pibs.nats.co.uk/operational/pibs/PIB.xml"
        )
        assert REAL_NOTAM_METADATA.exists(), (
            f"NOTAM metadata missing: {REAL_NOTAM_METADATA}"
        )

    def test_real_notam_fixture_age(self):
        """Test that real NOTAM fixture is not older than 6 months."""
        if not REAL_NOTAM_METADATA.exists():
            pytest.skip("NOTAM metadata file not found")

        with open(REAL_NOTAM_METADATA, 'r') as f:
            metadata = json.load(f)

        downloaded_at_str = metadata.get("downloaded_at")
        if not downloaded_at_str:
            pytest.fail("NOTAM metadata missing 'downloaded_at' field")

        # Parse ISO datetime
        downloaded_at = datetime.fromisoformat(downloaded_at_str.replace("Z", "+00:00"))
        now = datetime.now(downloaded_at.tzinfo)
        age_days = (now - downloaded_at).days

        # Warning threshold: 6 months (~180 days)
        if age_days > 180:
            pytest.fail(
                f"⚠️  NOTAM fixture is {age_days} days old (downloaded {downloaded_at_str}). "
                f"Fixtures older than 6 months should be refreshed to ensure tests "
                f"match current production data format. "
                f"\\n\\nTo refresh: "
                f"\\n  curl -o tests/fixtures/notam_sample_real.xml "
                f"https://pibs.nats.co.uk/operational/pibs/PIB.xml"
                f"\\n  # Then update downloaded_at in tests/fixtures/notam_sample_real.json"
            )

        # Info message for age
        if age_days > 90:
            print(f"\\nℹ️  NOTAM fixture is {age_days} days old. Consider refreshing soon.")

    def test_real_notam_parses_successfully(self):
        """Test that real NOTAM XML fixture parses without errors."""
        if not REAL_NOTAM_XML.exists():
            pytest.skip("Real NOTAM fixture not found")

        from unittest.mock import MagicMock
        mock_hass = MagicMock()
        mock_hass.config.path = lambda x: f"/mock/{x}"
        
        client = NOTAMClient(mock_hass)
        
        with open(REAL_NOTAM_XML, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        notams = client._parse_pib_xml(xml_content)

        # Should parse at least some NOTAMs from real data
        assert len(notams) > 0, "Real NOTAM XML should contain NOTAMs"
        
        # Validate structure of first NOTAM
        first_notam = notams[0]
        assert "id" in first_notam
        assert "location" in first_notam
        assert "text" in first_notam
        
        print(f"\\n✓ Successfully parsed {len(notams)} NOTAMs from real fixture")
        print(f"  Sample: {first_notam['id']} - {first_notam.get('location', 'N/A')}")

    def test_real_notam_structure_matches_tests(self):
        """Test that real NOTAM structure matches our test expectations."""
        if not REAL_NOTAM_XML.exists():
            pytest.skip("Real NOTAM fixture not found")

        from unittest.mock import MagicMock
        mock_hass = MagicMock()
        mock_hass.config.path = lambda x: f"/mock/{x}"
        
        client = NOTAMClient(mock_hass)
        
        with open(REAL_NOTAM_XML, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        notams = client._parse_pib_xml(xml_content)

        # Check that NOTAMs have expected fields
        for notam in notams[:10]:  # Check first 10
            assert isinstance(notam, dict)
            assert "id" in notam
            assert "location" in notam
            assert "category" in notam
            assert "text" in notam
            
            # Optional fields should be present (may be None)
            assert "start_time" in notam
            assert "end_time" in notam
            assert "q_code" in notam
            assert "latitude" in notam
            assert "longitude" in notam

        print(f"\\n✓ Real NOTAM structure validated against {len(notams)} NOTAMs")
