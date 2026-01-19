from fpdf import FPDF
import os

class CAP1590BGenerator(FPDF):
    def generate(self, output_path, pilot, aircraft, passengers, flight_details):
        self.add_page()
        self.set_font("Helvetica", 'B', 14)
        self.cell(0, 10, "UK CAA COST SHARING DECLARATION (CAP 1590B)", ln=True, align='C')
        self.set_font("Helvetica", '', 9)
        self.multi_cell(0, 5, "Recreational flight. Safety standards differ from commercial transport.")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.output(output_path)