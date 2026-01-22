"""Security utilities for Hangar Assistant.

Provides sanitization and validation functions to protect against security vulnerabilities.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict


def sanitize_config_for_logging(config: dict) -> dict:
    """Remove sensitive data before logging configuration.
    
    Scrubs API keys, passwords, tokens, and other credentials from config
    dictionaries to prevent exposure in logs.
    
    Args:
        config: Configuration dictionary potentially containing sensitive data
    
    Returns:
        Copy of config with sensitive fields redacted
    
    Example:
        >>> config = {"name": "Airport", "api_key": "secret123"}
        >>> safe = sanitize_config_for_logging(config)
        >>> safe
        {"name": "Airport", "api_key": "***REDACTED***"}
    """
    if not isinstance(config, dict):
        return config
    
    sanitized = config.copy()
    
    # List of sensitive field names (lowercase for case-insensitive matching)
    sensitive_keys = [
        "api_key",
        "password",
        "token",
        "secret",
        "credential",
        "auth",
        "authorization",
        "bearer",
    ]
    
    for key in list(sanitized.keys()):
        # Check if key name contains any sensitive term
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        # Recursively sanitize nested dicts
        elif isinstance(sanitized[key], dict):
            sanitized[key] = sanitize_config_for_logging(sanitized[key])
    
    return sanitized


def sanitize_filename(user_input: str) -> str:
    """Sanitize user input for safe file naming.
    
    Removes all characters except alphanumeric, underscore, and hyphen
    to prevent path traversal attacks and filesystem issues.
    
    Args:
        user_input: Raw user input (airfield name, aircraft reg, etc.)
    
    Returns:
        Sanitized string safe for file paths
    
    Raises:
        ValueError: If input contains no valid characters or is empty
    
    Example:
        >>> sanitize_filename("London/../../etc/passwd")
        'Londonetcpasswd'
        >>> sanitize_filename("G-ABCD")
        'G-ABCD'
    """
    if not user_input:
        raise ValueError("Cannot sanitize empty filename")
    
    # Remove all characters except alphanumeric, underscore, hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', str(user_input))
    
    if not sanitized:
        raise ValueError(f"Invalid input for filename: {user_input}")
    
    # Limit length to prevent filesystem issues (most filesystems support 255)
    return sanitized[:255]


def validate_path_safety(path: Path, base_dir: Path) -> bool:
    """Validate that a path is safe and within expected directory.
    
    Checks that the resolved path is within the base directory and
    doesn't contain suspicious patterns that could indicate path traversal.
    
    Args:
        path: Path to validate
        base_dir: Expected base directory
    
    Returns:
        True if path is safe, False otherwise
    
    Example:
        >>> base = Path("/config/cache")
        >>> safe_path = base / "weather.json"
        >>> validate_path_safety(safe_path, base)
        True
        >>> unsafe_path = Path("/etc/passwd")
        >>> validate_path_safety(unsafe_path, base)
        False
    """
    try:
        # Resolve both paths to absolute
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()
        
        # Check if resolved path is within base directory
        return resolved_path.is_relative_to(resolved_base)
    except (ValueError, OSError):
        # Any error during resolution = unsafe
        return False


def sanitize_entity_id(entity_id: str) -> str:
    """Sanitize entity ID for safe usage in code.
    
    Validates entity ID format and removes potential injection risks.
    
    Args:
        entity_id: Entity ID to sanitize
    
    Returns:
        Sanitized entity ID
    
    Raises:
        ValueError: If entity ID format is invalid
    
    Example:
        >>> sanitize_entity_id("sensor.temperature")
        'sensor.temperature'
        >>> sanitize_entity_id("sensor.temp; DROP TABLE")
        ValueError: Invalid entity ID format
    """
    if not entity_id or not isinstance(entity_id, str):
        raise ValueError("Entity ID must be a non-empty string")
    
    # Entity IDs must follow domain.object_id pattern
    if not re.match(r'^[a-z_]+\.[a-z0-9_]+$', entity_id):
        raise ValueError(f"Invalid entity ID format: {entity_id}")
    
    return entity_id


def sanitize_url(url: str, allowed_schemes: list[str] | None = None) -> str:
    """Sanitize URL to ensure it's safe to use.
    
    Validates URL scheme and structure to prevent SSRF and other attacks.
    
    Args:
        url: URL to sanitize
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
    
    Returns:
        Sanitized URL
    
    Raises:
        ValueError: If URL is invalid or uses disallowed scheme
    
    Example:
        >>> sanitize_url("https://example.com/api")
        'https://example.com/api'
        >>> sanitize_url("file:///etc/passwd")
        ValueError: Disallowed URL scheme: file
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    # Extract scheme (handle both :// and : formats)
    if ':' not in url:
        raise ValueError(f"Invalid URL format: {url}")
    
    scheme = url.split(':')[0].lower()
    
    if scheme not in allowed_schemes:
        raise ValueError(f"Disallowed URL scheme: {scheme}")
    
    # Verify proper format for schemes that use ://
    if scheme in ['http', 'https', 'ftp'] and '://' not in url:
        raise ValueError(f"Invalid URL format for {scheme}: {url}")
    
    # Basic validation - no spaces or control characters
    if any(char in url for char in [' ', '\n', '\r', '\t']):
        raise ValueError("URL contains invalid characters")
    
    return url
