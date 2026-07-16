from __future__ import annotations

import argparse
import atexit
from html import escape
import hashlib
from pathlib import Path
import re
import shutil
import tempfile

from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import math_to_image
from PIL import Image as PillowImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from classcorpus.math_notation import (
    group_math_lines,
    looks_like_display_math,
    normalize_inline_math,
    normalize_math_expression,
    strip_display_math_delimiters,
)

PAGE_LABEL = "STUDY GUIDE"
FOOTER_LABEL = "COURSE MATERIALS"

INK = colors.HexColor("#17212B")
NAVY = colors.HexColor("#183B56")
TEAL = colors.HexColor("#147D92")
AMBER = colors.HexColor("#D99A20")
PALE_BLUE = colors.HexColor("#EAF4F7")
PALE_AMBER = colors.HexColor("#FFF5DC")
MUTED = colors.HexColor("#5B6872")
RULE = colors.HexColor("#CBD7DD")
WHITE = colors.white
MATH_ASSET_DIR = Path(tempfile.mkdtemp(prefix="classcorpus-math-"))
atexit.register(shutil.rmtree, MATH_ASSET_DIR, ignore_errors=True)


def register_math_font() -> str:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/STIXTwoText.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            pdfmetrics.registerFont(TTFont("StudyMath", str(path)))
            return "StudyMath"
    return "Helvetica"


MATH_FONT = register_math_font()


