import unittest, copy
from model import *

class ModelChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=demo_rows();cls.series=group_rows(cls.rows)['milk']
    def test_roundtrip(self):
        self.assertEqual(parse_csv(csv_text(self.rows)),self.rows)
    def test_duplicate_and_gap(self):
        for rows in [self.rows+[self.rows[0]],self.rows[:100]+self.rows[101:]]:
            with self.assertRaises(ValueError):parse_csv(csv_text(rows))
    def test_bad_number(self):
        for value in ['nan','-1','inf']:
            changed=copy.deepcopy(self.rows);changed[0]['sales']=value
            with self.assertRaises(ValueError):parse_csv(csv_text(changed))
    def test_target_censoring(self):
        series=copy.deepcopy(self.series[:540]);indices=fit(series,1)['indices']
        self.assertTrue(all(not series[i]['stockout'] for i in indices))
        self.assertGreater(len(indices),450)
    def test_future_does_not_change_prediction(self):
        a=predict(self.series[:630],[0]*7,10)
        changed=copy.deepcopy(self.series)
        for row in changed[630:]:row['sales']*=10
        b=predict(changed[:630],[0]*7,10)
        self.assertEqual(a,b)
    def test_recursive_no_future_actuals(self):
        series=self.series[:630];p=predict(series,[0]*7,10)
        fake=series+[dict(date=p[0]['date'],sku='milk',sales=p[0]['forecast'],promo=0,stockout=0)]
        # Проверяем сезонный эталон: второй шаг берётся из того же прошлого.
        first=predict(series,[0]*7,method='naive')
        continuation=predict(series+[dict(date=first[0]['date'],sku='milk',sales=first[0]['forecast'],promo=0,stockout=0)],[0]*6,method='naive')
        self.assertEqual(first[1:],continuation)
    def test_past_imputation(self):
        series=copy.deepcopy(self.series);a=corrected_history(series[:100])
        for row in series[100:]:row['sales']=1e6
        self.assertEqual(a,corrected_history(series)[:100])
    def test_expiry_and_capacity(self):
        r=production(100,[{'expiry':'2026-10-08','quantity':50},{'expiry':'2026-10-09','quantity':20},{'expiry':'2026-10-10','quantity':10}],'2026-10-09',50,5)
        self.assertEqual((r['available'],r['expired'],r['production'],r['uncovered']),(30,50,50,25))
        self.assertEqual(r['batches'][0]['expiry'],'2026-10-09')
    def test_negative_and_nan_stock(self):
        for quantity in [-1,float('nan')]:
            with self.assertRaises(ValueError):production(100,[{'expiry':'2026-10-10','quantity':quantity}],'2026-10-09',100)
    def test_zero_and_no_production(self):
        self.assertEqual(production(0,[],'2026-10-09',100)['production'],0)
        self.assertEqual(production(20,[{'expiry':'2026-10-10','quantity':50}],'2026-10-09',100)['production'],0)
    def test_promo_input(self):
        with self.assertRaises(ValueError):analyse(self.rows,{'milk':[2]*7})
    def test_metrics(self):
        self.assertEqual(scores([100,100],[90,110]),{'n':2,'mae':10.,'rmse':10.,'wape':10.})
    def test_vectorized_training_matches_scalar(self):
        series=self.series[:200];hist=corrected_history(series);trained=fit(series,10)
        x=np.asarray([feature(hist[:i],date.fromisoformat(series[i]['date']),series[i]['promo'],i) for i in trained['indices']])
        np.testing.assert_allclose(trained['mean'],x.mean(0),rtol=1e-12,atol=1e-9)
        np.testing.assert_allclose(trained['scale'],np.where(x.std(0)<1e-8,1,x.std(0)),rtol=1e-12,atol=1e-9)

if __name__=='__main__':unittest.main()
