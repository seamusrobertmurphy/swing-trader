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
from docx.shared import Cm

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


def format_tables(path: Path) -> dict:
    doc = Document(str(path))
    rows_set = 0
    for table in doc.tables:
        _full_width(table)
        for i, row in enumerate(table.rows):
            _row_height(row, HEADER_CM if i == 0 else BODY_CM)
            rows_set += 1
        if table.rows:
            _bold_header(table.rows[0])
    doc.save(str(path))
    return dict(tables=len(doc.tables), rows=rows_set)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"no such file: {path}")
        return 1
    r = format_tables(path)
    print(f"{path.name}: {r['tables']} tables, {r['rows']} rows. "
          f"Full width, header {HEADER_CM}cm bold, body {BODY_CM}cm minimum.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