def inline_markup(text: str) -> str:
    value = escape(text)
    value = re.sub(r"`([^`]+)`", _inline_code_markup, value)
    value = re.sub(
        r"(?<!\$)\$([^$\n]+)\$(?!\$)",
        _inline_code_markup,
        value,
    )
    value = re.sub(r"\\\((.+?)\\\)", _inline_code_markup, value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return value


def _inline_code_markup(match: re.Match[str]) -> str:
    value = match.group(1)
    looks_mathematical = (
        any(
            symbol in value
            for symbol in (
                "=",
                "^",
                "_",
                "\\",
                "/",
                "(",
                ")",
                "&lt;",
                "&gt;",
            )
        )
        or "\\" in value
        or any(
            re.search(rf"(?<![A-Za-z]){name}(?![A-Za-z])", value)
            for name in (
                "alpha",
                "beta",
                "gamma",
                "lambda",
                "theta",
                "sigma",
            )
        )
        or bool(re.search(r"\d", value) and re.search(r"[A-Za-z/]", value))
        or bool(re.fullmatch(r"[A-Za-z]", value))
    )
    if not looks_mathematical:
        return f'<font name="Courier">{value}</font>'
    value = normalize_inline_math(value)
    value = re.sub(r"\^\{([^}]+)\}", r"<super>\1</super>", value)
    value = re.sub(r"\^\(([^)]+)\)", r"<super>\1</super>", value)
    value = re.sub(r"\^([+-]?[0-9]+)", r"<super>\1</super>", value)
    value = re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", value)
    value = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", value)
    return f'<font name="{MATH_FONT}">{value}</font>'


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GuideTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=27,
            leading=31,
            textColor=WHITE,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#DDECF1"),
        ),
        "h1": ParagraphStyle(
            "Section",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=NAVY,
            spaceBefore=13,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "Subsection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=TEAL,
            spaceBefore=9,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.6,
            leading=13.5,
            textColor=INK,
            spaceAfter=6,
        ),
        "citation": ParagraphStyle(
            "Citation",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=7.4,
            leading=10,
            textColor=MUTED,
            leftIndent=10,
            borderColor=TEAL,
            borderWidth=0,
            borderPadding=0,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=13,
            textColor=INK,
        ),
        "code": ParagraphStyle(
            "Formula",
            parent=base["Code"],
            fontName="Courier",
            fontSize=9,
            leading=13,
            textColor=NAVY,
            backColor=PALE_BLUE,
            borderColor=colors.HexColor("#B7D9E1"),
            borderWidth=0.7,
            borderPadding=8,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "math": ParagraphStyle(
            "Math",
            parent=base["BodyText"],
            fontName=MATH_FONT,
            fontSize=13,
            leading=22,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
    }


def cover(
    st: dict[str, ParagraphStyle],
    *,
    title: str,
    subtitle: str,
    course_label: str,
    stats_values: list[str],
) -> list:
    title_block = Table(
        [
            [Paragraph(inline_markup(course_label), st["subtitle"])],
            [Paragraph(inline_markup(title), st["title"])],
            [Paragraph(inline_markup(subtitle), st["subtitle"])],
        ],
        colWidths=[7.2 * inch],
    )
    title_block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("BOX", (0, 0), (-1, -1), 0, NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 24),
                ("RIGHTPADDING", (0, 0), (-1, -1), 24),
                ("TOPPADDING", (0, 0), (-1, 0), 20),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 24),
            ]
        )
    )
    stats = Table(
        [
            [
                Paragraph(inline_markup(value), st["cover_meta"])
                for value in stats_values
            ]
        ],
        colWidths=[6.9 * inch / len(stats_values)] * len(stats_values),
    )
    stats.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_AMBER),
                ("BOX", (0, 0), (-1, -1), 0.8, AMBER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, AMBER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return [
        Spacer(1, 0.45 * inch),
        title_block,
        Spacer(1, 0.32 * inch),
        stats,
        Spacer(1, 0.4 * inch),
        Paragraph(
            "A compact, evidence-grounded review with formulas, graph rules, "
            "problem-solving methods, common traps, and a checked answer key.",
            st["body"],
        ),
        Spacer(1, 0.18 * inch),
        HRFlowable(width="100%", thickness=1, color=RULE),
        Spacer(1, 0.18 * inch),
        Paragraph(
            "Keep course-specific claims tied to their lecture and page citations. "
            "Disclose incomplete extraction or visual coverage in the review notes.",
            st["small"],
        ),
        PageBreak(),
    ]


def math_markup(text: str) -> str:
    value = escape(text.strip())
    replacements = {
        "Delta": "Δ",
        "theta": "θ",
        " degrees": "°",
        "(1/2)": "½",
        "&lt;": "(",
        "&gt;": ")",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"sqrt\((.*)\)", r"(\1)^(1/2)", value)
    value = re.sub(r"\^\(([^)]+)\)", r"<super>\1</super>", value)
    value = re.sub(r"\^([0-9]+)", r"<super>\1</super>", value)
    value = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", value)
    return value


def math_block(lines: list[str], st: dict[str, ParagraphStyle]):
    rows = []
    for line in group_math_lines(lines):
        if not line.strip():
            rows.append([Spacer(1, 3)])
            continue
        try:
            expression = normalize_math_expression(line)
            digest = hashlib.sha256(expression.encode("utf-8")).hexdigest()[:16]
            path = MATH_ASSET_DIR / f"{digest}.png"
            math_to_image(
                f"${expression}$",
                path,
                dpi=220,
                format="png",
                prop=FontProperties(size=12.5),
                color="#183B56",
            )
        except ValueError:
            rows.append([Paragraph(math_markup(line), st["math"])])
            continue
        with PillowImage.open(path).convert("RGBA") as rendered:
            pixel_data = getattr(
                rendered,
                "get_flattened_data",
                rendered.getdata,
            )()
            pixels = [
                (
                    (234, 244, 247, 255)
                    if alpha < 250 or min(red, green, blue) > 225
                    else (red, green, blue, alpha)
                )
                for red, green, blue, alpha in pixel_data
            ]
            rendered.putdata(pixels)
            rendered.convert("RGB").save(path)
        image = Image(str(path))
        width = image.imageWidth * 72 / 220
        height = image.imageHeight * 72 / 220
        if width > 6.1 * inch:
            height *= (6.1 * inch) / width
            width = 6.1 * inch
        image.drawWidth = width
        image.drawHeight = height
        rows.append([image])
    table = Table(rows, colWidths=[6.75 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#B7D9E1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def flush_paragraph(lines: list[str], story: list, st: dict[str, ParagraphStyle]) -> None:
    if not lines:
        return
    text = " ".join(line.strip() for line in lines)
    style = st["citation"] if text.startswith("[Physics,") else st["body"]
    story.append(Paragraph(inline_markup(text), style))
    lines.clear()


def flush_list(
    items: list[str],
    story: list,
    st: dict[str, ParagraphStyle],
    *,
    ordered: bool,
) -> None:
    if not items:
        return
    flow_items = [
        ListItem(
            Paragraph(inline_markup(item), st["bullet"]),
            leftIndent=14,
        )
        for item in items
    ]
    list_arguments = {
        "bulletType": "1" if ordered else "bullet",
        "leftIndent": 20,
        "bulletFontName": "Helvetica-Bold",
        "bulletFontSize": 8,
        "bulletColor": TEAL,
        "spaceAfter": 7,
    }
    if ordered:
        list_arguments["start"] = "1"
    else:
        list_arguments["start"] = "circle"
    story.append(ListFlowable(flow_items, **list_arguments))
    items.clear()


def markdown_story(text: str, st: dict[str, ParagraphStyle]) -> list:
    story: list = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_ordered = False
    code_lines: list[str] = []
    code_language = ""
    table_lines: list[str] = []
    in_code = False
    math_fence_end = ""

    def flush_all() -> None:
        nonlocal table_lines
        flush_paragraph(paragraph, story, st)
        flush_list(list_items, story, st, ordered=list_ordered)
        if table_lines:
            rows = [
                [cell.strip() for cell in line.strip().strip("|").split("|")]
                for line in table_lines
                if not re.match(r"^\|?[\s|:-]+\|?$", line)
            ]
            data = [
                [Paragraph(inline_markup(cell), st["small"]) for cell in row]
                for row in rows
            ]
            table = Table(data, colWidths=[1.55 * inch, 1.55 * inch, 3.7 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE_BLUE]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 7))
            table_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not in_code and stripped in {"$$", r"\["}:
            flush_all()
            code_language = "math"
            math_fence_end = "$$" if stripped == "$$" else r"\]"
            in_code = True
            continue
        if in_code and math_fence_end and stripped == math_fence_end:
            story.append(math_block(code_lines, st))
            story.append(Spacer(1, 8))
            code_lines.clear()
            code_language = ""
            math_fence_end = ""
            in_code = False
            continue
        if in_code and math_fence_end:
            code_lines.append(line)
            continue
        if line.startswith("```"):
            if in_code:
                if code_language == "math":
                    story.append(math_block(code_lines, st))
                    story.append(Spacer(1, 8))
                else:
                    story.append(Preformatted("\n".join(code_lines), st["code"]))
                code_lines.clear()
                code_language = ""
                math_fence_end = ""
                in_code = False
            else:
                flush_all()
                code_language = line[3:].strip()
                math_fence_end = ""
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("|"):
            flush_paragraph(paragraph, story, st)
            flush_list(list_items, story, st, ordered=list_ordered)
            table_lines.append(line)
            continue
        if table_lines and not line.startswith("|"):
            flush_all()
        if not line:
            flush_all()
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_all()
            story.append(Paragraph(inline_markup(line[3:]), st["h1"]))
            story.append(HRFlowable(width="100%", thickness=0.8, color=RULE))
            continue
        if line.startswith("### "):
            flush_all()
            story.append(Paragraph(inline_markup(line[4:]), st["h2"]))
            continue
        if looks_like_display_math(line):
            flush_all()
            story.append(
                math_block([strip_display_math_delimiters(line)], st)
            )
            story.append(Spacer(1, 8))
            continue
        unordered = re.match(r"^- (.+)$", line)
        ordered = re.match(r"^\d+\. (.+)$", line)
        if unordered or ordered:
            flush_paragraph(paragraph, story, st)
            is_ordered = ordered is not None
            if list_items and is_ordered != list_ordered:
                flush_list(list_items, story, st, ordered=list_ordered)
            list_ordered = is_ordered
            list_items.append((ordered or unordered).group(1))
            continue
        if list_items and line.startswith("  "):
            list_items[-1] += " " + line.strip()
            continue
        flush_list(list_items, story, st, ordered=list_ordered)
        paragraph.append(line)

    flush_all()
    return story


def page_decor(canvas, doc) -> None:
    canvas.saveState()
    width, height = letter
    if doc.page > 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 0.32 * inch, width, 0.32 * inch, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(0.65 * inch, height - 0.21 * inch, PAGE_LABEL)
    canvas.setStrokeColor(RULE)
    canvas.line(0.65 * inch, 0.47 * inch, width - 0.65 * inch, 0.47 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(0.65 * inch, 0.29 * inch, FOOTER_LABEL)
    canvas.drawRightString(width - 0.65 * inch, 0.29 * inch, f"Page {doc.page}")
    canvas.restoreState()


def main() -> None:
    global FOOTER_LABEL, PAGE_LABEL
    parser = argparse.ArgumentParser(
        description="Render a cited Markdown study guide as a polished PDF."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="Study Guide")
    parser.add_argument("--subtitle", default="Evidence-grounded course review")
    parser.add_argument("--course-label", default="COURSE")
    parser.add_argument(
        "--stat",
        action="append",
        default=[],
        help="Cover statistic; repeat up to three times.",
    )
    arguments = parser.parse_args()
    stats_values = arguments.stat or ["Cited concepts", "Formula review", "Practice set"]
    if len(stats_values) > 3:
        parser.error("--stat may be repeated at most three times")
    PAGE_LABEL = f"{arguments.course_label} STUDY GUIDE".upper()
    FOOTER_LABEL = arguments.course_label.upper()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)

    st = styles()
    document = SimpleDocTemplate(
        str(arguments.output),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.62 * inch,
        title=f"{arguments.course_label} {arguments.title}",
        author="ClassCorpus",
        subject="Evidence-grounded course study guide",
    )
    source_text = arguments.source.read_text(encoding="utf-8")
    story = cover(
        st,
        title=arguments.title,
        subtitle=arguments.subtitle,
        course_label=arguments.course_label,
        stats_values=stats_values,
    )
    story.extend(markdown_story(source_text, st))
    document.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    print(arguments.output.resolve())


if __name__ == "__main__":
    main()
