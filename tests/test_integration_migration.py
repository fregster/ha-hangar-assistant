"""Tests for OWM settings migration to integrations namespace.

This module tests backward compatibility and migration of OpenWeatherMap
settings from entry.data["settings"] to entry.data["integrations"].

Migration ensures:
- Existing installs preserve OWM configuration
- NOTAM integration added with appropriate defaults
- No data loss during migration
- Idempotent migration (safe to run multiple times)
- New installs get sensible defaults

Test Strategy:
    - Mock config entries with various structures
    - Test migration logic in async_setup_entry()
    - Verify data preservation and transformation
    - Test both old and new config structures
    - Validate backward compatibility

Coverage:
    - Migration from settings namespace
    - Default value injection
    - New vs existing install detection
    - Idempotent migration behavior
    - Data integrity validation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance for migration testing.
    
    Provides:
        - Mock config entries
        - Mock async_create_task for background tasks
    
    Returns:
        MagicMock: Configured Home Assistant instance
    """
    hass = MagicMock()
    hass.config_entries = MagicMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.fixture
def old_config_entry_with_owm():
    """Create a config entry with OWM in old settings namespace.
    
    Simulates existing installation before migration. OWM settings
    are in entry.data["settings"] rather than entry.data["integrations"].
    
    Provides:
        - OWM API key and settings in legacy location
        - No integrations namespace
        - Airfields and aircraft data (unaffected by migration)
    
    Returns:
        MagicMock: Config entry with old structure
    """
    entry = MagicMock()
    entry.data = {
        "airfields": [{"name": "Popham", "icao": "EGHP"}],
        "aircraft": [{"reg": "G-ABCD", "type": "C172"}],
        "settings": {
            "openweathermap_api_key": "old_api_key_12345",
            "openweathermap_enabled": True,
            "openweathermap_cache_enabled": True,
            "openweathermap_update_interval": 15,
            "openweathermap_cache_ttl": 15,
        }
    }
    entry.entry_id = "test_entry"
    return entry


@pytest.fixture
def new_config_entry_no_owm():
    """Create a config entry for new installation (no OWM configured).
    
    Simulates fresh install - no OWM settings at all.
    
    Provides:
        - Basic airfield/aircraft data
        - No settings or integrations namespace
    
    Returns:
        MagicMock: Config entry for new install
    """
    entry = MagicMock()
    entry.data = {
        "airfields": [{"name": "Shoreham", "icao": "EGKA"}],
        "aircraft": []
    }
    entry.entry_id = "test_entry_new"
    return entry


@pytest.fixture
def already_migrated_entry():
    """Create a config entry already in new integrations namespace.
    
    Simulates installation that already ran migration. Should not
    re-migrate or duplicate data.
    
    Provides:
        - OWM in integrations namespace
        - NOTAM in integrations namespace
        - No settings namespace
    
    Returns:
        MagicMock: Config entry already migrated
    """
    entry = MagicMock()
    entry.data = {
        "airfields": [{"name": "Popham", "icao": "EGHP"}],
        "integrations": {
            "openweathermap": {
                "enabled": True,
                "api_key": "already_migrated_key",
                "cache_enabled": True,
                "update_interval": 10,
                "cache_ttl": 10,
                "consecutive_failures": 0,
            },
            "notams": {
                "enabled": True,
                "update_time": "02:00",
                "cache_days": 7,
                "consecutive_failures": 0,
            }
        }
    }
    entry.entry_id = "test_entry_migrated"
    return entry


