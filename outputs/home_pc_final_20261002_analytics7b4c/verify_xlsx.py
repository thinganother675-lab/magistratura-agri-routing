"""Read-only verification of the exported XLSX using Python's standard library."""
from pathlib import Path
import json
import math
import zipfile
import xml.etree.ElementTree as ET

folder = Path(__file__).resolve().parent
validation = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(folder / 'home_pc_models_final150_20261002.xlsx') as book:
    workbook = ET.fromstring(book.read('xl/workbook.xml'))
    names = [s.attrib['name'] for s in workbook.findall('s:sheets/s:sheet', ns)]
    assert names == ['Модели DEV', 'FINAL150', 'Все серии'], names
    shared = ET.fromstring(book.read('xl/sharedStrings.xml'))
    strings = [''.join(n.itertext()) for n in shared.findall('s:si', ns)]
    sheets = [ET.fromstring(book.read(f'xl/worksheets/sheet{i}.xml')) for i in (1, 2, 3)]
    def cell(sheet, address):
        element = sheet.find(f'.//s:c[@r="{address}"]', ns)
        assert element is not None, address
        value = element.find('s:v', ns)
        if element.attrib.get('t') == 's':
            return strings[int(value.text)]
        if element.attrib.get('t') == 'inlineStr':
            return ''.join(element.find('s:is', ns).itertext())
        if element.attrib.get('t') == 'str':
            return value.text
        return None if value is None else float(value.text)
    for address, expected in {'B4': 242, 'E4': 113332, 'H4': 17259, 'K4': 9083,
                              'B5': 339, 'E5': 135133, 'H5': 39087}.items():
        assert cell(sheets[2], address) == expected, (address, expected)
    # Two API models never ran. Missing counters remain text, not zero.
    for row in (22, 23):
        assert cell(sheets[0], f'C{row}') == 0
        assert cell(sheets[0], f'E{row}') == 'NOT RUN'
        assert cell(sheets[0], f'G{row}') == 'UNKNOWN'
    assert cell(sheets[0], 'A24') == 'mercury-2.5'
    assert cell(sheets[0], 'C24') == 36
    assert cell(sheets[0], 'E24') == .75
    assert cell(sheets[0], 'S24') == 'N/A'
    assert cell(sheets[0], 'R9') == 33.53
    assert cell(sheets[0], 'R10') == 13.545
    assert cell(sheets[0], 'Q9') == 'UNKNOWN'
    assert not math.isclose(cell(sheets[0], 'P9'), cell(sheets[0], 'R9'))
    for row in range(9, 14):
        measured = cell(sheets[1], f'D{row}')
        quality = cell(sheets[1], f'G{row}')
        correct = cell(sheets[1], f'F{row}')
        assert quality == (correct / measured if measured else 'NOT RUN')
        assert cell(sheets[1], f'C{row}') == 150
        assert measured == 150
        assert cell(sheets[1], f'E{row}') == 1
    assert [cell(sheets[1], f'F{r}') for r in range(9, 14)] == [102, 130, 139, 133, 114]
    assert cell(sheets[1], 'Q22') == 'UNKNOWN'  # incomplete billed usage
    assert cell(sheets[1], 'Q24') == 'UNKNOWN'
    assert math.isclose(cell(sheets[1], 'Q26'), .005275933333333333)
    assert sum(cell(sheets[1], f'C{r}') for r in (19, 21, 23, 25, 27)) == 310
    assert sum(cell(sheets[1], f'C{r}') for r in (20, 22, 24, 26, 28)) == 270
    assert sum(cell(sheets[1], f'P{r}') for r in (20, 22, 24, 26, 28)) == 12
    assert math.isclose(sum(cell(sheets[1], f'N{r}') for r in (20, 22, 24, 26, 28)), .01234546)
    assert cell(sheets[1], 'B35') == 13758
    assert math.isclose(cell(sheets[1], 'C35'), 13758 / 1024)
    assert cell(sheets[1], 'F35') == 'UNKNOWN'
    assert cell(sheets[1], 'C53') == 30
    assert cell(sheets[1], 'C54') == 720
    assert math.isclose(cell(sheets[1], 'B53'), 14.77836)
    assert math.isclose(cell(sheets[1], 'B54'), 8.7673739)
    assert 'WinError5' in cell(sheets[1], 'D53')
    assert '998.585' in cell(sheets[1], 'A58')
    assert '2 сегмента после WinError5' in cell(sheets[1], 'A3')
    assert '258/270' in cell(sheets[1], 'A7')
    errors, panes = [], []
    for i, sheet in enumerate(sheets):
        errors.extend((names[i], c.attrib['r']) for c in sheet.findall('.//s:c[@t="e"]', ns))
        pane = sheet.find('s:sheetViews/s:sheetView/s:pane', ns)
        assert pane is not None, names[i]
        assert pane.attrib.get('ySplit') == '8', pane.attrib
        assert pane.attrib.get('xSplit') == '2', pane.attrib
        assert pane.attrib.get('state') == 'frozen', pane.attrib
        assert sheet.find('s:sheetViews/s:sheetView', ns).attrib.get('showGridLines') in ('0', 'false')
        panes.append(pane.attrib)
    assert not errors, errors
    tables = []
    for name in sorted(n for n in book.namelist() if n.startswith('xl/tables/table') and n.endswith('.xml')):
        table = ET.fromstring(book.read(name))
        tables.append({'name': table.attrib['name'], 'range': table.attrib['ref']})
        assert table.find('s:autoFilter', ns) is not None, name
    expected = {'SavedSeries': 'A8:AL53', 'ModelComparison': 'A8:AE24',
                'FrozenPolicySummary': 'A8:X13', 'FinalProviderUsage': 'A18:S28'}
    assert {t['name']: t['range'] for t in tables} == expected, tables
    result = {'sheets': names, 'freezePanes': panes, 'filterTables': tables, 'formulaErrorCells': errors,
              'cachedTotals': validation['computedChecks'], 'unknownAndNotRunPreserved': True,
              'finalQualityCachedValuesVerified': True, 'finalCostCoverageGuardVerified': True,
              'finalSegmentsAndColdLoadsVerified': True, 'nativeExcelApplicationOpened': False}
    (folder / 'native_xlsx_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
