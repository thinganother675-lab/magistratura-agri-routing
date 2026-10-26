# SPDX-License-Identifier: Apache-2.0
"""Add explicit evidence-status aliases to the new final analysis table.

Preserves its first version and its independent QA hashes. Original inference
records/summaries are never modified; an append-only receipt binds both tables.
"""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results/20261003_resource_analysis"
PATH=OUT/"final_model_table.csv"


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    original=PATH.read_bytes()
    preserved=OUT/"final_model_table_before_status_aliases.csv"
    with preserved.open("xb") as handle:handle.write(original)
    reader=csv.DictReader(io.StringIO(original.decode("utf-8-sig")));rows=list(reader)
    identities=json.loads((OUT/"analysis.json").read_text("utf-8"))["models"]
    fields=list(reader.fieldnames)+["status","resource_status","resource_scope","exact_gguf_sha256"]
    for row in rows:
        measured=row["systems_status"]=="SYSTEMS_TELEMETRY"
        row.update(status="DEV_QUALITY_WITH_SYSTEMS_TELEMETRY" if measured else "DEV_QUALITY_WITH_HISTORICAL_RESOURCE_REFERENCE",
                   resource_status="SYSTEMS_TELEMETRY" if measured else "HISTORICAL",
                   resource_scope="whole GPU and whole system RAM; RSS is basename working-set sum, may include unrelated llama-server and double-count shared pages" if measured else "historical whole GPU and whole system RAM; no process allocation measurement",
                   exact_gguf_sha256=identities[row["model_key"]]["resources"]["exact_gguf_sha256"])
    stream=io.StringIO(newline="");writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    revised=stream.getvalue().encode("utf-8-sig");PATH.write_bytes(revised)
    receipt={"status":"APPEND_ONLY_TABLE_PRESENTATION_REVISION","original_table_path":preserved.relative_to(ROOT).as_posix(),"original_table_sha256":digest(original),
             "revised_table_path":PATH.relative_to(ROOT).as_posix(),"revised_table_sha256":digest(revised),
             "reason":"Explicit status/resource_status aliases and exact SHA; no scientific number changed",
             "added_columns":["status","resource_status","resource_scope","exact_gguf_sha256"],"original_numbers_unchanged":True,
             "prior_qa_receipt":"results/20261003_resource_session/independent_systems_v2_qa.json",
             "prior_qa_sha256":digest((ROOT/"results/20261003_resource_session/independent_systems_v2_qa.json").read_bytes()),
             "script_sha256":digest(Path(__file__).read_bytes())}
    with (OUT/"final_model_table_status_revision.json").open("x",encoding="utf-8") as handle:json.dump(receipt,handle,indent=2);handle.write("\n")
    print(json.dumps({"table":str(PATH),"added_columns":receipt["added_columns"],"scientific_numbers_changed":False}))


if __name__=="__main__":main()
