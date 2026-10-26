"""Independent Decimal fixture construction; never imports the executor."""
import copy
from decimal import Decimal, localcontext
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GDD_URL = "https://mrcc.purdue.edu/resources/growing-degree-day-description"
FAO3 = "https://www.fao.org/4/x0490e/x0490e07.htm"
FAO4 = "https://www.fao.org/4/x0490e/x0490e08.htm"
FAO2 = "https://www.fao.org/4/x0490e/x0490e06.htm"
POLICY = "docs/DETERMINISTIC_STUDY_C_20261003_RU.md#экспериментальная-разность-цели-и-осадков"
D = lambda x: Decimal(str(x))

def saturation(t):
    return D(".6108") * (D("17.27") * D(t) / (D(t) + D("237.3"))).exp()

def reference(task, i):
    with localcontext() as ctx:
        ctx.prec = 60
        if task == "heat_sum_simple_daily":
            return sum(max(D(0), (D(a)+D(b))/2-D(i["base"])) for a,b in zip(i["tmin"],i["tmax"]))
        if task == "vapour_deficit_single_observation":
            return saturation(i["temperature"]) * (1-D(i["rh"])/100)
        if task == "vapour_deficit_daily_extrema":
            eslo, eshi = saturation(i["tmin"]), saturation(i["tmax"])
            return (eslo*(1-D(i["rhmax"])/100)+eshi*(1-D(i["rhmin"])/100))/2
        if task == "reference_et_daily_precomputed":
            den = D(i["delta"])+D(i["gamma"])*(1+D(".34")*D(i["u2"]))
            radiation = D(".408")*D(i["delta"])*(D(i["rn"])-D(i["g"]))/den
            aerodynamic = D(i["gamma"])*900*D(i["u2"])*(D(i["es"])-D(i["ea"])) / ((D(i["temperature"])+273)*den)
            return radiation+aerodynamic
        return max(D(0), D(i["target"])-sum(D(v) for v in i["rain"]))

META = {
 "heat_sum_simple_daily": ("gdd_simple_daily_v1","degC day",GDD_URL,"simple daily average; sum(max(0,(Tmin+Tmax)/2-base)); no upper cap",{"temperature":"C","time_step":"day"}),
 "vapour_deficit_single_observation": ("vpd_single_observation_v1","kPa",FAO3,"FAO-56 Eq.11 and relative humidity definition Eq.10; es(T)*(1-RH/100)",{"temperature":"C","humidity":"%"}),
 "vapour_deficit_daily_extrema": ("vpd_daily_extrema_v1","kPa",FAO3,"FAO-56 Eqs.11,12,17; VPD=es-ea",{"temperature":"C","humidity":"%","time_step":"day"}),
 "reference_et_daily_precomputed": ("et0_fao56_daily_v1","mm/day",FAO2,"FAO-56 Eq.6 daily grass reference, all derived inputs explicitly supplied",{"temperature":"C","radiation":"MJ/m2/day","wind":"m/s","pressure":"kPa","slope":"kPa/C","height":"m","time_step":"day"}),
 "experimental_rain_target_gap": ("rain_target_gap_v1","mm",POLICY,"experimental arithmetic only: max(0,target-sum(rain)); not irrigation requirement",{"precipitation":"mm"}),
}
CASES=[]
def add(task,inputs,question,*,published=None,tolerance=1e-8,group=None,category="numeric"):
    tool,unit,url,formula,units=META[task]
    calculated=reference(task,inputs)
    expected=float(calculated) if published is None else published
    case={"id":f"study_c_{len(CASES)+1:03d}","split":"development_reference","category":category,"group":group or tool,
      "source":{"url":url,"formula_version":tool,"formula":formula,"accessed":"2026-10-03"},
      "request":{"question_ru":question,"task":task,"inputs":inputs,"units":copy.deepcopy(units)},
      "expected":{"action":"ANSWER","tool":tool,"numeric":expected,"unit":unit,"abs_tolerance":tolerance},
      "gold_method":"published rounded worked example" if published is not None else "independent Decimal arithmetic at precision 60; not model output",
      "independent_formula_value":str(calculated)}
    CASES.append(case)
    return case

