"""Tests for Q-code parser utility."""
import pytest
from custom_components.hangar_assistant.utils.qcode_parser import (
    parse_qcode,
    get_criticality_emoji,
    filter_notams_by_criticality,
    sort_notams_by_criticality,
    NOTAMCriticality,
)


class TestQCodeParser:
    """Test Q-code parsing functionality."""
    
    def test_parse_known_critical_qcode(self):
        """Test parsing a known CRITICAL Q-code."""
        result = parse_qcode("QMRLC")
        
        assert result["parsed"] is True
        assert result["category"] == "AERODROME"
        assert result["criticality"] == NOTAMCriticality.CRITICAL
        assert "runway closed" in result["description"].lower()
        assert result["raw_qcode"] == "QMRLC"
    
    def test_parse_known_high_qcode(self):
        """Test parsing a known HIGH Q-code."""
        result = parse_qcode("QNVAS")
        
        assert result["parsed"] is True
        assert result["category"] == "NAVIGATION"
        assert result["criticality"] == NOTAMCriticality.HIGH
        assert "vor" in result["description"].lower()
        assert result["raw_qcode"] == "QNVAS"
    
    def test_parse_known_medium_qcode(self):
        """Test parsing a known MEDIUM Q-code."""
        result = parse_qcode("QMALS")
        
        assert result["parsed"] is True
        assert result["category"] == "AERODROME"
        assert result["criticality"] == NOTAMCriticality.MEDIUM
        assert "approach lighting" in result["description"].lower()
        assert result["raw_qcode"] == "QMALS"
    
    def test_parse_wildcard_qcode(self):
        """Test parsing a wildcard Q-code pattern (QMRxx)."""
        result = parse_qcode("QMRAA")  # Should match QMRxx pattern
        
        assert result["parsed"] is True
        assert result["category"] == "AERODROME"
        # Should use wildcard criticality
        assert result["criticality"] in [NOTAMCriticality.CRITICAL, NOTAMCriticality.HIGH]
    
    def test_parse_category_fallback(self):
        """Test category fallback for unknown specific Q-code."""
        result = parse_qcode("QMZZY")  # Unknown specific code, should fallback to QM category
        
        assert result["parsed"] is True
        assert result["category"] == "AERODROME"  # QM = AERODROME
        assert result["criticality"] == NOTAMCriticality.MEDIUM  # Default for category
    
    def test_parse_unknown_qcode(self):
        """Test parsing completely unknown Q-code."""
        result = parse_qcode("QZZZZ")  # Unknown category
        
        assert result["parsed"] is False
        assert result["category"] == "UNKNOWN"
        assert result["criticality"] == NOTAMCriticality.LOW  # Default for unknown
        assert "unknown" in result["description"].lower()
    
    def test_parse_none_qcode(self):
        """Test parsing None Q-code."""
        result = parse_qcode(None)
        
        assert result["parsed"] is False
        assert result["category"] == "UNKNOWN"
        assert result["criticality"] == NOTAMCriticality.LOW
        assert result["raw_qcode"] is None
    
    def test_parse_empty_qcode(self):
        """Test parsing empty string Q-code."""
        result = parse_qcode("")
        
        assert result["parsed"] is False
        assert result["category"] == "UNKNOWN"
        assert result["criticality"] == NOTAMCriticality.LOW
        assert result["raw_qcode"] == ""
    
    def test_get_criticality_emoji_critical(self):
        """Test emoji for CRITICAL criticality."""
        emoji = get_criticality_emoji(NOTAMCriticality.CRITICAL)
        assert emoji == "🔴"
    
    def test_get_criticality_emoji_high(self):
        """Test emoji for HIGH criticality."""
        emoji = get_criticality_emoji(NOTAMCriticality.HIGH)
        assert emoji == "🟠"
    
    def test_get_criticality_emoji_medium(self):
        """Test emoji for MEDIUM criticality."""
        emoji = get_criticality_emoji(NOTAMCriticality.MEDIUM)
        assert emoji == "🟡"
    
    def test_get_criticality_emoji_low(self):
        """Test emoji for LOW criticality."""
        emoji = get_criticality_emoji(NOTAMCriticality.LOW)
        assert emoji == "⚪"
    
    def test_filter_notams_by_criticality(self):
        """Test filtering NOTAMs by minimum criticality."""
        notams = [
            {"id": "A001", "q_code": "QMRLC"},  # CRITICAL
            {"id": "A002", "q_code": "QNVAS"},  # HIGH
            {"id": "A003", "q_code": "QMALS"},  # MEDIUM
            {"id": "A004", "q_code": "QOBCE"},  # LOW
        ]
        
        # Filter for HIGH and above
        filtered = filter_notams_by_criticality(notams, NOTAMCriticality.HIGH)
        
        assert len(filtered) == 2
        assert filtered[0]["id"] == "A001"  # CRITICAL
        assert filtered[1]["id"] == "A002"  # HIGH
        
        # Check that parsed_qcode was added
        assert "parsed_qcode" in filtered[0]
        assert filtered[0]["parsed_qcode"]["criticality"] == NOTAMCriticality.CRITICAL
    
    def test_filter_notams_no_matches(self):
        """Test filtering with no matches."""
        notams = [
            {"id": "A001", "q_code": "QMALS"},  # MEDIUM
            {"id": "A002", "q_code": "QOBCE"},  # LOW
        ]
        
        # Filter for CRITICAL only
        filtered = filter_notams_by_criticality(notams, NOTAMCriticality.CRITICAL)
        
        assert len(filtered) == 0
    
    def test_sort_notams_by_criticality(self):
        """Test sorting NOTAMs by criticality (highest first)."""
        notams = [
            {"id": "A001", "q_code": "QOBCE"},  # LOW
            {"id": "A002", "q_code": "QMALS"},  # MEDIUM
            {"id": "A003", "q_code": "QMRLC"},  # CRITICAL
            {"id": "A004", "q_code": "QNVAS"},  # HIGH
        ]
        
        sorted_notams = sort_notams_by_criticality(notams)
        
        assert len(sorted_notams) == 4
        assert sorted_notams[0]["id"] == "A003"  # CRITICAL first
        assert sorted_notams[1]["id"] == "A004"  # HIGH second
        assert sorted_notams[2]["id"] == "A002"  # MEDIUM third
        assert sorted_notams[3]["id"] == "A001"  # LOW last
        
        # Check criticality order
        assert sorted_notams[0]["parsed_qcode"]["criticality"] == NOTAMCriticality.CRITICAL
        assert sorted_notams[1]["parsed_qcode"]["criticality"] == NOTAMCriticality.HIGH
        assert sorted_notams[2]["parsed_qcode"]["criticality"] == NOTAMCriticality.MEDIUM
        assert sorted_notams[3]["parsed_qcode"]["criticality"] == NOTAMCriticality.LOW
    
    def test_sort_empty_notams(self):
        """Test sorting empty NOTAM list."""
        sorted_notams = sort_notams_by_criticality([])
        assert len(sorted_notams) == 0
    
    def test_qcode_case_insensitivity(self):
        """Test that Q-codes are case-insensitive."""
        result_upper = parse_qcode("QMRLC")
        result_lower = parse_qcode("qmrlc")
        result_mixed = parse_qcode("QmRlC")
        
        assert result_upper["criticality"] == result_lower["criticality"]
        assert result_upper["criticality"] == result_mixed["criticality"]
        assert result_upper["category"] == result_lower["category"]
    
    def test_qcode_specific_categories(self):
        """Test that Q-codes map to correct categories."""
        # QM = AERODROME
        qm_result = parse_qcode("QMRLC")
        assert qm_result["category"] == "AERODROME"
        
        # QN = NAVIGATION
        qn_result = parse_qcode("QNVAS")
        assert qn_result["category"] == "NAVIGATION"
        
        # QR = AIRSPACE
        qr_result = parse_qcode("QRTCA")
        assert qr_result["category"] == "AIRSPACE"
        
        # QO = OBSTACLES
        qo_result = parse_qcode("QOBCE")
        assert qo_result["category"] == "OBSTACLES"
    
    def test_notam_without_qcode(self):
        """Test NOTAM without Q-code field."""
        notams = [
            {"id": "A001", "text": "Runway closed"},  # No q_code field
        ]
        
        sorted_notams = sort_notams_by_criticality(notams)
        
        assert len(sorted_notams) == 1
        assert sorted_notams[0]["parsed_qcode"]["criticality"] == NOTAMCriticality.LOW
        assert sorted_notams[0]["parsed_qcode"]["parsed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
