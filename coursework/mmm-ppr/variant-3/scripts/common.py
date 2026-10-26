"""Local numerical dependencies and paths; no GAMS replacement."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
IN_PROJECT = ROOT.parent.name=='mmm-ppr' and ROOT.parent.parent.name=='coursework'
PROJECT_ROOT = ROOT.parents[2] if IN_PROJECT else ROOT
sys.path.insert(0, str(ROOT.parent / 'variant-11/runtime/python_packages'))
sys.path.insert(0, str(ROOT / 'runtime/python_packages'))
import csv, json

def write_csv(name, rows):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def write_json(name, data):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
