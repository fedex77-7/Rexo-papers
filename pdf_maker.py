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
    styles = getSampleStyleSheet()
    center = ParagraphStyle('center', parent=styles['Normal'], alignment=TA_CENTER)
    title_style = ParagraphStyle('title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=15)
    sub_style = ParagraphStyle('sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=11)
    q_style = ParagraphStyle('q', parent=styles['Normal'], fontSize=11, spaceAfter=6, leading=15)
    opt_style = ParagraphStyle('opt', parent=styles['Normal'], fontSize=11, leftIndent=14, spaceAfter=3)
    section_style = ParagraphStyle('sect', parent=styles['Normal'], fontSize=10, spaceAfter=6)
    footer_style = ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)

    story = []

    if meta.get("school_name"):
        story.append(Paragraph(meta["school_name"], title_style))
    story.append(Paragraph(meta.get("exam_title", "Question Paper"), sub_style))
    bits = " | ".join(filter(None, [meta.get("cls"), meta.get("subject")]))
    if bits:
        story.append(Paragraph(bits, sub_style))
    tm = "   ".join(filter(None, [
        f"Time: {meta['time']}" if meta.get("time") else "",
        f"Full Marks: {meta['marks']}" if meta.get("marks") else "",
    ]))
    if tm:
        story.append(Paragraph(tm, sub_style))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 6))

    info = Table([["Roll No: ______________", "Name: ____________________________"]], colWidths=[85 * mm, 85 * mm])
    info.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 9)]))
    story.append(info)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 10))

    if parsed.get("instructions"):
        story.append(Paragraph("<b>General Instructions:</b>", q_style))
        for ins in parsed["instructions"]:
            story.append(Paragraph(ins, section_style))
        story.append(Spacer(1, 6))

    for sec in parsed.get("sections", []):
        if sec.get("heading"):
            story.append(Paragraph(f"<b>{sec['heading']}</b>", q_style))
        for q in sec.get("questions", []):
            marks = f" <font color='#9C3B36'>[{q['marks']}]</font>" if q.get("marks") else ""
            story.append(Paragraph(f"{q.get('number','')}. {q.get('text','')}{marks}", q_style))
            for opt in q.get("options", []):
                story.append(Paragraph(opt, opt_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(Paragraph("Powered by Rexo International — Rexo Papers", footer_style))

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=18 * mm, bottomMargin=18 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)

    watermark_text = "REXO PAPERS — PREVIEW" if watermark else None

    def _make_canvas(*args, **kwargs):
        return WatermarkCanvas(*args, watermark_text=watermark_text, **kwargs)

    doc.build(story, canvasmaker=_make_canvas)