gdd=add("heat_sum_simple_daily",{"tmin":[10],"tmax":[26],"base":10},"Рассчитай сумму тепла за один день: среднее минимума и максимума минус явно заданная база, отрицательный вклад равен нулю. Верхнего ограничения нет.")
add("heat_sum_simple_daily",{"tmin":[0],"tmax":[10],"base":5},"Рассчитай тепловой вклад дня при среднем, равном базе; используй простое среднее и нулевой нижний предел.")
add("heat_sum_simple_daily",{"tmin":[0,6,10],"tmax":[10,14,20],"base":5},"Сложи тепловые вклады трёх дней по явно заданной простой формуле. Не усредняй весь период перед ограничением нулём.")
add("heat_sum_simple_daily",{"tmin":[35],"tmax":[45],"base":5},"Посчитай тепловой вклад без верхнего температурного ограничения. Не применяй отдельную схему для кукурузы.")
vpd=add("vapour_deficit_single_observation",{"temperature":24.5,"rh":0},"Рассчитай дефицит давления водяного пара для одного наблюдения; при нулевой влажности он равен давлению насыщения.",published=3.075,tolerance=.001,group="fao56_example3")
add("vapour_deficit_single_observation",{"temperature":15,"rh":0},"Рассчитай дефицит давления для одного наблюдения при заданной температуре и нулевой относительной влажности.",published=1.705,tolerance=.001,group="fao56_example3")
add("vapour_deficit_single_observation",{"temperature":20,"rh":50},"Рассчитай дефицит давления по одной температуре и относительной влажности. Это не восстановление среднего за сутки.")
add("vapour_deficit_single_observation",{"temperature":20,"rh":100},"Рассчитай дефицит давления при насыщенном воздухе для одного наблюдения.")
daily=add("vapour_deficit_daily_extrema",{"tmin":18,"tmax":25,"rhmin":54,"rhmax":82},"Рассчитай суточную оценку дефицита давления по минимуму и максимуму температуры и влажности согласно формулам 12 и 17 FAO-56.",published=.91,tolerance=.005,group="fao56_example6")
add("vapour_deficit_daily_extrema",{"tmin":20,"tmax":20,"rhmin":50,"rhmax":50},"Рассчитай суточную оценку при одинаковых минимуме и максимуме температуры и влажности.")
et0inputs={"temperature":16.9,"rn":13.28,"g":0,"u2":2.078,"es":1.997,"ea":1.409,"delta":.122,"gamma":.0666,"wind_height":2}
et=add("reference_et_daily_precomputed",et0inputs,"Рассчитай суточную эталонную эвапотранспирацию травяной поверхности по формуле 6 FAO-56. Все промежуточные параметры заданы явно.",published=3.88,tolerance=.01,group="fao56_example18")
et["source"]["worked_example_url"]=FAO4
zero=copy.deepcopy(et0inputs);zero.update(rn=0,g=0,u2=0,es=1.5,ea=1.5)
add("reference_et_daily_precomputed",zero,"Посчитай значение суточной формулы FAO-56 при нулевом радиационном и аэродинамическом членах; не добавляй типовые значения ветра.")
rain=add("experimental_rain_target_gap",{"target":10,"rain":[3]},"В экспериментальной арифметической задаче посчитай max(0, заданная цель минус сумма осадков). Это не рекомендация по поливу.")
add("experimental_rain_target_gap",{"target":3,"rain":[1,2,3]},"Для явно заданной арифметической формулы посчитай разность с ограничением нулём при избытке осадков.")
add("experimental_rain_target_gap",{"target":1,"rain":[.1,.15]},"Посчитай экспериментальную разность цели и осадков в миллиметрах. Не переводить в норму полива.")

