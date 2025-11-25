"""
Division Report PDF Generator using reportlab
Generates professional PDF reports with DENR official standards
"""
import os
import io
from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas


class DivisionReportPDFGenerator:
    """
    Professional PDF generator for division reports
    """
    
    def __init__(self, buffer, report_data, filters_applied, user_info, watermark=None):
        self.buffer = buffer
        self.report_data = report_data
        self.filters_applied = filters_applied
        self.user_info = user_info
        self.watermark = watermark  # "For Review", "For Compliance", "For Endorsement"
        self.doc = None
        self.styles = None
        self.story = []
        self.reference_number = None
        
        # Logo paths
        self.LOGO1_PATH = os.path.join(settings.BASE_DIR, '../public/assets/document/logo1.png')
        self.LOGO2_PATH = os.path.join(settings.BASE_DIR, '../public/assets/document/logo2.png')
        
    def _get_denr_colors(self):
        """Return standardized DENR color palette"""
        return {
            'denr_blue': colors.HexColor('#0066CC'),  # DENR Blue
            'denr_green': colors.HexColor('#008000'),  # DENR Green
            'earth_brown': colors.HexColor('#8B4513'),  # Earth tone brown
            'earth_chocolate': colors.HexColor('#D2691E'),  # Earth tone chocolate
            'light_green': colors.HexColor('#E7F7E7'),  # Light green fill
            'light_blue': colors.HexColor('#E7F0F7'),  # Light blue fill
            'light_red': colors.HexColor('#FFE7E7'),  # Light red fill
            'border_gray': colors.HexColor('#CCCCCC'),  # Border gray
        }
    
    def _generate_reference_number(self):
        """Generate DENR reference number: EIA-YYYY-MM-DD-####"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        # Use timestamp milliseconds as sequence (simplified - in production use proper sequence tracking)
        sequence = str(int(now.timestamp() * 1000))[-4:]
        return f"EIA-{date_str}-{sequence}"
    
    def _setup_styles(self):
        """Setup professional text styles with DENR color scheme"""
        self.styles = getSampleStyleSheet()
        denr_colors = self._get_denr_colors()
        
        # DENR colors
        self.denr_blue = denr_colors['denr_blue']
        self.denr_green = denr_colors['denr_green']
        self.earth_brown = denr_colors['earth_brown']
        self.earth_chocolate = denr_colors['earth_chocolate']
        self.light_blue = denr_colors['light_blue']
        self.light_green = denr_colors['light_green']
        self.light_red = denr_colors['light_red']
        self.border_gray = denr_colors['border_gray']
        
        # Generate reference number
        self.reference_number = self._generate_reference_number()
        
        # Title style - Arial font
        self.styles.add(ParagraphStyle(
            name='DENRTitle',
            parent=self.styles['Title'],
            fontSize=18,
            textColor=self.denr_blue,
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName='Helvetica-Bold'  # Arial equivalent in ReportLab
        ))
        
        # Subtitle style - Arial font
        self.styles.add(ParagraphStyle(
            name='DENRSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.denr_green,
            alignment=TA_CENTER,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=self.denr_blue,
            spaceAfter=6,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Body text style - Arial font
        self.styles.add(ParagraphStyle(
            name='DENRBody',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica'
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey,
            fontName='Helvetica'
        ))
        
    def _add_header(self):
        """Add official DENR header with logos and agency information"""
        # Try to load logos
        logo1 = None
        logo2 = None
        
        if os.path.exists(self.LOGO1_PATH):
            try:
                logo1 = Image(self.LOGO1_PATH, width=1.2*inch, height=1.2*inch)
            except:
                pass
        
        if os.path.exists(self.LOGO2_PATH):
            try:
                logo2 = Image(self.LOGO2_PATH, width=1.2*inch, height=1.2*inch)
            except:
                pass
        
        # Official DENR header
        header_text = """
        <para align='center'>
            <font name='Helvetica-Bold' size='14' color='#0066CC'>REPUBLIC OF THE PHILIPPINES</font><br/>
            <font name='Helvetica-Bold' size='12' color='#008000'>DEPARTMENT OF ENVIRONMENT AND NATURAL RESOURCES</font><br/>
            <font name='Helvetica-Bold' size='12' color='#008000'>ENVIRONMENTAL MANAGEMENT BUREAU</font><br/>
            <font name='Helvetica' size='11' color='#008000'>REGION I</font><br/>
            <font name='Helvetica-Oblique' size='9' color='#666666'>Kalikasang Protektado, Paglilingkod na Tapat.</font>
        </para>
        """
        
        # Header table
        header_data = [
            [logo1, Paragraph(header_text, self.styles['Normal']), logo2],
        ]
        
        header_table = Table(header_data, colWidths=[1.5*inch, 4*inch, 1.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        self.story.append(header_table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def _get_legal_bases(self):
        """Return applicable legal bases for inspection reports"""
        return [
            'RA 8749 - Clean Air Act',
            'RA 9275 - Clean Water Act',
            'RA 9003 - Ecological Solid Waste Management Act',
            'PD 1586 - EIS Law',
            'DAO 2016-08 (Procedural Manual for PEISS)',
            'DAO 1996-37 (Hazardous Waste)',
            'DAO 2021-19 (Updated Standards)',
            'EMB Memorandum Circulars and Regional Policies'
        ]
    
    def _add_title_page(self):
        """Add professional title page with DENR standards"""
        # Report title
        title_text = "<para align='center'><b><font size='18' color='#0066CC'>DIVISION REPORT</font></b></para>"
        self.story.append(Paragraph(title_text, self.styles['DENRTitle']))
        
        subtitle_text = "<para align='center'><font size='14' color='#008000'>Inspection Summary Report</font></para>"
        self.story.append(Paragraph(subtitle_text, self.styles['DENRSubtitle']))
        
        self.story.append(Spacer(1, 0.2*inch))
        
        # Generation info
        gen_date = datetime.now().strftime("%B %d, %Y")
        date_text = f"<para align='center'><font size='10'>Generated on: {gen_date}</font></para>"
        self.story.append(Paragraph(date_text, self.styles['DENRBody']))
        
        self.story.append(Spacer(1, 0.3*inch))
        
        # Report metadata
        metadata_data = [
            ['Reference Number:', self.reference_number],
            ['Prepared by:', f"{self.user_info.first_name} {self.user_info.last_name}"],
            ['User Level:', self.user_info.userlevel],
            ['Email:', self.user_info.email],
            ['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        ]
        
        metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
        metadata_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('BACKGROUND', (0, 0), (0, -1), self.light_blue),
        ]))
        
        self.story.append(metadata_table)
        self.story.append(Spacer(1, 0.3*inch))
        
        # Legal bases section
        self.story.append(Paragraph("<b>LEGAL BASES</b>", self.styles['SectionHeader']))
        legal_bases = self._get_legal_bases()
        for base in legal_bases:
            base_text = f"<bullet>&bull;</bullet> {base}"
            self.story.append(Paragraph(base_text, self.styles['DENRBody']))
        self.story.append(Spacer(1, 0.3*inch))
        
        # Filters applied
        if self.filters_applied:
            filter_data = [['FILTERS APPLIED:', '']]
            for key, value in self.filters_applied.items():
                if value:
                    filter_data.append([key.replace('_', ' ').title() + ':', str(value)])
            
            if len(filter_data) > 1:
                filter_table = Table(filter_data, colWidths=[2*inch, 4*inch])
                filter_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (0, 0), 11),
                    ('BACKGROUND', (0, 0), (-1, 0), self.light_blue),
                    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('PADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
                ]))
                
                self.story.append(filter_table)
                self.story.append(Spacer(1, 0.3*inch))
    
    def _add_statistics_section(self):
        """Add statistics summary section"""
        stats = self.report_data.get('statistics', {})
        inspection_stats = stats.get('inspection_summary', {})
        compliance_stats = stats.get('compliance_summary', {})
        
        stats_title = Paragraph("<b>SUMMARY STATISTICS</b>", self.styles['Heading2'])
        self.story.append(stats_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Inspection summary
        stats_data = [
            ['Metric', 'Value'],
            ['Total Inspections', str(inspection_stats.get('total_inspections', 0))],
            ['Division Reviewed', str(inspection_stats.get('division_reviewed', 0))],
            ['Section Completed', str(inspection_stats.get('section_completed', 0))],
            ['Total NOV Issued', str(inspection_stats.get('total_nov', 0))],
            ['Total NOO Issued', str(inspection_stats.get('total_noo', 0))],
            ['Compliant', str(compliance_stats.get('compliant_count', 0))],
            ['Non-Compliant', str(compliance_stats.get('non_compliant_count', 0))],
            ['Pending', str(compliance_stats.get('pending_count', 0))],
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        
        self.story.append(stats_table)
        self.story.append(PageBreak())
    
    def _add_data_table(self):
        """Add main data table"""
        records = self.report_data.get('records', [])
        
        if not records:
            no_data = Paragraph("<b>No inspection records found for the selected filters.</b>", self.styles['Normal'])
            self.story.append(no_data)
            return
        
        data_title = Paragraph("<b>DETAILED INSPECTION DATA</b>", self.styles['SectionHeader'])
        self.story.append(data_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Table headers
        headers = [
            'Inspection No.', 'Establishment', 'Law', 'Inspection Date',
            'Status', 'NOV', 'NOO', 'Compliance', 'Inspected By'
        ]
        
        # Prepare data rows
        data_rows = [headers]
        for record in records:
            has_nov = record.get('has_nov', False)
            has_noo = record.get('has_noo', False)
            status = record.get('simplified_status', record.get('current_status', 'N/A'))
            if 'CLOSED' in status or 'SECTION_COMPLETED' in status:
                status = 'Completed'
            
            # Format compliance status with color indicators
            compliance = record.get('compliance_status', 'PENDING')
            
            row = [
                record.get('code', 'N/A'),
                record.get('establishment_name', 'N/A')[:30],  # Truncate long names
                record.get('law', 'N/A'),
                record.get('created_at', 'N/A')[:10] if record.get('created_at') else 'N/A',
                status,
                '✓' if has_nov else '✗',
                '✓' if has_noo else '✗',
                compliance,
                record.get('inspected_by_name', 'Not Inspected') or 'Not Inspected',
            ]
            data_rows.append(row)
        
        # Create table
        col_widths = [1*inch, 2*inch, 1*inch, 0.8*inch, 1*inch, 0.5*inch, 0.5*inch, 0.8*inch, 1.2*inch]
        data_table = Table(data_rows, colWidths=col_widths, repeatRows=1)
        
        # Style the table with DENR standards
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Status column centered
            ('ALIGN', (5, 1), (6, -1), 'CENTER'),  # NOV/NOO columns centered
            ('ALIGN', (7, 1), (7, -1), 'CENTER'),  # Compliance column centered
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]
        
        data_table.setStyle(TableStyle(table_style))
        self.story.append(data_table)
    
    def _add_recommendations(self):
        """Add recommendations section"""
        recommendations = self.report_data.get('recommendations', [])
        
        if not recommendations:
            return
        
        self.story.append(PageBreak())
        rec_title = Paragraph("<b>SYSTEM RECOMMENDATIONS</b>", self.styles['SectionHeader'])
        self.story.append(rec_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        for idx, rec in enumerate(recommendations, start=1):
            rec_type = Paragraph(f"<b>{idx}. {rec.get('type', 'Recommendation')}</b>", self.styles['DENRBody'])
            self.story.append(rec_type)
            
            rec_desc = Paragraph(rec.get('description', ''), self.styles['DENRBody'])
            self.story.append(rec_desc)
            self.story.append(Spacer(1, 0.15*inch))
    
    def _add_routing_section(self):
        """Add DENR routing section for workflow tracking"""
        self.story.append(PageBreak())
        routing_title = Paragraph("<b>ROUTING AND APPROVAL</b>", self.styles['SectionHeader'])
        self.story.append(routing_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        routing_data = [
            ['Stage', 'Name', 'Position', 'Date', 'Signature'],
            ['Prepared by', '', 'Monitoring Staff', '', ''],
            ['Reviewed by', '', 'Section Chief', '', ''],
            ['Recommended by', '', 'Division Chief', '', ''],
            ['Approved by', '', 'Regional Director', '', ''],
        ]
        
        routing_table = Table(routing_data, colWidths=[1.5*inch, 2*inch, 2*inch, 1.2*inch, 1.3*inch])
        routing_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        self.story.append(routing_table)
        self.story.append(Spacer(1, 0.3*inch))
    
    def _add_watermark(self, canvas, doc):
        """Add watermark to PDF pages"""
        if not self.watermark:
            return
        
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 60)
        canvas.setFillColor(colors.grey)
        canvas.setFillAlpha(0.1)  # Very transparent
        
        # Rotate and center watermark
        width, height = doc.pagesize
        canvas.translate(width / 2, height / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, self.watermark)
        canvas.restoreState()
    
    def _add_footer(self, canvas, doc):
        """Add professional DENR footer with page numbers and reference number"""
        canvas.saveState()
        
        # Footer line
        canvas.setStrokeColor(self.denr_blue)
        canvas.setLineWidth(0.5)
        canvas.line(50, 60, doc.pagesize[0] - 50, 60)
        
        # Footer text
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        
        # Left: Office information
        office_info = "EMB Region I | Email: emb1@denr.gov.ph"
        canvas.drawString(50, 45, office_info)
        
        # Center: Page number and reference
        page_text = f"Page {canvas.getPageNumber()}"
        ref_text = f"Ref: {self.reference_number}"
        canvas.drawCentredString(doc.pagesize[0] / 2, 45, page_text)
        canvas.drawCentredString(doc.pagesize[0] / 2, 35, ref_text)
        
        # Right: Generation timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        canvas.drawRightString(doc.pagesize[0] - 50, 45, f"Generated: {timestamp}")
        
        canvas.restoreState()
    
    def generate(self):
        """Generate the complete PDF document with DENR standards"""
        try:
            # Setup styles first
            self._setup_styles()
            
            # Create document with proper margins
            self.doc = SimpleDocTemplate(
                self.buffer,
                pagesize=A4,
                rightMargin=0.5*inch,
                leftMargin=0.5*inch,
                topMargin=0.7*inch,
                bottomMargin=0.9*inch  # More space for footer
            )
            
            # Build story
            self._add_header()
            self._add_title_page()
            self._add_statistics_section()
            self._add_data_table()
            self._add_recommendations()
            self._add_routing_section()
            
            # Build PDF with footer and watermark callbacks
            def on_first_page(canvas, doc):
                self._add_watermark(canvas, doc)
                self._add_footer(canvas, doc)
            
            def on_later_pages(canvas, doc):
                self._add_watermark(canvas, doc)
                self._add_footer(canvas, doc)
            
            self.doc.build(self.story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
        except Exception as e:
            print(f"PDF Generation Error: {str(e)}")
            raise e
        
        return self.buffer

