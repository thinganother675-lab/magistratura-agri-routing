"""Read-only verification of the exported workbook with Python's standard library."""
from pathlib import Path
import json
import zipfile
import xml.etree.ElementTree as ET

folder = Path(__file__).resolve().parent
ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
with zipfile.ZipFile(folder / "home_pc_models_20261001.xlsx") as book:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    names = [s.attrib["name"] for s in workbook.findall("s:sheets/s:sheet", ns)]
    assert names == ["Итоги", "Все прогоны"], names
    shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
    strings = ["".join(n.itertext()) for n in shared.findall("s:si", ns)]
    sheets = [ET.fromstring(book.read(f"xl/worksheets/sheet{i}.xml")) for i in (1, 2)]
    def cell(sheet, address):
        element = sheet.find(f'.//s:c[@r="{address}"]', ns)
        assert element is not None, address
        value = element.find("s:v", ns)
        if element.attrib.get("t") == "s":
            return strings[int(value.text)]
        if element.attrib.get("t") == "inlineStr":
            return "".join(element.find("s:is", ns).itertext())
        if element.attrib.get("t") == "str":
            return value.text
        return None if value is None else float(value.text)
    assert cell(sheets[0], "B4") == 14
    assert cell(sheets[0], "C23") == 0
    assert cell(sheets[0], "E23") == "NOT RUN"
    assert cell(sheets[0], "F23") == "UNKNOWN"
    assert cell(sheets[1], "B4") == 339
    assert cell(sheets[1], "B5") == 135133
    assert cell(sheets[1], "B6") == 39087
    errors = []
    panes = []
    formula_counts = []
    for i, sheet in enumerate(sheets):
        errors.extend((names[i], c.attrib["r"]) for c in sheet.findall('.//s:c[@t="e"]', ns))
        pane = sheet.find("s:sheetViews/s:sheetView/s:pane", ns)
        assert pane is not None, names[i]
        assert pane.attrib.get("ySplit") == "8", pane.attrib
        assert pane.attrib.get("xSplit") == "2", pane.attrib
        assert pane.attrib.get("state") == "frozen", pane.attrib
        panes.append(pane.attrib)
        formula_counts.append(len(sheet.findall(".//s:f", ns)))
    assert not errors, errors
    table_ranges = []
    for name in sorted(n for n in book.namelist() if n.startswith("xl/tables/table") and n.endswith(".xml")):
        table = ET.fromstring(book.read(name))
        table_ranges.append(table.attrib["ref"])
        assert table.find("s:autoFilter", ns) is not None, name
    assert table_ranges == ["A8:Y23", "A8:AB33"], table_ranges
    result = {
        "sheets": names,
        "freezePanes": panes,
        "filterTableRanges": table_ranges,
        "formulaCounts": formula_counts,
        "formulaErrorCells": errors,
        "cachedTotals": {"requests": 339, "inputKnown": 135133, "outputKnown": 39087},
        "unknownAndNotRunPreserved": True,
        "nativeExcelApplicationOpened": False,
    }
    (folder / "native_xlsx_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
