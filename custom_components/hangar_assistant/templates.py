"""Quick start templates for common aviation setup scenarios.

Templates provide pre-configured setups for typical use cases, reducing
setup time and ensuring best practices are followed.
"""
from typing import Dict, List, Any


# Aircraft performance templates with realistic defaults
AIRCRAFT_TEMPLATES = {
    "cessna_172": {
        "name": "Cessna 172 Skyhawk",
        "mtow_kg": 1157,
        "empty_weight_kg": 743,
        "min_runway_m": 500,
        "cruise_speed_kts": 105,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 35,
        "fuel_capacity_l": 155,
        "description": "Most popular training aircraft worldwide",
    },
    "piper_pa28": {
        "name": "Piper PA-28 Cherokee",
        "mtow_kg": 1111,
        "empty_weight_kg": 612,
        "min_runway_m": 480,
        "cruise_speed_kts": 110,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 38,
        "fuel_capacity_l": 189,
        "description": "Popular training and touring aircraft",
    },
    "diamond_da40": {
        "name": "Diamond DA40",
        "mtow_kg": 1150,
        "empty_weight_kg": 750,
        "min_runway_m": 400,
        "cruise_speed_kts": 130,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 28,
        "fuel_capacity_l": 155,
        "description": "Modern composite aircraft with excellent efficiency",
    },
    "cirrus_sr20": {
        "name": "Cirrus SR20",
        "mtow_kg": 1497,
        "empty_weight_kg": 953,
        "min_runway_m": 533,
        "cruise_speed_kts": 155,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 50,
        "fuel_capacity_l": 227,
        "description": "High-performance touring aircraft with parachute system",
    },
    "robin_dr400": {
        "name": "Robin DR400",
        "mtow_kg": 1100,
        "empty_weight_kg": 650,
        "min_runway_m": 450,
        "cruise_speed_kts": 115,
        "fuel_type": "AVGAS",
        "fuel_burn_lh": 32,
        "fuel_capacity_l": 150,
        "description": "Popular European touring aircraft",
    },
    "glider_generic": {
        "name": "Glider (Generic)",
        "mtow_kg": 600,
        "empty_weight_kg": 350,
        "min_runway_m": 300,
        "cruise_speed_kts": 60,
        "fuel_type": "NONE",
        "fuel_burn_lh": 0,
        "fuel_capacity_l": 0,
        "description": "Sailplane - no fuel required",
    },
    "tecnam_p2008": {
        "name": "Tecnam P2008",
        "mtow_kg": 600,
        "empty_weight_kg": 350,
        "min_runway_m": 250,
        "cruise_speed_kts": 105,
        "fuel_type": "MOGAS",
        "fuel_burn_lh": 18,
        "fuel_capacity_l": 100,
        "description": "Modern light sport aircraft",
    },
}


