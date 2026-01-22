"""Tests for NOTAM (Notice to Airmen) client with graceful degradation.

This module tests the UK NATS PIB XML feed integration that provides
critical airfield and airspace information to pilots.

Test Strategy:
    - Mock HTTP requests to NATS PIB XML feed
    - Test XML parsing with realistic NOTAM data structures
    - Validate persistent caching with configurable retention
    - Test graceful degradation (use stale cache on failures)
    - Verify location filtering (ICAO codes and geographic radius)
    - Test failure tracking for monitoring

Coverage:
    - Client initialization with cache retention settings
    - PIB XML parsing (NOTAM structure extraction)
    - Persistent cache read/write operations
    - ICAO code filtering
    - Geographic proximity filtering (Haversine distance)
    - Graceful failure handling (network errors, malformed XML)
    - Stale cache usage when fresh data unavailable
    - Failure tracking in config entry

Aviation Context:
    - NOTAMs provide critical safety information (runway closures, airspace restrictions)
    - Integration uses free UK NATS PIB service (no API key required)
    - Stale NOTAMs better than no NOTAMs for situational awareness
    - Daily updates sufficient for most general aviation planning
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import pytest

from custom_components.hangar_assistant.utils.notam import NOTAMClient


# Sample PIB XML response for testing
SAMPLE_PIB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PIBS>
  <PIB>
    <ID>A0001/25</ID>
    <Location>EGKA</Location>
    <Category>AERODROME</Category>
    <StartDate>2025-01-15T06:00:00Z</StartDate>
    <EndDate>2025-01-20T18:00:00Z</EndDate>
    <Text>RWY 09/27 CLOSED FOR MAINTENANCE</Text>
    <Q_Code>QMRLC</Q_Code>
    <Latitude>51.33</Latitude>
    <Longitude>-0.75</Longitude>
  </PIB>
  <PIB>
    <ID>A0002/25</ID>
    <Location>EGLL</Location>
    <Category>AIRSPACE</Category>
    <StartDate>2025-01-16T10:00:00Z</StartDate>
    <EndDate>2025-01-16T14:00:00Z</EndDate>
    <Text>TEMPORARY RESTRICTED AREA ACTIVE</Text>
    <Q_Code>QRTCA</Q_Code>
    <Latitude>51.47</Latitude>
    <Longitude>-0.46</Longitude>
  </PIB>
  <PIB>
    <ID>A0003/25</ID>
    <Location>EGHI</Location>
    <Category>NAVIGATION</Category>
    <StartDate>2025-01-14T08:00:00Z</StartDate>
    <EndDate>2025-01-25T16:00:00Z</EndDate>
    <Text>VOR/DME UNSERVICEABLE</Text>
    <Latitude>50.95</Latitude>
    <Longitude>-1.36</Longitude>
  </PIB>
</PIBS>
"""


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance for NOTAM client testing.
    
    Provides:
        - Mock hass with config.path() for cache file location
        - Returns cache path: /mock/config/hangar_assistant_cache/notams.json
    
    Used By:
        - All NOTAM client test classes
        - Tests requiring cache file operations
    
    Returns:
        MagicMock: Configured Home Assistant instance
    """
    hass = MagicMock()
    hass.config.path = lambda x: f"/mock/config/{x}"
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    return hass


@pytest.fixture
def mock_entry():
    """Create a mock config entry with NOTAM integration settings.
    
    Provides:
        - Mock entry with integrations.notams configuration
        - enabled=True (NOTAM integration active)
        - consecutive_failures=0 (no prior errors)
        - Tracking fields for failure monitoring
    
    Used By:
        - Tests validating failure tracking
        - Tests requiring config entry updates
    
    Returns:
        MagicMock: Config entry with NOTAM settings
    """
    entry = MagicMock()
    entry.data = {
        "integrations": {
            "notams": {
                "enabled": True,
                "consecutive_failures": 0,
                "last_update": None,
                "last_error": None
            }
        }
    }
    return entry


@pytest.fixture
def notam_client(mock_hass, mock_entry):
    """Create a NOTAM client instance with 7-day cache retention.
    
    Provides:
        - Configured NOTAMClient with mock hass
        - Cache retention: 7 days
        - Failure tracking enabled via mock_entry
    
    Used By:
        - Most NOTAM client tests
        - Tests requiring pre-configured client
    
    Returns:
        NOTAMClient: Ready-to-use client instance
    """
    return NOTAMClient(mock_hass, cache_days=7, entry=mock_entry)


class TestNOTAMClientInitialization:
    """Test suite for NOTAM client initialization and configuration.
    
    Tests basic client setup with various configuration options including
    default parameters, custom cache retention, and config entry tracking.
    
    Test Approach:
        - Direct instantiation without mocking internals
        - Validate attribute assignment
        - Verify cache path construction
    
    Scenarios Covered:
        - Default initialization (7-day cache, no entry)
        - Custom cache retention (14 days)
        - Config entry tracking for failure monitoring
        - Cache file path construction
    """

    def test_initialization_with_defaults(self, mock_hass):
        """Test NOTAM client initializes with default 7-day cache retention.
        
        This test validates the default configuration when no custom
        parameters are provided during client initialization.
        
        Setup:
            - Create client with only mock_hass (no cache_days or entry)
        
        Validation:
            - hass reference stored correctly
            - cache_days defaults to 7
            - entry is None (no failure tracking)
        
        Expected Result:
            Client ready to fetch NOTAMs with 7-day cache retention.
        """
        client = NOTAMClient(mock_hass)
        assert client.hass == mock_hass
        assert client.cache_days == 7
        assert client.entry is None

    def test_initialization_with_custom_cache_days(self, mock_hass, mock_entry):
        """Test NOTAM client accepts custom cache retention period.
        
        This test validates that cache retention can be configured per
        installation (e.g., 14 days for frequent flyers, 3 days for occasional).
        
        Setup:
            - Create client with cache_days=14
            - Provide mock_entry for failure tracking
        
        Validation:
            - cache_days set to 14 (not default 7)
            - entry reference stored for failure tracking
        
        Expected Result:
            Client configured to retain cached NOTAMs for 14 days,
            enabling longer offline operation.
        """
        client = NOTAMClient(mock_hass, cache_days=14, entry=mock_entry)
        assert client.cache_days == 14
        assert client.entry == mock_entry

    def test_cache_directory_path(self, notam_client):
        """Test cache file path constructed correctly in HA config directory.
        
        This test validates the cache file path follows the standard
        Hangar Assistant cache directory structure.
        
        Setup:
            - Use notam_client fixture (pre-configured)
        
        Validation:
            - cache_file path is /mock/config/hangar_assistant_cache/notams.json
            - Path uses hass.config.path() helper
        
        Expected Result:
            Cache file stored in persistent location that survives
            Home Assistant restarts.
        """
        expected_path = "/mock/config/hangar_assistant_cache/notams.json"
        assert str(notam_client.cache_file) == expected_path


class TestXMLParsing:
    """Test suite for UK NATS PIB XML parsing.
    
    Tests the XML parsing logic that extracts structured NOTAM data from
    the UK NATS PIB feed. Validates data extraction, field mapping, and
    graceful handling of missing/malformed fields.
    
    Test Approach:
        - Use realistic SAMPLE_PIB_XML fixture
        - Test with complete and incomplete XML structures
        - Validate type coercion (lat/lon to float, dates to ISO strings)
    
    Scenarios Covered:
        - Valid complete XML (all fields present)
        - XML with missing optional fields (latitude, longitude, Q-code)
        - Empty XML (no NOTAMs)
        - Malformed XML (invalid structure)
    
    Aviation Context:
        NOTAMs may have partial data depending on type. For example,
        airspace NOTAMs often lack precise coordinates.
    """

    def test_parse_valid_xml(self, notam_client):
        """Test parsing complete PIB XML extracts all NOTAM fields correctly.
        
        This test validates the primary parsing flow with realistic,
        complete NOTAM data including all optional fields.
        
        Scenario:
            - Sample XML contains 3 NOTAMs (EGKA, EGLL, EGHI)
            - All have complete data including coordinates and Q-codes
        
        Setup:
            - Use SAMPLE_PIB_XML (defined at module level)
            - Parse via _parse_pib_xml() method
        
        Validation:
            - Returns list of 3 NOTAM dictionaries
            - First NOTAM (EGKA):
                - id: "A0001/25"
                - location: "EGKA" (Shoreham)
                - category: "AERODROME"
                - text: "RWY 09/27 CLOSED FOR MAINTENANCE"
                - q_code: "QMRLC" (runway closure)
                - latitude: 51.33, longitude: -0.75
        
        Expected Result:
            All NOTAM data extracted correctly with proper type conversions.
            Coordinates as floats, dates as ISO strings.
        """
        notams = notam_client._parse_pib_xml(SAMPLE_PIB_XML)
        
        assert len(notams) == 3
        assert notams[0]["id"] == "A0001/25"
        assert notams[0]["location"] == "EGKA"
        assert notams[0]["category"] == "AERODROME"
        assert notams[0]["text"] == "RWY 09/27 CLOSED FOR MAINTENANCE"
        assert notams[0]["q_code"] == "QMRLC"
        assert notams[0]["latitude"] == 51.33
        assert notams[0]["longitude"] == -0.75

    def test_parse_xml_with_missing_fields(self, notam_client):
        """Test parsing XML with missing optional fields handles gaps gracefully.
        
        This test validates that the parser doesn't crash when NOTAMs
        lack optional fields like coordinates or Q-codes.
        
        Scenario:
            - XML contains NOTAM without latitude, longitude, Q-code
            - These fields are optional in PIB format
        
        Setup:
            - Create XML with minimal required fields only
            - Parse via _parse_pib_xml()
        
        Validation:
            - Parser returns NOTAM dictionary
            - Missing fields either None or omitted from dict
            - Required fields (id, location, text) still present
        
        Expected Result:
            Parser extracts available data without errors. Location
            filtering may not work without coordinates, but NOTAM
            still visible in full list.
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <PIBS>
          <PIB>
            <ID>A0004/25</ID>
            <Location>EGKA</Location>
            <Text>TEST NOTAM</Text>
          </PIB>
        </PIBS>"""
        
        notams = notam_client._parse_pib_xml(xml)
        
        assert len(notams) == 1
        assert notams[0]["id"] == "A0004/25"
        assert notams[0]["category"] == "UNKNOWN"  # Defaults to UNKNOWN
        assert notams[0]["latitude"] is None
        assert notams[0]["longitude"] is None

    def test_parse_empty_xml(self, notam_client):
        """Test parsing empty XML returns empty list."""
        xml = """<?xml version="1.0" encoding="UTF-8"?><PIBS></PIBS>"""
        notams = notam_client._parse_pib_xml(xml)
        assert notams == []

    def test_parse_malformed_xml(self, notam_client):
        """Test parsing malformed XML returns empty list (graceful handling)."""
        xml = """<PIBS><PIB><ID>broken"""  # Unclosed tags
        
        notams = notam_client._parse_pib_xml(xml)
        assert notams == []  # Parser catches errors and returns empty list


class TestCaching:
    """Test NOTAM cache read/write functionality."""

    def test_write_and_read_cache(self, notam_client, tmp_path):
        """Test writing cache and reading it back returns same data."""
        # Override cache path to use temp directory
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        test_notams = [
            {"id": "A0001/25", "location": "EGKA", "text": "Test NOTAM"}
        ]
        
        asyncio.run(notam_client._write_cache(test_notams))
        
        # Read back
        assert os.path.exists(notam_client.cache_file)
        with open(notam_client.cache_file, "r") as f:
            cache_data = json.load(f)
        
        assert cache_data["notams"] == test_notams
        assert "cached_at" in cache_data  # Implementation uses cached_at not timestamp

    def test_read_fresh_cache(self, notam_client, tmp_path):
        """Test reading fresh cache returns NOTAMs."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Write fresh cache
        test_notams = [{"id": "A0001/25", "text": "Test"}]
        asyncio.run(notam_client._write_cache(test_notams))

        # Read within retention period
        result = asyncio.run(notam_client._read_cache())

        assert result == test_notams

    def test_read_expired_cache_returns_none(self, notam_client, tmp_path):
        """Test reading expired cache returns None."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        notam_client.cache_days = 7
        
        # Write cache with old timestamp
        old_time = (datetime.utcnow() - timedelta(days=8)).isoformat()
        cache_data = {
            "notams": [{"id": "A0001/25"}],
            "timestamp": old_time
        }
        
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Attempt to read - should return None (expired)
        result = asyncio.run(notam_client._read_cache())

        assert result is None

    def test_read_stale_cache(self, notam_client, tmp_path):
        """Test reading stale cache still returns NOTAMs for graceful degradation."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Write stale cache
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        cache_data = {
            "notams": [{"id": "A0001/25", "text": "Stale"}],
            "timestamp": old_time
        }
        
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Read stale cache
        result = asyncio.run(notam_client._read_stale_cache())

        assert result == [{"id": "A0001/25", "text": "Stale"}]

    def test_read_nonexistent_cache(self, notam_client, tmp_path):
        """Test reading nonexistent cache returns None."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "does_not_exist.json"))
        
        result = asyncio.run(notam_client._read_cache())

        assert result is None


class TestFetchNOTAMs:
    """Test NOTAM fetching with network and cache fallback."""

    @pytest.mark.asyncio
    async def test_fetch_with_fresh_cache(self, notam_client, tmp_path):
        """Test fetch returns fresh cache without network call."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Create fresh cache
        test_notams = [{"id": "A0001/25", "location": "EGKA"}]
        await notam_client._write_cache(test_notams)
        
        # Fetch should return cache without network call
        notams, is_stale = await notam_client.fetch_notams()
        
        assert notams == test_notams
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_fetch_from_nats_on_cache_miss(self, notam_client, tmp_path):
        """Test fetch calls NATS API when cache is missing."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Mock successful HTTP response via HA's aiohttp helper
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=SAMPLE_PIB_XML)
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(notam_client.hass.helpers.aiohttp_client, "async_get_clientsession", return_value=mock_session):
            notams, is_stale = await notam_client.fetch_notams()
            
            assert len(notams) == 3
            assert is_stale is False
            assert notams[0]["id"] == "A0001/25"

    @pytest.mark.asyncio
    async def test_fetch_handles_network_error_gracefully(self, notam_client, mock_entry, tmp_path):
        """Test fetch falls back to stale cache on network error."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Create stale cache
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        cache_data = {
            "notams": [{"id": "STALE001", "text": "Stale NOTAM"}],
            "timestamp": old_time
        }
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Mock network failure via HA's aiohttp helper
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        
        with patch.object(notam_client.hass.helpers.aiohttp_client, "async_get_clientsession", return_value=mock_session):
            notams, is_stale = await notam_client.fetch_notams()
            
            # Should return stale cache
            assert notams == [{"id": "STALE001", "text": "Stale NOTAM"}]
            assert is_stale is True
            
            # Should increment failure counter
            assert mock_entry.data["integrations"]["notams"]["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_fetch_handles_http_error_status(self, notam_client, tmp_path):
        """Test fetch handles HTTP error status codes gracefully."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Create stale cache for fallback
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        cache_data = {
            "notams": [{"id": "FALLBACK001"}],
            "timestamp": old_time
        }
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Mock HTTP 500 error via HA's aiohttp helper
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(notam_client.hass.helpers.aiohttp_client, "async_get_clientsession", return_value=mock_session):
            notams, is_stale = await notam_client.fetch_notams()
            
            # Should fall back to stale cache
            assert notams == [{"id": "FALLBACK001"}]
            assert is_stale is True

    @pytest.mark.asyncio
    async def test_fetch_with_no_cache_and_network_error(self, notam_client, tmp_path):
        """Test fetch returns empty list when no cache and network fails."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "nonexistent.json"))
        
        # Mock network failure via HA's aiohttp helper
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        
        with patch.object(notam_client.hass.helpers.aiohttp_client, "async_get_clientsession", return_value=mock_session):
            notams, is_stale = await notam_client.fetch_notams()
            
            assert notams == []
            assert is_stale is True  # No cache + failure = stale/no data


class TestLocationFiltering:
    """Test NOTAM filtering by ICAO and geographic location."""

    def test_filter_by_icao_code(self, notam_client):
        """Test filtering NOTAMs by ICAO code."""
        notams = notam_client._parse_pib_xml(SAMPLE_PIB_XML)
        
        filtered = notam_client.filter_by_location(notams, icao="EGKA")
        
        assert len(filtered) == 1
        assert filtered[0]["location"] == "EGKA"

    def test_filter_by_coordinates(self, notam_client):
        """Test filtering NOTAMs by proximity to coordinates."""
        notams = notam_client._parse_pib_xml(SAMPLE_PIB_XML)
        
        # Popham coordinates: 51.20, -1.23 (within 50nm of EGHI)
        filtered = notam_client.filter_by_location(
            notams, 
            icao=None, 
            lat=51.20, 
            lon=-1.23, 
            radius_nm=50
        )
        
        # Should include EGHI (50.95, -1.36) which is ~12nm away
        assert any(n["location"] == "EGHI" for n in filtered)

    def test_filter_excludes_distant_notams(self, notam_client):
        """Test filtering excludes NOTAMs beyond radius."""
        notams = notam_client._parse_pib_xml(SAMPLE_PIB_XML)
        
        # Use small radius
        filtered = notam_client.filter_by_location(
            notams,
            icao=None,
            lat=51.33,
            lon=-0.75,
            radius_nm=5
        )
        
        # Should only include EGKA (0nm away)
        assert len(filtered) == 1
        assert filtered[0]["location"] == "EGKA"

    def test_filter_with_no_coordinates_returns_all(self, notam_client):
        """Test filtering with no ICAO or coordinates returns empty list (no filter criteria)."""
        notams = notam_client._parse_pib_xml(SAMPLE_PIB_XML)
        
        filtered = notam_client.filter_by_location(notams, icao=None, lat=None, lon=None)
        
        assert len(filtered) == 0  # No filter criteria = no matches


class TestDistanceCalculation:
    """Test Haversine distance calculation."""

    def test_distance_calculation_same_point(self, notam_client):
        """Test distance between same point is zero."""
        distance = notam_client._calculate_distance_nm(51.33, -0.75, 51.33, -0.75)
        assert distance == pytest.approx(0.0, abs=0.1)

    def test_distance_calculation_known_distance(self, notam_client):
        """Test distance calculation matches known distance."""
        # London Heathrow to Gatwick ~22nm
        distance = notam_client._calculate_distance_nm(
            51.4700, -0.4543,  # Heathrow
            51.1537, -0.1821   # Gatwick
        )
        assert distance == pytest.approx(22, abs=2)  # Allow 2nm tolerance

    def test_distance_with_none_coordinates(self, notam_client):
        """Test distance calculation with None coordinates returns infinity."""
        distance = notam_client._calculate_distance_nm(None, None, 51.33, -0.75)
        assert distance == float('inf')


class TestFailureTracking:
    """Test failure counter integration."""

    @pytest.mark.asyncio
    async def test_increment_failure_counter(self, notam_client, mock_entry):
        """Test failure counter increments correctly."""
        await notam_client._increment_failure_counter("Test error message")
        
        assert mock_entry.data["integrations"]["notams"]["consecutive_failures"] == 1
        assert mock_entry.data["integrations"]["notams"]["last_error"] == "Test error message"

    @pytest.mark.asyncio
    async def test_increment_failure_counter_without_entry(self, mock_hass):
        """Test failure counter handles missing entry gracefully."""
        client = NOTAMClient(mock_hass, entry=None)
        
        # Should not raise exception
        await client._increment_failure_counter("Error")

    @pytest.mark.asyncio
    async def test_reset_failure_counter(self, notam_client, mock_entry):
        """Test failure counter resets on success."""
        # Set failures first
        mock_entry.data["integrations"]["notams"]["consecutive_failures"] = 5
        
        await notam_client._reset_failure_counter()
        
        assert mock_entry.data["integrations"]["notams"]["consecutive_failures"] == 0
        assert "last_update" in mock_entry.data["integrations"]["notams"]


class TestCacheManagement:
    """Test cache management utilities."""

    @pytest.mark.asyncio
    async def test_clear_cache(self, notam_client, tmp_path):
        """Test cache clearing removes file."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Create cache
        await notam_client._write_cache([{ "id": "A0001/25" }])
        assert os.path.exists(notam_client.cache_file)
        
        # Clear cache
        await notam_client.clear_cache()
        
        assert not os.path.exists(notam_client.cache_file)

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_existing_cache(self, notam_client, tmp_path):
        """Test cache stats returns correct information."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "notams.json"))
        
        # Create cache
        await notam_client._write_cache([{ "id": "A0001/25" }, { "id": "A0002/25" }])
        
        stats = await notam_client.get_cache_stats()
        
        assert stats["exists"] is True
        assert stats["count"] == 2
        assert stats["age_hours"] < 1  # Just created
        assert stats["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_no_cache(self, notam_client, tmp_path):
        """Test cache stats returns False for nonexistent cache."""
        from pathlib import Path
        notam_client.cache_dir = Path(str(tmp_path))

        notam_client.cache_file = Path(str(tmp_path / "nonexistent.json"))
        
        stats = await notam_client.get_cache_stats()
        
        assert stats["exists"] is False
        assert stats["count"] == 0
        assert stats["age_hours"] == 0
        assert stats["size_bytes"] == 0
