"""Markdown to PDF conversion using fpdf2 (pure Python, no system deps)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

_FONTS_DIR = Path(__file__).parent / "fonts"


class SpecBoxPDF(FPDF):
    """Custom PDF with header/footer for SpecBox Engine reports."""

    def __init__(self, title: str = "SpecBox Engine Report", **kwargs):
        super().__init__(**kwargs)
        self.report_title = title
        self.set_auto_page_break(auto=True, margin=25)
        # Register DejaVu Sans (Unicode TTF) as the default font family
        self.add_font("DejaVu", "", str(_FONTS_DIR / "DejaVuSans.ttf"), uni=True)
        self.add_font("DejaVu", "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"), uni=True)
        self.add_font("DejaVu", "I", str(_FONTS_DIR / "DejaVuSans-Oblique.ttf"), uni=True)
        self.add_font("DejaVuMono", "", str(_FONTS_DIR / "DejaVuSansMono.ttf"), uni=True)

    def header(self):
        self.set_font("DejaVu", "B", 10)
        w = self.get_string_width(self.report_title) + 10
        self.cell(w, 8, self.report_title)
        self.set_font("DejaVu", "", 8)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.cell(0, 8, date_str, align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")


def markdown_to_pdf(markdown_content: str, title: str = "SpecBox Engine Report") -> bytes:
    """Convert markdown content to PDF bytes.

    Supports: headers (##, ###), bold (**text**), lists (- item), code blocks (```).
    """
    pdf = SpecBoxPDF(title=title)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("DejaVu", "", 10)

    lines = markdown_content.split("\n")
    in_code_block = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code block toggle
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                pdf.set_font("DejaVuMono", "", 9)
                pdf.set_fill_color(240, 240, 240)
            else:
                pdf.set_font("DejaVu", "", 10)
            i += 1
            continue

        if in_code_block:
            pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT", fill=True)
            i += 1
            continue

        stripped = line.strip()

        # Headers — check longest prefix first
        if stripped.startswith("### "):
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 12)
            pdf.cell(0, 6, stripped[4:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 10)
            pdf.ln(1)
        elif stripped.startswith("## "):
            pdf.ln(3)
            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 7, stripped[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 10)
            pdf.ln(2)
        elif stripped.startswith("# "):
            pdf.ln(4)
            pdf.set_font("DejaVu", "B", 16)
            pdf.cell(0, 8, stripped[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 10)
            pdf.ln(3)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = _clean_markdown(stripped[2:])
            pdf.cell(0, 5, f"  \u2022 {text}", new_x="LMARGIN", new_y="NEXT")
        elif stripped == "":
            pdf.ln(3)
        else:
            text = _clean_markdown(stripped)
            pdf.cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

        i += 1

    return bytes(pdf.output())


def _clean_markdown(text: str) -> str:
    """Remove markdown formatting from text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text
