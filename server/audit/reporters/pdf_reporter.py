"""PDF report using ReportLab with NumberedCanvas header/footer pattern and
embed.build brand tokens.

Cover page has no header/footer. Every other page has a branded header and
a centered footer with "Página N / M".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..schema import CharacteristicResult, QualityReport, Severity, TrafficLight
from .brand_loader import BrandConfig


SQUARE_TITLES = {
    "functional_suitability": "1. Functional Suitability",
    "performance_efficiency": "2. Performance Efficiency",
    "compatibility": "3. Compatibility",
    "usability": "4. Usability",
    "reliability": "5. Reliability",
    "security": "6. Security",
    "maintainability": "7. Maintainability",
    "portability": "8. Portability",
}

TL_HEX = {
    TrafficLight.GREEN: "#3FDB6B",
    TrafficLight.AMBER: "#FFB347",
    TrafficLight.RED: "#FF4C4C",
}


class NumberedCanvas(canvas.Canvas):
    """ReportLab canvas that numbers pages at the end, skipping page 1 (cover)."""

    def __init__(self, *args: Any, brand: BrandConfig, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._brand = brand
        self._saved_page_states: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 — ReportLab API
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_page_states)
        for idx, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            page_num = idx + 1
            if page_num > 1:
                self._draw_header(page_num)
                self._draw_footer(page_num, total)
            super().showPage()
        super().save()

    def _draw_header(self, page_num: int) -> None:
        self.saveState()
        self.setFillColor(colors.HexColor(self._brand.background_color))
        self.rect(0, A4[1] - 18 * mm, A4[0], 18 * mm, fill=1, stroke=0)
        self.setFillColor(colors.HexColor(self._brand.primary_color))
        self.setFont("Helvetica-Bold", 11)
        self.drawString(18 * mm, A4[1] - 11 * mm, "SpecBox Quality Audit — ISO/IEC 25010")
        self.setFillColor(colors.HexColor(self._brand.text_color))
        self.setFont("Helvetica", 8)
        self.drawRightString(A4[0] - 18 * mm, A4[1] - 11 * mm, self._brand.name)
        self.restoreState()

    def _draw_footer(self, page_num: int, total: int) -> None:
        self.saveState()
        self.setFillColor(colors.HexColor(self._brand.primary_color))
        self.setFont("Helvetica", 8)
        self.drawCentredString(A4[0] / 2, 10 * mm, f"Página {page_num} / {total}")
        self.restoreState()


def _make_canvas_factory(brand: BrandConfig):
    def _factory(*args: Any, **kwargs: Any) -> NumberedCanvas:
        return NumberedCanvas(*args, brand=brand, **kwargs)
    return _factory


def _styles(brand: BrandConfig) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    primary = colors.HexColor(brand.primary_color)
    text = colors.HexColor("#111111")
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontSize=28,
            textColor=colors.HexColor(brand.primary_color), alignment=1, spaceAfter=12,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontSize=12,
            textColor=colors.HexColor("#FFFFFF"), alignment=1,
        ),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], textColor=primary, fontSize=18, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=text, fontSize=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], textColor=text, fontSize=11, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9, leading=12, textColor=text),
        "mono": ParagraphStyle("mono", parent=base["Code"], fontSize=8, leading=10, textColor=text),
    }


def _traffic_light_cell(tl: TrafficLight, score: float) -> Table:
    color = colors.HexColor(TL_HEX[tl])
    t = Table([[f"{score:.1f}", tl.value.upper()]], colWidths=[20 * mm, 20 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    return t


def _cover_story(report: QualityReport, styles: dict[str, ParagraphStyle], brand: BrandConfig) -> list:
    story: list = []
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph("SpecBox Quality Audit", styles["cover_title"]))
    story.append(Paragraph("ISO/IEC 25010 — SQuaRE", styles["cover_sub"]))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(f"<b>Project:</b> {report.project}", styles["cover_sub"]))
    story.append(Paragraph(f"<b>Commit:</b> {report.commit[:12] or 'n/a'}", styles["cover_sub"]))
    story.append(Paragraph(f"<b>Generated:</b> {report.generated_at}", styles["cover_sub"]))
    story.append(Spacer(1, 2 * cm))
    story.append(_traffic_light_cell(report.global_traffic_light, report.global_score))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Brand: {brand.name}", styles["cover_sub"]))
    story.append(PageBreak())
    return story


def _executive_summary(report: QualityReport, styles: dict[str, ParagraphStyle]) -> list:
    story: list = [Paragraph("Resumen ejecutivo", styles["h1"])]
    rows = [["#", "Characteristic", "Score", "Traffic Light"]]
    for c in report.characteristics:
        title = SQUARE_TITLES.get(c.characteristic.value, c.characteristic.value)
        rows.append([
            title.split(".", 1)[0],
            title.split(". ", 1)[-1],
            f"{c.score:.1f}" if not c.skipped else "—",
            c.traffic_light.value.upper() if not c.skipped else "SKIPPED",
        ])
    t = Table(rows, colWidths=[1 * cm, 7 * cm, 2 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#29F3E3")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"<b>Global score:</b> {report.global_score:.1f} / 100 "
        f"<b>({report.global_traffic_light.value.upper()})</b>",
        styles["body"],
    ))
    story.append(PageBreak())
    return story


def _characteristic_section(c: CharacteristicResult, styles: dict[str, ParagraphStyle]) -> list:
    title = SQUARE_TITLES.get(c.characteristic.value, c.characteristic.value)
    story: list = [Paragraph(title, styles["h1"])]
    header = Table(
        [[f"Score: {c.score:.1f}", f"Traffic light: {c.traffic_light.value.upper()}"]],
        colWidths=[6 * cm, 6 * cm],
    )
    header.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(TL_HEX[c.traffic_light])),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
    ]))
    story.append(header)
    story.append(Spacer(1, 3 * mm))

    if c.skipped:
        story.append(Paragraph(f"<i>Skipped: {c.skipped_reason or 'unknown'}</i>", styles["body"]))
        story.append(PageBreak())
        return story

    story.append(Paragraph("<b>Justification</b>", styles["h3"]))
    story.append(Paragraph(c.justification or "—", styles["body"]))
    story.append(Spacer(1, 2 * mm))

    if c.raw_metrics:
        story.append(Paragraph("<b>Raw metrics</b>", styles["h3"]))
        metric_rows = [[k, str(v)[:120]] for k, v in c.raw_metrics.items()]
        mt = Table(metric_rows, colWidths=[6 * cm, 10 * cm])
        mt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(mt)
        story.append(Spacer(1, 2 * mm))

    if c.breakdown is not None:
        story.append(Paragraph("<b>Breakdown (60/40 mix)</b>", styles["h3"]))
        br = c.breakdown
        bt = Table([
            ["Component", "Score", "Weight", "Contribution"],
            ["Classic (industry)", br["classic_60"]["score"], br["classic_60"]["weight"], br["classic_60"]["contribution"]],
            ["SpecBox signals", br["specbox_40"]["score"], br["specbox_40"]["weight"], br["specbox_40"]["contribution"]],
        ], colWidths=[5 * cm, 3 * cm, 3 * cm, 3 * cm])
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#29F3E3")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
        ]))
        story.append(bt)
        story.append(Spacer(1, 2 * mm))

    if c.findings:
        story.append(Paragraph(f"<b>Findings ({len(c.findings)})</b>", styles["h3"]))
        bullets = []
        for f in c.findings:
            loc = ""
            if f.file:
                loc = f" — <i>{f.file}{':' + str(f.line) if f.line else ''}</i>"
            text = f"<b>[{f.severity.value.upper()}]</b> {f.description}{loc}<br/>→ {f.remediation}"
            if f.cwe:
                text += f" <i>(CWE: {f.cwe})</i>"
            bullets.append(ListItem(Paragraph(text, styles["body"])))
        story.append(ListFlowable(bullets, bulletType="bullet", leftIndent=10))
        story.append(Spacer(1, 2 * mm))

    if c.recommendations:
        story.append(Paragraph(f"<b>Recommendations ({len(c.recommendations)})</b>", styles["h3"]))
        for r in c.recommendations:
            story.append(Paragraph(
                f"<b>[{r.priority.value.upper()}]</b> {r.action}<br/><i>{r.rationale}</i>",
                styles["body"],
            ))

    story.append(PageBreak())
    return story


def _appendix(report: QualityReport, styles: dict[str, ParagraphStyle]) -> list:
    story: list = [Paragraph("Anexo — Metadatos", styles["h1"])]
    meta_rows = [
        ["Audit ID", report.audit_id],
        ["Project", report.project],
        ["Commit", report.commit or "n/a"],
        ["Generated at", report.generated_at],
        ["Schema version", report.audit_schema_version],
        ["Stack detected", str(report.stack.get("detected", "unknown"))],
        ["Analyzers run", ", ".join(report.stack.get("analyzers_run", []))],
        ["Duration (ms)", str(report.meta.get("duration_ms", "n/a"))],
    ]
    mt = Table(meta_rows, colWidths=[5 * cm, 11 * cm])
    mt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.2, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(mt)
    story.append(Spacer(1, 4 * mm))

    if report.tools_used:
        story.append(Paragraph("<b>Tools used</b>", styles["h3"]))
        rows = [["Tool", "Status", "Version", "Notes"]]
        for t in report.tools_used:
            rows.append([t.name, t.status, t.version or "—", (t.message or "")[:80]])
        tt = Table(rows, colWidths=[3 * cm, 3 * cm, 4 * cm, 6 * cm])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#29F3E3")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
        ]))
        story.append(tt)

    warnings = report.meta.get("warnings", [])
    if warnings:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("<b>Warnings</b>", styles["h3"]))
        for w in warnings:
            story.append(Paragraph(f"• {w}", styles["body"]))
    return story


def write_pdf_report(report: QualityReport, out_path: Path, brand: BrandConfig) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles(brand)

    doc = BaseDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=f"SpecBox Quality Audit — {report.project}",
        author="SpecBox Engine",
    )

    # Cover template: fills the page with brand background, no header/footer
    def _cover_bg(canv: canvas.Canvas, _doc: Any) -> None:
        canv.saveState()
        canv.setFillColor(colors.HexColor(brand.background_color))
        canv.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canv.restoreState()

    cover_frame = Frame(0, 0, A4[0], A4[1], id="cover", leftPadding=2 * cm, rightPadding=2 * cm, topPadding=2 * cm, bottomPadding=2 * cm)
    content_frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="content",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=_cover_bg),
        PageTemplate(id="content", frames=[content_frame]),
    ])

    story: list = []
    story.extend(_cover_story(report, styles, brand))
    # Switch to content template after cover
    from reportlab.platypus import NextPageTemplate
    story.insert(len(story) - 1, NextPageTemplate("content"))

    story.extend(_executive_summary(report, styles))
    for c in report.characteristics:
        story.extend(_characteristic_section(c, styles))
    story.extend(_appendix(report, styles))

    doc.build(story, canvasmaker=_make_canvas_factory(brand))
    return out_path
