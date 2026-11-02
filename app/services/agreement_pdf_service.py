"""Builds a branded PDF acta for a closed topic agreement."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.agreements import (
    VOTE_RESULT_APPROVED,
    VOTE_RESULT_NO_VOTES,
    VOTE_RESULT_REJECTED,
    VOTE_RESULT_TIED,
)
from app.domain.topics import TopicOpinionRecord, TopicVoteRecord

BRAND_NAVY = colors.HexColor("#001545")
BRAND_ACTION = colors.HexColor("#1F4B99")
BRAND_MUTED = colors.HexColor("#5B6B86")
BRAND_SURFACE = colors.HexColor("#F3F6FB")
BRAND_SUCCESS = colors.HexColor("#0F7B4B")
BRAND_DANGER = colors.HexColor("#B42318")

CATEGORY_LABELS = {
    "maintenance": "Mantención",
    "security": "Seguridad",
    "coexistence": "Convivencia",
    "administration": "Administración",
    "finance": "Finanzas",
    "proposal": "Propuesta",
    "other": "Otro",
}

VOTE_LABELS = {
    "yes": "A favor",
    "no": "En contra",
    "abstain": "Abstención",
}

RESULT_LABELS = {
    VOTE_RESULT_APPROVED: "APROBADO",
    VOTE_RESULT_REJECTED: "RECHAZADO",
    VOTE_RESULT_TIED: "EMPATE",
    VOTE_RESULT_NO_VOTES: "SIN VOTOS",
}


def _logo_path() -> Path | None:
    path = Path(__file__).resolve().parents[2] / "docs" / "brand" / "tu-comite-logo.png"
    return path if path.is_file() else None


def build_agreement_pdf(
    *,
    title: str,
    decision: str,
    description: str,
    category_key: str,
    vote_yes: int,
    vote_no: int,
    vote_abstain: int,
    vote_result: str,
    closed_at: str | None,
    votes: list[TopicVoteRecord],
    opinions: list[TopicOpinionRecord],
    building_name: str | None = None,
) -> bytes:
    """Return PDF bytes for one agreement acta."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"Acta de acuerdo · {title}",
        author="Tu Comité",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AgreementTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=BRAND_NAVY,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "AgreementSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        textColor=BRAND_MUTED,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        "AgreementHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=BRAND_NAVY,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "AgreementBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=BRAND_NAVY,
        alignment=TA_JUSTIFY,
    )
    highlight_style = ParagraphStyle(
        "AgreementHighlight",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=BRAND_NAVY,
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        "AgreementSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=BRAND_MUTED,
        alignment=TA_CENTER,
    )

    story: list = []
    logo = _logo_path()
    if logo is not None:
        story.append(Image(str(logo), width=4.8 * cm, height=1.6 * cm, kind="proportional"))
        story.append(Spacer(1, 0.35 * cm))
    else:
        story.append(Paragraph("Tu Comité", title_style))

    story.append(Paragraph("Acta de acuerdo", title_style))
    story.append(Paragraph("Tu comunidad, mejor conectada", subtitle_style))
    if building_name:
        story.append(Paragraph(_escape(building_name), subtitle_style))

    result_label = RESULT_LABELS.get(vote_result, vote_result.upper())
    result_hex = "#1F4B99"
    if vote_result == VOTE_RESULT_APPROVED:
        result_hex = "#0F7B4B"
    elif vote_result == VOTE_RESULT_REJECTED:
        result_hex = "#B42318"

    highlight_rows = [
        [Paragraph("<b>Decisión sometida a votación</b>", highlight_style)],
        [Paragraph(_escape(decision or "Sin decisión registrada."), body_style)],
        [Paragraph(f"<b>Resultado:</b> <font color='{result_hex}'>{result_label}</font>", highlight_style)],
        [
            Paragraph(
                f"A favor: <b>{vote_yes}</b> · En contra: <b>{vote_no}</b> · Abstenciones: <b>{vote_abstain}</b>",
                body_style,
            )
        ],
    ]
    highlight = Table(highlight_rows, colWidths=[16.5 * cm])
    highlight.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_SURFACE),
                ("BOX", (0, 0), (-1, -1), 1.2, BRAND_ACTION),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ],
        ),
    )
    story.append(KeepTogether([highlight, Spacer(1, 0.45 * cm)]))

    story.append(Paragraph("Resumen del tema", heading_style))
    meta = [
        f"<b>Título:</b> {_escape(title)}",
        f"<b>Categoría:</b> {_escape(CATEGORY_LABELS.get(category_key, category_key or '—'))}",
    ]
    if closed_at:
        meta.append(f"<b>Cerrado:</b> {_escape(_format_date(closed_at))}")
    for line in meta:
        story.append(Paragraph(line, body_style))
        story.append(Spacer(1, 0.12 * cm))

    story.append(Paragraph("Descripción", heading_style))
    story.append(Paragraph(_escape(description or "Sin descripción."), body_style))

    story.append(Paragraph("Detalle de la votación", heading_style))
    if votes:
        vote_table_data = [["Integrante", "Voto"]]
        for vote in votes:
            vote_table_data.append(
                [
                    _escape(vote.author_name or "Sin nombre"),
                    VOTE_LABELS.get(vote.choice, vote.choice),
                ],
            )
        vote_table = Table(vote_table_data, colWidths=[10 * cm, 6.5 * cm])
        vote_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DEEA")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ],
            ),
        )
        story.append(vote_table)
    else:
        story.append(Paragraph("No se registraron votos.", body_style))

    story.append(Paragraph("Comentarios y opiniones", heading_style))
    if opinions:
        for opinion in opinions:
            block = [
                Paragraph(f"<b>{_escape(opinion.author_name or 'Integrante')}</b>", body_style),
                Paragraph(_escape(opinion.body), body_style),
                Spacer(1, 0.25 * cm),
            ]
            story.extend(block)
    else:
        story.append(Paragraph("No se registraron comentarios.", body_style))

    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Documento generado automáticamente por Tu Comité.", small_style))
    story.append(Paragraph("Conservar como respaldo del acuerdo del comité.", small_style))

    document.build(story)
    return buffer.getvalue()


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br/>")
    )


def _format_date(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 10 and cleaned[4] == "-" and cleaned[7] == "-":
        return f"{cleaned[8:10]}/{cleaned[5:7]}/{cleaned[0:4]}"
    return cleaned
