"""Q-code parser for NOTAM criticality and category extraction.

Parses ICAO Q-codes from NOTAMs to determine:
1. Criticality level (CRITICAL, HIGH, MEDIUM, LOW)
2. Human-readable category
3. Subject area (runway, navigation, airspace, etc.)

Q-code format: QXXXX/X/XXX/XX/X/XXX/XXX
- First 5 chars indicate subject (e.g., QMRLC = runway closure)
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)


class NOTAMCriticality(Enum):
    """NOTAM criticality levels."""
    CRITICAL = "critical"  # Immediate impact on operations (runway closures, airspace closures)
    HIGH = "high"          # Significant impact (nav aid failures, restricted areas)
    MEDIUM = "medium"      # Moderate impact (lighting issues, partial restrictions)
    LOW = "low"            # Informational (construction, exercises, minor changes)


# Q-code subject mapping (first 5 characters)
# Format: code -> (category, criticality, description)
Q_CODE_SUBJECTS = {
    # Runway/Aerodrome - CRITICAL
    "QMRLC": ("AERODROME", NOTAMCriticality.CRITICAL, "Runway closed"),
    "QMRXX": ("AERODROME", NOTAMCriticality.CRITICAL, "Runway unusable"),
    "QMTXX": ("AERODROME", NOTAMCriticality.CRITICAL, "Taxiway closed"),
    "QMPXX": ("AERODROME", NOTAMCriticality.CRITICAL, "Apron closed"),
    "QMAXX": ("AERODROME", NOTAMCriticality.CRITICAL, "Movement area closed"),
    "QFAXX": ("AERODROME", NOTAMCriticality.CRITICAL, "Aerodrome closed"),
    
    # Navigation - HIGH
    "QNVAS": ("NAVIGATION", NOTAMCriticality.HIGH, "VOR out of service"),
    "QNDAS": ("NAVIGATION", NOTAMCriticality.HIGH, "DME out of service"),
    "QNNAS": ("NAVIGATION", NOTAMCriticality.HIGH, "NDB out of service"),
    "QNIXX": ("NAVIGATION", NOTAMCriticality.HIGH, "ILS out of service"),
    "QNGXX": ("NAVIGATION", NOTAMCriticality.HIGH, "GNSS interference"),
    "QNMXX": ("NAVIGATION", NOTAMCriticality.HIGH, "Marker beacon u/s"),
    
    # Airspace - HIGH
    "QRTCA": ("AIRSPACE", NOTAMCriticality.HIGH, "Temporary restricted area"),
    "QRDCA": ("AIRSPACE", NOTAMCriticality.HIGH, "Danger area active"),
    "QRPCA": ("AIRSPACE", NOTAMCriticality.HIGH, "Prohibited area established"),
    "QRRCA": ("AIRSPACE", NOTAMCriticality.HIGH, "Restricted area active"),
    "QRAXX": ("AIRSPACE", NOTAMCriticality.HIGH, "Airspace reservation"),
    
    # Lighting - MEDIUM
    "QMALS": ("AERODROME", NOTAMCriticality.MEDIUM, "Approach lighting out of service"),
    "QMRLS": ("AERODROME", NOTAMCriticality.MEDIUM, "Runway lighting out of service"),
    "QMTLS": ("AERODROME", NOTAMCriticality.MEDIUM, "Taxiway lighting out of service"),
    "QMPLS": ("AERODROME", NOTAMCriticality.MEDIUM, "Apron lighting out of service"),
    
    # Obstacles - MEDIUM
    "QOBXX": ("OBSTACLES", NOTAMCriticality.MEDIUM, "Obstacle erected"),
    "QOBCE": ("OBSTACLES", NOTAMCriticality.LOW, "Obstacle erected - lights not checked"),
    "QOLXX": ("OBSTACLES", NOTAMCriticality.MEDIUM, "Obstacle lighting changed"),
    
    # Services - MEDIUM
    "QFAXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Aerodrome services"),
    "QFBXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Friction measurement"),
    "QFCXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Clearance delivery"),
    "QFFXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Fire category"),
    "QFGXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Ground services"),
    "QFHXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Helicopter operations"),
    "QFJXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Ground services"),
    "QFQXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Traffic services"),
    "QFTXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Tower services"),
    "QFUXX": ("SERVICES", NOTAMCriticality.MEDIUM, "UAV operations"),
    "QFWXX": ("SERVICES", NOTAMCriticality.MEDIUM, "Weather services"),
    
    # Communications - MEDIUM
    "QCAXX": ("COMMUNICATIONS", NOTAMCriticality.MEDIUM, "Approach control"),
    "QCCXX": ("COMMUNICATIONS", NOTAMCriticality.MEDIUM, "Area control"),
    "QCTXX": ("COMMUNICATIONS", NOTAMCriticality.MEDIUM, "Tower frequency"),
    "QCGXX": ("COMMUNICATIONS", NOTAMCriticality.MEDIUM, "Ground frequency"),
    "QCFXX": ("COMMUNICATIONS", NOTAMCriticality.MEDIUM, "Flight information"),
    
    # Warnings - LOW to MEDIUM
    "QWXXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Warning"),
    "QWAXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Air display"),
    "QWBXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Aerobatics"),
    "QWCXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Captive balloon"),
    "QWDXX": ("WARNINGS", NOTAMCriticality.LOW, "Demolition"),
    "QWEXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Exercises"),
    "QWFXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Air refuelling"),
    "QWGXX": ("WARNINGS", NOTAMCriticality.LOW, "Glider flying"),
    "QWHXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Blasting"),
    "QWJXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Banner towing"),
    "QWKXX": ("WARNINGS", NOTAMCriticality.LOW, "Kite flying"),
    "QWLXX": ("WARNINGS", NOTAMCriticality.LOW, "Laser display"),
    "QWMXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Missile/rocket/gun firing"),
    "QWPXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Parachute jumping"),
    "QWRXX": ("WARNINGS", NOTAMCriticality.LOW, "Radioactive materials"),
    "QWTXX": ("WARNINGS", NOTAMCriticality.LOW, "Mass movement of aircraft"),
    "QWUXX": ("WARNINGS", NOTAMCriticality.MEDIUM, "Unmanned aircraft"),
    "QWVXX": ("WARNINGS", NOTAMCriticality.LOW, "Formation flight"),
    "QWWXX": ("WARNINGS", NOTAMCriticality.LOW, "Aerotow"),
    "QWZXX": ("WARNINGS", NOTAMCriticality.LOW, "Other aerial activity"),
    
    # Chart changes - LOW
    "QLAXX": ("CHART", NOTAMCriticality.LOW, "Chart changes"),
    "QLBXX": ("CHART", NOTAMCriticality.LOW, "AIP changes"),
    
    # Procedures - MEDIUM
    "QPAXX": ("PROCEDURES", NOTAMCriticality.MEDIUM, "Instrument approach procedure"),
    "QPBXX": ("PROCEDURES", NOTAMCriticality.MEDIUM, "SID changes"),
    "QPCXX": ("PROCEDURES", NOTAMCriticality.MEDIUM, "STAR changes"),
    "QPDXX": ("PROCEDURES", NOTAMCriticality.MEDIUM, "Holding procedure"),
    
    # Facilities - MEDIUM
    "QSAXX": ("FACILITIES", NOTAMCriticality.MEDIUM, "Facilities"),
    "QSBXX": ("FACILITIES", NOTAMCriticality.LOW, "Operating hours"),
    
    # Airspace changes - HIGH
    "QRRXX": ("AIRSPACE", NOTAMCriticality.HIGH, "Airspace restriction"),
}


def parse_qcode(q_code: Optional[str]) -> Dict[str, Any]:
    """Parse a Q-code and return criticality and category information.
    
    Args:
        q_code: ICAO Q-code string (e.g., "QMRLC" or full "QMRLC/A/IV/BO/W/000/999")
    
    Returns:
        Dictionary containing:
        - category: Category string (e.g., "AERODROME")
        - criticality: NOTAMCriticality enum value
        - description: Human-readable description
        - parsed: Whether Q-code was successfully parsed
        - raw_qcode: Original Q-code string
    """
    if not q_code or q_code == "":
        return {
            "category": "UNKNOWN",
            "criticality": NOTAMCriticality.LOW,
            "description": "No Q-code provided",
            "parsed": False,
            "raw_qcode": q_code  # Return exact value (None or empty string)
        }
    
    # Extract first 5 characters (subject code)
    subject_code = q_code[:5].upper()
    
    # Try exact match first
    if subject_code in Q_CODE_SUBJECTS:
        category, criticality, description = Q_CODE_SUBJECTS[subject_code]
        return {
            "category": category,
            "criticality": criticality,
            "description": description,
            "parsed": True,
            "raw_qcode": q_code
        }
    
    # Try wildcard match (e.g., QMRxx matches QMRXX)
    wildcard_code = subject_code[:3] + "XX"
    if wildcard_code in Q_CODE_SUBJECTS:
        category, criticality, description = Q_CODE_SUBJECTS[wildcard_code]
        return {
            "category": category,
            "criticality": criticality,
            "description": description,
            "parsed": True,
            "raw_qcode": q_code
        }
    
    # Try broader category match (first 2 chars)
    category_code = subject_code[:2]
    category_map = {
        "QM": ("AERODROME", NOTAMCriticality.MEDIUM),
        "QN": ("NAVIGATION", NOTAMCriticality.HIGH),
        "QR": ("AIRSPACE", NOTAMCriticality.HIGH),
        "QO": ("OBSTACLES", NOTAMCriticality.MEDIUM),
        "QF": ("SERVICES", NOTAMCriticality.MEDIUM),
        "QC": ("COMMUNICATIONS", NOTAMCriticality.MEDIUM),
        "QW": ("WARNINGS", NOTAMCriticality.LOW),
        "QL": ("CHART", NOTAMCriticality.LOW),
        "QP": ("PROCEDURES", NOTAMCriticality.MEDIUM),
        "QS": ("FACILITIES", NOTAMCriticality.MEDIUM),
    }
    
    if category_code in category_map:
        category, criticality = category_map[category_code]
        return {
            "category": category,
            "criticality": criticality,
            "description": f"{category} related",
            "parsed": True,
            "raw_qcode": q_code
        }
    
    # Unknown Q-code - default to LOW criticality
    _LOGGER.debug("Unknown Q-code: %s", q_code)
    return {
        "category": "UNKNOWN",
        "criticality": NOTAMCriticality.LOW,
        "description": "Unknown NOTAM type",
        "parsed": False,
        "raw_qcode": q_code
    }


def get_criticality_emoji(criticality: NOTAMCriticality) -> str:
    """Get emoji indicator for criticality level.
    
    Args:
        criticality: NOTAMCriticality enum value
    
    Returns:
        Emoji string for display
    """
    emoji_map = {
        NOTAMCriticality.CRITICAL: "🔴",
        NOTAMCriticality.HIGH: "🟠",
        NOTAMCriticality.MEDIUM: "🟡",
        NOTAMCriticality.LOW: "⚪",
    }
    return emoji_map.get(criticality, "⚪")


def filter_notams_by_criticality(
    notams: list[Dict[str, Any]], 
    min_criticality: NOTAMCriticality = NOTAMCriticality.LOW
) -> list[Dict[str, Any]]:
    """Filter NOTAMs by minimum criticality level.
    
    Args:
        notams: List of NOTAM dictionaries with 'q_code' field
        min_criticality: Minimum criticality level to include
    
    Returns:
        Filtered list of NOTAMs with parsed Q-code data added
    """
    criticality_order = {
        NOTAMCriticality.CRITICAL: 4,
        NOTAMCriticality.HIGH: 3,
        NOTAMCriticality.MEDIUM: 2,
        NOTAMCriticality.LOW: 1,
    }
    
    min_level = criticality_order[min_criticality]
    filtered = []
    
    for notam in notams:
        q_data = parse_qcode(notam.get("q_code"))
        notam_level = criticality_order[q_data["criticality"]]
        
        if notam_level >= min_level:
            # Add parsed data to NOTAM
            notam["parsed_qcode"] = q_data
            filtered.append(notam)
    
    return filtered


def sort_notams_by_criticality(notams: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Sort NOTAMs by criticality (highest first).
    
    Args:
        notams: List of NOTAM dictionaries with 'q_code' field
    
    Returns:
        Sorted list with parsed Q-code data
    """
    criticality_order = {
        NOTAMCriticality.CRITICAL: 4,
        NOTAMCriticality.HIGH: 3,
        NOTAMCriticality.MEDIUM: 2,
        NOTAMCriticality.LOW: 1,
    }
    
    # Parse Q-codes and add to NOTAMs
    for notam in notams:
        if "parsed_qcode" not in notam:
            notam["parsed_qcode"] = parse_qcode(notam.get("q_code"))
    
    # Sort by criticality (highest first)
    return sorted(
        notams,
        key=lambda n: criticality_order[n["parsed_qcode"]["criticality"]],
        reverse=True
    )
