"""Unit tests for NOTAM client."""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, mock_open
import pytest
import aiohttp

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
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = lambda x: f"/mock/config/{x}"
    return hass


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
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
    """Create a NOTAM client instance."""
    return NOTAMClient(mock_hass, cache_days=7, entry=mock_entry)


class TestNOTAMClientInitialization:
    """Test NOTAM client initialization."""

    def test_initialization_with_defaults(self, mock_hass):
        """Test client initializes with default parameters."""
        client = NOTAMClient(mock_hass)
        assert client.hass == mock_hass
        assert client.cache_days == 7
        assert client.entry is None

    def test_initialization_with_custom_cache_days(self, mock_hass, mock_entry):
        """Test client initializes with custom cache retention."""
        client = NOTAMClient(mock_hass, cache_days=14, entry=mock_entry)
        assert client.cache_days == 14
        assert client.entry == mock_entry

    def test_cache_directory_path(self, notam_client):
        """Test cache directory path is constructed correctly."""
        expected_path = "/mock/config/hangar_assistant_cache/notams.json"
        assert notam_client.cache_file == expected_path


class TestXMLParsing:
    """Test PIB XML parsing functionality."""

    def test_parse_valid_xml(self, notam_client):
        """Test parsing valid PIB XML returns correct data structure."""
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
        """Test parsing XML with missing optional fields gracefully handles gaps."""
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
        assert notams[0]["category"] is None
        assert notams[0]["latitude"] is None
        assert notams[0]["longitude"] is None

    def test_parse_empty_xml(self, notam_client):
        """Test parsing empty XML returns empty list."""
        xml = """<?xml version="1.0" encoding="UTF-8"?><PIBS></PIBS>"""
        notams = notam_client._parse_pib_xml(xml)
        assert notams == []

    def test_parse_malformed_xml(self, notam_client):
        """Test parsing malformed XML raises exception."""
        xml = """<PIBS><PIB><ID>broken"""  # Unclosed tags
        
        with pytest.raises(Exception):  # ElementTree.ParseError
            notam_client._parse_pib_xml(xml)


class TestCaching:
    """Test NOTAM cache read/write functionality."""

    def test_write_and_read_cache(self, notam_client, tmp_path):
        """Test writing cache and reading it back returns same data."""
        # Override cache path to use temp directory
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        test_notams = [
            {"id": "A0001/25", "location": "EGKA", "text": "Test NOTAM"}
        ]
        
        notam_client._write_cache(test_notams)
        
        # Read back
        assert os.path.exists(notam_client.cache_file)
        with open(notam_client.cache_file, "r") as f:
            cache_data = json.load(f)
        
        assert cache_data["notams"] == test_notams
        assert "timestamp" in cache_data

    def test_read_fresh_cache(self, notam_client, tmp_path):
        """Test reading fresh cache returns NOTAMs."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Write fresh cache
        test_notams = [{"id": "A0001/25", "text": "Test"}]
        notam_client._write_cache(test_notams)
        
        # Read within retention period
        result = notam_client._read_cache()
        
        assert result == test_notams

    def test_read_expired_cache_returns_none(self, notam_client, tmp_path):
        """Test reading expired cache returns None."""
        notam_client.cache_file = str(tmp_path / "notams.json")
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
        result = notam_client._read_cache()
        
        assert result is None

    def test_read_stale_cache(self, notam_client, tmp_path):
        """Test reading stale cache still returns NOTAMs for graceful degradation."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Write stale cache
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        cache_data = {
            "notams": [{"id": "A0001/25", "text": "Stale"}],
            "timestamp": old_time
        }
        
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Read stale cache
        result = notam_client._read_stale_cache()
        
        assert result == [{"id": "A0001/25", "text": "Stale"}]

    def test_read_nonexistent_cache(self, notam_client, tmp_path):
        """Test reading nonexistent cache returns None."""
        notam_client.cache_file = str(tmp_path / "does_not_exist.json")
        
        result = notam_client._read_cache()
        
        assert result is None


