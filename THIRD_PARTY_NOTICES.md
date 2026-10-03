# Third-party material and license boundaries

Copyright 2026 Antoniy Sarychev and Denis Shesternin for original software only.
The root Apache-2.0 license does not relicense any item below. The public
candidate ships source code and small synthetic examples; dependencies are
downloaded independently. It does not bundle upstream code, models or texts.

| Material | Verified declaration / boundary | Public candidate |
|---|---|---|
| AgXQA Part B annotations, MSU-CECO/agxqa_benchmark_v1, commit `8626771b289d48cff113f0c13d0603ac644628c0` | Upstream repository declares Apache-2.0, preserved in `data/raw/agxqa/LICENSE`. Embedded Extension paragraphs retain underlying rights; repository declaration alone is insufficient to clear all source texts. | Excluded, including transformed records and raw/model outputs containing paragraphs. |
| FAO-56, Allen, Pereira, Raes, Smith (1998); FAO irrigation texts (1985) | [FAO-56 copyright page](https://www.fao.org/4/x0490e/x0490e00.htm) states all rights reserved. Original equation implementations and numerical facts are attributed; full text and source-derived paragraphs are excluded. | No full text, paragraphs or tables; numerical tool implementations and small fact-based test values only. |
| University of Minnesota Extension and other Extension source pages | Rights vary by page. [`umn_cover`](https://blog-crop-news.extension.umn.edu/2022/09/maximize-your-cover-crop-benefits-by.html) currently declares CC BY-SA 4.0; the 2019 nitrogen-credit page returned HTTP 429 and lacks a verified blanket redistribution permission in this audit. A translated/paraphrased paragraph does not become Apache-2.0 code. | All Extension prose excluded, including prose in generators. |
| NASA POWER weather snapshot | Upstream NASA/source attribution and provenance retained. Service/data terms must be checked for the specific requested variables; no software relicensing. [POWER data sources](https://power.larc.nasa.gov/docs/methodology/data/sources/). | Snapshot excluded. |
| ERA5 via Open-Meteo | [Open-Meteo data license](https://open-meteo.com/en/licence) is CC BY 4.0; [API terms](https://open-meteo.com/en/terms) separately restrict free API service use. [ERA5 entry](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview) lists CC-BY. Exact source/version/attribution remain necessary. | Weather snapshot and existing review40 excluded. |
| Scientific papers and extracted reading sections | Each paper has its own publication/preprint terms. An arXiv PDF's availability is not permission to redistribute it under Apache-2.0. | PDFs, extracted pages/paragraphs and screenshots excluded. Bibliographic references remain references. |
| Local model weights and tokenizer files (Qwen, Phi, BitNet, Gemma, Laya and others) | Each revision/model card has independent terms. Recorded licenses for base models do not prove the terms of every quantization artifact. No new model license is assigned. | All weights, tokenizers and model snapshots excluded. |
| BitNet source/runtime | `.runtime/bitnet/BitNet/LICENSE` declares MIT; bundled llama.cpp and LLVM-MinGW contain additional license notices. | Entire runtime/toolchain excluded. |
| Laya source/runtime | `.runtime/jev/laya-src/LICENSE` declares Apache-2.0; nested SDK/benchmark files carry independent notices. | Entire checkout/runtime excluded. |
| Prior Jev project | Reference checkout is a separate project; current audit confirms it is not copied into the release candidate. No ownership/license inferred from a shared human author. | Excluded. |
| Provider response text and private account/log metadata | Provider terms and input/source rights apply. Public-candidate statistical measurements omit provider output and prompt/context/gold text. | Raw logs/responses/account records excluded. |

Direct installation dependencies are `httpx`, `numpy`, `scipy`, `matplotlib`,
with `pytest` for development. Their upstream license files remain authoritative;
the environment and transitive dependencies are not vendored. Local dist-info
license inventory is recorded by the private provenance audit. When redistributing
a compiled/bundled distribution later, collect the actual bundled dependency
licenses and notices rather than copying this source-only boundary statement.

New release smoke scenarios and measurements-only projections have a separate
CC0-1.0 data dedication stated in `data/public_sample/DATA_LICENSES.md`. This
does not cover original source datasets, model text, or the scientific manuscript.
