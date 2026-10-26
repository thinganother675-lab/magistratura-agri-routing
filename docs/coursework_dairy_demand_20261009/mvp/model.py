"""Учебный прогноз. Все признаки используют только доступное прошлое."""
import csv, io, math
from datetime import date, timedelta
import numpy as np

PRODUCTS = {'milk': 'Молоко', 'kefir': 'Кефир', 'yogurt': 'Йогурт'}

def demo_rows(days=730):
    rng = np.random.default_rng(61)
    start = date(2024, 10, 9)
    rows = []
    for sku, base in zip(PRODUCTS, [1100, 700, 450]):
        for i in range(days):
            day = start + timedelta(days=i)
            promo = int(i % 35 in range(21, 26))
            demand = max(0, round(base * (1 + .11 * math.sin(2*math.pi*day.weekday()/7)
                + .08*math.sin(2*math.pi*i/365) + .00022*i + .23*promo) + rng.normal(0, base*.035)))
            stockout = int(i % 47 == 13)
            sales = round(demand * .76) if stockout else demand
            rows.append({'date': day.isoformat(), 'sku': sku, 'sales': sales,
                'promo': promo, 'stockout': stockout})
    return rows

def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if reader.fieldnames != ['date', 'sku', 'sales', 'promo', 'stockout']:
        raise ValueError('Нужны столбцы date,sku,sales,promo,stockout в указанном порядке.')
    rows = []
    for line, row in enumerate(reader, 2):
        try:
            day = date.fromisoformat(row['date'])
            sku = row['sku']
            sales = float(row['sales'])
            promo, stockout = int(row['promo']), int(row['stockout'])
            if sku not in PRODUCTS or not math.isfinite(sales) or sales < 0 or sales > 1e7:
                raise ValueError()
            if promo not in [0, 1] or stockout not in [0, 1]:
                raise ValueError()
            rows.append(dict(date=day.isoformat(), sku=sku, sales=sales, promo=promo, stockout=stockout))
        except (ValueError, TypeError):
            raise ValueError(f'Некорректная строка {line}.') from None
    grouped = group_rows(rows)
    if not grouped or any(len(series) < 180 for series in grouped.values()):
        raise ValueError('Нужно не менее 180 последовательных дней для каждого представленного товара.')
    return rows

def group_rows(rows):
    result = {}
    for row in rows:
        result.setdefault(row['sku'], []).append(row)
    for series in result.values():
        series.sort(key=lambda r:r['date'])
        for a, b in zip(series, series[1:]):
            if date.fromisoformat(b['date']) - date.fromisoformat(a['date']) != timedelta(days=1):
                raise ValueError('Повтор даты или пропуск дня. Сначала проверьте выгрузку.')
    return result

def corrected_history(series):
    values = []
    for i, row in enumerate(series):
        if row['stockout']:
            past = [series[j]['sales'] for j in range(max(0,i-28),i)
                    if not series[j]['stockout'] and (i-j)%7==0]
            if not past:
                past = [series[j]['sales'] for j in range(max(0,i-28),i) if not series[j]['stockout']]
            values.append(float(np.median(past)) if past else row['sales'])
        else:
            values.append(float(row['sales']))
    return values

def feature(history, day, promo, index):
    if len(history)<28:
        raise ValueError('Для признаков нужны 28 прошлых дней.')
    return [history[-1], history[-7], history[-14], history[-28],
        sum(history[-7:])/7, sum(history[-28:])/28,
        math.sin(2*math.pi*day.weekday()/7), math.cos(2*math.pi*day.weekday()/7),
        math.sin(2*math.pi*day.timetuple().tm_yday/365.25),
        math.cos(2*math.pi*day.timetuple().tm_yday/365.25), promo, index]

def fit(series, alpha):
    hist = corrected_history(series)
    indices = [i for i in range(28,len(series)) if not series[i]['stockout']]
    if len(indices)<90:
        raise ValueError('Недостаточно дней без дефицита: требуется 90 целевых наблюдений.')
    # Пакетное построение тех же прошлых признаков без повторных средних в цикле.
    values=np.asarray(hist,dtype=float);idx=np.asarray(indices)
    sums=np.r_[0,np.cumsum(values)]
    dates=[date.fromisoformat(series[i]['date']) for i in indices]
    weekdays=np.asarray([d.weekday() for d in dates]);year_days=np.asarray([d.timetuple().tm_yday for d in dates])
    x=np.column_stack([values[idx-1],values[idx-7],values[idx-14],values[idx-28],
        (sums[idx]-sums[idx-7])/7,(sums[idx]-sums[idx-28])/28,
        np.sin(2*np.pi*weekdays/7),np.cos(2*np.pi*weekdays/7),
        np.sin(2*np.pi*year_days/365.25),np.cos(2*np.pi*year_days/365.25),
        [series[i]['promo'] for i in indices],idx])
    y = np.asarray([series[i]['sales'] for i in indices],dtype=float)
    mean, scale = x.mean(0), x.std(0)
    scale[scale<1e-8]=1
    z = np.column_stack([np.ones(len(x)), (x-mean)/scale])
    penalty = np.eye(z.shape[1])*alpha
    penalty[0,0]=0
    coef = np.linalg.solve(z.T@z+penalty, z.T@y)
    return {'mean': mean,'scale':scale,'coef':coef,'indices':indices}