class TestFetchNOTAMs:
    """Test NOTAM fetching with network and cache fallback."""

    @pytest.mark.asyncio
    async def test_fetch_with_fresh_cache(self, notam_client, tmp_path):
        """Test fetch returns fresh cache without network call."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Create fresh cache
        test_notams = [{"id": "A0001/25", "location": "EGKA"}]
        notam_client._write_cache(test_notams)
        
        # Fetch should return cache without network call
        notams, is_stale = await notam_client.fetch_notams()
        
        assert notams == test_notams
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_fetch_from_nats_on_cache_miss(self, notam_client, tmp_path):
        """Test fetch calls NATS API when cache is missing."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Mock successful HTTP response
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = MagicMock(return_value=SAMPLE_PIB_XML)
            mock_get.return_value.__aenter__.return_value = mock_response
            
            notams, is_stale = await notam_client.fetch_notams()
            
            assert len(notams) == 3
            assert is_stale is False
            assert notams[0]["id"] == "A0001/25"

    @pytest.mark.asyncio
    async def test_fetch_handles_network_error_gracefully(self, notam_client, mock_entry, tmp_path):
        """Test fetch falls back to stale cache on network error."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Create stale cache
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        cache_data = {
            "notams": [{"id": "STALE001", "text": "Stale NOTAM"}],
            "timestamp": old_time
        }
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Mock network failure
        with patch("aiohttp.ClientSession.get", side_effect=aiohttp.ClientError("Network error")):
            notams, is_stale = await notam_client.fetch_notams()
            
            # Should return stale cache
            assert notams == [{"id": "STALE001", "text": "Stale NOTAM"}]
            assert is_stale is True
            
            # Should increment failure counter
            assert mock_entry.data["integrations"]["notams"]["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_fetch_handles_http_error_status(self, notam_client, tmp_path):
        """Test fetch handles HTTP error status codes gracefully."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Create stale cache for fallback
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        cache_data = {
            "notams": [{"id": "FALLBACK001"}],
            "timestamp": old_time
        }
        with open(notam_client.cache_file, "w") as f:
            json.dump(cache_data, f)
        
        # Mock HTTP 500 error
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status = 500
            mock_get.return_value.__aenter__.return_value = mock_response
            
            notams, is_stale = await notam_client.fetch_notams()
            
            # Should fall back to stale cache
            assert notams == [{"id": "FALLBACK001"}]
            assert is_stale is True

    @pytest.mark.asyncio
    async def test_fetch_with_no_cache_and_network_error(self, notam_client, tmp_path):
        """Test fetch returns empty list when no cache and network fails."""
        notam_client.cache_file = str(tmp_path / "nonexistent.json")
        
        # Mock network failure
        with patch("aiohttp.ClientSession.get", side_effect=aiohttp.ClientError):
            notams, is_stale = await notam_client.fetch_notams()
            
            assert notams == []
            assert is_stale is True


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
            latitude=51.20, 
            longitude=-1.23, 
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
            latitude=51.33,
            longitude=-0.75,
            radius_nm=5
        )
        
        # Should only include EGKA (0nm away)
        assert len(filtered) == 1
        assert filtered[0]["location"] == "EGKA"

    def test_filter_with_no_coordinates_returns_all(self, notam_client):
        """Test filtering with no ICAO or coordinates returns all NOTAMs."""
        notams = notam_client._parse_pib_xml(SAMPLE_PIB_XML)
        
        filtered = notam_client.filter_by_location(notams, icao=None, latitude=None, longitude=None)
        
        assert len(filtered) == len(notams)


class TestDistanceCalculation:
    """Test Haversine distance calculation."""

    def test_distance_calculation_same_point(self, notam_client):
        """Test distance between same point is zero."""
        distance = notam_client._calculate_distance_nm(51.33, -0.75, 51.33, -0.75)
        assert distance == pytest.approx(0.0, abs=0.1)

    def test_distance_calculation_known_distance(self, notam_client):
        """Test distance calculation matches known distance."""
        # London Heathrow to Gatwick ~24nm
        distance = notam_client._calculate_distance_nm(
            51.4700, -0.4543,  # Heathrow
            51.1537, -0.1821   # Gatwick
        )
        assert distance == pytest.approx(24, abs=2)  # Allow 2nm tolerance

    def test_distance_with_none_coordinates(self, notam_client):
        """Test distance calculation with None coordinates returns infinity."""
        distance = notam_client._calculate_distance_nm(None, None, 51.33, -0.75)
        assert distance == float('inf')


class TestFailureTracking:
    """Test failure counter integration."""

    def test_increment_failure_counter(self, notam_client, mock_entry):
        """Test failure counter increments correctly."""
        notam_client._increment_failure_counter("Test error message")
        
        assert mock_entry.data["integrations"]["notams"]["consecutive_failures"] == 1
        assert mock_entry.data["integrations"]["notams"]["last_error"] == "Test error message"

    def test_increment_failure_counter_without_entry(self, mock_hass):
        """Test failure counter handles missing entry gracefully."""
        client = NOTAMClient(mock_hass, entry=None)
        
        # Should not raise exception
        client._increment_failure_counter("Error")

    def test_reset_failure_counter(self, notam_client, mock_entry):
        """Test failure counter resets on success."""
        # Set failures first
        mock_entry.data["integrations"]["notams"]["consecutive_failures"] = 5
        
        notam_client._reset_failure_counter()
        
        assert mock_entry.data["integrations"]["notams"]["consecutive_failures"] == 0
        assert "last_update" in mock_entry.data["integrations"]["notams"]


class TestCacheManagement:
    """Test cache management utilities."""

    def test_clear_cache(self, notam_client, tmp_path):
        """Test cache clearing removes file."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Create cache
        notam_client._write_cache([{"id": "A0001/25"}])
        assert os.path.exists(notam_client.cache_file)
        
        # Clear cache
        notam_client.clear_cache()
        
        assert not os.path.exists(notam_client.cache_file)

    def test_get_cache_stats_with_existing_cache(self, notam_client, tmp_path):
        """Test cache stats returns correct information."""
        notam_client.cache_file = str(tmp_path / "notams.json")
        
        # Create cache
        notam_client._write_cache([{"id": "A0001/25"}, {"id": "A0002/25"}])
        
        stats = notam_client.get_cache_stats()
        
        assert stats["exists"] is True
        assert stats["count"] == 2
        assert stats["age_hours"] < 1  # Just created
        assert stats["size_bytes"] > 0

    def test_get_cache_stats_with_no_cache(self, notam_client, tmp_path):
        """Test cache stats returns False for nonexistent cache."""
        notam_client.cache_file = str(tmp_path / "nonexistent.json")
        
        stats = notam_client.get_cache_stats()
        
        assert stats["exists"] is False
        assert stats["count"] == 0
        assert stats["age_hours"] == 0
        assert stats["size_bytes"] == 0
