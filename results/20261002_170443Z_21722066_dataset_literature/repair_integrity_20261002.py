"""Light, one-shot versioned inventory repair; never regenerate questions/gold."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json

RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[1]
PACK=RUN/'human_review_pack'
NAMES=('blinded_questions.csv','blinded_questions.jsonl','README_RU.md',
       'provisional_gold_separate.csv','provisional_gold_separate.jsonl')
def digest(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def save_exclusive(path,data):
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(data,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
def now():return datetime.now(timezone.utc).isoformat()

def main():
    original_manifest=PACK/'manifest.json'
    original_delivery=RUN/'delivery_manifest.json'
    v2_path=PACK/'manifest_v2_integrity_20261002.json'
    delivery_v2_path=RUN/'delivery_manifest_v2.json'
    if v2_path.exists() or delivery_v2_path.exists():
        raise ValueError('VersionedCorrectionAlreadyExistsNoOverwrite')
    protected_paths=[original_manifest,original_delivery,*[PACK/name for name in NAMES]]
    protected_before={str(path.relative_to(ROOT).as_posix()):digest(path) for path in protected_paths}
    old=json.loads(original_manifest.read_text(encoding='utf-8'))
    delivery=json.loads(original_delivery.read_text(encoding='utf-8'))
    assert len(delivery['files'])==31
    assert old['human_review'] is False and old['inference_run'] is False
    generator=ROOT/'scripts/build_blinded_review_pack_20261002.py'
    source=generator.read_text(encoding='utf-8')
    tree=ast.parse(source,filename=str(generator))
    assert source.index('(dest / "README_RU.md").write_text(')<source.index('pack_files = (')<source.index('(dest / "manifest.json").write_text(')
    pack_assignments=[node for node in ast.walk(tree) if isinstance(node,ast.Assign)
      and any(isinstance(target,ast.Name) and target.id=='pack_files' for target in node.targets)]
    assert len(pack_assignments)==1 and set(ast.literal_eval(pack_assignments[0].value))==set(NAMES)
    # Historical CC0 is confirmed only for this exact existing benchmark subset.
    benchmark=ROOT/'data/benchmark.jsonl'
    controlled=[json.loads(line) for line in benchmark.read_text(encoding='utf-8').splitlines()
                if line and json.loads(line)['id'].startswith('controlled_')]
    assert len(controlled)==240 and all(row.get('license')=='CC0-1.0 (new controlled scenarios)' for row in controlled)
    actual_files={name:digest(PACK/name) for name in sorted(NAMES)}
    corrected=copy.deepcopy(old)
    corrected['files']=actual_files
    corrected['integrity_version']='v2_integrity_20261002'
    corrected['integrity_updated_utc']=now()
    corrected['file_inventory_scope']='Finalized question/gold files plus README only; this manifest and all manifest self-hashes excluded'
    corrected['correction_provenance']={
      'original_manifest_path':original_manifest.relative_to(ROOT).as_posix(),
      'original_manifest_record':digest(original_manifest),
      'original_manifest_preserved':True,
      'stale_self_entry_removed':old.get('files',{}).get('manifest.json'),
      'stale_readme_entry_replaced':old.get('files',{}).get('README_RU.md'),
      'current_final_readme_entry':actual_files['README_RU.md'],
      'reason':'Original inventory included the previous manifest and hashed README before its final write.',
      'original_questions_gold_readme_bytes_preserved':True,
      'questions_or_answers_regenerated':False,'generator_rerun':False,
      'human_review_performed':False,'inference_performed':False,
      'source_generator_path':generator.relative_to(ROOT).as_posix(),
      'source_generator_current':digest(generator),
      'source_generator_repair':'README finalized before canonical five-file hashing; self-entry omitted',
    }
    save_exclusive(v2_path,corrected)
    original_paths=[ROOT/item['path'].replace('\\','/') for item in delivery['files']]
    extras=[v2_path,original_delivery,ROOT/'docs/GITHUB_APARTMAN_BACKUP_RU.md',Path(__file__).resolve()]
    all_paths=list(dict.fromkeys(original_paths+extras))
    records=[{'path':path.relative_to(ROOT).as_posix(),**digest(path)} for path in all_paths]
    current=copy.deepcopy(delivery)
    current.update(phase='VERSIONED_INTEGRITY_CORRECTION_NO_NEW_EXPERIMENT',updated_utc=now(),files=records,
      integrity_version='v2_integrity_20261002',
      git_commits_or_push='NOT_PERFORMED_DURING_THIS_INTEGRITY_REPAIR; original record refers to paper agent',
      original_scientific_status_metadata_inherited_without_revalidation=True,
      integrity_correction={
        'original_delivery_manifest_path':original_delivery.relative_to(ROOT).as_posix(),
        'original_delivery_manifest_record':digest(original_delivery),'original_delivery_preserved':True,
        'original_owned_file_count':31,'current_inventory_file_count':len(records),
        'corrected_pack_manifest_path':v2_path.relative_to(ROOT).as_posix(),
        'new_delivery_self_hash_included':False,'generator_executed':False,
        'questions_gold_or_original_manifests_modified':False,'human_review_performed':False,
        'inference_network_download_render_scan_tests_or_git_mutations_performed':False,
        'protected_before':protected_before,
        'license_scope':'Only 240 controlled_* rows of data/benchmark.jsonl agro-route-v0.2 declare CC0; no new review40/manuscript license assigned',
      })
    save_exclusive(delivery_v2_path,current)
    protected_after={str(path.relative_to(ROOT).as_posix()):digest(path) for path in protected_paths}
    assert protected_before==protected_after
    assert set(corrected['files'])==set(NAMES) and v2_path.name not in corrected['files']
    assert all(digest(PACK/name)==entry for name,entry in corrected['files'].items())
    assert all(digest(ROOT/item['path'])=={'bytes':item['bytes'],'sha256':item['sha256']} for item in records)
    validation={'checked_utc':now(),'status':'PASS_LIGHT_INTEGRITY_VALIDATION',
      'protected_files_unchanged':len(protected_paths),'pack_file_hashes_verified':len(NAMES),
      'delivery_inventory_files_verified':len(records),'generator_ast_syntax':'PASS',
      'generator_write_order_and_canonical_inventory':'PASS_STATIC_CHECK_NOT_EXECUTED',
      'historical_controlled_cc0_records_verified':240,
      'source_generator_executed':False,'human_review':False,'model_inference':False,
      'original_protected_records':protected_after,'new_pack_manifest':digest(v2_path),
      'new_delivery_manifest':digest(delivery_v2_path),
      'heavy_tests_render_security_scans_network_downloads_or_git_mutations':'NOT RUN'}
    save_exclusive(RUN/'integrity_repair_validation_20261002.json',validation)
    print(json.dumps({key:validation[key] for key in ('status','protected_files_unchanged','pack_file_hashes_verified','delivery_inventory_files_verified','generator_ast_syntax','human_review')}))

if __name__=='__main__':main()
