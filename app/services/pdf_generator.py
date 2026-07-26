import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPORTS_DIR = "generated_reports"


def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=30,
            spaceAfter=20,
            textColor=colors.HexColor("#1a365d"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading1"],
            fontSize=16,
            leading=22,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor("#2b6cb0"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeader",
            parent=styles["Heading2"],
            fontSize=13,
            leading=18,
            spaceBefore=15,
            spaceAfter=8,
            textColor=colors.HexColor("#2d3748"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="StatLabel",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#4a5568"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="StatValue",
            parent=styles["Normal"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1a202c"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#a0aec0"),
            alignment=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
        )
    )
    return styles


def _build_summary_table(stats: dict, styles) -> list:
    data = [
        [
            Paragraph("Metric", styles["TableCell"]),
            Paragraph("Value", styles["TableCell"]),
        ],
        [
            Paragraph("Total Tasks", styles["TableCell"]),
            Paragraph(str(stats.get("total", 0)), styles["TableCell"]),
        ],
        [
            Paragraph("Completed Tasks", styles["TableCell"]),
            Paragraph(str(stats.get("done", 0)), styles["TableCell"]),
        ],
        [
            Paragraph("Pending Tasks", styles["TableCell"]),
            Paragraph(str(stats.get("not_done", 0)), styles["TableCell"]),
        ],
        [
            Paragraph("Completion Rate", styles["TableCell"]),
            Paragraph(f"{stats.get('completion_pct', 0):.1f}%", styles["TableCell"]),
        ],
    ]

    table = Table(data, colWidths=[3 * inch, 2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#edf2f7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.HexColor("#edf2f7"), colors.white],
                ),
            ]
        )
    )
    return [Spacer(1, 10), table]


def _build_scraped_books_section(books_stats: dict | None, styles) -> list:
    elements = []
    elements.append(Paragraph("Scraped Books Statistics", styles["SectionHeader"]))
    if books_stats:
        data = [
            [
                Paragraph("Metric", styles["TableCell"]),
                Paragraph("Value", styles["TableCell"]),
            ],
            [
                Paragraph("Total Books Scraped", styles["TableCell"]),
                Paragraph(str(books_stats.get("total", 0)), styles["TableCell"]),
            ],
        ]
        if books_stats.get("avg_price"):
            data.append(
                [
                    Paragraph("Average Price", styles["TableCell"]),
                    Paragraph(f"${books_stats['avg_price']:.2f}", styles["TableCell"]),
                ]
            )
        if books_stats.get("categories"):
            data.append(
                [
                    Paragraph("Categories", styles["TableCell"]),
                    Paragraph(str(books_stats.get("categories")), styles["TableCell"]),
                ]
            )
        table = Table(data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#edf2f7"), colors.white],
                    ),
                ]
            )
        )
        elements.append(Spacer(1, 10))
        elements.append(table)
    else:
        elements.append(
            Paragraph("No scraped book data available.", styles["StatLabel"])
        )
    return elements


def _build_ai_jobs_section(ai_stats: dict | None, styles) -> list:
    elements = []
    elements.append(Paragraph("AI Job Statistics", styles["SectionHeader"]))
    if ai_stats:
        data = [
            [
                Paragraph("Metric", styles["TableCell"]),
                Paragraph("Value", styles["TableCell"]),
            ],
            [
                Paragraph("Total AI Jobs", styles["TableCell"]),
                Paragraph(str(ai_stats.get("total", 0)), styles["TableCell"]),
            ],
            [
                Paragraph("Completed Jobs", styles["TableCell"]),
                Paragraph(str(ai_stats.get("completed", 0)), styles["TableCell"]),
            ],
            [
                Paragraph("Failed Jobs", styles["TableCell"]),
                Paragraph(str(ai_stats.get("failed", 0)), styles["TableCell"]),
            ],
        ]
        table = Table(data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#edf2f7"), colors.white],
                    ),
                ]
            )
        )
        elements.append(Spacer(1, 10))
        elements.append(table)
    else:
        elements.append(Paragraph("No AI job data available.", styles["StatLabel"]))
    return elements


def generate_report(
    job_id: str,
    stats: dict,
    books_stats: dict | None,
    ai_stats: dict | None,
) -> str:
    _ensure_reports_dir()
    styles = _build_styles()

    filename = f"report_{job_id}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    elements = []

    elements.append(Paragraph("FlyRank System Report", styles["ReportTitle"]))
    elements.append(Paragraph(f"Generated: {now}", styles["StatLabel"]))
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("Executive Summary", styles["SectionHeader"]))
    total = stats.get("total", 0)
    done = stats.get("done", 0)
    pct = stats.get("completion_pct", 0)
    elements.append(
        Paragraph(
            f"This report provides an overview of the FlyRank system. "
            f"Out of <b>{total}</b> total tasks, <b>{done}</b> are completed "
            f"({pct:.1f}%). The system is tracking task progress, scraped book data, "
            f"and AI job execution statistics.",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Task Summary", styles["SectionHeader"]))
    elements.extend(_build_summary_table(stats, styles))

    elements.append(Spacer(1, 15))

    if stats.get("recent_tasks"):
        elements.append(Paragraph("Recent Tasks", styles["SubHeader"]))
        recent_data = [
            [
                Paragraph("ID", styles["TableCell"]),
                Paragraph("Title", styles["TableCell"]),
                Paragraph("Status", styles["TableCell"]),
            ]
        ]
        for task in stats["recent_tasks"]:
            recent_data.append(
                [
                    Paragraph(str(task.get("id", "")), styles["TableCell"]),
                    Paragraph(str(task.get("title", "")), styles["TableCell"]),
                    Paragraph(
                        "Done" if task.get("done") else "Pending", styles["TableCell"]
                    ),
                ]
            )
        recent_table = Table(recent_data, colWidths=[0.5 * inch, 3 * inch, 1 * inch])
        recent_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.HexColor("#edf2f7"), colors.white],
                    ),
                ]
            )
        )
        elements.append(Spacer(1, 5))
        elements.append(recent_table)

    elements.append(PageBreak())

    elements.extend(_build_scraped_books_section(books_stats, styles))

    elements.append(Spacer(1, 15))

    elements.extend(_build_ai_jobs_section(ai_stats, styles))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Background Job Summary", styles["SectionHeader"]))
    elements.append(
        Paragraph(
            f"Report generated via background job <b>{job_id}</b>. "
            f"The report was produced asynchronously using RQ (Redis Queue) "
            f"and the dedicated report worker process.",
            styles["Normal"],
        )
    )

    elements.append(Spacer(1, 30))

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#a0aec0"))
        canvas.drawCentredString(
            A4[0] / 2,
            10 * mm,
            f"FlyRank System Report | Generated {now} | Job ID: {job_id} | Page {doc.page}",
        )
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    return filepath
