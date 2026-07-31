import asyncio
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    KeepTogether, Table, TableStyle
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

# ──────────────────────────────────────────────
# Color palette
# ──────────────────────────────────────────────
NAVY = colors.HexColor("#1a365d")
BLUE = colors.HexColor("#2b6cb0")
ACCENT = colors.HexColor("#4299e1")
TEXT = colors.HexColor("#1a202c")
MUTED = colors.HexColor("#718096")
DIVIDER = colors.HexColor("#e2e8f0")
WHITE = colors.white
LIGHT_BG = colors.HexColor("#f0f4f8")

# ──────────────────────────────────────────────
# Styles
# ──────────────────────────────────────────────
def _make_styles():
    name_style = ParagraphStyle(
        "name",
        fontName="Helvetica-Bold",
        fontSize=26,
        textColor=WHITE,
        leading=30,
        spaceAfter=2,
    )
    title_style = ParagraphStyle(
        "title",
        fontName="Helvetica",
        fontSize=12,
        textColor=colors.HexColor("#bfdbfe"),
        leading=16,
        spaceAfter=0,
    )
    contact_style = ParagraphStyle(
        "contact",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=WHITE,
        leading=13,
        alignment=TA_RIGHT,
    )
    section_header_style = ParagraphStyle(
        "section_header",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=NAVY,
        leading=12,
        spaceBefore=10,
        spaceAfter=3,
        letterSpacing=1.5,
    )
    body_style = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9.2,
        textColor=TEXT,
        leading=14,
        spaceAfter=2,
    )
    bold_body_style = ParagraphStyle(
        "bold_body",
        fontName="Helvetica-Bold",
        fontSize=9.2,
        textColor=TEXT,
        leading=14,
        spaceAfter=1,
    )
    role_style = ParagraphStyle(
        "role",
        fontName="Helvetica-BoldOblique",
        fontSize=9.2,
        textColor=BLUE,
        leading=13,
        spaceAfter=1,
    )
    bullet_style = ParagraphStyle(
        "bullet",
        fontName="Helvetica",
        fontSize=9.0,
        textColor=TEXT,
        leading=13.5,
        leftIndent=12,
        firstLineIndent=-12,
        spaceAfter=1,
    )
    skill_label_style = ParagraphStyle(
        "skill_label",
        fontName="Helvetica-Bold",
        fontSize=8.8,
        textColor=NAVY,
        leading=13,
    )
    skill_val_style = ParagraphStyle(
        "skill_val",
        fontName="Helvetica",
        fontSize=8.8,
        textColor=TEXT,
        leading=13,
    )
    muted_style = ParagraphStyle(
        "muted",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=MUTED,
        leading=12,
        spaceAfter=0,
    )
    return {
        "name": name_style,
        "title": title_style,
        "contact": contact_style,
        "section_header": section_header_style,
        "body": body_style,
        "bold_body": bold_body_style,
        "role": role_style,
        "bullet": bullet_style,
        "skill_label": skill_label_style,
        "skill_val": skill_val_style,
        "muted": muted_style,
    }


def _section_header(text: str, styles: dict) -> list:
    return [
        Paragraph(text.upper(), styles["section_header"]),
        HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=5),
    ]


def _build_header_table(cv: dict, styles: dict, content_width: float) -> Table:
    name = cv.get("name", "Your Name") or "Your Name"
    target_role = cv.get("target_role", "") or ""
    contact = cv.get("contact", {}) or {}

    left_col = [
        Paragraph(name, styles["name"]),
        Paragraph(target_role, styles["title"]),
    ]

    contact_lines = []
    if contact.get("email"):
        contact_lines.append(contact["email"])
    if contact.get("phone"):
        contact_lines.append(contact["phone"])
    if contact.get("location"):
        contact_lines.append(contact["location"])
    if contact.get("linkedin"):
        url = contact["linkedin"].replace("https://", "").replace("http://", "")
        contact_lines.append(url)
    if contact.get("github"):
        url = contact["github"].replace("https://", "").replace("http://", "")
        contact_lines.append(url)
    if contact.get("website"):
        contact_lines.append(contact["website"])

    right_col = [Paragraph("<br/>".join(contact_lines), styles["contact"])]

    table = Table(
        [[left_col, right_col]],
        colWidths=[content_width * 0.60, content_width * 0.40],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 22),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 22),
        ("LEFTPADDING", (0, 0), (0, -1), 22),
        ("RIGHTPADDING", (0, 0), (0, -1), 10),
        ("LEFTPADDING", (1, 0), (1, -1), 10),
        ("RIGHTPADDING", (1, 0), (1, -1), 22),
    ]))
    return table


def _build_summary(cv: dict, styles: dict) -> list:
    summary = cv.get("summary", "")
    if not summary:
        return []
    return [
        *_section_header("Resumen Profesional", styles),
        Paragraph(summary, styles["body"]),
        Spacer(1, 4),
    ]


