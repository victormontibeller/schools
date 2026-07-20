"""Documentos financeiros internos gerados no servidor com ReportLab."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value) -> str:
    formatted = f"{value or 0:,.2f}"
    return f"R$ {formatted.replace(',', '_').replace('.', ',').replace('_', '.')}"


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="DocumentTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=colors.HexColor("#24324a"),
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocumentMeta",
            parent=styles["BodyText"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569"),
        )
    )
    styles.add(
        ParagraphStyle(name="DocumentRight", parent=styles["DocumentMeta"], alignment=TA_RIGHT)
    )
    styles.add(
        ParagraphStyle(
            name="DocumentNotice",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.HexColor("#9f1239"),
        )
    )
    return styles


def _table(data, widths, *, alignments=()):
    table = Table(data, colWidths=widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#24324a")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for column in alignments:
        commands.append(("ALIGN", (column, 1), (column, -1), "RIGHT"))
    table.setStyle(TableStyle(commands))
    return table


def _footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(18 * mm, 9 * mm, "Documento interno não fiscal — School Manager")
    canvas.drawRightString(192 * mm, 9 * mm, f"Página {document.page}")
    canvas.restoreState()


def render_payment_receipt(payment, *, school_name="Escola") -> bytes:
    """Gera recibo confirmado ou estornado sem ocultar o histórico."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=payment.receipt_number or "Recibo financeiro",
        author=school_name,
    )
    styles = _styles()
    allocations = list(payment.allocations.select_related("billing__student"))
    student = allocations[0].billing.student if allocations else None
    story = [
        Paragraph("RECIBO INTERNO NÃO FISCAL", styles["DocumentTitle"]),
        Paragraph(school_name, styles["Heading2"]),
        Spacer(1, 2 * mm),
        _table(
            [
                ["Número", "Data do pagamento", "Forma", "Valor"],
                [
                    payment.receipt_number or "Pendente",
                    payment.paid_date.strftime("%d/%m/%Y"),
                    payment.get_payment_method_display(),
                    _money(payment.amount),
                ],
            ],
            [42 * mm, 42 * mm, 47 * mm, 43 * mm],
            alignments=(3,),
        ),
        Spacer(1, 5 * mm),
        Paragraph(f"Aluno: {student.get_full_name() if student else '—'}", styles["DocumentMeta"]),
        Spacer(1, 3 * mm),
    ]
    if payment.status == payment.Status.REVERSED:
        story.extend(
            [Paragraph("PAGAMENTO ESTORNADO", styles["DocumentNotice"]), Spacer(1, 3 * mm)]
        )
    rows = [["Cobrança", "Principal", "Multa", "Juros", "Total"]]
    for allocation in allocations:
        rows.append(
            [
                allocation.billing.description,
                _money(allocation.principal_amount),
                _money(allocation.late_fee_amount),
                _money(allocation.interest_amount),
                _money(allocation.amount),
            ]
        )
    story.append(
        _table(
            rows,
            [62 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm],
            alignments=(1, 2, 3, 4),
        )
    )
    story.extend(
        [
            Spacer(1, 8 * mm),
            Paragraph(
                "Este recibo registra uma baixa interna e não substitui documento fiscal.",
                styles["DocumentMeta"],
            ),
        ]
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def render_student_statement(student, billings, *, school_name="Escola") -> bytes:
    """Gera extrato consolidado sem notas internas ou auditoria."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Extrato financeiro",
        author=school_name,
    )
    styles = _styles()
    rows = [["Competência", "Cobrança", "Vencimento", "Situação", "Pago", "Saldo"]]
    total_paid = 0
    total_balance = 0
    for billing in billings:
        total_paid += billing.paid_value
        total_balance += billing.outstanding_value
        rows.append(
            [
                billing.competency.strftime("%m/%Y") if billing.competency else "—",
                billing.description,
                billing.due_date.strftime("%d/%m/%Y"),
                f"{billing.settlement_status_label} / {billing.due_status_label}",
                _money(billing.paid_value),
                _money(billing.outstanding_value),
            ]
        )
    rows.append(["", "Totais", "", "", _money(total_paid), _money(total_balance)])
    story = [
        Paragraph("EXTRATO FINANCEIRO", styles["DocumentTitle"]),
        Paragraph(school_name, styles["Heading2"]),
        Paragraph(f"Aluno: {student.get_full_name()}", styles["DocumentMeta"]),
        Spacer(1, 5 * mm),
        _table(
            rows,
            [24 * mm, 55 * mm, 25 * mm, 35 * mm, 26 * mm, 26 * mm],
            alignments=(4, 5),
        ),
    ]
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
