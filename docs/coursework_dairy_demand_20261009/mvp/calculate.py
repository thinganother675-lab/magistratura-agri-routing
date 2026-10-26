"""Новый расчёт и автономная страница без HTTP-сервера."""
import argparse,csv,io,json,sys
from pathlib import Path
from model import analyse,demo_rows,parse_csv
ROOT=Path(__file__).resolve().parent
def export(report,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'forecast_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=['date','sku','forecast','promo']);writer.writeheader()
    for p in report['products']:
        for row in p['forecast']:writer.writerow(dict(row,sku=p['sku']))
    (output/'forecast.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
    data=json.dumps(report,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(ROOT/'offline_template.html').read_text(encoding='utf-8')
    (output/'offline.html').write_text(template.replace('__REPORT_DATA__',data),encoding='utf-8')
    return output/'offline.html'
def main():
    parser=argparse.ArgumentParser(description='Прогноз без запуска сайта.')
    parser.add_argument('--csv',type=Path);parser.add_argument('--promos',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'results');args=parser.parse_args()
    try:
        rows=parse_csv(args.csv.read_text(encoding='utf-8-sig')) if args.csv else demo_rows()
        promos=json.loads(args.promos.read_text(encoding='utf-8-sig')) if args.promos else None
        if promos is not None and not isinstance(promos,dict):raise ValueError('План акций должен содержать объект с кодами товаров.')
        report=analyse(rows,promos);report['synthetic']=args.csv is None;page=export(report,args.output)
    except (ValueError,OSError,TypeError) as error:
        print(f'Расчёт не выполнен: {error}',file=sys.stderr);return 1
    print(f'Готово. Откройте {page} . Прогноз и отчёт находятся в той же папке.',flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
