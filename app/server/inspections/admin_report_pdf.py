"""
Admin Report PDF Generator using reportlab
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


class AdminReportPDFGenerator:
    """
    Professional PDF generator for admin reports (establishments and users)
    """
    
    def __init__(self, buffer, report_data, filters_applied, user_info, watermark=None):
        self.buffer = buffer
        self.report_data = report_data
        self.filters_applied = filters_applied
        self.user_info = user_info if isinstance(user_info, dict) else {
            'name': getattr(user_info, 'get_full_name', lambda: '')() or getattr(user_info, 'email', ''),
            'userlevel': getattr(user_info, 'userlevel', 'Admin')
        }
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
        self.gov_blue = self.denr_blue  # Backward compatibility
        self.gov_green = self.denr_green  # Backward compatibility
        
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
            fontName='Helvetica-Bold'
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
        """Add header with logos and agency information"""
        # Try to load logos
        logo1 = None
        logo2 = None
        
        if os.path.exists(self.LOGO1_PATH):
            try:
                logo1 = Image(self.LOGO1_PATH, width=1.5*inch, height=1.5*inch)
            except:
                pass
        
        if os.path.exists(self.LOGO2_PATH):
            try:
                logo2 = Image(self.LOGO2_PATH, width=1.5*inch, height=1.5*inch)
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
    
    def _add_title_page(self, report_type):
        """Add professional title page"""
        title_map = {
            'establishments': 'ADMIN REPORT - ESTABLISHMENTS',
            'users': 'ADMIN REPORT - USERS'
        }
        subtitle_map = {
            'establishments': 'Generation of Added Establishments',
            'users': 'Generation of Added Users'
        }
        
        # Report title
        title_text = f"<para align='center'><b><font size='18' color='#0066CC'>{title_map.get(report_type, 'ADMIN REPORT')}</font></b></para>"
        self.story.append(Paragraph(title_text, self.styles['DENRTitle']))
        
        subtitle_text = f"<para align='center'><font size='14' color='#008000'>{subtitle_map.get(report_type, 'Admin Report')}</font></para>"
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
            ['Prepared by:', self.user_info.get('name', 'N/A')],
            ['User Level:', self.user_info.get('userlevel', 'Admin')],
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
        
        # Filters applied
        if self.filters_applied:
            filter_data = [['FILTERS APPLIED:', '']]
            for key, value in self.filters_applied.items():
                if value and str(value) != 'ALL':
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
    
    def _add_routing_section(self):
        """Add DENR routing section for workflow tracking"""
        self.story.append(PageBreak())
        routing_title = Paragraph("<b>ROUTING AND APPROVAL</b>", self.styles['SectionHeader'])
        self.story.append(routing_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        routing_data = [
            ['Stage', 'Name', 'Position', 'Date', 'Signature'],
            ['Prepared by', self.user_info.get('name', 'N/A'), 'Admin Staff', '', ''],
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
    
    def generate_establishments_report(self):
        """Generate establishments report"""
        self._setup_styles()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=A4, topMargin=0.7*inch, bottomMargin=0.9*inch)
        
        self._add_header()
        self._add_title_page('establishments')
        
        # Statistics
        total = len(self.report_data)
        active = sum(1 for r in self.report_data if r.get('is_active', False))
        inactive = total - active
        
        stats_title = Paragraph("<b>SUMMARY STATISTICS</b>", self.styles['Heading2'])
        self.story.append(stats_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        stats_data = [
            ['Metric', 'Value'],
            ['Total Establishments', str(total)],
            ['Active', str(active)],
            ['Inactive', str(inactive)],
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.gov_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
        ]))
        
        self.story.append(stats_table)
        self.story.append(PageBreak())
        
        # Data table
        if not self.report_data:
            no_data = Paragraph("<b>No establishment records found for the selected filters.</b>", self.styles['Normal'])
            self.story.append(no_data)
        else:
            data_title = Paragraph("<b>ESTABLISHMENT DATA</b>", self.styles['Heading2'])
            self.story.append(data_title)
            self.story.append(Spacer(1, 0.2*inch))
            
            headers = ['Name', 'Nature of Business', 'Province', 'City', 'Barangay', 'Date Added', 'Status']
            
            data_rows = [headers]
            for record in self.report_data:
                created_at = record.get('created_at', '')
                if created_at:
                    try:
                        if 'T' in created_at:
                            created_at = created_at.split('T')[0]
                        created_at = created_at[:10]
                    except:
                        pass
                
                status = 'Active' if record.get('is_active', False) else 'Inactive'
                status_color = self.light_green if record.get('is_active', False) else self.light_red
                
                row = [
                    record.get('name', 'N/A')[:30],
                    record.get('nature_of_business', 'N/A')[:25],
                    record.get('province', 'N/A')[:15],
                    record.get('city', 'N/A')[:20],
                    record.get('barangay', 'N/A')[:20],
                    created_at or 'N/A',
                    status,
                ]
                data_rows.append(row)
            
            col_widths = [1.5*inch, 1.5*inch, 1*inch, 1*inch, 1*inch, 0.8*inch, 0.7*inch]
            data_table = Table(data_rows, colWidths=col_widths, repeatRows=1)
            data_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            self.story.append(data_table)
        
        # Add routing section before building
        self._add_routing_section()
        
        # Add footer and watermark callbacks
        def on_first_page(canvas, doc):
            self._add_watermark(canvas, doc)
            self._add_footer(canvas, doc)
        
        def on_later_pages(canvas, doc):
            self._add_watermark(canvas, doc)
            self._add_footer(canvas, doc)
        
        self.doc.build(self.story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    
    def generate_users_report(self):
        """Generate users report"""
        self._setup_styles()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=A4, topMargin=0.7*inch, bottomMargin=0.9*inch)
        
        self._add_header()
        self._add_title_page('users')
        
        # Statistics
        total = len(self.report_data)
        active = sum(1 for r in self.report_data if r.get('is_active', False))
        inactive = total - active
        
        stats_title = Paragraph("<b>SUMMARY STATISTICS</b>", self.styles['Heading2'])
        self.story.append(stats_title)
        self.story.append(Spacer(1, 0.2*inch))
        
        stats_data = [
            ['Metric', 'Value'],
            ['Total Users', str(total)],
            ['Active', str(active)],
            ['Inactive', str(inactive)],
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.gov_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
        ]))
        
        self.story.append(stats_table)
        self.story.append(PageBreak())
        
        # Data table
        if not self.report_data:
            no_data = Paragraph("<b>No user records found for the selected filters.</b>", self.styles['Normal'])
            self.story.append(no_data)
        else:
            data_title = Paragraph("<b>USER DATA</b>", self.styles['Heading2'])
            self.story.append(data_title)
            self.story.append(Spacer(1, 0.2*inch))
            
            headers = ['Name', 'Email', 'User Level', 'Section', 'Date Joined', 'Last Updated', 'Status']
            
            data_rows = [headers]
            for record in self.report_data:
                date_joined = record.get('date_joined', '')
                if date_joined:
                    try:
                        if 'T' in date_joined:
                            date_joined = date_joined.split('T')[0]
                        date_joined = date_joined[:10]
                    except:
                        pass
                
                updated_at = record.get('updated_at', '')
                if updated_at:
                    try:
                        if 'T' in updated_at:
                            updated_at = updated_at.split('T')[0]
                        updated_at = updated_at[:10]
                    except:
                        pass
                
                status = 'Active' if record.get('is_active', False) else 'Inactive'
                
                row = [
                    record.get('full_name', record.get('email', 'N/A'))[:25],
                    record.get('email', 'N/A')[:30],
                    record.get('userlevel', 'N/A')[:15],
                    record.get('section', 'N/A') or 'N/A',
                    date_joined or 'N/A',
                    updated_at or 'N/A',
                    status,
                ]
                data_rows.append(row)
            
            col_widths = [1.5*inch, 1.8*inch, 1.2*inch, 1*inch, 0.9*inch, 0.9*inch, 0.7*inch]
            data_table = Table(data_rows, colWidths=col_widths, repeatRows=1)
            data_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.denr_blue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.light_blue, colors.white]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            self.story.append(data_table)
        
        # Add routing section before building
        self._add_routing_section()
        
        # Add footer and watermark callbacks
        def on_first_page(canvas, doc):
            self._add_watermark(canvas, doc)
            self._add_footer(canvas, doc)
        
        def on_later_pages(canvas, doc):
            self._add_watermark(canvas, doc)
            self._add_footer(canvas, doc)
        
        self.doc.build(self.story, onFirstPage=on_first_page, onLaterPages=on_later_pages)

