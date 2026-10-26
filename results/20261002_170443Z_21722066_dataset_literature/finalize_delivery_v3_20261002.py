"""Freeze light delivery inventory after the root's offline integration smoke."""
from pathlib import Path
from datetime import datetime,timezone
import copy
import hashlib
import json

RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[1]
EXPECTED_BUILDER='cc368575f2fa632c3184f79b422f57e5e8ff956c81f4be133b22cb9aae17702d'
def now():return datetime.now(timezone.utc).isoformat()
def record(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def save(path,body):
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(body,handle,ensure_ascii=False,indent=2);handle.write('\n')

def main():
    builder=ROOT/'scripts/build_blinded_review_pack_20261002.py'
    test=ROOT/'tests/test_review_pack_preservation.py'
    integration=RUN/'review_pack_generator_integration_20261002.json'
    snapshot=RUN/'builder_snapshot_20261002.py'
    delivery_v2=RUN/'delivery_manifest_v2.json'
    delivery_v3=RUN/'delivery_manifest_v3.json'
    previous=json.loads(delivery_v2.read_text(encoding='utf-8'))
    smoke=json.loads(integration.read_text(encoding='utf-8'))
    protected=json.loads((RUN/'integrity_repair_validation_20261002.json').read_text(encoding='utf-8'))['original_protected_records']
    assert record(builder)['sha256']==EXPECTED_BUILDER==smoke['source_sha256']
    assert smoke['status']=='PASS' and smoke['provider_requests']==0 and smoke['human_review'] is False
    assert smoke['new_pack_rows']==40 and smoke['finalized_inventory_hashes_verified']==5
    assert smoke['manifest_self_hash_present'] is False
    assert smoke['existing_destination_refused_before_source_read'] is True
    assert all(record(ROOT/path)==expected for path,expected in protected.items())
    v2_bytes=delivery_v2.read_bytes()
    v1_path=RUN/'delivery_manifest.json';v1_bytes=v1_path.read_bytes()
    pack_v2=RUN/'human_review_pack/manifest_v2_integrity_20261002.json';pack_v2_bytes=pack_v2.read_bytes()
    if snapshot.exists() or delivery_v3.exists():raise ValueError('FinalVersionExistsNoOverwrite')
    with snapshot.open('xb') as handle:handle.write(builder.read_bytes())
    assert record(snapshot)==record(builder)
    time_suffix=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
    provenance_path=RUN/('builder_source_provenance_'+time_suffix+'.json')
    current_source=record(builder)
    previous_source=next(item for item in previous['files'] if item['path']=='scripts/build_blinded_review_pack_20261002.py')
    provenance={
      'captured_utc':now(),'status':'CURRENT_SOURCE_EQUALS_VERIFIED_ROOT_SMOKE_AND_ARCHIVAL_SNAPSHOT',
      'source_path':builder.relative_to(ROOT).as_posix(),'source_record':current_source,
      'snapshot_path':snapshot.relative_to(ROOT).as_posix(),'snapshot_record':record(snapshot),
      'snapshot_execution_intended':False,
      'integration_evidence_path':integration.relative_to(ROOT).as_posix(),'integration_evidence_record':record(integration),
      'preservation_test_path':test.relative_to(ROOT).as_posix(),'preservation_test_record':record(test),
      'previous_v2_source_record':previous_source,
      'previous_version_scope':'V2 is the timestamped inventory before root added no-overwrite guard; its old source hash is not a claim about current source.',
      'generator_guard':'Existing destination refused before source read; atomic mkdir exist_ok=False; --output accepts only fresh directory.',
      'same_human_review_and_scientific_results':True,'model_inference_requests':0,
      'full_test_suite':'NOT RUN BY THIS FINALIZER; root owns final suite',
    }
    save(provenance_path,provenance)
    paths=[ROOT/item['path'] for item in previous['files']]
    paths.extend([test,snapshot,integration,provenance_path,delivery_v2,
                  RUN/'integrity_repair_validation_20261002.json',Path(__file__).resolve()])
    paths=list(dict.fromkeys(paths))
    files=[{'path':path.relative_to(ROOT).as_posix(),**record(path)} for path in paths]
    status=copy.deepcopy(previous)
    status.update(phase='FINAL_DELIVERY_V3_AFTER_OFFLINE_PRESERVATION_INTEGRATION',
      updated_utc=now(),integrity_version='v3_integrity_20261002',files=files,
      current_inventory_file_count=len(files),
      snapshot_scope='Exact files at captured UTC; prior inventories remain archival. Future edits need a new versioned inventory.',
      integration_validation={
        'evidence_path':integration.relative_to(ROOT).as_posix(),'evidence_record':record(integration),
        'source_provenance_path':provenance_path.relative_to(ROOT).as_posix(),
        'source_provenance_record':record(provenance_path),
        'current_builder_sha256':EXPECTED_BUILDER,'source_snapshot_path':snapshot.relative_to(ROOT).as_posix(),
        'original_protected_files':protected,'original_protected_files_unchanged':True,
        'previous_delivery_v1_record':record(v1_path),'previous_delivery_v2_record':record(delivery_v2),
        'corrected_pack_v2_record':record(pack_v2),'previous_manifests_preserved':True,
        'meaningful_preservation_test_included':True,'source_generator_run_by_this_agent':False,
        'root_offline_smoke_pass':True,'human_review':False,'provider_requests_by_this_agent':0,
        'full_suite_security_scans_downloads_render_or_git_mutations_by_this_agent':'NOT RUN',
      })
    # V3 is a snapshot of the current source after guard changes, not a replacement
    # for the v2 creation-time source or its static validation statement.
    status['integrity_correction']['current_inventory_file_count']=len(files)
    save(delivery_v3,status)
    assert v1_path.read_bytes()==v1_bytes and delivery_v2.read_bytes()==v2_bytes and pack_v2.read_bytes()==pack_v2_bytes
    assert all(record(ROOT/path)==expected for path,expected in protected.items())
    assert all(record(ROOT/item['path'])=={'bytes':item['bytes'],'sha256':item['sha256']} for item in files)
    assert record(builder)==record(snapshot)
    validation={'checked_utc':now(),'status':'PASS_LIGHT_FINAL_DELIVERY_V3',
      'inventory_files_verified':len(files),'protected_original_files_unchanged':len(protected),
      'old_delivery_v1_v2_and_pack_v2_preserved':True,
      'builder_source_equals_snapshot_equals_root_smoke':True,
      'builder_sha256':EXPECTED_BUILDER,'human_review':False,
      'provider_requests':0,'full_suite_scans_render_downloads_or_git_mutations':'NOT RUN',
      'delivery_v3_path':delivery_v3.relative_to(ROOT).as_posix(),'delivery_v3_record':record(delivery_v3),
      'source_provenance_path':provenance_path.relative_to(ROOT).as_posix()}
    save(RUN/'delivery_integrity_validation_v3_20261002.json',validation)
    print(json.dumps({key:validation[key] for key in ('status','inventory_files_verified','protected_original_files_unchanged','builder_sha256','human_review','provider_requests')}))

if __name__=='__main__':main()
