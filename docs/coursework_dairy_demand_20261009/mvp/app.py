"""Локальный сервер учебного проекта Дениса. Без внешних API."""
import json, argparse, sys, webbrowser, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from model import demo_rows, analyse, parse_csv, production, csv_text

ROOT=Path(__file__).resolve().parent
class DairyServer(ThreadingHTTPServer):
    allow_reuse_address=False
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()
DEMO=None
def demo():
    global DEMO
    if DEMO is None:
        DEMO=analyse(demo_rows());DEMO['synthetic']=True
    return DEMO

class Handler(BaseHTTPRequestHandler):
    def send(self, data, content_type='application/json; charset=utf-8',status=200):
        if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        if isinstance(data,str):data=data.encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',len(data));self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/':self.send((ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
        elif self.path=='/api/health':self.send({'application':'dairy-plan','status':'ready'})
        elif self.path=='/api/demo':self.send(demo())
        elif self.path=='/demo.csv':self.send('\ufeff'+csv_text(demo_rows()),'text/csv; charset=utf-8')
        else:self.send({'error':'Страница не найдена.'},status=404)
    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>2_000_000:raise ValueError('Допустимый размер запроса: до 2 МБ.')
            value=json.loads(self.rfile.read(size).decode('utf-8-sig'))
            if not isinstance(value,dict):raise ValueError('Запрос должен содержать объект с параметрами.')
            if self.path=='/api/analyse':
                result=analyse(parse_csv(value['csv']),value.get('promos'));self.send(result)
            elif self.path=='/api/production':
                self.send(production(float(value['forecast']),value['batches'],value['date'],float(value['capacity']),float(value['safety'])))
            else:self.send({'error':'Команда не найдена.'},status=404)
        except (ValueError,KeyError,TypeError,OverflowError) as error:
            self.send({'error':str(error) or 'Некорректные данные.'},status=400)
        except Exception:
            self.send({'error':'Не удалось выполнить расчёт. Проверьте файл и повторите.'},status=500)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8096)
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args()
    if not 0<=args.port<=65535:parser.error('Порт должен быть от 0 до 65535.')
    try:server=DairyServer(('127.0.0.1',args.port),Handler)
    except OSError as error:
        print(f'Не удалось открыть порт {args.port}: {error}.',file=sys.stderr)
        print('Повторите запуск с --port 0, чтобы выбрать свободный порт.',file=sys.stderr)
        return 1
    url=f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'Откройте {url} . Оставьте это окно открытым. Для остановки нажмите Ctrl+C.',flush=True)
    if args.open_browser:
        try:webbrowser.open(url)
        except Exception:print('Браузер не открылся автоматически. Скопируйте адрес из строки выше.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nСервер остановлен.',flush=True)
    finally:server.server_close()
    return 0

if __name__=='__main__':raise SystemExit(main())
