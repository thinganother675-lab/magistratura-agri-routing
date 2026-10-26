import unittest,json,threading,tempfile,subprocess,sys,csv,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from model import demo_rows,analyse,production
from calculate import export
from app import Handler
ROOT=Path(__file__).resolve().parent

class DeliveryChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_health_and_page(self):
        with self.op.open(self.url+'/api/health',timeout=5) as r:self.assertEqual(json.load(r),{'application':'dairy-plan','status':'ready'})
        with self.op.open(self.url+'/',timeout=5) as r:self.assertIn('Молочный план',r.read().decode('utf-8'))
    def test_nonobject_request(self):
        req=urllib.request.Request(self.url+'/api/analyse',data=b'[]',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as e:self.op.open(req,timeout=5)
        self.assertEqual(e.exception.code,400)
    def test_offline_export(self):
        report=json.loads((ROOT/'demo_result.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            page=export(report,folder);text=page.read_text(encoding='utf-8')
            self.assertNotIn('__REPORT_DATA__',text);self.assertNotIn('fetch(',text)
            saved=json.loads((Path(folder)/'forecast_report.json').read_text(encoding='utf-8'));self.assertEqual(saved,report)
            with (Path(folder)/'forecast.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),21);self.assertEqual(float(rows[0]['forecast']),report['products'][0]['forecast'][0]['forecast'])
    def test_html_embedded_text_escaped(self):
        with tempfile.TemporaryDirectory() as folder:
            page=export({'products':[],'note':'</script><script>bad</script>'},folder)
            self.assertNotIn('</script><script>bad',page.read_text(encoding='utf-8'))
    def test_cli_independent_of_cwd(self):
        with tempfile.TemporaryDirectory() as folder:
            r=subprocess.run([sys.executable,str(ROOT/'calculate.py'),'--csv',str(ROOT/'example_sales.csv'),'--output',folder],cwd=folder,capture_output=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr)
            report=json.loads((Path(folder)/'forecast_report.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['products']),3);self.assertFalse(report['synthetic'])
            self.assertTrue((Path(folder)/'offline.html').exists())
    def test_cli_invalid_file(self):
        with tempfile.TemporaryDirectory() as folder:
            bad=Path(folder)/'bad.csv';bad.write_text('bad',encoding='utf-8')
            r=subprocess.run([sys.executable,str(ROOT/'calculate.py'),'--csv',str(bad),'--output',str(Path(folder)/'results')],capture_output=True,timeout=15)
            self.assertEqual(r.returncode,1);self.assertFalse((Path(folder)/'results').exists())
    def test_port_busy_clear_error(self):
        # Родитель держит порт; дочерний сервер должен завершиться с объяснением.
        port=self.server.server_address[1]
        r=subprocess.run([sys.executable,str(ROOT/'app.py'),'--port',str(port)],capture_output=True,timeout=30)
        self.assertEqual(r.returncode,1);self.assertIn(b'--port 0',r.stderr)

if __name__=='__main__':unittest.main()