def defect(base,question,reason,fields,*,remove=(),units_remove=(),units_override=None,inputs_override=None):
    c=copy.deepcopy(base);c["id"]=f"study_c_{len(CASES)+1:03d}";c["category"]="input_sufficiency";c["request"]["question_ru"]=question
    for key in remove:c["request"]["inputs"].pop(key)
    for key in units_remove:c["request"]["units"].pop(key)
    c["request"]["units"].update(units_override or {});c["request"]["inputs"].update(inputs_override or {})
    c["expected"]={"action":"ASK_FOR_DATA","tool":base["expected"]["tool"],"reason_code":reason,"requested_fields":sorted(fields)}
    c["gold_method"]="explicit versioned input contract; no assumed or model-generated values";c.pop("independent_formula_value")
    CASES.append(c)

defect(gdd,"Для тепловой суммы база не задана. Запроси её; не выбирай типичный порог культуры.","MISSING_INPUTS",["base"],remove=["base"])
defect(vpd,"Влажность для расчёта дефицита давления не задана. Запроси её.","MISSING_INPUTS",["rh"],remove=["rh"])
defect(et,"Для суточной формулы не задана чистая радиация. Запроси её; не подставляй солнечную радиацию вместо чистой.","MISSING_INPUTS",["rn"],remove=["rn"])
defect(et,"Для суточной формулы не задан ветер на высоте двух метров. Запроси его; не подставляй типовой ветер.","MISSING_INPUTS",["u2"],remove=["u2"])
defect(et,"Для суточной формулы нет насыщенного и фактического давления пара. Запроси их или отдельный полностью заданный способ их вычисления.","MISSING_INPUTS",["es","ea"],remove=["es","ea"])
defect(et,"Наклон кривой насыщения и психрометрическая постоянная не заданы. Запроси эти параметры; не угадывай давление или высоту местности.","MISSING_INPUTS",["delta","gamma"],remove=["delta","gamma"])
defect(et,"Радиация сообщена в ваттах на квадратный метр вместо суточных мегаджоулей. Запроси явно приведённые единицы для суточной формулы.","EXPLICIT_CONVERSION_REQUIRED",["units.radiation"],units_override={"radiation":"W/m2"})
defect(et,"Ветер измерен на высоте десяти метров. Не подставляй его вместо ветра на двух метрах; запроси явное преобразование.","EXPLICIT_CONVERSION_REQUIRED",["u2","wind_height"],inputs_override={"wind_height":10})
defect(et,"Входной временной шаг указан как час. Суточную формулу применять нельзя; запроси суточные данные или отдельную часовую формулу.","EXPLICIT_CONVERSION_REQUIRED",["units.time_step"],units_override={"time_step":"hour"})
defect(rain,"Число осадков дано без единиц измерения. Запроси единицы перед вычитанием.","MISSING_INPUTS",["units.precipitation"],units_remove=["precipitation"])
CASES.append({"id":f"study_c_{len(CASES)+1:03d}","split":"development_reference","category":"scope_control","group":"unsupported_advice","source":{"url":"docs/DETERMINISTIC_STUDY_C_20261003_RU.md","formula_version":"unsupported_task_v1","formula":"no deterministic formula is defined for a guaranteed yield prediction","accessed":"2026-10-03"},"request":{"question_ru":"По этой температуре гарантируй точный урожай неизвестной культуры на неизвестном поле.","task":"guaranteed_unspecified_crop_yield","inputs":{"temperature":20},"units":{"temperature":"C"}},"expected":{"action":"ABSTAIN","reason_code":"UNSUPPORTED_TASK"},"gold_method":"explicit scope restriction; no agronomic truth label"})
add("vapour_deficit_single_observation",{"temperature":24.5,"rh":50},"Выбери инструмент для дефицита давления водяного пара по одному наблюдению температуры и влажности, затем вычисли результат. Инструмент тепловой суммы здесь не подходит.",category="tool_selection")

package={"schema_version":1,"study":"C","version":"study_c_technical_20261003_v1","status":"DEVELOPMENT_REFERENCE_ONLY_NOT_CONFIRMATORY","language":"ru","independence":"27 constructed development cases; repeated formula families; not 27 independent agronomic truths","license":"project-authored questions and synthetic inputs Apache-2.0; source documents not redistributed","cases":CASES}
assert len(CASES)==27
(ROOT/"data/study_c_technical_20261003.json").write_text(json.dumps(package,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
