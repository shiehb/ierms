"""
Legal Report PDF Generator using reportlab
Generates professional PDF reports with DENR official standards
"""
import os
import io
from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas


class LegalReportPDFGenerator:
    """
    Professional PDF generator for legal reports
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
    
    def _get_user_display_name(self):
        """Safely get user's full name"""
        first_name = getattr(self.user_info, 'first_name', '') or ''
        last_name = getattr(self.user_info, 'last_name', '') or ''
        if first_name or last_name:
            return f"{first_name} {last_name}".strip()
        # Fallback to email if no name
        return getattr(self.user_info, 'email', 'Unknown User') or 'Unknown User'
    
    def _get_user_level(self):
        """Safely get user level, handling both CharField and ForeignKey"""
        userlevel = getattr(self.user_info, 'userlevel', None)
        if userlevel is None:
            return 'N/A'
        # If it's a ForeignKey (has code attribute), get the code
        if hasattr(userlevel, 'code'):
            return userlevel.code
        # If it's a ForeignKey (has name attribute), get the name
        if hasattr(userlevel, 'name'):
            return userlevel.name
        # If it's already a string, return it
        return str(userlevel)
    
    def _get_user_email(self):
        """Safely get user email"""
        return getattr(self.user_info, 'email', 'N/A') or 'N/A'
    
    def _safe_float(self, value, default=0.0):
        """Safely convert value to float, handling strings, Decimals, None, etc."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols and whitespace
            cleaned = value.replace('₱', '').replace(',', '').strip()
            if not cleaned:
                return default
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return default
        # Handle Decimal and other numeric types
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
        
    def _get_denr_colors(self):
        """Return standardized DENR color palette"""
        return {
            'denr_blue': colors.HexColor('#0066CC'),
            'denr_green': colors.HexColor('#008000'),
            'earth_brown': colors.HexColor('#8B4513'),
            'earth_chocolate': colors.HexColor('#D2691E'),
            'light_green': colors.HexColor('#E7F7E7'),
            'light_blue': colors.HexColor('#E7F0F7'),
            'light_red': colors.HexColor('#FFE7E7'),
            'border_gray': colors.HexColor('#CCCCCC'),
        }
    
    def _generate_reference_number(self):
        """Generate DENR reference number: EIA-YYYY-MM-DD-####"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
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
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=self.denr_blue,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style - Arial font
        self.styles.add(ParagraphStyle(
            name='DENRSubtitle',
            parent=self.styles['Heading1'],
            fontSize=14,
            spaceAfter=8,
            alignment=TA_CENTER,
            textColor=self.denr_green,
            fontName='Helvetica-Bold'
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=6,
            spaceBefore=12,
            textColor=self.denr_blue,
            fontName='Helvetica-Bold'
        ))
        
        # Body text style - Arial font
        self.styles.add(ParagraphStyle(
            name='DENRBody',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica'
        ))
        
        # Normal text with justified alignment
        self.styles.add(ParagraphStyle(
            name='Justified',
            parent=self.styles['Normal'],
            alignment=TA_JUSTIFY,
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
    
    def _get_logo_path(self, logo_num):
        """Get logo path with fallback"""
        path = self.LOGO1_PATH if logo_num == 1 else self.LOGO2_PATH
        return path if os.path.exists(path) else None
    
    def _add_header(self):
        """Add professional government header with logos"""
        logo1_path = self._get_logo_path(1)
        logo2_path = self._get_logo_path(2)
        
        header_data = []
        header_row = []
        
        # Left logo
        if logo1_path:
            try:
                logo1 = Image(logo1_path, width=0.8*inch, height=0.8*inch)
                header_row.append(logo1)
            except:
                header_row.append('')
        else:
            header_row.append('')
        
        # Center text - Official DENR header
        header_text = """
        <para align='center'>
            <font name='Helvetica-Bold' size='14' color='#0066CC'>REPUBLIC OF THE PHILIPPINES</font><br/>
            <font name='Helvetica-Bold' size='12' color='#008000'>DEPARTMENT OF ENVIRONMENT AND NATURAL RESOURCES</font><br/>
            <font name='Helvetica-Bold' size='12' color='#008000'>ENVIRONMENTAL MANAGEMENT BUREAU</font><br/>
            <font name='Helvetica' size='11' color='#008000'>REGION I</font><br/>
            <font name='Helvetica-Oblique' size='9' color='#666666'>Kalikasang Protektado, Paglilingkod na Tapat.</font>
        </para>
        """
        header_row.append(Paragraph(header_text, self.styles['Normal']))
        
        # Right logo
        if logo2_path:
            try:
                logo2 = Image(logo2_path, width=0.8*inch, height=0.8*inch)
                header_row.append(logo2)
            except:
                header_row.append('')
        else:
            header_row.append('')
        
        header_data.append(header_row)
        
        # Create header table
        header_table = Table(header_data, colWidths=[1.5*inch, 7*inch, 1.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        self.story.append(header_table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def _add_title_page(self):
        """Add professional title page"""
        # Report title
        title_text = "<para align='center'><b><font size='18' color='#0066CC'>LEGAL UNIT REPORT</font></b></para>"
        self.story.append(Paragraph(title_text, self.styles['DENRTitle']))
        
        subtitle_text = "<para align='center'><font size='14' color='#008000'>Billing and Compliance Summary</font></para>"
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
            ['Prepared by:', self._get_user_display_name()],
            ['User Level:', self._get_user_level()],
            ['Email:', self._get_user_email()],
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
        legal_bases = [
            'RA 8749 - Clean Air Act',
            'RA 9275 - Clean Water Act',
            'RA 9003 - Ecological Solid Waste Management Act',
            'PD 1586 - EIS Law',
            'DAO 2016-08 (Procedural Manual for PEISS)',
            'DAO 1996-37 (Hazardous Waste)',
            'DAO 2021-19 (Updated Standards)',
            'EMB Memorandum Circulars and Regional Policies'
        ]
        for base in legal_bases:
            base_text = f"<bullet>&bull;</bullet> {base}"
            self.story.append(Paragraph(base_text, self.styles['DENRBody']))
        self.story.append(Spacer(1, 0.3*inch))
        
        # Filters applied
        if self.filters_applied:
            self.story.append(Paragraph("<b>FILTERS APPLIED</b>", self.styles['SectionHeader']))
            
            filters_data = []
            for key, value in self.filters_applied.items():
                if value and value != 'All':
                    filters_data.append([key.replace('_', ' ').title(), str(value)])
            
            if filters_data:
                filters_table = Table(filters_data, colWidths=[2*inch, 4*inch])
                filters_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('PADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
                    ('BACKGROUND', (0, 0), (0, -1), self.light_blue),
                ]))
                self.story.append(filters_table)
        
        self.story.append(PageBreak())
    
    def _add_statistics_section(self):
        """Add summary statistics section"""
        self.story.append(Paragraph("<b>SUMMARY STATISTICS</b>", self.styles['SectionHeader']))
        
        stats = self.report_data.get('statistics', {})
        billing_stats = stats.get('billing_summary', {})
        compliance_stats = stats.get('compliance_summary', {})
        
        # Billing summary
        billing_data = [
            ['BILLING SUMMARY', ''],
            ['Total Billed Amount', f"₱{self._safe_float(billing_stats.get('total_billed', 0)):,.2f}"],
            ['Total Paid Amount', f"₱{self._safe_float(billing_stats.get('total_paid', 0)):,.2f}"],
            ['Outstanding Balance', f"₱{self._safe_float(billing_stats.get('outstanding_balance', 0)):,.2f}"],
            ['Average Days to Payment', f"{billing_stats.get('avg_days_to_payment', 0):.1f} days"],
            ['Total NOV Issued', str(billing_stats.get('total_nov', 0))],
            ['Total NOO Issued', str(billing_stats.get('total_noo', 0))],
        ]
        
        billing_table = Table(billing_data, colWidths=[3*inch, 2*inch])
        billing_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('SPAN', (0, 0), (1, 0)),
            
            # Data rows
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('BACKGROUND', (0, 1), (0, -1), self.light_blue),
        ]))
        
        self.story.append(billing_table)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Compliance summary
        compliance_data = [
            ['COMPLIANCE SUMMARY', ''],
            ['Compliant Establishments', str(compliance_stats.get('compliant_count', 0))],
            ['Non-Compliant Establishments', str(compliance_stats.get('non_compliant_count', 0))],
            ['Pending Actions', str(compliance_stats.get('pending_count', 0))],
            ['Re-inspections Recommended', str(compliance_stats.get('reinspection_recommended', 0))],
        ]
        
        compliance_table = Table(compliance_data, colWidths=[3*inch, 2*inch])
        compliance_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), self.denr_green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('SPAN', (0, 0), (1, 0)),
            
            # Data rows
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('BACKGROUND', (0, 1), (0, -1), self.light_green),
        ]))
        
        self.story.append(compliance_table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def _add_detailed_data_table(self):
        """Add detailed billing data table"""
        self.story.append(Paragraph("<b>DETAILED BILLING RECORDS</b>", self.styles['SectionHeader']))
        
        records = self.report_data.get('records', [])
        
        if not records:
            self.story.append(Paragraph("<b>No billing records found for the selected filters.</b>", 
                                       self.styles['Normal']))
            return
        
        # Table headers
        table_data = [[
            'Inspection No.', 'Establishment', 'Amount', 'Billing Date',
            'Payment Status', 'NOV/NOO', 'Compliance'
        ]]
        
        # Add data rows (limit to avoid huge PDFs)
        for record in records[:50]:  # Limit to 50 records
            billing_date = record.get('sent_date', '')
            if billing_date:
                try:
                    billing_date = datetime.fromisoformat(billing_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                except:
                    pass
            
            nov_noo = []
            if record.get('has_nov'):
                nov_noo.append('NOV')
            if record.get('has_noo'):
                nov_noo.append('NOO')
            
            table_data.append([
                record.get('inspection_code', 'N/A')[:15],
                record.get('establishment_name', 'N/A')[:25],
                f"₱{self._safe_float(record.get('amount', 0)):,.0f}",
                billing_date[:10] if billing_date else 'N/A',
                record.get('payment_status', 'UNPAID')[:10],
                ', '.join(nov_noo) if nov_noo else 'None',
                record.get('compliance_status', 'N/A')[:10]
            ])
        
        if len(records) > 50:
            table_data.append(['...', f'Showing first 50 of {len(records)} records', '', '', '', '', ''])
        
        # Create table
        data_table = Table(table_data, colWidths=[
            1.2*inch, 2*inch, 0.8*inch, 1*inch, 0.9*inch, 0.8*inch, 1*inch
        ])
        
        data_table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data row styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('PADDING', (0, 1), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Borders
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            
            # Alternating colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.light_blue]),
        ]))
        
        self.story.append(data_table)
        self.story.append(Spacer(1, 0.2*inch))
    
    def _add_recommendations_section(self):
        """Add recommendations section"""
        self.story.append(PageBreak())
        self.story.append(Paragraph("<b>RECOMMENDATIONS</b>", self.styles['SectionHeader']))
        
        recommendations = self.report_data.get('recommendations', [])
        
        if recommendations:
            for idx, rec in enumerate(recommendations, start=1):
                rec_text = f"<b>{idx}. {rec.get('type', 'Recommendation')}:</b> {rec.get('description', '')}"
                self.story.append(Paragraph(rec_text, self.styles['Justified']))
                self.story.append(Spacer(1, 0.1*inch))
        else:
            self.story.append(Paragraph("No specific recommendations at this time.", self.styles['DENRBody']))
        
        self.story.append(Spacer(1, 0.3*inch))
        
        # Routing and approval section
        self.story.append(Paragraph("<b>ROUTING AND APPROVAL</b>", self.styles['SectionHeader']))
        
        routing_data = [
            ['Stage', 'Name', 'Position', 'Date', 'Signature'],
            ['Prepared by', self._get_user_display_name(), 'Legal Unit', '', ''],
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
    
    def _add_watermark(self, canvas, doc):
        """Add watermark to PDF pages"""
        if not self.watermark:
            return
        
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 60)
        canvas.setFillColor(colors.grey)
        canvas.setFillAlpha(0.1)
        
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
        """Main method to generate the complete PDF report"""
        try:
            # Create document with landscape orientation
            self.doc = SimpleDocTemplate(
                self.buffer,
                pagesize=landscape(A4),
                rightMargin=50,
                leftMargin=50,
                topMargin=72,
                bottomMargin=80  # More space for footer
            )
            
            # Setup styles
            self._setup_styles()
            
            # Build story
            self._add_header()
            self._add_title_page()
            self._add_statistics_section()
            self._add_detailed_data_table()
            self._add_recommendations_section()
            
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

