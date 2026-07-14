from pathlib import Path

import fitz
from pptx import Presentation
from pptx.util import Inches


def make_pdf_fixture(path: Path) -> Path:
    document = fitz.open()
    pages = [
        ("Shortest Paths", "Dijkstra handles non-negative edge weights."),
        ("Dynamic Programming", "Bellman-Ford handles negative edges."),
    ]

    for title, body in pages:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 96), title, fontsize=24)
        page.insert_text((72, 144), body, fontsize=14)

    document.save(path)
    document.close()
    return path


def make_pptx_fixture(path: Path) -> Path:
    presentation = Presentation()

    slide_1 = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide_1.shapes.title.text = "Recurrences"
    textbox_1 = slide_1.shapes.add_textbox(Inches(1), Inches(1.5), Inches(5), Inches(1))
    textbox_1.text_frame.text = "Divide-and-conquer recurrence trees."

    slide_2 = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide_2.shapes.title.text = "Dynamic Programming"
    textbox_2 = slide_2.shapes.add_textbox(Inches(1), Inches(1.5), Inches(5), Inches(1))
    textbox_2.text_frame.text = "Memoization avoids repeated subproblems."
    table = slide_2.shapes.add_table(2, 2, Inches(1), Inches(2.4), Inches(5), Inches(1.2)).table
    table.cell(0, 0).text = "Problem"
    table.cell(0, 1).text = "State"
    table.cell(1, 0).text = "Fibonacci"
    table.cell(1, 1).text = "n"
    slide_2.notes_slide.notes_text_frame.text = "Use Fibonacci as the example."

    presentation.save(path)
    return path
