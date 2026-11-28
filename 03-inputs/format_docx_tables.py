"""Give every table in the rendered document one consistent shape.

WHY THIS IS A SEPARATE PASS. Quarto writes the document through pandoc, and
pandoc sizes tables to their content and leaves row heights to Word's defaults.
The result is 35 tables at 35 different widths, which reads as a pile of
fragments rather than one report. Word's own table styles cannot fix it either,
because the reference document's style is applied before the content is known.

So this runs after the render, the same way the 8pt code pass did, and it is
the only place table geometry is decided.

WHAT IT SETS. Operator instruction, 2026-09-07.

  width        every table spans the full text column, expressed as 100 per cent
               rather than a fixed measurement so it survives a page-size or
               margin change in the reference document.
  header row   1 cm tall and bold.
  body rows    0.7 cm tall, as a MINIMUM. A cell whose text needs two lines
               grows to fit rather than clipping, which is what "unless more is
               needed" means and why the rule is AT_LEAST rather than EXACTLY.

    .venv/bin/python 03-inputs/format_docx_tables.py 02-runtime/trader-workflow.docx
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt

HEADER_CM = 1.0
BODY_CM = 0.7


def _full_width(table) -> None:
    """Make the table span the whole text column.

    Set as a percentage of the available width rather than a fixed number of
    centimetres, so it still fills the page if the reference document's margins
    or paper size ever change. Autofit is turned off first, because Word ignores
    an explicit width while it is on.
    """
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblPr = table._tbl.tblPr
    for existing in tblPr.findall(qn("w:tblW")):
        tblPr.remove(existing)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:type"), "pct")
    tblW.set(qn("w:w"), "5000")          # fifths of a per cent, so 5000 = 100%
    tblPr.append(tblW)

    # Cell widths must agree with the table, or Word re-derives them from content.
    if table.rows:
        share = int(5000 / len(table.columns))
        for row in table.rows:
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                for existing in tcPr.findall(qn("w:tcW")):
                    tcPr.remove(existing)
                tcW = OxmlElement("w:tcW")
                tcW.set(qn("w:type"), "pct")
                tcW.set(qn("w:w"), str(share))
                tcPr.append(tcW)


def _row_height(row, cm: float) -> None:
    """Set a minimum height, so a wrapped cell grows instead of clipping."""
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    row.height = Cm(cm)


def _bold_header(row) -> None:
    """Bold every run in the header row, adding one where a cell has no runs.

    A cell can hold text with no run objects when pandoc writes it, and setting
    bold on nothing does nothing, so the empty case is handled rather than
    silently skipped.
    """
    for cell in row.cells:
        for para in cell.paragraphs:
            if not para.runs and para.text:
                para.add_run(para.text)
                for child in list(para._p):
                    if child.tag == qn("w:r") and child is not para.runs[-1]._r:
                        continue
            for run in para.runs:
                run.font.bold = True


# Type size by column count. A table is set to the full text column, so the width
# per column falls as columns are added and at some point the header no longer fits
# on one line. Added 2026-09-08: the widest tables in this document were rendering
# as a column of broken single characters. The thresholds are the points at which a
# typical header in this document stops fitting, measured on the rendered file.
FONT_BY_COLS = ((5, None), (8, Pt(8)), (12, Pt(7)), (99, Pt(6)))


def _fit_type(table, n_cols: int) -> int:
    """Shrink the type in a wide table until its headers fit. Returns the size in
    points, or 0 where the table was left at the document default."""
    size = next(sz for lim, sz in FONT_BY_COLS if n_cols <= lim)
    if size is None:
        return 0
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = size
    return size.pt


def _tight_margins(table) -> None:
    """Narrow the cell padding, which is fixed by the style and costs a wide table
    more width than its content does."""
    tblPr = table._tbl.tblPr
    for tag in ("w:tblCellMar",):
        for el in tblPr.findall(qn(tag)):
            tblPr.remove(el)
    mar = OxmlElement("w:tblCellMar")
    for side, twips in (("left", "43"), ("right", "43")):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), twips)
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def format_tables(path: Path) -> dict:
    doc = Document(str(path))
    rows_set = 0
    shrunk = 0
    widest = 0
    for table in doc.tables:
        n_cols = len(table.columns)
        widest = max(widest, n_cols)
        _full_width(table)
        if n_cols > 5:
            _tight_margins(table)
        if _fit_type(table, n_cols):
            shrunk += 1
        for i, row in enumerate(table.rows):
            _row_height(row, HEADER_CM if i == 0 else BODY_CM)
            rows_set += 1
        if table.rows:
            _bold_header(table.rows[0])
    doc.save(str(path))
    return dict(tables=len(doc.tables), rows=rows_set, shrunk=shrunk, widest=widest)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"no such file: {path}")
        return 1
    r = format_tables(path)
    print(f"{path.name}: {r['tables']} tables, {r['rows']} rows, widest {r['widest']} columns. "
          f"Full width, header {HEADER_CM}cm bold, body {BODY_CM}cm minimum, "
          f"{r['shrunk']} wide tables set in smaller type.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