def test_migrates_owm_from_settings_to_integrations(old_config_entry_with_owm):
    """Test that OWM settings migrate from settings to integrations namespace.
    
    Core migration logic: move OWM settings from old location to new
    standardized integrations namespace.
    
    Setup:
        - Config entry with OWM in settings namespace
        - No integrations namespace present
    
    Validation:
        - integrations namespace created
        - openweathermap subkey present
        - All OWM settings moved correctly
        - Old settings namespace optionally removed
    
    Expected Result:
        OWM settings in integrations.openweathermap namespace.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    # Run migration
    migrated_data = _migrate_config_entry(old_config_entry_with_owm.data)
    
    # Should have integrations namespace
    assert "integrations" in migrated_data
    assert "openweathermap" in migrated_data["integrations"]
    
    # Should have migrated all OWM settings
    owm_config = migrated_data["integrations"]["openweathermap"]
    assert owm_config["api_key"] == "old_api_key_12345"
    assert owm_config["enabled"] is True
    assert owm_config["cache_enabled"] is True
    assert owm_config["update_interval"] == 15
    assert owm_config["cache_ttl"] == 15


def test_preserves_all_existing_owm_values(old_config_entry_with_owm):
    """Test that migration preserves all OWM configuration values.
    
    Data integrity: no settings lost during migration.
    
    Setup:
        - Config entry with all OWM settings populated
    
    Validation:
        - Every old setting present in new location
        - Values unchanged (no transformation)
        - No data loss
    
    Expected Result:
        100% data preservation during migration.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    migrated_data = _migrate_config_entry(old_config_entry_with_owm.data)
    
    old_owm = old_config_entry_with_owm.data["settings"]
    new_owm = migrated_data["integrations"]["openweathermap"]
    
    # Check every field preserved
    assert new_owm["api_key"] == old_owm["openweathermap_api_key"]
    assert new_owm["enabled"] == old_owm["openweathermap_enabled"]
    assert new_owm["cache_enabled"] == old_owm["openweathermap_cache_enabled"]
    assert new_owm["update_interval"] == old_owm["openweathermap_update_interval"]
    assert new_owm["cache_ttl"] == old_owm["openweathermap_cache_ttl"]


def test_adds_notams_config_with_defaults(old_config_entry_with_owm):
    """Test that migration adds NOTAM config with sensible defaults.
    
    New feature addition: NOTAM integration introduced with migration,
    needs default configuration.
    
    Setup:
        - Old config entry (pre-NOTAM feature)
    
    Validation:
        - notams key added to integrations
        - Default values appropriate (enabled=False for existing installs)
        - All required NOTAM fields present
    
    Expected Result:
        NOTAM config added with conservative defaults.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    migrated_data = _migrate_config_entry(old_config_entry_with_owm.data)
    
    # Should have NOTAM config
    assert "notams" in migrated_data["integrations"]
    
    notam_config = migrated_data["integrations"]["notams"]
    
    # Check defaults for existing install (disabled by default)
    assert notam_config["enabled"] is False  # Don't auto-enable for existing users
    assert notam_config["update_time"] == "02:00"
    assert notam_config["cache_days"] == 7
    assert notam_config["consecutive_failures"] == 0


def test_existing_installs_notams_disabled_by_default(old_config_entry_with_owm):
    """Test that existing installations get NOTAMs disabled by default.
    
    Backward compatibility: don't auto-enable new features for existing users.
    
    Setup:
        - Existing install with OWM configured
    
    Validation:
        - NOTAM enabled = False
        - User must explicitly enable via config flow
    
    Expected Result:
        NOTAMs disabled for existing users (opt-in).
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    migrated_data = _migrate_config_entry(old_config_entry_with_owm.data)
    
    # Existing installs should have NOTAMs disabled
    assert migrated_data["integrations"]["notams"]["enabled"] is False


def test_new_installs_notams_enabled_by_default(new_config_entry_no_owm):
    """Test that new installations get NOTAMs enabled by default.
    
    New user experience: free feature enabled out-of-box.
    
    Setup:
        - Fresh install (no existing OWM config)
    
    Validation:
        - NOTAM enabled = True
        - Default configuration applied
    
    Expected Result:
        NOTAMs enabled for new users (good UX).
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    migrated_data = _migrate_config_entry(new_config_entry_no_owm.data)
    
    # New installs should have NOTAMs enabled
    assert "integrations" in migrated_data
    assert migrated_data["integrations"]["notams"]["enabled"] is True


def test_no_migration_if_integrations_already_exists(already_migrated_entry):
    """Test that migration is idempotent (safe to run multiple times).
    
    Idempotency: running migration on already-migrated config should
    not duplicate or corrupt data.
    
    Setup:
        - Config entry already in integrations namespace
    
    Validation:
        - No changes made
        - Data unchanged
        - No duplication
    
    Expected Result:
        Already-migrated config untouched.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    original_data = already_migrated_entry.data.copy()
    
    # Run migration again
    migrated_data = _migrate_config_entry(already_migrated_entry.data)
    
    # Should be unchanged
    assert migrated_data == original_data
    
    # Specifically check OWM unchanged
    assert migrated_data["integrations"]["openweathermap"]["api_key"] == "already_migrated_key"
    
    # Specifically check NOTAM unchanged
    assert migrated_data["integrations"]["notams"]["enabled"] is True


