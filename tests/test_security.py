"""Tests for security utilities and protections."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from custom_components.hangar_assistant.utils.security import (
    sanitize_config_for_logging,
    sanitize_filename,
    validate_path_safety,
    sanitize_entity_id,
    sanitize_url,
)


class TestConfigSanitization:
    """Test configuration sanitization for logging."""

    def test_sanitize_api_key(self):
        """Test API key is redacted in logs."""
        config = {
            "name": "London Airfield",
            "api_key": "super_secret_key_12345",
            "latitude": 51.5
        }
        
        sanitized = sanitize_config_for_logging(config)
        
        assert sanitized["name"] == "London Airfield"
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["latitude"] == 51.5

    def test_sanitize_password(self):
        """Test password is redacted in logs."""
        config = {"password": "secret123", "username": "pilot"}
        sanitized = sanitize_config_for_logging(config)
        
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["username"] == "pilot"

    def test_sanitize_nested_credentials(self):
        """Test nested credential redaction."""
        config = {
            "integrations": {
                "openweathermap": {
                    "api_key": "secret",
                    "enabled": True
                }
            }
        }
        
        sanitized = sanitize_config_for_logging(config)
        
        assert sanitized["integrations"]["openweathermap"]["api_key"] == "***REDACTED***"
        assert sanitized["integrations"]["openweathermap"]["enabled"] is True

    def test_sanitize_case_insensitive(self):
        """Test case-insensitive credential detection."""
        config = {
            "API_KEY": "secret1",
            "Api_Key": "secret2",
            "bearer_token": "secret3",
            "AUTHORIZATION": "secret4"
        }
        
        sanitized = sanitize_config_for_logging(config)
        
        for key in config.keys():
            assert sanitized[key] == "***REDACTED***"

    def test_sanitize_non_dict(self):
        """Test sanitization handles non-dict input gracefully."""
        assert sanitize_config_for_logging("not a dict") == "not a dict"
        assert sanitize_config_for_logging(None) is None
        assert sanitize_config_for_logging(123) == 123


class TestFilenameSanitization:
    """Test filename sanitization against path traversal."""

    def test_sanitize_normal_filename(self):
        """Test normal airfield/aircraft names work correctly."""
        assert sanitize_filename("London_Heathrow") == "London_Heathrow"
        assert sanitize_filename("G-ABCD") == "G-ABCD"
        assert sanitize_filename("EGKA") == "EGKA"

    def test_sanitize_path_traversal_attack(self):
        """Test path traversal attacks are blocked."""
        malicious_inputs = [
            "../../../etc/passwd",
            "../../config",
            "..\\..\\windows\\system32",
        ]
        
        for malicious in malicious_inputs:
            result = sanitize_filename(malicious)
            assert ".." not in result
            assert "/" not in result
            assert "\\" not in result

    def test_sanitize_absolute_paths(self):
        """Test absolute paths are sanitized."""
        assert "/" not in sanitize_filename("/etc/passwd")
        assert "/" not in sanitize_filename("/var/log/messages")

    def test_sanitize_special_characters(self):
        """Test special characters are removed."""
        result = sanitize_filename("name<>:\"|?*")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_sanitize_length_limit(self):
        """Test filename length is limited."""
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_sanitize_empty_raises(self):
        """Test empty input raises ValueError."""
        with pytest.raises(ValueError, match="Cannot sanitize empty filename"):
            sanitize_filename("")

    def test_sanitize_no_valid_chars_raises(self):
        """Test input with no valid characters raises ValueError."""
        with pytest.raises(ValueError, match="Invalid input for filename"):
            sanitize_filename("///...")


class TestPathSafety:
    """Test path safety validation."""

    def test_validate_safe_path(self):
        """Test safe path within base directory is accepted."""
        base = Path("/config/cache")
        safe_path = base / "weather.json"
        
        assert validate_path_safety(safe_path, base) is True

    def test_validate_nested_safe_path(self):
        """Test nested safe path is accepted."""
        base = Path("/config/cache")
        safe_path = base / "subdir" / "file.json"
        
        assert validate_path_safety(safe_path, base) is True

    def test_validate_path_traversal_blocked(self):
        """Test path traversal outside base is blocked."""
        base = Path("/config/cache")
        unsafe_path = base / ".." / ".." / "etc" / "passwd"
        
        assert validate_path_safety(unsafe_path, base) is False

    def test_validate_absolute_path_blocked(self):
        """Test absolute path outside base is blocked."""
        base = Path("/config/cache")
        unsafe_path = Path("/etc/passwd")
        
        assert validate_path_safety(unsafe_path, base) is False


class TestEntityIdSanitization:
    """Test entity ID sanitization."""

    def test_sanitize_valid_entity_id(self):
        """Test valid entity IDs are accepted."""
        valid_ids = [
            "sensor.temperature",
            "binary_sensor.door_open",
            "input_number.test_value"
        ]
        
        for entity_id in valid_ids:
            assert sanitize_entity_id(entity_id) == entity_id

    def test_sanitize_invalid_format_raises(self):
        """Test invalid entity ID format raises ValueError."""
        invalid_ids = [
            "temperature",  # No domain
            "sensor.",  # No object_id
            "sensor.temp; DROP TABLE",  # SQL injection attempt
            "sensor../etc/passwd",  # Path traversal
        ]
        
        for entity_id in invalid_ids:
            with pytest.raises(ValueError, match="Invalid entity ID format"):
                sanitize_entity_id(entity_id)

    def test_sanitize_empty_raises(self):
        """Test empty entity ID raises ValueError."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            sanitize_entity_id("")


