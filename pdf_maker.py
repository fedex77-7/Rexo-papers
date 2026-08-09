"""
Builds the final exam paper PDF with Rexo Papers branding.
- "standard" tier: light footer branding only.
- watermark=True (used for the in-chat preview / non-A+ keys):
  large diagonal "REXO PAPERS - PREVIEW" watermark across every page,
  to discourage screenshot redistribution of unpurchased papers.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas as pdf_canvas


class WatermarkCanvas(pdf_canvas.Canvas):
    def __init__(self, *args, watermark_text=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.watermark_text = watermark_text

    def showPage(self):
        if self.watermark_text:
            self.saveState()
            self.setFont("Helvetica-Bold", 46)
            self.setFillColor(colors.Color(0.6, 0.6, 0.6, alpha=0.25))
            self.translate(300, 420)
            self.rotate(45)
            self.drawCentredString(0, 0, self.watermark_text)
            self.restoreState()
        super().showPage()


def build_pdf(output_path: str, parsed: dict, meta: dict, watermark: bool = False, logo_path: str = None):
    ACCENT = colors.HexColor("#1B6E8C")     # teal-blue header band
    ACCENT_LIGHT = colors.HexColor("#EAF4F8")  # light tint for info bar
    MARKS_COLOR = colors.HexColor("#C0392B")   # marks in red
    HEADING_COLOR = colors.HexColor("#1B6E8C")

    styles = getSampleStyleSheet()
    center = ParagraphStyle('center', parent=styles['Normal'], alignment=TA_CENTER)
    title_style = ParagraphStyle('title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=17, textColor=colors.white)
    sub_style = ParagraphStyle('sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=11, textColor=colors.white)
    q_style = ParagraphStyle('q', parent=styles['Normal'], fontSize=11, spaceAfter=6, leading=15)
    opt_style = ParagraphStyle('opt', parent=styles['Normal'], fontSize=11, leftIndent=14, spaceAfter=3)
    section_style = ParagraphStyle('sect', parent=styles['Normal'], fontSize=10, spaceAfter=6)
    footer_style = ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)

    story = []

    # Colored header band containing school name / exam title / time & marks
    header_lines = []
    if meta.get("school_name"):
        header_lines.append(Paragraph(meta["school_name"], title_style))
    header_lines.append(Paragraph(meta.get("exam_title", "Question Paper"), sub_style))
    bits = " | ".join(filter(None, [meta.get("cls"), meta.get("subject")]))
    if bits:
        header_lines.append(Paragraph(bits, sub_style))
    tm = "   ".join(filter(None, [
        f"Time: {meta['time']}" if meta.get("time") else "",
        f"Full Marks: {meta['marks']}" if meta.get("marks") else "",
    ]))
    if tm:
        header_lines.append(Paragraph(tm, sub_style))

    header_table = Table([[header_lines]], colWidths=[170 * mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    info = Table([["Roll No: ______________", "Name: ____________________________"]], colWidths=[85 * mm, 85 * mm])
    info.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, -1), ACCENT_LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info)
    story.append(Spacer(1, 12))

    if parsed.get("instructions"):
        story.append(Paragraph("<b>General Instructions:</b>", ParagraphStyle('instr', parent=q_style, textColor=HEADING_COLOR)))
        for ins in parsed["instructions"]:
            story.append(Paragraph(ins, section_style))
        story.append(Spacer(1, 6))

    for sec in parsed.get("sections", []):
        if sec.get("heading"):
            heading_table = Table([[Paragraph(f"<b>{sec['heading']}</b>", ParagraphStyle('sh', parent=q_style, textColor=colors.white, spaceAfter=0))]], colWidths=[170 * mm])
            heading_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), ACCENT),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(Spacer(1, 4))
            story.append(heading_table)
            story.append(Spacer(1, 4))
        for q in sec.get("questions", []):
            marks = f" <font color='#C0392B'>[{q['marks']}]</font>" if q.get("marks") else ""
            story.append(Paragraph(f"{q.get('number','')}. {q.get('text','')}{marks}", q_style))
            for opt in q.get("options", []):
                story.append(Paragraph(opt, opt_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Powered by Rexo International — Rexo Papers", footer_style))

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=16 * mm, bottomMargin=18 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)

    watermark_text = "REXO PAPERS — PREVIEW" if watermark else None

    def _make_canvas(*args, **kwargs):
        return WatermarkCanvas(*args, watermark_text=watermark_text, **kwargs)

    doc.build(story, canvasmaker=_make_canvas)


def build_generic_pdf(output_path: str, content: dict, watermark: bool = False):
    """Renders a free-form document (title/subtitle/sections with paragraphs
    and bullets) — used by the 'Custom PDF (Chat)' feature for anything that
    isn't an exam paper: certificates, notices, letters, worksheets, etc."""
    ACCENT = colors.HexColor("#1B6E8C")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ctitle', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=19, textColor=ACCENT)
    sub_style = ParagraphStyle('csub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, textColor=colors.grey)
    heading_style = ParagraphStyle('chead', parent=styles['Heading2'], fontSize=13, spaceBefore=10, spaceAfter=4, textColor=ACCENT)
    body_style = ParagraphStyle('cbody', parent=styles['Normal'], fontSize=11, spaceAfter=6, leading=15)
    bullet_style = ParagraphStyle('cbul', parent=styles['Normal'], fontSize=11, leftIndent=14, spaceAfter=3)
    footer_style = ParagraphStyle('cfooter', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)

    story = []
    if content.get("title"):
        story.append(Paragraph(content["title"], title_style))
    if content.get("subtitle"):
        story.append(Paragraph(content["subtitle"], sub_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(Spacer(1, 10))

    for sec in content.get("sections", []):
        if sec.get("heading"):
            story.append(Paragraph(sec["heading"], heading_style))
        for para in sec.get("paragraphs", []):
            story.append(Paragraph(para, body_style))
        for b in sec.get("bullets", []):
            story.append(Paragraph(f"•  {b}", bullet_style))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Powered by Rexo International — Rexo Papers", footer_style))

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=20 * mm, bottomMargin=18 * mm,
                             leftMargin=20 * mm, rightMargin=20 * mm)

    watermark_text = "REXO PAPERS — PREVIEW" if watermark else None

    def _make_canvas(*args, **kwargs):
        return WatermarkCanvas(*args, watermark_text=watermark_text, **kwargs)

    doc.build(story, canvasmaker=_make_canvas)
