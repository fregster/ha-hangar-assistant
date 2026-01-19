"""Tests for PDF generator."""
import pytest
from unittest.mock import patch, MagicMock
from custom_components.hangar_assistant.utils.pdf_generator import CAP1590BGenerator

def test_pdf_generation():
    """Test PDF generation calls."""
    generator = CAP1590BGenerator()
    
    pilot = {"name": "Test Pilot", "licence_number": "12345"}
    aircraft = {"reg": "G-TEST"}
    passengers = ["Pax 1"]
    flight = {"id": "123"}
    
    with patch("os.makedirs") as mock_makedirs, \
         patch("fpdf.FPDF.output") as mock_output:
        
        generator.generate(
            output_path="/tmp/test.pdf",
            pilot=pilot,
            aircraft=aircraft,
            passengers=passengers,
            flight_details=flight
        )
        
        mock_makedirs.assert_called_once()
        mock_output.assert_called_once_with("/tmp/test.pdf")
