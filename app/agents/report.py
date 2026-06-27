from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.config import Config
from app.agents.state import AgentState
from app.logging_config import logger

class ReportAgent:
    @staticmethod
    def generate_pdf_report(
        filename: str, 
        loc: str, 
        loc_type: str, 
        data: list, 
        prediction: dict, 
        simulation: dict, 
        recs: list
    ) -> str:
        """Generates a styled, publication-grade PDF report using ReportLab."""
        filepath = Config.BASE_DIR / "reports" / filename
        
        doc = SimpleDocTemplate(str(filepath), pagesize=letter,
                                rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
                                
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor('#002B49'),
            spaceAfter=12
        )
        
        h2_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#1E5B84'),
            spaceBefore=15,
            spaceAfter=8
        )
        
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=8
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            textColor=colors.white,
            fontName='Helvetica-Bold'
        )

        table_cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#333333')
        )
        
        story = []
        
        # Header / Title Block
        story.append(Paragraph(f"AquaMind AI Groundwater Assessment Report", title_style))
        story.append(Paragraph(f"Location: {loc.upper()} ({loc_type.upper()}) | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
        story.append(Spacer(1, 10))
        story.append(Table([['']], colWidths=[504], rowHeights=[2], style=TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#002B49')),
        ])))
        story.append(Spacer(1, 15))
        
        # Section 1: Historical GEC Data Table
        story.append(Paragraph("1. Historical Resource Assessment (GEC)", h2_style))
        if data:
            # Table columns
            headers = [
                Paragraph("Year", table_header_style), 
                Paragraph("Total Recharge (ham)", table_header_style), 
                Paragraph("Extractable (ham)", table_header_style), 
                Paragraph("Extraction (ham)", table_header_style), 
                Paragraph("Stage (%)", table_header_style), 
                Paragraph("Category", table_header_style)
            ]
            
            table_data = [headers]
            for r in data[-4:]: # Show last 4 assessment years
                table_data.append([
                    Paragraph(str(r["year"]), table_cell_style),
                    Paragraph(f"{r['total_recharge']:.1f}", table_cell_style),
                    Paragraph(f"{r['annual_extractable']:.1f}", table_cell_style),
                    Paragraph(f"{r['total_extraction']:.1f}", table_cell_style),
                    Paragraph(f"{r['stage_of_extraction']:.1f}%", table_cell_style),
                    Paragraph(str(r["category"]), table_cell_style),
                ])
                
            t = Table(table_data, colWidths=[70, 90, 85, 85, 80, 94])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E5B84')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')]),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("No GEC baseline dataset available for this area.", body_style))
            
        story.append(Spacer(1, 15))
        
        # Section 2: Scenario Simulation & Trend Predictions
        story.append(Paragraph("2. Groundwater Stress Forecast & Simulations", h2_style))
        
        if prediction and prediction.get("status") == "success":
            p_text = (
                f"Statistical trend analysis projects a baseline stage of <b>{prediction['forecast_stages'][-1]:.2f}%</b> "
                f"by 2030, putting the region in the <b>{prediction['forecast_categories'][-1].upper()}</b> category. "
                f"The historical extraction growth rate is measured at <b>{prediction['historical_slope_extraction']:+.2f} ham/year</b>."
            )
            story.append(Paragraph(p_text, body_style))
            story.append(Spacer(1, 10))
            
        if simulation and simulation.get("status") == "success":
            sim_text = (
                f"<b>Simulation Stress Test Result:</b> In a scenario of extraction change of <b>{simulation['extraction_change_pct']:+.1f}%</b> "
                f"and rainfall variation of <b>{simulation['rainfall_change_pct']:+.1f}%</b>, the stage of extraction shifts to "
                f"<b>{simulation['simulated_stage']:.2f}%</b> (Resource Category: <b>{simulation['simulated_category'].upper()}</b>)."
            )
            story.append(Paragraph(sim_text, body_style))
            story.append(Spacer(1, 10))
            
        if not prediction and not simulation:
            story.append(Paragraph("No prediction or simulation metrics were run for this session.", body_style))
            
        story.append(Spacer(1, 15))
        
        # Section 3: Recommendations
        story.append(Paragraph("3. Recommendations & Policy Action Plans", h2_style))
        if recs:
            for idx, r in enumerate(recs):
                r_text = f"<b>{idx+1}. {r['title']} [{r['category']}]</b><br/>" \
                         f"<i>Why:</i> {r['why']}<br/>" \
                         f"<i>Evidence:</i> {r['evidence']}<br/>" \
                         f"<i>Impact:</i> {r['impact']}"
                story.append(Paragraph(r_text, body_style))
                story.append(Spacer(1, 8))
        else:
            story.append(Paragraph("Standard conservation guidelines apply. Focus on rainwater harvesting and flood irrigation reduction.", body_style))

        # Build Document
        doc.build(story)
        logger.info(f"Report PDF compiled successfully at: {filepath}")
        return str(filepath)

    @staticmethod
    def process(state: AgentState) -> dict:
        """Report node that triggers the PDF builder for the current session data."""
        loc = state.get("resolved_location")
        loc_type = state.get("resolved_location_type")
        data = state.get("context_data", [])
        prediction = state.get("context_prediction")
        simulation = state.get("context_simulation")
        recs = state.get("context_recommendations", [])
        session_id = state.get("session_id", "default")
        
        logger.info(f"ReportAgent processing report requested for: {loc}")
        
        if not loc:
            logger.warning("No location specified. Skipping PDF report compilation.")
            return {"current_node": "synthesize"}
            
        filename = f"report_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        try:
            pdf_path = ReportAgent.generate_pdf_report(
                filename, loc, loc_type or "district", data, prediction, simulation, recs
            )
        except Exception as e:
            logger.error(f"ReportAgent PDF compilation failed: {e}", exc_info=True)
            pdf_path = None
            
        history = list(state.get("routing_history", []))
        history.append("report")

        return {
            "pdf_report_path": pdf_path,
            "routing_history": history,
            "current_node": "synthesize"
        }