# Complete setup templates for common scenarios
QUICK_START_TEMPLATES = {
    "uk_ppl_single": {
        "name": "UK PPL Single Aircraft",
        "description": "Single piston aircraft at UK airfield",
        "estimated_time": "10 minutes",
        "includes": [
            "1 airfield (UK ICAO code)",
            "1 aircraft (Cessna 172 defaults)",
            "CheckWX integration",
            "NOTAM service",
            "Glass Cockpit dashboard",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx"],
        "aircraft_template": "cessna_172",
    },
    
    "us_sport_pilot": {
        "name": "US Sport Pilot",
        "description": "Light Sport Aircraft setup",
        "estimated_time": "12 minutes",
        "includes": [
            "1 airfield (US ICAO code)",
            "1 LSA aircraft",
            "CheckWX integration",
            "OpenWeatherMap",
            "Glass Cockpit dashboard",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx", "openweathermap"],
        "aircraft_template": "tecnam_p2008",
    },
    
    "glider_club": {
        "name": "Glider Club",
        "description": "Gliding operations setup",
        "estimated_time": "8 minutes",
        "includes": [
            "1 airfield",
            "1 glider (Generic sailplane)",
            "Thermal forecasting sensors",
            "CheckWX integration",
            "Glass Cockpit dashboard",
        ],
        "default_settings": {
            "unit_preference": "si",  # Gliders often use metric
            "language": "en",
        },
        "recommended_apis": ["checkwx", "openweathermap"],
        "aircraft_template": "glider_generic",
    },
    
    "flight_school": {
        "name": "Flight School",
        "description": "Multi-aircraft training environment",
        "estimated_time": "20 minutes",
        "includes": [
            "2 airfields",
            "3 aircraft (training fleet)",
            "CheckWX integration",
            "Fuel cost tracking",
            "Multi-aircraft dashboard",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx"],
        "aircraft_templates": ["cessna_172", "piper_pa28", "cessna_172"],
        "multi_aircraft": True,
    },
    
    "uk_touring": {
        "name": "UK Touring Pilot",
        "description": "Cross-country flying setup",
        "estimated_time": "12 minutes",
        "includes": [
            "3 airfields (home + favorites)",
            "1 touring aircraft",
            "CheckWX integration",
            "NOTAM service",
            "Fuel price tracking",
        ],
        "default_settings": {
            "unit_preference": "aviation",
            "language": "en",
        },
        "recommended_apis": ["checkwx"],
        "aircraft_template": "robin_dr400",
        "multi_airfield": True,
    },
}


def get_aircraft_template(template_id: str) -> Dict[str, Any]:
    """Get aircraft template by ID.
    
    Args:
        template_id: Template identifier (e.g., "cessna_172")
    
    Returns:
        Aircraft template configuration dict
    
    Raises:
        KeyError: If template not found
    """
    if template_id not in AIRCRAFT_TEMPLATES:
        raise KeyError(f"Aircraft template '{template_id}' not found")
    
    return AIRCRAFT_TEMPLATES[template_id].copy()


def get_quick_start_template(template_id: str) -> Dict[str, Any]:
    """Get quick start template by ID.
    
    Args:
        template_id: Template identifier (e.g., "uk_ppl_single")
    
    Returns:
        Quick start template configuration dict
    
    Raises:
        KeyError: If template not found
    """
    if template_id not in QUICK_START_TEMPLATES:
        raise KeyError(f"Quick start template '{template_id}' not found")
    
    return QUICK_START_TEMPLATES[template_id].copy()


def list_aircraft_templates() -> List[Dict[str, Any]]:
    """Get list of all available aircraft templates.
    
    Returns:
        List of aircraft template dicts with metadata
    """
    return [
        {
            "id": template_id,
            **template_data
        }
        for template_id, template_data in AIRCRAFT_TEMPLATES.items()
    ]


def list_quick_start_templates() -> List[Dict[str, Any]]:
    """Get list of all available quick start templates.
    
    Returns:
        List of quick start template dicts with metadata
    """
    return [
        {
            "id": template_id,
            **template_data
        }
        for template_id, template_data in QUICK_START_TEMPLATES.items()
    ]


def apply_aircraft_template(template_id: str, registration: str) -> Dict[str, Any]:
    """Apply aircraft template with user's registration.
    
    Args:
        template_id: Template to apply
        registration: User's aircraft registration
    
    Returns:
        Complete aircraft configuration dict
    """
    template = get_aircraft_template(template_id)
    
    return {
        "reg": registration,
        "type": template["name"],
        "mtow_kg": template["mtow_kg"],
        "empty_weight_kg": template["empty_weight_kg"],
        "min_runway_m": template["min_runway_m"],
        "cruise_speed_kts": template["cruise_speed_kts"],
        "fuel": {
            "type": template["fuel_type"],
            "burn_rate_lh": template["fuel_burn_lh"],
            "tank_capacity_l": template["fuel_capacity_l"],
        },
    }