def _build_experience(cv: dict, styles: dict) -> list:
    items = cv.get("experience", [])
    if not items:
        return []
    flowables = [*_section_header("Experiencia", styles)]
    for exp in items:
        company = exp.get("company", "")
        role = exp.get("role", "")
        start = exp.get("start_date", "")
        end = exp.get("end_date", "Present")
        location = exp.get("location", "")
        bullets = exp.get("bullets", [])

        date_loc = f"{start} – {end}"
        if location:
            date_loc += f"  |  {location}"

        company_table = Table(
            [[Paragraph(company, styles["bold_body"]), Paragraph(date_loc, styles["muted"])]],
            colWidths=None,
        )
        company_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        entry = [
            company_table,
            Paragraph(role, styles["role"]),
        ]
        for bullet in bullets:
            entry.append(Paragraph(f"•  {bullet}", styles["bullet"]))
        entry.append(Spacer(1, 6))
        flowables.append(KeepTogether(entry))
    return flowables


def _build_skills(cv: dict, styles: dict) -> list:
    skills = cv.get("skills", {}) or {}
    categories = {
        "Lenguajes": skills.get("languages", []),
        "Frameworks": skills.get("frameworks", []),
        "Cloud & DevOps": skills.get("cloud", []),
        "Bases de datos": skills.get("databases", []),
        "Herramientas": skills.get("tools", []),
        "Otros": skills.get("other", []),
    }
    rows = [(label, vals) for label, vals in categories.items() if vals]
    if not rows:
        return []

    flowables = [*_section_header("Habilidades Técnicas", styles)]
    for label, vals in rows:
        row_table = Table(
            [[Paragraph(label, styles["skill_label"]), Paragraph(", ".join(vals), styles["skill_val"])]],
            colWidths=["22%", "78%"],
        )
        row_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        flowables.append(row_table)
    flowables.append(Spacer(1, 4))
    return flowables


def _build_education(cv: dict, styles: dict) -> list:
    items = cv.get("education", [])
    if not items:
        return []
    flowables = [*_section_header("Educación", styles)]
    for edu in items:
        institution = edu.get("institution", "")
        degree = edu.get("degree", "")
        field = edu.get("field", "")
        year = edu.get("year", "")
        degree_str = degree
        if field:
            degree_str += f" en {field}"

        edu_table = Table(
            [[Paragraph(degree_str, styles["bold_body"]), Paragraph(year, styles["muted"])]],
            colWidths=None,
        )
        edu_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        flowables.append(edu_table)
        flowables.append(Paragraph(institution, styles["role"]))
        flowables.append(Spacer(1, 5))
    return flowables


def _build_projects(cv: dict, styles: dict) -> list:
    items = cv.get("projects", [])
    if not items:
        return []
    flowables = [*_section_header("Proyectos", styles)]
    for proj in items:
        name = proj.get("name", "")
        description = proj.get("description", "")
        techs = proj.get("technologies", [])
        url = proj.get("url", "")
        highlights = proj.get("highlights", [])

        entry = [Paragraph(name, styles["bold_body"])]
        if description:
            entry.append(Paragraph(description, styles["body"]))
        if techs:
            entry.append(Paragraph(f"<i>Stack: {', '.join(techs)}</i>", styles["muted"]))
        for h in highlights:
            entry.append(Paragraph(f"•  {h}", styles["bullet"]))
        if url:
            entry.append(Paragraph(url, styles["muted"]))
        entry.append(Spacer(1, 5))
        flowables.append(KeepTogether(entry))
    return flowables


def _build_certifications(cv: dict, styles: dict) -> list:
    items = cv.get("certifications", [])
    if not items:
        return []
    flowables = [*_section_header("Certificaciones", styles)]
    for cert in items:
        name = cert.get("name", "")
        issuer = cert.get("issuer", "")
        year = cert.get("year", "")
        line = name
        if issuer:
            line += f" — {issuer}"
        if year:
            line += f" ({year})"
        flowables.append(Paragraph(line, styles["body"]))
    flowables.append(Spacer(1, 4))
    return flowables


def _generate_pdf_sync(cv_data: dict) -> bytes:
    buffer = io.BytesIO()
    page_width = A4[0]
    inner_margin = 2 * cm
    content_width = page_width - 2 * inner_margin

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=inner_margin,
        rightMargin=inner_margin,
        topMargin=0,
        bottomMargin=2 * cm,
    )

    styles = _make_styles()
    story = []

    header = _build_header_table(cv_data, styles, content_width)
    story.append(header)
    story.append(Spacer(1, 0.5 * cm))

    # Body sections with margins via a wrapper table
    story.extend(_build_summary(cv_data, styles))
    story.extend(_build_experience(cv_data, styles))
    story.extend(_build_skills(cv_data, styles))
    story.extend(_build_education(cv_data, styles))
    story.extend(_build_projects(cv_data, styles))
    story.extend(_build_certifications(cv_data, styles))

    doc.build(story)
    return buffer.getvalue()


async def generate_cv_pdf(cv_data: dict) -> bytes:
    return await asyncio.to_thread(_generate_pdf_sync, cv_data)