def predict(series, future_promos, alpha=1, method='ridge'):
    hist = corrected_history(series)
    trained = fit(series, alpha) if method=='ridge' else None
    output=[]
    last = date.fromisoformat(series[-1]['date'])
    for h,promo in enumerate(future_promos):
        day = last+timedelta(days=h+1)
        if trained:
            x = np.asarray(feature(hist, day,promo,len(series)+h))
            pred = float(np.r_[1,(x-trained['mean'])/trained['scale']]@trained['coef'])
        else:
            pred = hist[-7]
        pred=max(0,pred)
        if not math.isfinite(pred):
            raise ValueError('Модель вернула некорректный прогноз. Используйте ручной план.')
        hist.append(pred)
        output.append({'date':day.isoformat(),'forecast':round(pred,2),'promo':int(promo)})
    return output

def scores(actual, predicted):
    a,p=np.asarray(actual),np.asarray(predicted)
    error=a-p
    return {'n':len(a),'mae':round(float(np.mean(np.abs(error))),3),
        'rmse':round(float(np.sqrt(np.mean(error**2))),3),
        'wape':round(float(np.sum(np.abs(error))/np.sum(a)*100),3) if np.sum(a)>0 else None}

def evaluate(series, origins, alpha, method):
    actual,predicted=[],[]
    for origin in origins:
        future=series[origin:origin+7]
        forecasts=predict(series[:origin],[r['promo'] for r in future],alpha,method)
        for row,pr in zip(future,forecasts):
            if not row['stockout']:
                actual.append(row['sales']);predicted.append(pr['forecast'])
    if not actual:
        raise ValueError('В проверочном периоде нет продаж без дефицита.')
    return scores(actual,predicted)

def analyse(rows, future_promos=None):
    result=[]
    for sku,series in group_rows(rows).items():
        n=len(series);a=int(n*.74);b=int(n*.86)
        val_origins=list(range(a,b-6,7));test_origins=list(range(b,n-6,7))
        if not val_origins or not test_origins:
            raise ValueError('Недостаточно дней для временной проверки.')
        tuning={str(alpha):evaluate(series,val_origins,alpha,'ridge')['mae'] for alpha in [1,10,100]}
        alpha=float(min(tuning,key=tuning.get))
        model_val=evaluate(series,val_origins,alpha,'ridge')
        naive_val=evaluate(series,val_origins,alpha,'naive')
        chosen='ridge' if model_val['mae']<naive_val['mae'] else 'naive'
        model_test=evaluate(series,test_origins,alpha,'ridge')
        naive_test=evaluate(series,test_origins,alpha,'naive')
        promos=(future_promos or {}).get(sku,[0]*7)
        if len(promos)!=7 or any(p not in [0,1] for p in promos):
            raise ValueError('План акций должен содержать семь значений 0 или 1.')
        result.append({'sku':sku,'name':PRODUCTS[sku],'days':n,'alpha':alpha,'method':chosen,
            'train_end':series[a-1]['date'],'validation_end':series[b-1]['date'],
            'test_start':series[b]['date'],'tuning':tuning,'model_test':model_test,
            'naive_test':naive_test,'forecast':predict(series,promos,alpha,chosen),
            'history':series[-35:],'censored_days':sum(r['stockout'] for r in series)})
    return {'products':result,'synthetic':False,'note':'Проверка точности исключает дни дефицита. Скрытый спрос не наблюдается.'}

def production(forecast, batches, target_date, capacity, safety_percent=5):
    """Рекомендация на один день. Годные партии расходуются по раннему сроку."""
    target=date.fromisoformat(target_date)
    if any(not math.isfinite(float(v)) or v<0 for v in [forecast,capacity,safety_percent]):
        raise ValueError('Объём, мощность и запас должны быть конечными и неотрицательными.')
    if safety_percent>100:
        raise ValueError('Запас не должен превышать 100%.')
    valid=[];expired=0
    for b in batches:
        expiry=date.fromisoformat(b['expiry']);q=float(b['quantity'])
        if not math.isfinite(q) or q<0:
            raise ValueError('Некорректный остаток партии.')
        if expiry<target:expired+=q
        else:valid.append({'expiry':expiry.isoformat(),'quantity':q})
    valid.sort(key=lambda b:b['expiry'])
    available=sum(b['quantity'] for b in valid)
    target_quantity=math.ceil(forecast*(1+safety_percent/100))
    required=max(0,target_quantity-available)
    recommended=min(math.ceil(required),math.floor(capacity))
    return {'target':target_quantity,'available':available,'expired':expired,
        'production':recommended,'uncovered':max(0,target_quantity-available-recommended),'batches':valid}

def csv_text(rows):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=['date','sku','sales','promo','stockout'])
    writer.writeheader();writer.writerows(rows);return output.getvalue()
