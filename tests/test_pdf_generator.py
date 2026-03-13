"""Tests for pdf_generator module."""

import pytest

from src.pdf_generator import markdown_to_pdf, _clean_markdown


class TestMarkdownToPdf:
    def test_generates_bytes(self):
        md = "# Title\n\nSome text\n"
        result = markdown_to_pdf(md, title="Test Report")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_header(self):
        result = markdown_to_pdf("# Hello", title="Test")
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"

    def test_headers_rendering(self):
        md = "# H1\n## H2\n### H3\nRegular text"
        result = markdown_to_pdf(md)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_list_items(self):
        md = "- Item one\n- Item two\n* Item three"
        result = markdown_to_pdf(md)
        assert len(result) > 100

    def test_bold_text(self):
        md = "**Bold text here**\nNormal text"
        result = markdown_to_pdf(md)
        assert len(result) > 100

    def test_code_block(self):
        md = "```python\ndef hello():\n    print('hi')\n```"
        result = markdown_to_pdf(md)
        assert len(result) > 100

    def test_empty_content(self):
        result = markdown_to_pdf("")
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_complex_markdown(self):
        md = """# SpecBox Engine Report

## US-01: Autenticacion

**Horas**: 11
**Pantallas**: 1A, 1B

### Criterios de Aceptacion
- AC-01: Valida email
- AC-02: Muestra error

### Contexto
Sistema con Supabase Auth.

```json
{"status": "ok"}
```

Normal paragraph at the end.
"""
        result = markdown_to_pdf(md, title="US-01 PRD")
        assert len(result) > 200


class TestCleanMarkdown:
    def test_removes_bold(self):
        assert _clean_markdown("**bold text**") == "bold text"

    def test_removes_italic(self):
        assert _clean_markdown("*italic*") == "italic"

    def test_removes_code(self):
        assert _clean_markdown("`code`") == "code"

    def test_removes_links(self):
        assert _clean_markdown("[click here](http://example.com)") == "click here"

    def test_plain_text_unchanged(self):
        assert _clean_markdown("plain text") == "plain text"

    def test_mixed(self):
        assert _clean_markdown("**bold** and *italic* with `code`") == "bold and italic with code"
