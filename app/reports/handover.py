"""
Handover Report PDF Generator.

Generates a clinical shift handover PDF listing all HIGH and CRITICAL patients.
Uses reportlab for PDF generation with color-coded rows.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False

import io

# Colour scheme
_CRITICAL_BG = colors.HexColor("#FFD5D5")   # red tint
_HIGH_BG = colors.HexColor("#FFF3CD")       # amber tint
_HEADER_BG = colors.HexColor("#1a365d")     # dark navy
_HEADER_FG = colors.white
_ACCENT = colors.HexColor("#2b6cb0")        # blue


def generate_handover_pdf(patients: List[Dict[str, Any]]) -> bytes:
    """
    Generate a PDF handover report for HIGH and CRITICAL patients.

    Args:
        patients: List of patient dicts with keys:
            name, ward, risk_level, dhs_score, news2_score,
            latest_note, forecast_direction, alert_triggered.

    Returns:
        PDF as bytes.
    """
    if not _REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab"
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=_ACCENT,
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=2,
        alignment=TA_CENTER,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        wordWrap="LTR",
    )

    elements = []

    # Header
    elements.append(Paragraph("PhysioDiff", title_style))
    elements.append(Paragraph("Clinical Shift Handover Report", subtitle_style))
    elements.append(Paragraph(
        f"Ward: All  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        subtitle_style,
    ))
    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=_ACCENT))
    elements.append(Spacer(1, 4 * mm))

    if not patients:
        elements.append(Paragraph("No HIGH or CRITICAL patients at this time.", styles["Normal"]))
    else:
        # Summary
        n_critical = sum(1 for p in patients if p.get("risk_level") == "CRITICAL")
        n_high = sum(1 for p in patients if p.get("risk_level") == "HIGH")
        summary_text = (
            f"<b>{len(patients)} patients require attention</b> &nbsp;|&nbsp; "
            f"<font color='red'><b>CRITICAL: {n_critical}</b></font> &nbsp;|&nbsp; "
            f"<font color='orange'><b>HIGH: {n_high}</b></font>"
        )
        elements.append(Paragraph(summary_text, styles["Normal"]))
        elements.append(Spacer(1, 4 * mm))

        # Table
        col_widths = [38 * mm, 28 * mm, 18 * mm, 18 * mm, 18 * mm, 20 * mm, 65 * mm]
        headers = ["Patient", "Ward", "Risk", "DHS", "NEWS2", "Trend", "Latest Note"]

        table_data = [headers]
        row_styles: list[tuple] = []

        for idx, p in enumerate(patients):
            row_num = idx + 1  # offset by 1 for header

            note = str(p.get("latest_note", ""))[:100]
            note_para = Paragraph(note, note_style)

            dhs = p.get("dhs_score", 0.0)
            news2 = p.get("news2_score", 0)
            trend = p.get("forecast_direction", "STABLE")
            trend_arrow = {"RISING": "↑ RISING", "FALLING": "↓ FALLING"}.get(trend, "→ STABLE")

            alert_flag = " ⚠" if p.get("alert_triggered") else ""
            row = [
                p.get("name", "Unknown") + alert_flag,
                p.get("ward", "—"),
                p.get("risk_level", "—"),
                f"{dhs:.3f}",
                str(news2),
                trend_arrow,
                note_para,
            ]
            table_data.append(row)

            # Row background based on risk level
            bg = (
                _CRITICAL_BG
                if p.get("risk_level") == "CRITICAL"
                else _HIGH_BG
            )
            row_styles.append(("BACKGROUND", (0, row_num), (-1, row_num), bg))

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        base_style = [
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_FG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # Body
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (2, 1), (5, -1), "CENTER"),
            ("ALIGN", (0, 1), (1, -1), "LEFT"),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        base_style.extend(row_styles)
        table.setStyle(TableStyle(base_style))
        elements.append(table)

    elements.append(Spacer(1, 6 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "PhysioDiff — ACUHIT Hackathon 2026 | Confidential clinical document",
        subtitle_style,
    ))

    doc.build(elements)
    return buffer.getvalue()
