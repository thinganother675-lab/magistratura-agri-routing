"""Build an additive compact bibliography; retain historical reading provenance."""
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
old = json.loads((ROOT / 'results/publication_sources_20261003/verified_bibliography_18.json').read_text(encoding='utf8'))
keys = ['routellm', 'hybridllm', 'unifiedrouting', 'routerbench', 'automix', 'frugalgpt', 'semanticentropy', 'abstention', 'pllama', 'agrigpt', 'agrollm', 'agriagent', 'agrotools', 'taubench', 'toolace', 'bitnet', 'gemma4', 'agxqa']
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
entries = []
for key, e in zip(keys, old['entries']):
    row = {k: e.get(k) for k in ['id', 'title', 'authors', 'initial_year', 'primary_url', 'published_primary_url', 'venue', 'latest_arxiv_version', 'reading_status', 'historical_ledger']}
    row.update(citekey=key, source_class='SCIENTIFIC_AI_2023_2026', metadata_check_utc=now,
               metadata_check_method='Official arXiv page reopened through web tool; selected-section reading remains historical',
               full_paper_read_this_session=False)
    if key == 'agxqa':
        row['metadata_check_method'] = 'Retained 2026-10-03 primary Crossref metadata; current web retrieval unavailable'
        row['metadata_check_utc'] = e['metadata_checked_utc']
        row['volume'], row['article_number'], row['doi'] = e['volume'], e['article_number'], e['doi']
    if key == 'routellm':
        row['published_title'] = 'RouteLLM: Learning to Route LLMs from Preference Data'
        row['published_metadata_reopened_this_session'] = True
    if key == 'hybridllm':
        row['venue_note'] = 'Current arXiv Comments reports acceptance to ICLR 2024; proceedings not independently checked in this audit'
    entries.append(row)
fao = dict(citekey='fao56', id='FAO_IDP_56_1998', title='Crop evapotranspiration - Guidelines for computing crop water requirements',
           authors=['Allen, Richard G.', 'Pereira, Luis S.', 'Raes, Dirk', 'Smith, Martin'], initial_year=1998,
           venue='FAO Irrigation and Drainage Paper 56', publisher='Food and Agriculture Organization of the United Nations',
           primary_url='https://www.fao.org/4/x0490e/x0490e00.htm', source_class='FOUNDATIONAL_FORMULA',
           metadata_check_utc=now, metadata_check_method='Official FAO title page and chapters 2/3 reopened through web tool',
           equation_sources={'daily_ET0_equation_6': 'https://www.fao.org/4/x0490e/x0490e06.htm',
                             'saturation_vapour_pressure_equation_11': 'https://www.fao.org/4/x0490e/x0490e07.htm'},
           reading_status='RELEVANT_FORMULA_CHAPTERS', full_paper_read_this_session=False)
entries.append(fao)
order = ['frugalgpt', 'automix', 'hybridllm', 'routellm', 'unifiedrouting', 'routerbench', 'semanticentropy', 'abstention', 'pllama', 'agrigpt', 'agrollm', 'agriagent', 'agrotools', 'taubench', 'toolace', 'bitnet', 'gemma4', 'agxqa', 'fao56']
entries.sort(key=lambda row: order.index(row['citekey']))
for i, row in enumerate(entries, 1):
    row['manuscript_number'] = i
    if row['citekey'] == 'unifiedrouting':
        row['published_primary_url'] = 'https://proceedings.mlr.press/v267/dekoninck25a.html'
        row['published_metadata_reopened_this_session'] = True
        row['venue'] = 'ICML 2025, PMLR 267:12987-13010'
(OUT/'compact_bibliography_19.json').write_text(json.dumps(dict(created_utc=now, scientific_count=19,
    recent_AI_count=18, foundational_formula_count=1, entries=entries), ensure_ascii=False, indent=2), encoding='utf8')
lines = ['# Компактная библиография для согласованных RU/EN рукописей', '', f'Сформировано UTC: {now}.', '',
         '18 научных работ 2023–2026 годов и один фундаментальный расчётный источник. Model cards, API и правила публикации не входят в этот счёт. 17 страниц arXiv повторно открыты в текущем аудите; AgXQA сохраняет первичные Crossref-метаданные 03.10.2026. Ранее прочитанные выбранные разделы не выдаются за новое полное чтение. Препринты не объявлены рецензированными публикациями.', '', '## Научные источники по ИИ', '']
bibs=[]
for i, e in enumerate(entries, 1):
    if i == 19:
        lines.extend(['', '## Фундаментальный источник формул', ''])
    authors='; '.join(e['authors'][:3]) + ('; et al.' if len(e['authors'])>3 else '')
    title=e.get('published_title',e['title'])
    url=e.get('published_primary_url') or e['primary_url']
    venue=e.get('venue') or 'arXiv preprint'
    year=2025 if e['citekey'] in ['routellm','unifiedrouting','toolace'] else e['initial_year']
    lines.append(f"{i}. **[{e['citekey']}]** {authors}. {title}. {year}. {venue}. [Первичный источник]({url}).")
    if e['citekey']=='routellm':
        lines.append('   Название опубликованной версии содержит *from*; название arXiv-версии — *with*. Это версии одной работы.')
    if e['citekey']=='hybridllm':
        lines.append('   arXiv сообщает принятие в ICLR 2024; здесь цитируется подтверждённая arXiv-версия.')
    bibauthors=' and '.join(e['authors'][:3]) + (' and others' if len(e['authors'])>3 else '')
    bibs.append('@misc{'+e['citekey']+',\n  author = {'+bibauthors+'},\n  title = {'+title.replace('$\\tau$','{\\tau}')+'},\n  year = {'+str(year)+'},\n  howpublished = {'+venue+'},\n  url = {'+url+'}\n}')
lines.extend(['', '## Точные формулы FAO-56 и предел интерпретации', '',
              r'Ежесуточная эталонная эвапотранспирация, гл. 2, уравнение (6): $ET_0=[0.408\Delta(R_n-G)+\gamma(900/(T+273))u_2(e_s-e_a)]/[\Delta+\gamma(1+0.34u_2)]$.', '',
              'Единицы: ET0 — мм/сут; Rn и G — МДж/(м²·сут); T — °C на 2 м; u2 — м/с на 2 м; es, ea — кПа; Δ и γ — кПа/°C. Это ET0 стандартизованной эталонной поверхности; расчёт не является ETc или готовой нормой полива.', '',
              r'Гл. 3, уравнение (11): $e^0(T)=0.6108\exp[17.27T/(T+237.3)]$ кПа. VPD=$e_s-e_a$; для суточных данных FAO-56 уравнение (12) использует среднее $[e^0(T_{max})+e^0(T_{min})]/2$. Упрощение по одному T и RH должно быть явно названо в методах.', '',
              'Rain gap является собственным определением Study C; FAO-56 не служит подтверждением агрономической нормы этой величины. GDD требует отдельного определения базовой температуры и правил ограничения; источник FAO-56 не следует использовать как универсальное обоснование GDD.', '',
              '[FAO-56, титульная страница](https://www.fao.org/4/x0490e/x0490e00.htm); [глава 2, ET0](https://www.fao.org/4/x0490e/x0490e06.htm); [глава 3, влажность и VPD](https://www.fao.org/4/x0490e/x0490e07.htm).'])
(OUT/'VERIFIED_BIBLIOGRAPHY_19_RU.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
(OUT/'references_19.bib').write_text('\n\n'.join(bibs)+'\n',encoding='utf8')
print(f'Wrote {len(entries)} references at {now}')
