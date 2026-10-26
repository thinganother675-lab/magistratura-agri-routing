"""Author a fresh HOME final set after tuning stops; never use model predictions.

The independent Decimal references are written before validating frozen tools.
Output files are exclusively created; rebuilding cannot overwrite a frozen set.
QA contexts are short authored paraphrases of verified official source facts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261001
TUNING_STOP_UTC = "2026-10-01T20:11:00Z"
DATA_PATH = ROOT / "data/home_holdout_20261001.jsonl"
SOURCES_PATH = ROOT / "data/home_holdout_20261001_sources.json"

SOURCES = {
    "fao56_ch1": {"document": "FAO56_1998", "title": "FAO Irrigation and Drainage Paper56, Chapter1", "url": "https://www.fao.org/4/x0490e/x0490e04.htm", "publisher": "FAO", "published": "1998", "sections": "Transpiration; Evapotranspiration process", "source_rights": "FAO source rights retained; short authored paraphrases with attribution"},
    "fao56_ch2": {"document": "FAO56_1998", "title": "FAO56, Chapter2", "url": "https://www.fao.org/4/x0490e/x0490e06.htm", "publisher": "FAO", "published": "1998", "sections": "Reference surface; Eq6", "source_rights": "FAO source rights retained; short authored paraphrases with attribution"},
    "fao56_ch3": {"document": "FAO56_1998", "title": "FAO56, Chapter3", "url": "https://www.fao.org/4/x0490e/x0490e07.htm", "publisher": "FAO", "published": "1998", "sections": "Wind profile relationship; vapour pressure; Eqs11,13", "source_rights": "FAO source rights retained; short authored paraphrases with attribution"},
    "fao_salinity": {"document": "FAO_irrigation_training_salty_soils", "title": "Irrigation Water Management: Training Manual1, Chapter7 Salty Soils", "url": "https://www.fao.org/4/r4082e/r4082e08.htm", "publisher": "FAO", "published": "1985", "sections": "7.1 Salinization; 7.5 Improvement of saline soils", "source_rights": "FAO source rights retained; short authored paraphrases with attribution"},
    "nrcs_soil": {"document": "USDA_NRCS_soil_health_cropland", "title": "Soil Health on Cropland", "url": "https://www.nrcs.usda.gov/conservation-basics/soil/soil-health/soil-health-on-cropland", "publisher": "USDA NRCS", "published": "Undated live official page, verified2026-10-01", "sections": "Maximize soil cover; Biodiversity; Continuous living roots", "source_rights": "USDA government source; authored paraphrase and attribution"},
    "umn_cover": {"document": "UMN_cover_species_20220929", "title": "Maximize your cover crop benefits by selecting the best species", "url": "https://blog-crop-news.extension.umn.edu/2022/09/maximize-your-cover-crop-benefits-by.html", "publisher": "University of Minnesota Extension", "published": "2022-09-29", "sections": "Table1; Winter-killed and winter-hardy cover crops", "source_rights": "Page declares CC BY-SA4.0; attribution retained for authored paraphrases"},
    "umn_nitrogen": {"document": "UMN_cover_nitrogen_20190426", "title": "Cover Crops and Nitrogen Credits", "url": "https://blog-nwcrops.extension.umn.edu/2019/04/cover-crops-and-nitrogen-credits.html", "publisher": "University of Minnesota Extension", "published": "2019-04-26", "sections": "Introduction; Legume cover crops", "source_rights": "Underlying University source rights retained; short authored paraphrases with attribution"},
}

# key, EN context/question/short span, RU context/question/short span.
FACTS = [
 ("fao56_ch1", "Leaves release most water vapour through stomata; roots first supply the plant with water.", "Which leaf openings release most water vapour?", "stomata", "Большая часть водяного пара выходит из листьев через устьица; воду сначала поставляют корни.", "Через какие отверстия листьев выходит основная часть водяного пара?", "устьица"),
 ("fao56_ch1", "Evapotranspiration combines evaporation from the soil with transpiration from plants.", "Which plant process joins evaporation in evapotranspiration?", "transpiration", "Эвапотранспирация объединяет испарение из почвы с транспирацией растений.", "Какой процесс растений вместе с испарением образует эвапотранспирацию?", "транспирацией"),
 ("fao56_ch2", "FAO defines hypothetical reference grass as 0.12 m tall, with fixed surface characteristics.", "How tall is the reference grass? Return the written value and unit.", "0.12 m", "FAO определяет гипотетическую эталонную траву высотой 0.12 м с фиксированными характеристиками поверхности.", "Какова высота эталонной травы? Верните значение и единицу из текста.", "0.12 м"),
 ("fao56_ch2", "The hypothetical FAO reference grass has albedo 0.23 and receives adequate water.", "What albedo is assigned to reference grass?", "0.23", "Гипотетическая эталонная трава FAO имеет альбедо 0.23 и обеспечена водой.", "Какое альбедо задано эталонной траве?", "0.23"),
 ("fao56_ch3", "FAO evapotranspiration calculations use wind speed at 2 m above the surface.", "At what height is wind speed required?", "2 m", "В расчётах эвапотранспирации FAO используется скорость ветра на высоте 2 м над поверхностью.", "На какой высоте требуется скорость ветра?", "2 м"),
 ("fao56_ch3", "Saturation vapour pressure increases when air temperature rises; the relationship is nonlinear.", "What happens to saturation vapour pressure when temperature rises?", "increases", "Давление насыщенного водяного пара увеличивается при повышении температуры; зависимость нелинейна.", "Что происходит с давлением насыщенного пара при повышении температуры?", "увеличивается"),
 ("fao_salinity", "Accumulation of salts left in irrigated soil is called salinization.", "What is salt accumulation in soil called?", "salinization", "Накопление солей, остающихся в орошаемой почве, называется засолением.", "Как называется накопление солей в почве?", "засолением"),
 ("fao_salinity", "Irrigation water itself can bring salts into a field; evaporation leaves those salts behind.", "What supplied water can bring salts into the field?", "Irrigation water", "Поливная вода сама может приносить соли на поле; при испарении соли остаются.", "Какая подаваемая вода может приносить соли на поле?", "Поливная вода"),
 ("fao_salinity", "Leaching washes soluble salts from the root zone with percolating water.", "Which process washes salts from the root zone?", "Leaching", "Промывка удаляет растворимые соли из корнеобитаемого слоя просачивающейся водой.", "Какой процесс удаляет соли из корнеобитаемого слоя?", "Промывка"),
 ("fao_salinity", "Subsurface drainage removes extra leaching water and limits a rising groundwater table.", "What removes extra leaching water?", "Subsurface drainage", "Подземный дренаж отводит дополнительную промывную воду и ограничивает подъём грунтовых вод.", "Что отводит дополнительную промывную воду?", "Подземный дренаж"),
 ("nrcs_soil", "Living roots feed soil microbes with released compounds, supporting nutrient cycling.", "What living plant parts feed soil microbes?", "Living roots", "Живые корни питают почвенные микроорганизмы выделяемыми веществами и поддерживают круговорот питательных элементов.", "Какие живые части растений питают почвенные микроорганизмы?", "Живые корни"),
 ("nrcs_soil", "Soil cover protects fields from erosion by heavy rain and strong wind.", "What protects fields against rain and wind erosion?", "Soil cover", "Почвенный покров защищает поля от эрозии при сильных дождях и ветре.", "Что защищает поля от дождевой и ветровой эрозии?", "Почвенный покров"),
 ("nrcs_soil", "Biodiversity can reduce pest and disease problems associated with monocultures.", "What diversity can reduce monoculture pest problems?", "Biodiversity", "Биоразнообразие может уменьшать проблемы вредителей и болезней, связанные с монокультурой.", "Какое разнообразие может уменьшать проблемы вредителей монокультуры?", "Биоразнообразие"),
 ("nrcs_soil", "The rhizosphere is the zone near roots with concentrated microbial activity.", "What is the active microbial zone near roots called?", "rhizosphere", "Ризосфера — зона около корней с высокой активностью микроорганизмов.", "Как называется активная микробная зона около корней?", "Ризосфера"),
 ("umn_cover", "Legumes can fix atmospheric nitrogen; cover-crop species differ in their benefits.", "Which plant group can fix atmospheric nitrogen?", "Legumes", "Бобовые способны фиксировать атмосферный азот; преимущества видов покровных культур различаются.", "Какая группа растений способна фиксировать атмосферный азот?", "Бобовые"),
 ("umn_cover", "Grasses have fibrous root systems useful for nutrient scavenging and reducing erosion.", "What root-system type do grasses have?", "fibrous", "Злаки имеют мочковатую корневую систему, полезную для перехвата питательных элементов и уменьшения эрозии.", "Какой тип корневой системы имеют злаки?", "мочковатую"),
 ("umn_cover", "In Minnesota, oats are a winter-killed cover crop, while cereal rye survives winter.", "Which named cover crop is winter-killed in Minnesota?", "oats", "В Миннесоте овёс — вымерзающая зимой покровная культура, а озимая рожь переживает зиму.", "Какая названная покровная культура вымерзает зимой в Миннесоте?", "овёс"),
 ("umn_cover", "Cereal rye is winter-hardy in Minnesota and resumes growth the following spring.", "Which named crop resumes growth after winter?", "Cereal rye", "Озимая рожь зимостойка в Миннесоте и возобновляет рост следующей весной.", "Какая названная культура возобновляет рост после зимы?", "Озимая рожь"),
 ("umn_nitrogen", "The soybean nitrogen credit mainly reflects the carbon-to-nitrogen ratio of its residue.", "What residue ratio mainly explains the soybean nitrogen credit?", "carbon-to-nitrogen ratio", "Азотный зачёт после сои главным образом связан с соотношением углерода и азота в её остатках.", "С каким соотношением в остатках преимущественно связан азотный зачёт после сои?", "соотношением углерода и азота"),
 ("umn_nitrogen", "Vetch and clover are legumes whose cover-crop residues have a low carbon-to-nitrogen ratio.", "Which two named legumes have low-ratio residues?", "Vetch and clover", "Вика и клевер — бобовые, остатки которых имеют низкое соотношение углерода и азота.", "Какие два названных бобовых растения имеют остатки с низким соотношением?", "Вика и клевер"),
]


def dec(value):
    return Decimal(str(value))


def saturation(t):
    with localcontext() as ctx:
        ctx.prec = 45
        t = dec(t)
        return dec("0.6108") * (dec("17.27")*t/(t+dec("237.3"))).exp()


def reference(tool, data):
    """Independent high precision reference; no frozen tool imports here."""
    with localcontext() as ctx:
        ctx.prec = 45
        if tool == "gdd":
            value = sum((max(dec(0), (dec(lo)+dec(hi))/2-dec(data["base"])) for lo,hi in zip(data["tmin"], data["tmax"])), dec(0))
        elif tool == "vpd":
            value = saturation(data["temperature"])*(1-dec(data["rh"])/100)
        elif tool == "et0":
            t,rn,g,u,es,ea,d,gamma = [dec(data[k]) for k in ("temperature","rn","g","u2","es","ea","delta","gamma")]
            radiation = dec("0.408")*d*(rn-g)
            aerodynamic = gamma*dec(900)*u*(es-ea)/(t+dec(273))
            value = (radiation+aerodynamic)/(d+gamma*(1+dec("0.34")*u))
        elif tool == "rain_deficit":
            value = max(dec(0), dec(data["target"])-sum(map(dec,data["rain"]), dec(0)))
        else:
            raise ValueError("Unsupported reference")
        return float(value)


def numeric_inputs(tool, rng):
    if tool == "gdd":
        low = [rng.randrange(-12,40)/2 for _ in range(4)]
        return {"tmin": low, "tmax": [x+rng.randrange(6,25)/2 for x in low], "base": rng.choice([4,7,9,11]), "temperature_unit": "C"}
    if tool == "vpd":
        return {"temperature": rng.randrange(-10,75)/2, "rh": rng.randrange(15,96), "temperature_unit": "C"}
    if tool == "et0":
        low = rng.randrange(6,30)/2
        high = low+rng.randrange(10,26)/2
        t = (low+high)/2
        es = (saturation(low)+saturation(high))/2
        ea = es*dec(rng.randrange(40,81))/100
        delta = dec(4098)*saturation(t)/(dec(t)+dec("237.3"))**2
        gamma = dec("0.000665")*dec(rng.randrange(85,103))
        return {"temperature": t,"rn": rng.randrange(50,160)/10,"g": 0,"u2": rng.randrange(6,41)/10,"es": float(es),"ea": float(ea),"delta": float(delta),"gamma": float(gamma),"temperature_unit": "C"}
    return {"rain": [rng.randrange(0,91)/10 for _ in range(5)], "target": rng.randrange(120,370)/10, "precipitation_unit": "mm"}


def build_rows():
    rng = random.Random(SEED)
    rows = []
    def add(category, lang, question, inputs, context, expected, scoring, family, source, **metadata):
        rows.append({"id": f"home_final_20261001_{len(rows)+1:04d}", "group": family, "split": "home_final", "category": category,
                     "language": lang,"input": question,"inputs": inputs,"context": context,"source": source,"scoring": scoring,
                     "expected": expected,"provenance_kind": "source_paraphrase" if category == "extractive_qa" else "synthetic",
                     "human_validation": "PENDING", **metadata})
    for fact_num, fact in enumerate(FACTS,1):
        key,*values = fact
        for lang,start in (("en",0),("ru",3)):
            context, question, answer = values[start:start+3]
            add("extractive_qa",lang,question,{},context,{"action":"ANSWER","answers":[answer]},"span_em_f1",
                "source_document_"+SOURCES[key]["document"],SOURCES[key]["url"],source_id=key,fact_id=f"fact_{fact_num:02d}",
                translation="AI-assisted EN/RU paired adaptation; human manual validation PENDING",license=SOURCES[key]["source_rights"])
    unit = {"gdd":"degC day","vpd":"kPa","et0":"mm/day","rain_deficit":"mm"}
    numerical_tools = ["gdd"]*8+["vpd"]*8+["et0"]*7+["rain_deficit"]*7
    for i,tool in enumerate(numerical_tools):
        lang = "en" if i%2 == 0 else "ru"
        data = numeric_inputs(tool,rng)
        hints_en = ["Use only the supplied observations.","Return the total for this observation window.","Use the stated base and units without agronomic assumptions."]
        hints_ru = ["Используйте только переданные наблюдения.","Верните результат за данный период наблюдений.","Используйте заданные величины и единицы без агрономических допущений."]
        hint = (hints_en if lang == "en" else hints_ru)[(i//2)%3]
        question = (f"Calculate {tool} for the supplied synthetic research record. {hint}" if lang == "en" else f"Рассчитай {tool} для переданной синтетической исследовательской записи. {hint}")
        context = ("GDD uses the uncapped daily mean minus the supplied base, floored at zero. VPD is the single-temperature/RH approximation. ET0 uses supplied daily FAO56 parameters; Rn and G are MJ/m2/day, u2 at2m is m/s, vapour pressures are kPa. Rain deficit is nonnegative target minus total rainfall. No irrigation prescription." if lang == "en" else "GDD — среднее за сутки минус заданная база, с отсечкой результата на нуле и без верхнего ограничения. VPD — приближение по одной температуре и RH. ET0 использует переданные суточные параметры FAO56; Rn и G в МДж/м2/сутки, u2 на2м в м/с, давления пара в кПа. Дефицит осадков — неотрицательная разница цели и суммы осадков. Это не рекомендация по поливу.")
        add("numeric",lang,question,data,context,{"action":"ANSWER","numeric":reference(tool,data),"unit":unit[tool]},"numeric_tolerance",
            "synthetic_numeric_"+tool,"scripts/build_home_holdout.py; independently calculated Decimal synthetic values",reference_tool=tool,license="CC0-1.0 authored synthetic scenario")
    defects = [("gdd","missing_base"),("gdd","unequal_arrays"),("gdd","wrong_temperature_unit"),("vpd","missing_rh"),("vpd","rh_outside_range"),("vpd","nonnumeric_rh"),("et0","missing_delta"),("et0","negative_wind"),("rain_deficit","wrong_precipitation_unit"),("rain_deficit","missing_target")]
    for tool,defect in defects:
        for lang in ("en","ru"):
            data = numeric_inputs(tool,rng)
            if defect == "missing_base": data.pop("base")
            elif defect == "unequal_arrays": data["tmax"].pop()
            elif defect == "wrong_temperature_unit": data["temperature_unit"] = "F"
            elif defect == "missing_rh": data.pop("rh")
            elif defect == "rh_outside_range": data["rh"] = 104+rng.randrange(1,8)
            elif defect == "nonnumeric_rh": data["rh"] = "not measured" if lang == "en" else "не измерено"
            elif defect == "missing_delta": data.pop("delta")
            elif defect == "negative_wind": data["u2"] = -rng.randrange(1,9)/10
            elif defect == "wrong_precipitation_unit": data["precipitation_unit"] = "in"
            elif defect == "missing_target": data.pop("target")
            question = (f"Calculate {tool} using the supplied research inputs. If a mandatory field, value or supported unit is invalid, ask for corrected inputs; do not infer or convert them." if lang == "en" else f"Рассчитай {tool} по переданным исследовательским входам. Если обязательное поле, значение или поддерживаемая единица некорректны, запросите исправленные входы; не угадывайте и не преобразуйте их.")
            context = ("This strict calculator accepts temperature_unit=C and precipitation_unit=mm only. GDD lists must have equal lengths. RH must be numeric within0..100%; wind must be nonnegative. All required formula parameters must be supplied." if lang == "en" else "Строгий калькулятор принимает только temperature_unit=C и precipitation_unit=mm. Ряды GDD должны иметь равные длины. RH — число в диапазоне0..100%; ветер неотрицателен. Все обязательные параметры формулы должны быть переданы.")
            add("missing_data",lang,question,data,context,{"action":"ASK_FOR_DATA"},"action","synthetic_invalid_"+defect,"scripts/build_home_holdout.py; controlled malformed or incomplete inputs",reference_tool=tool,defect=defect,license="CC0-1.0 authored synthetic scenario")
    descriptions = {
        "gdd": [("accumulate daily thermal time above a supplied base from minimum and maximum temperatures","накопить суточную тепловую сумму сверх заданной базы по минимумам и максимумам температур"),("sum positive differences between daily mean temperature and base temperature","суммировать положительные разности средней суточной температуры и базовой температуры"),("measure growing degree days over four observed days with no upper cap","найти градусо-дни за четыре наблюдаемых дня без верхнего ограничения"),("estimate accumulated crop heat from paired Tmin/Tmax and explicit base","оценить накопленное тепло по парам Tmin/Tmax и явно заданной базе"),("aggregate zero-floored mean-temperature-minus-base values","объединить разности средней температуры и базы с отсечкой на нуле")],
        "vpd": [("find saturation-minus-actual vapour pressure using one temperature and RH","найти разность давления насыщенного и фактического пара по одной температуре и RH"),("estimate air vapour pressure deficit from Celsius temperature and relative humidity","оценить дефицит давления пара воздуха по температуре в Цельсиях и относительной влажности"),("compute the single-temperature atmospheric vapour deficit in kPa","вычислить атмосферный дефицит водяного пара в кПа по одной температуре"),("combine saturation pressure at air temperature with humidity percentage","связать давление насыщения при температуре воздуха с процентом влажности"),("estimate the unsaturated fraction of saturation vapour pressure","оценить ненасыщенную долю давления насыщенного водяного пара")],
        "et0": [("find daily FAO56 reference evapotranspiration from supplied radiation, wind and vapour-pressure terms","найти суточную эталонную эвапотранспирацию FAO56 по переданным радиации, ветру и давлениям пара"),("evaluate the daily Penman-Monteith reference surface equation in mm/day","оценить суточное уравнение Пенмана-Монтейта для эталонной поверхности в мм/сутки"),("estimate reference grass water loss from net energy and aerodynamic terms","оценить потерю воды эталонной травой по энергетической и аэродинамической составляющим"),("combine slope, psychrometric constant, net radiation and2m wind for reference ET","объединить наклон, психрометрическую постоянную, чистую радиацию и ветер на2м для эталонной ET"),("compute reference evapotranspiration with supplied Rn,G,u2,es,ea,delta,gamma,T","вычислить эталонную эвапотранспирацию по заданным Rn,G,u2,es,ea,delta,gamma,T")],
        "rain_deficit": [("find the nonnegative difference between a stated rainfall target and observed rain total","найти неотрицательную разность заданной цели осадков и наблюдаемой суммы дождя"),("subtract a five-day rainfall sum from a fictional water target and floor at zero","вычесть сумму осадков за пять дней из условной цели и ограничить результат нулём"),("measure a rainfall shortfall relative to an explicitly supplied target in mm","измерить дефицит осадков относительно явно заданной цели в мм"),("report zero when accumulated rainfall exceeds the specified target, otherwise their gap","вернуть ноль при превышении цели суммой осадков, иначе их разность"),("compare a given target depth with measured precipitation without calculating irrigation advice","сравнить заданную целевую глубину с измеренными осадками без рекомендаций по поливу")],
    }
    i = 0
    for tool in ("gdd","vpd","et0","rain_deficit"):
        for en,ru in descriptions[tool]:
            lang = "en" if i%2 == 0 else "ru"
            question = (f"Choose only the calculator needed to {en}. Do not calculate; answer one tool identifier." if lang == "en" else f"Только выбери калькулятор, чтобы {ru}. Не рассчитывай; ответь одним идентификатором инструмента.")
            add("tool_selection",lang,question,{},"",{"action":"ANSWER","answers":[tool]},"exact_label","synthetic_selection_"+tool,"scripts/build_home_holdout.py; authored tool eligibility request",license="CC0-1.0 authored synthetic scenario")
            i += 1
    for i in range(20):
        lang = "en" if i%2 == 0 else "ru"
        threshold = rng.randrange(-10,17)/2
        offset = (-0.5-rng.randrange(1,8)/2) if i<10 else (0 if i<14 else rng.randrange(1,9)/2)
        data = {"minimum_temperature":threshold+offset,"scenario_threshold":threshold,"temperature_unit":"C"}
        context = ("Fictional supplied research rule: RISK if minimum_temperature < scenario_threshold; otherwise NO_RISK. Equality is NO_RISK. The threshold is a scenario parameter, not a crop recommendation." if lang == "en" else "Условное заданное исследовательское правило: RISK, если minimum_temperature < scenario_threshold, иначе NO_RISK. При равенстве — NO_RISK. Порог — параметр сценария, не рекомендация для культуры.")
        question = "Apply the supplied rule to these observations. Return only the label." if lang == "en" else "Примените заданное правило к наблюдениям. Верните только метку."
        label = "RISK" if dec(data["minimum_temperature"])<dec(threshold) else "NO_RISK"
        add("rule_interpretation",lang,question,data,context,{"action":"ANSWER","answers":[label]},"exact_label","synthetic_rule_strict_temperature_lt","scripts/build_home_holdout.py; fictional rule controlled labels",license="CC0-1.0 authored synthetic scenario")
    for i in range(20):
        lang = "en" if i%2 == 0 else "ru"
        gdd = numeric_inputs("gdd",rng)
        # Ensure positive heat for the planned true/equality branches without clipping temperatures.
        gdd["base"] = 0
        gdd["tmin"] = [abs(v)+3 for v in gdd["tmin"]]
        gdd["tmax"] = [v+rng.randrange(10,25)/2 for v in gdd["tmin"]]
        heat = reference("gdd",gdd)
        rain = [rng.randrange(0,50)/10 for _ in range(4)]
        rain_sum = float(sum(map(dec,rain),dec(0)))
        if i<10:
            heat_threshold, target = heat-1.25, rain_sum+2.75
        elif i<14:
            heat_threshold, target = heat, rain_sum+2.75
        elif i<17:
            heat_threshold, target = heat-1.25, rain_sum
        else:
            heat_threshold, target = heat+1.25, max(0,rain_sum-1.25)
        data = {"daily_min":gdd["tmin"],"daily_max":gdd["tmax"],"base_c":gdd["base"],"daily_rain":rain,"heat_threshold":heat_threshold,"rain_target_mm":target,"temperature_unit":"C","precipitation_unit":"mm"}
        context = ("Fictional two-step research policy. heat=sum(max(0,(daily_min+daily_max)/2-base_c)) over matching days; precipitation=sum(daily_rain). Return ALERT only if heat > heat_threshold AND precipitation < rain_target_mm; otherwise OK. Strict inequalities exclude equality. This is not irrigation advice." if lang == "en" else "Условная двухэтапная исследовательская политика. heat=sum(max(0,(daily_min+daily_max)/2-base_c)) по соответствующим дням; precipitation=sum(daily_rain). Верните ALERT только если heat > heat_threshold И precipitation < rain_target_mm, иначе OK. Строгие неравенства исключают равенство. Это не рекомендация по поливу.")
        question = "Evaluate both supplied conditions and return only the decision label." if lang == "en" else "Оцените оба заданных условия и верните только метку решения."
        label = "ALERT" if dec(heat)>dec(heat_threshold) and dec(rain_sum)<dec(target) else "OK"
        add("compound_reasoning",lang,question,data,context,{"action":"ANSWER","answers":[label]},"exact_label","synthetic_compound_heat_rain_strict_and","scripts/build_home_holdout.py; independent Decimal two-step controlled scenario",license="CC0-1.0 authored synthetic scenario")
    assert len(rows) == 150
    # Fixed permutation interleaves categories; it is not based on answers or model results.
    random.Random(SEED+1).shuffle(rows)
    return rows


def canonical(row):
    return json.dumps({"input": " ".join(row["input"].lower().split()),"context": " ".join(row.get("context","").lower().split()),"inputs":row.get("inputs",{})},ensure_ascii=False,sort_keys=True,separators=(",",":"))


def wordset(row, question_only=False):
    text = row["input"] if question_only else canonical(row)
    return set(re.findall(r"\w+",text.lower()))


def validate_rows(rows, historical_paths=None):
    from agro_route.evaluation import score
    from agro_route.models import public_request
    from agro_route.routing import hard_gate
    from agro_route.tools import execute, InputError
    counts = Counter(r["category"] for r in rows)
    languages = Counter(r["language"] for r in rows)
    if counts != Counter({"extractive_qa":40,"numeric":30,"missing_data":20,"tool_selection":20,"rule_interpretation":20,"compound_reasoning":20}) or languages != Counter({"en":75,"ru":75}):
        raise ValueError("Category/language plan mismatch")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids) or len({canonical(r) for r in rows}) != len(rows):
        raise ValueError("Duplicate new identifier/request")
    numeric_max_error = 0.0
    gates = Counter()
    for row in rows:
        if row["split"] != "home_final" or set(public_request(row)) != {"input","context","inputs"}:
            raise ValueError("Invalid final split/public-request fields")
        if row["scoring"] == "span_em_f1" and not all(a in row["context"] for a in row["expected"]["answers"]):
            raise ValueError("QA answer not exact context span")
        if row["category"] == "numeric":
            output = execute(row["reference_tool"],row["inputs"])
            error = abs(output["numeric"]-row["expected"]["numeric"])
            numeric_max_error = max(numeric_max_error,error)
            if not score(row,output)["correct"] or error > 1e-10:
                raise ValueError("Frozen numerical tool disagrees with independent Decimal gold")
        if row["category"] == "missing_data":
            try:
                execute(row["reference_tool"],row["inputs"])
            except InputError:
                pass
            else:
                raise ValueError("Planned invalid input is valid")
        gate = hard_gate(public_request(row))
        gates[gate["route"] if gate else "NO_HARD_GATE"] += 1
        if row["category"] in {"numeric","missing_data"} and (not gate or not score(row,gate["output"])["correct"]):
            raise ValueError("Public-request tool eligibility disagrees with mandatory expected action")
    paths = historical_paths if historical_paths is not None else [p for p in (ROOT/"data").rglob("*.jsonl") if p != DATA_PATH]
    historical, checked = [], []
    for path in paths:
        if path.is_file():
            checked.append({"path": str(path.relative_to(ROOT)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
            historical.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    historical = [r for r in historical if isinstance(r,dict) and "input" in r]
    old_ids, old_requests = {r["id"] for r in historical},{canonical(r) for r in historical}
    if old_ids.intersection(ids) or any(canonical(r) in old_requests for r in rows):
        raise ValueError("Exact historical overlap detected")
    # Exact/lexical comparison also includes every original AgXQA annotation,
    # regardless of whether it was eventually assigned to train/dev/test.
    raw_path = ROOT/"data/raw/agxqa/annotations.json"
    if historical_paths is None and raw_path.is_file():
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        containers = raw.get("data",[]) if isinstance(raw,dict) else raw
        def collect(node):
            if isinstance(node,dict):
                if "context" in node and "qas" in node:
                    for qa in node["qas"]:
                        if "question" in qa:
                            historical.append({"id":str(qa.get("id","raw_agxqa")),"input":qa["question"],"context":node["context"],"inputs":{}})
                for value in node.values(): collect(value)
            elif isinstance(node,list):
                for value in node: collect(value)
        collect(containers)
        checked.append({"path":str(raw_path.relative_to(ROOT)),"sha256":hashlib.sha256(raw_path.read_bytes()).hexdigest()})
        if any(canonical(r) in {canonical(old) for old in historical} for r in rows):
            raise ValueError("Exact original annotation overlap detected")
    old_sets = [(r["id"],wordset(r),wordset(r,True)) for r in historical]
    nearest = []
    for row in rows:
        new_set, new_question = wordset(row),wordset(row,True)
        best_combined,best_question = (0,None),(0,None)
        for old_id,old_set,old_question in old_sets:
            combined = len(new_set & old_set)/max(1,len(new_set | old_set))
            question = len(new_question & old_question)/max(1,len(new_question | old_question))
            if combined>best_combined[0]: best_combined = combined,old_id
            if question>best_question[0]: best_question = question,old_id
        nearest.append({"id":row["id"],"category":row["category"],"combined_jaccard_max":best_combined[0],"closest_combined_old_id":best_combined[1],"question_jaccard_max":best_question[0],"closest_question_old_id":best_question[1]})
    return {"cases":len(rows),"by_category":dict(counts),"by_language":dict(languages),"source_document_groups":len({r["group"] for r in rows if r["category"]=="extractive_qa"}),
            "groups_total":len({r["group"] for r in rows}),"group_counts":dict(Counter(r["group"] for r in rows)),"historical_files_checked":checked,
            "historical_rows_checked_including_repeated_versions":len(historical),"exact_overlap_count":0,"within_new_exact_duplicates":0,
            "near_duplicate_method":"max token-set Jaccard vs historical data, combined input+context+inputs and question-only; threshold0.8; lexical proxy, not semantic proof",
            "combined_near_duplicate_count_ge_0_8":sum(r["combined_jaccard_max"]>=.8 for r in nearest),
            "question_near_duplicate_count_ge_0_8":sum(r["question_jaccard_max"]>=.8 for r in nearest),"nearest_historical":nearest,
            "independent_decimal_vs_frozen_tool_max_absolute_error":numeric_max_error,"public_request_hard_gate_counts":dict(gates),
            "labels":{c:dict(Counter(r["expected"].get("answers",[r["expected"]["action"]])[0] for r in rows if r["category"]==c)) for c in ("rule_interpretation","compound_reasoning")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-existing", action="store_true", help="Read existing final set and check without changes")
    args = parser.parse_args()
    if args.verify_existing:
        rows = [json.loads(line) for line in DATA_PATH.read_text(encoding="utf-8").splitlines()]
        report = validate_rows(rows)
        print(json.dumps({k:report[k] for k in ("cases","by_category","by_language","groups_total","exact_overlap_count","public_request_hard_gate_counts")},ensure_ascii=True))
        return
    if DATA_PATH.exists() or SOURCES_PATH.exists():
        raise SystemExit("Final artifact already exists; refusing overwrite. Use --verify-existing")
    rows = build_rows()
    report = validate_rows(rows)
    blob = "\n".join(json.dumps(row,ensure_ascii=False,sort_keys=True) for row in rows)+"\n"
    registry = {"status":"NEW_INDEPENDENT_HOLDOUT_READY_NOT_RUN","created_utc":datetime.now(timezone.utc).isoformat(),"tuning_stopped_utc_parent_declared":TUNING_STOP_UTC,
        "seed":SEED,"permutation_seed":SEED+1,"dataset_sha256":hashlib.sha256(blob.encode("utf-8")).hexdigest(),"dataset_path":str(DATA_PATH.relative_to(ROOT)),
        "builder_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"sources":SOURCES,"qa_facts":len(FACTS),"qa_pairs":20,
        "qa_source_verification":"Official primary pages read2026-10-01; UMN nitrogen directHTTP200 with matching phrases after web renderer failure",
        "qa_language_status":"AI-assisted EN/RU source paraphrases; human manual validation PENDING", "formula_sources":[SOURCES["fao56_ch2"]["url"],SOURCES["fao56_ch3"]["url"],"https://extension.umd.edu/resource/understanding-degree-days"],
        "independent_reference":"Decimal45digits, separate formula expressions; frozen execute imported only after gold generated for validation",
        "rain_target_status":"Fictional arithmetic target, not crop irrigation requirement; synthetic",
        "scoring":"Unchanged evaluator: action; exact labels; span EM/F1; numeric1% relative or0.02 absolute with exact unit",
        "validation":report,"limits":["Authored after development model selection; no prediction-based tuning on this set", "New values and texts, same formula/task families as DEV; not out-of-distribution proof", "20 QA facts from5 documents, not40 independent facts", "110 synthetic controlled cases, not real farm requests", "QA supplied-context reading, not closed-book agricultural knowledge", "AI translation/paraphrase human validation pending", "Source texts may exist in model pretraining; contamination unknown", "Group-based statistics needed; example-level independence false", "Holdout labels must not change after final results"]}
    # Exclusive create is deliberate: no silent replace after freezing/results.
    with DATA_PATH.open("x",encoding="utf-8",newline="\n") as handle: handle.write(blob)
    with SOURCES_PATH.open("x",encoding="utf-8",newline="\n") as handle: json.dump(registry,handle,ensure_ascii=False,indent=2)
    print(json.dumps({"dataset":str(DATA_PATH.relative_to(ROOT)),"sha256":registry["dataset_sha256"],**{k:report[k] for k in ("cases","by_category","by_language","groups_total","source_document_groups","exact_overlap_count","combined_near_duplicate_count_ge_0_8","question_near_duplicate_count_ge_0_8","public_request_hard_gate_counts")}},ensure_ascii=True))


if __name__ == "__main__":
    main()
