# Agro Route Lab — research software candidate

Authors: **Antoniy Sarychev**, **Denis Shesternin**.
Russian State Agrarian University – Moscow Timiryazev Agricultural Academy.

This is a local publication candidate for `v0.1.0-research`, prepared 3 October
2026. No public GitHub release, DOI or article submission is asserted. The
software implements deterministic agricultural calculations, local/cloud
routing, development evaluation and statistics. It is not a production farm
advice service. Historical research found substantially fewer generative cloud
calls in the controlled setting; quality non-inferiority was not demonstrated.
Jev-first development routing did not establish superiority over rule-first.

Original software/tests/configuration and this software documentation:
**Apache-2.0**, see `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`.
Small synthetic scenarios and measurements-only data have a separate CC0-1.0
dedication in `data/public_sample/DATA_LICENSES.md`. Scientific manuscripts,
third-party datasets/source texts, model weights and provider outputs are outside
the software license and excluded from this candidate.

## Install and inspect without credentials

Python 3.12+; create a fresh environment, then install the checked lock and
editable project. PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts/public_smoke.py
.venv\Scripts\python.exe scripts/reproduce_public_aggregates.py --output reproduction_output/home150_aggregates.json
.venv\Scripts\python.exe scripts/build_public_release.py --verify .
```

POSIX: use `.venv/bin/python` in the same commands. The tests and smoke make no
paid calls. The smoke uses eight invented formal cases, no local model, no
hidden gold sent to a router, and no external inference. This checks software,
not independent agricultural generalization.

`RELEASE_MANIFEST.json` records every approved file and its SHA256/provenance.
It excludes private Git history. `--verify` permits disposable environment/test
cache and `reproduction_output/` created after extraction, while checking every
release payload file. Deterministic ZIP reproduction:

```powershell
.venv\Scripts\python.exe scripts/build_public_release.py --archive-tree . --archive-output ../agro-route-v0.1.0-research-rebuilt.zip
```

Do not overwrite an existing archive; select a new output path. Files, ordering,
ZIP member timestamps and permissions are fixed. Repeat with the same Python/
zlib versions to obtain byte-identical ZIP bytes. Installing dependencies does
not bundle their code into this source distribution; upstream notices apply.

## What the retained data reproduce

`home150_measurements.jsonl` preserves 750 numerical/boolean decisions on 150
cases for local, cloud, tools+cloud, hybrid and offline policies. Source/input/
context/gold/provider text is removed; IDs/groups are pseudonymous. Offline replay
reproduces 13 recorded aggregate fields per policy, including accuracy, group
bootstrap intervals, call counts, latency and known costs. Preserved source
digests establish the projection relationship to the private frozen archive.

The projected facts cannot independently validate gold, reconstruct model
outputs or run the historical corpus. Full source/output redistribution remains
blocked by mixed third-party rights and human gold review. Unknown timeout
charges remain unknown. Replaying these aggregates is not a new confirmatory
experiment and does not rescore the historical HOME150.

## Legitimate data and optional inference

Obtain AgXQA or any alternative benchmark directly from the upstream publisher
and inspect per-source rights before redistribution. The AgXQA repository has an
Apache declaration, while embedded Extension paragraphs may have separate rights.
FAO full texts are reference-only here. ERA5/Open-Meteo data retain attribution/
data license and API service terms. Record dataset commit/version, document
groups, overlap and rights in a new manifest; translations share their source
group. Use truly source-disjoint data and human reviewed gold before a new freeze.

For optional local inference, install LM Studio separately, obtain a model under
its exact upstream license, start a loopback OpenAI-compatible endpoint, and set
`LOCAL_BASE_URL` and the exact `LOCAL_MODEL` ID in the process environment.
Software does not download or include weights in this candidate. The historical
legacy benchmark defaults are documented code, not a current model recommendation.

For optional cloud inference, set an authorized provider URL/model, explicit
current prices/budget and a locally stored key. Keep `.env` out of Git; its
example is blank and cloud availability defaults false. A paired live benchmark
can incur charges and requires separate consent/budget; never execute it merely
to inspect retained results. The minimal public reproduction commands above
need no provider account or key. New OpenRouter supplementary work follows a
separate verified-free, fail-closed guard; it does not replace historical Mercury.

## Attribution

Use `CITATION.cff`, the exact software version/commit and both authors. DOI is
absent until a real authorized software archival record exists. A GitHub release
or software DOI does not constitute peer review of the manuscript. Publishing
this candidate, connecting Zenodo, or submitting the paper needs author approval.