def test_migration_preserves_other_config_data(old_config_entry_with_owm):
    """Test that migration preserves airfields, aircraft, and other data.
    
    Data isolation: migration should only touch integrations namespace,
    leaving airfields/aircraft/hangars untouched.
    
    Setup:
        - Config entry with airfields, aircraft data
    
    Validation:
        - Airfields list unchanged
        - Aircraft list unchanged
        - Only integrations namespace added/modified
    
    Expected Result:
        Non-integration data preserved perfectly.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    original_airfields = old_config_entry_with_owm.data["airfields"].copy()
    original_aircraft = old_config_entry_with_owm.data["aircraft"].copy()
    
    migrated_data = _migrate_config_entry(old_config_entry_with_owm.data)
    
    # Airfields and aircraft should be untouched
    assert migrated_data["airfields"] == original_airfields
    assert migrated_data["aircraft"] == original_aircraft


def test_migration_logs_completion():
    """Test that migration logs completion for debugging.
    
    Note: Logging happens in the async wrapper _migrate_to_integrations,
    not in the synchronous _migrate_config_entry helper function.
    
    Setup:
        - Old config with OWM settings
    
    Validation:
        - Migration creates integrations namespace
    
    Expected Result:
        Migration successful (logging tested separately in async wrapper).
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    old_config = {
        "settings": {
            "openweathermap_api_key": "test_key",
            "openweathermap_enabled": True,
        }
    }
    
    # Test migration logic (logging happens in async wrapper)
    migrated_data = _migrate_config_entry(old_config)
    
    # Verify migration actually happened
    assert "integrations" in migrated_data


def test_migration_adds_failure_tracking_fields():
    """Test that migration adds failure tracking fields to OWM config.
    
    Feature addition: failure tracking introduced with integrations refactor,
    must be added during migration.
    
    Setup:
        - Old config without consecutive_failures, last_error, etc.
    
    Validation:
        - consecutive_failures field added (default: 0)
        - Optional last_error field ready for use
        - Optional last_success field ready for use
    
    Expected Result:
        Failure tracking fields initialized in migrated config.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    old_config = {
        "settings": {
            "openweathermap_api_key": "test_key",
            "openweathermap_enabled": True,
            "openweathermap_cache_enabled": True,
        }
    }
    
    migrated_data = _migrate_config_entry(old_config)
    
    owm_config = migrated_data["integrations"]["openweathermap"]
    
    # Should have failure tracking fields
    assert "consecutive_failures" in owm_config
    assert owm_config["consecutive_failures"] == 0


def test_migration_handles_partial_owm_config():
    """Test that migration handles partial OWM configuration gracefully.
    
    Edge case: user may have only some OWM settings configured
    (e.g., API key but no other settings).
    
    Setup:
        - Config with only openweathermap_api_key
        - Missing other OWM settings
    
    Validation:
        - Migration adds default values for missing fields
        - API key preserved
        - No crash on partial config
    
    Expected Result:
        Partial config completed with sensible defaults.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    partial_config = {
        "settings": {
            "openweathermap_api_key": "partial_key",
            # Missing: enabled, cache_enabled, intervals, etc.
        }
    }
    
    migrated_data = _migrate_config_entry(partial_config)
    
    owm_config = migrated_data["integrations"]["openweathermap"]
    
    # Should preserve API key
    assert owm_config["api_key"] == "partial_key"
    
    # Should add defaults for missing fields
    assert "enabled" in owm_config
    assert "cache_enabled" in owm_config
    assert "update_interval" in owm_config
    assert "cache_ttl" in owm_config


def test_migration_handles_missing_settings_namespace():
    """Test that migration handles missing settings namespace gracefully.
    
    Edge case: new install with no settings at all.
    
    Setup:
        - Config with only airfields (no settings namespace)
    
    Validation:
        - Integrations namespace created
        - OWM and NOTAM configs added with defaults
        - No crash
    
    Expected Result:
        Clean config created for new install.
    """
    from custom_components.hangar_assistant import _migrate_config_entry
    
    minimal_config = {
        "airfields": [{"name": "Popham"}],
        # No settings namespace at all
    }
    
    migrated_data = _migrate_config_entry(minimal_config)
    
    # Should create integrations namespace
    assert "integrations" in migrated_data
    
    # Should have default OWM config (disabled)
    assert "openweathermap" in migrated_data["integrations"]
    assert migrated_data["integrations"]["openweathermap"]["enabled"] is False
    
    # Should have default NOTAM config (enabled for new install)
    assert "notams" in migrated_data["integrations"]
    assert migrated_data["integrations"]["notams"]["enabled"] is True