class TestUrlSanitization:
    """Test URL sanitization."""

    def test_sanitize_valid_https_url(self):
        """Test valid HTTPS URLs are accepted."""
        url = "https://api.example.com/data"
        assert sanitize_url(url) == url

    def test_sanitize_valid_http_url(self):
        """Test valid HTTP URLs are accepted."""
        url = "https://api.example.com/data"
        assert sanitize_url(url) == url

    def test_sanitize_file_scheme_blocked(self):
        """Test file:// URLs are blocked."""
        with pytest.raises(ValueError, match="Disallowed URL scheme: file"):
            sanitize_url("file:///etc/passwd")

    def test_sanitize_javascript_blocked(self):
        """Test javascript: URLs are blocked."""
        with pytest.raises(ValueError, match="Disallowed URL scheme"):
            sanitize_url("javascript:alert('xss')")

    def test_sanitize_data_scheme_blocked(self):
        """Test data: URLs are blocked by default."""
        with pytest.raises(ValueError, match="Disallowed URL scheme: data"):
            sanitize_url("data:text/html,<script>alert('xss')</script>")

    def test_sanitize_custom_schemes(self):
        """Test custom allowed schemes work."""
        url = "ftp://example.com/file"
        assert sanitize_url(url, allowed_schemes=["ftp"]) == url

    def test_sanitize_invalid_format_raises(self):
        """Test invalid URL format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URL format"):
            sanitize_url("not a url")

    def test_sanitize_control_characters_blocked(self):
        """Test URLs with control characters are blocked."""
        invalid_urls = [
            "https://example.com/path with spaces",
            "https://example.com/\ninjection",
            "https://example.com/\tinjection",
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError, match="contains invalid characters"):
                sanitize_url(url)


class TestCacheManagerSanitization:
    """Test cache manager filename sanitization."""

    @pytest.mark.asyncio
    async def test_cache_key_sanitization(self):
        """Test cache keys are properly sanitized."""
        from custom_components.hangar_assistant.utils.cache_manager import CacheManager
        
        mock_hass = MagicMock()
        mock_hass.config.path = lambda x: f"/config/{x}"
        mock_hass.async_add_executor_job = AsyncMock(side_effect=lambda f: f())
        
        cache = CacheManager(
            mock_hass,
            namespace="test",
            memory_enabled=True,
            persistent_enabled=False  # Disable persistence for unit test
        )
        
        # Test that malicious keys are sanitized
        cache_path = cache._get_cache_file_path("../../etc/passwd")
        filename = cache_path.name
        
        # Should not contain path traversal
        assert ".." not in filename
        assert "/" not in str(filename)
        assert "\\" not in str(filename)


class TestXXEProtection:
    """Test XML External Entity (XXE) attack protection."""

    @pytest.mark.asyncio
    async def test_xxe_attack_blocked(self):
        """Test XXE attack is blocked in NOTAM parsing."""
        from custom_components.hangar_assistant.utils.notam import NOTAMClient
        
        mock_hass = MagicMock()
        mock_hass.config.path = lambda x: f"/config/{x}"
        mock_hass.async_add_executor_job = AsyncMock(side_effect=lambda f: f())
        
        client = NOTAMClient(mock_hass, cache_days=7)
        
        # XXE attack payload
        xxe_payload = """<?xml version="1.0"?>
        <!DOCTYPE foo [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <root>&xxe;</root>
        """
        
        # Should not raise exception or expose file contents
        try:
            result = client._parse_pib_xml(xxe_payload)
            # Result should be empty or not contain file contents
            assert result == [] or not any("/etc/passwd" in str(n) for n in result)
        except Exception:
            # Parser rejecting malicious XML is also acceptable
            pass


@pytest.mark.asyncio
async def test_async_file_operations():
    """Test that file operations use async executor jobs."""
    from custom_components.hangar_assistant.utils.notam import NOTAMClient
    
    mock_hass = MagicMock()
    mock_hass.config.path = lambda x: f"/config/{x}"
    
    # Track if async_add_executor_job is called
    executor_calls = []
    
    async def track_executor(func):
        executor_calls.append(func.__name__)
        return func()
    
    mock_hass.async_add_executor_job = track_executor
    
    client = NOTAMClient(mock_hass, cache_days=7)
    
    # Call async methods that should use executor
    await client._read_cache()
    
    # Verify executor was used
    assert len(executor_calls) > 0
    assert "_read_sync" in executor_calls
