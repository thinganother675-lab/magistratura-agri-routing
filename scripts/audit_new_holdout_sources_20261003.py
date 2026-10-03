# SPDX-License-Identifier: Apache-2.0
"""Read-only source/overlap audit. No split, gold labels, or model calls are made."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.runtime/new_sources_20261003'
OUT = ROOT / 'results/new_holdout_sources_20261003'
OUT.mkdir(parents=True, exist_ok=True)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def norm(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', str(value)).casefold()))

def present(value):
    return bool(str(value).strip()) and str(value).strip().casefold() not in {'na', 'n/a', 'null', 'none', 'nan'}

def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)

def urls(value):
    found = set()
    for text in strings(value):
        for raw in re.findall(r'https?://[^\s<>"\]\[{}]+', text):
            raw = raw.rstrip('.,;:)')
            p = urlsplit(raw)
            # Conservative diagnostic canonicalization, not document-identity proof.
            host = p.netloc.lower().removeprefix('www.')
            found.add(urlunsplit(('https', host, p.path.rstrip('/'), p.query, '')))
    return found

def qitems(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'question', 'input'} and isinstance(item, str):
                yield item
            elif key not in {'expected', 'answers', 'answer'}:
                yield from qitems(item)
    elif isinstance(value, list):
        for item in value:
            yield from qitems(item)

old_paths = [ROOT / p for p in (
    'data/benchmark.jsonl', 'data/versions/benchmark_v0.1.jsonl',
    'data/home_dev_bilingual_20261001.jsonl', 'data/home_holdout_20261001.jsonl',
    'data/raw/agxqa/annotations.json', 'data/home_holdout_20261001_sources.json',
    '.runtime/20261002_170443Z_21722066_dataset_literature/agxqa_train.jsonl',
    '.runtime/20261002_170443Z_21722066_dataset_literature/agxqa_validation.jsonl',
    '.runtime/20261002_170443Z_21722066_dataset_literature/agxqa_test.jsonl',
    '.runtime/20261002_170443Z_21722066_dataset_literature/agxqa_test_main.jsonl',
)]
old_q = defaultdict(set)
old_urls = defaultdict(set)
old_summary = []
for path in old_paths:
    if not path.exists():
        old_summary.append({'path': path.relative_to(ROOT).as_posix(), 'status': 'MISSING'})
        continue
    text = path.read_text(encoding='utf-8-sig')
    try:
        records = [json.loads(line) for line in text.split('\n') if line.strip()] if path.suffix == '.jsonl' else [json.loads(text)]
    except json.JSONDecodeError:
        old_summary.append({'path': path.relative_to(ROOT).as_posix(), 'status': 'NOT_VALID_JSON_EXCLUDED', 'sha256': digest(path)})
        continue
    qs = [norm(q) for rec in records for q in qitems(rec) if present(q)]
    us = set().union(*(urls(rec) for rec in records))
    rel = path.relative_to(ROOT).as_posix()
    for q in qs:
        old_q[q].add(rel)
    for u in us:
        old_urls[u].add(rel)
    old_summary.append({'path': rel, 'sha256': digest(path), 'records': len(records), 'question_fields': len(qs), 'unique_normalized_questions': len(set(qs)), 'unique_urls': len(us)})

path = CACHE / 'ilri_all598.csv'
with path.open(encoding='utf-8-sig', newline='') as fh:
    reader = csv.DictReader(fh)
    fields = list(reader.fieldnames)
    rows = list(reader)
meta = json.loads((CACHE / 'ilri_metadata.json').read_text(encoding='utf-8'))
version = meta['data']['latestVersion']
questions = defaultdict(list)
for i, row in enumerate(rows):
    questions[norm(row['question'])].append(i)
dupes = [ids for ids in questions.values() if len(ids) > 1]
parent = list(range(len(rows)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
def union(a, b):
    parent[find(b)] = find(a)

source_members = defaultdict(list)
source_url_members = defaultdict(list)
for i, row in enumerate(rows):
    source = row.get('sources', '')
    us = urls(source)
    for u in us:
        source_url_members[u].append(i)
        source_members['url:' + u].append(i)
    if present(source) and not us:
        source_members['citation:' + norm(source)].append(i)
    if not present(source):
        # Unknown reference identity must not become one independently split group per row.
        source_members['unknown:ILRI_HACKATHON_20250609_UNSOURCED'].append(i)
for ids in list(questions.values()) + list(source_members.values()):
    for i in ids[1:]:
        union(ids[0], i)
components = defaultdict(list)
for i in range(len(rows)):
    components[find(i)].append(i)
components_sorted = sorted(components.values(), key=lambda v: (-len(v), min(v)))
duplicate_manifest = []
for ids in dupes:
    answers = {norm(rows[i]['answer']) for i in ids if present(rows[i]['answer'])}
    duplicate_manifest.append({'row_indices_1based': [i + 1 for i in ids], 'question_sha256': hashlib.sha256(norm(rows[ids[0]]['question']).encode()).hexdigest(), 'distinct_nonmissing_normalized_answers': len(answers), 'different_answers_require_review': len(answers) > 1})
exact = []
near = []
old_token_sets = {q: set(q.split()) for q in old_q}
for q, ids in questions.items():
    qhash = hashlib.sha256(q.encode()).hexdigest()
    if q in old_q:
        exact.append({'question_sha256': qhash, 'new_row_indices_1based': [i+1 for i in ids], 'old_paths': sorted(old_q[q])})
    tokens = set(q.split())
    if len(tokens) < 5:
        continue
    best_q, score = None, 0
    for old, otokens in old_token_sets.items():
        if min(len(tokens),len(otokens)) / max(len(tokens),len(otokens)) < .8:
            continue
        j = len(tokens & otokens) / len(tokens | otokens)
        if j > score:
            best_q, score = old, j
    if score >= .8:
        near.append({'question_sha256': qhash, 'old_question_sha256': hashlib.sha256(best_q.encode()).hexdigest(), 'jaccard': score, 'new_row_indices_1based': [i+1 for i in ids], 'old_paths': sorted(old_q[best_q])})
shared_urls = [{'url': u, 'new_row_indices_1based': [i+1 for i in ids], 'old_paths': sorted(old_urls[u])} for u, ids in sorted(source_url_members.items()) if u in old_urls]
answer_counts = Counter(norm(r['answer']) for r in rows if present(r['answer']))
audit = {
    'status': 'CANDIDATE_AUDIT_DATA_BLOCKED_NOT_FROZEN_NOT_RUN',
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'purpose': 'Source acquisition/schema/group/overlap only; no human gold, final split, scoring or model inference',
    'review40': 'Not imported or used for development; no review40 file read by this script',
    'old_comparison': {'files': old_summary, 'unique_normalized_questions': len(old_q), 'unique_urls': len(old_urls), 'method': 'NFKC/casefold word normalization exact; word-set Jaccard>=0.8 for >=5-token questions; conservative URL diagnostic', 'limits': 'No semantic/paraphrase/cross-language overlap guarantee; no model-pretraining contamination audit'},
    'ilri': {
        'source': 'https://data.mel.cgiar.org/dataset.xhtml?persistentId=hdl:20.500.11766.1/FK2/6U4UAI',
        'metadata_api': 'https://data.mel.cgiar.org/api/datasets/:persistentId/?persistentId=hdl:20.500.11766.1/FK2/6U4UAI',
        'version': f"{version['versionNumber']}.{version['versionMinorNumber']}", 'release_time': version['releaseTime'],
        'license': version['license'], 'local_file': path.relative_to(ROOT).as_posix(),
        'sha256': digest(path), 'md5': hashlib.md5(path.read_bytes()).hexdigest(),
        'official_md5_matches': hashlib.md5(path.read_bytes()).hexdigest() == version['files'][0]['dataFile']['md5'],
        'bytes': path.stat().st_size, 'schema': fields, 'rows': len(rows),
        'nonmissing_by_column': {f:sum(present(r.get(f,'')) for r in rows) for f in fields},
        'unique_normalized_questions': len(questions), 'duplicate_question_groups': len(dupes), 'duplicate_extra_rows': sum(len(v)-1 for v in dupes),
        'duplicate_groups_with_different_nonmissing_answers': sum(d['different_answers_require_review'] for d in duplicate_manifest),
        'unique_nonmissing_normalized_answers': len(answer_counts), 'repeated_answer_groups': sum(n>1 for n in answer_counts.values()),
        'team_counts': dict(Counter(r['team'] for r in rows)), 'persona_counts': dict(Counter(r['persona'] for r in rows)), 'topic_counts': dict(Counter(r['topic'] for r in rows)),
        'source_cells_nonmissing': sum(present(r['sources']) for r in rows), 'unique_exact_nonmissing_source_cells': len({r['sources'] for r in rows if present(r['sources'])}),
        'rows_with_parseable_source_url': sum(bool(urls(r['sources'])) for r in rows), 'unique_source_urls': len(source_url_members),
        'collection_events': 1, 'collection_group': 'ILRI_NAIROBI_HACKATHON_20250609',
        'evidence_components': len(components_sorted), 'evidence_component_sizes': [len(v) for v in components_sorted],
        'evidence_component_method': 'Connected components of exact normalized question/shared URL/shared normalized non-URL citation; all unreferenced rows one unknown-source bucket; independence not certified',
        'overlap': {'exact_old_question_groups': len(exact), 'near_old_question_groups_jaccard_ge_08': len(near), 'shared_exact_canonical_source_urls': len(shared_urls), 'exact_matches': exact, 'near_matches': near, 'shared_urls': shared_urls},
        'scientific_companion': {'status':'NO_PEER_REVIEWED_COMPANION_VERIFIED','declared_related_publication':'CGIAR 2025 AgriLLM news article; not a scientific paper'},
        'gold_status': 'Crowdsourced answers are candidate evidence; neither NA nor omitted answers establishes gold ASK/ABSTAIN; new human adjudication required',
        'language': 'English only; Russian paired translations and adequacy have not been created/validated',
    },
    'mendeley': {
        'source':'https://data.mendeley.com/datasets/xxzm838jn8/1', 'doi':'10.17632/xxzm838jn8.1',
        'title':"A Comprehensive Multilingual Dataset of Farmers' Queries and Expert Advisories for LLM and RAG-Driven Agricultural Chatbots",
        'version':1,'publication_date':'2026-07-03','license_declared':'CC BY 4.0',
        'status':'METADATA_ONLY_DATA_DOWNLOAD_BLOCKED_HTTP_403','observed_rows':None,
        'depositor_claimed_rows':29982,'depositor_claimed_rows_per_language':{'en':9994,'bn':9994,'zh':9994},
        'depositor_claimed_schema':['id','question','answer','category','language','q_length','a_length'],
        'depositor_claimed_splits':{'train':20987,'validation':4497,'test':4498},
        'split_method_declared':'Stratified by language; 70/15/15 random_state=42; no document or translation-family grouping shown',
        'download_attempts':[{'url':u,'http_status':403} for u in ['https://data.mendeley.com/datasets/xxzm838jn8/1','https://data.mendeley.com/public-api/datasets/xxzm838jn8/versions/1/files','https://data.mendeley.com/public-api/datasets/xxzm838jn8/versions/1']],
        'groups_count':None,'overlap_with_old': 'NOT_MEASURED_FILES_UNAVAILABLE',
        'translation_family_leakage':'PLAUSIBLE_RISK_NOT_MEASURED; synchronized multilingual rows plus row-wise split; regroup before use',
        'scientific_companion':{'status':'NO_COMPANION_SCIENTIFIC_PAPER_VERIFIED'},
        'gold_status':'Expert verification is depositor claim; protocol/annotator evidence not independently verified',
    },
    'reference_only':[
        {'id':'NOAA_GHCND','url':'https://www.ncei.noaa.gov/pub/data/cdo/documentation/GHCND_documentation.pdf','status':'REFERENCE_ONLY_RIGHTS_FOR_SELECTED_DATA_UNVERIFIED','observed_samples':0,'group_count':None,'license_note':'Official documentation p1 contains WMO/non-US commercial redistribution caveats; cannot call all GHCND public domain','source_group_rule':'station/source-stream plus contiguous time block; not one independent row per day','scientific_companion':{'title':'An Overview of the Global Historical Climatology Network-Daily Database','authors':['Matthew J. Menne','Imke Durre','Russell S. Vose','Byron E. Gleason','Tamara G. Houston'],'year':2012,'journal':'Journal of Atmospheric and Oceanic Technology','volume':29,'issue':7,'pages':'897-910','doi':'10.1175/JTECH-D-11-00103.1','primary_url':'https://journals.ametsoc.org/abstract/journals/atot/29/7/jtech-d-11-00103_1.xml','reading_status':'ABSTRACT_READ_METADATA_VERIFIED','full_text_read':False}},
        {'id':'NRCS_CPS449_2020','url':'https://www.nrcs.usda.gov/sites/default/files/2022-09/Irrigation_Water_Management_449_CPS_9_2020.pdf','status':'REFERENCE_ONLY_DOCUMENT_LICENSE_UNVERIFIED','observed_samples':0,'group_count':1,'group_count_meaning':'one document candidate; no gold task sample authored','source_group_rule':'entire CPS449 document, including translations and derived paraphrases','old_source_document_overlap':'Different document from USDA_NRCS_soil_health_cropland; shared institution/topic not proof of independence','scientific_companion':'Technical standard, not peer-reviewed scientific paper','currency_note':'September2020 national PDF; current state FOTG version not verified'}
    ],
}
(OUT / 'source_manifest.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT / 'ilri_duplicate_groups.json').write_text(json.dumps(duplicate_manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT / 'ilri_evidence_groups.json').write_text(json.dumps([{'group_id':f'ILRI_EVIDENCE_{i+1:03d}','row_indices_1based':[r+1 for r in members],'certified_independent':False} for i,members in enumerate(components_sorted)],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'manifest':(OUT/'source_manifest.json').relative_to(ROOT).as_posix(),'ilri':{k:audit['ilri'][k] for k in ['rows','nonmissing_by_column','unique_normalized_questions','duplicate_question_groups','duplicate_extra_rows','duplicate_groups_with_different_nonmissing_answers','unique_source_urls','evidence_components','evidence_component_sizes','overlap']},'old_question_count':len(old_q)},ensure_ascii=False,indent=2))
