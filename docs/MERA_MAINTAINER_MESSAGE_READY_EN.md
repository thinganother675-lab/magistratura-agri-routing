# Ready message to MERA maintainers

Status: **DRAFT_READY_FOR_AUTHOR_REVIEW / NOT_SENT**. Date: 3 October 2026.
Suggested address listed on the MERA website: `mera@a-ai.ru`.

**Subject: ruTXTAgroBench: production EM/F1 and research usage clarification**

Dear MERA team,

We are Antoniy Sarychev and Denis Shesternin, first-year master's students at the Russian State Agrarian University – Moscow Timiryazev Agricultural Academy. We study local/cloud LLM routing for agricultural tasks and currently use the public ruTXTAgroBench DEV split for development. We have not run or submitted TEST, redistributed questions or reference answers, or trained models on the benchmark.

At `MERA_Industrial` commit `7752f19d1658ba80f5f34144895c26dd1bf5239d`, `agro_bench/utils.py::process_results` calls SQuAD EM/F1. Independently executing the original Transformers v4.57.1 functions on **synthetic option labels** gives EM=F1=1 for reference `A` versus an empty prediction, and for reference `A, C` versus prediction `C`. The normalizer removes `a` as an English article. The spelling `A,C` without a space behaves differently. Pending clarification, we report separate strict option-set metrics and do not describe them as official MERA scores.

Could you please clarify:

1. Does the private evaluation service use this same normalization code? Is Latin option A preserved in production scoring? Can you identify the deployed version/commit or an intended fix?
2. How are official EM/F1 defined for multiple correct options, and what is the canonical output format? How does the service handle Cyrillic А/В/Е appearing in a few DEV references?
3. Can a private evaluation return per-item correctness without revealing reference answers? This is needed for paired comparisons of local, cloud, and cascade policies.
4. Which license and usage terms apply to the ruTXTAgroBench question content separately from the code repository's MIT license? Is DEV-based development of fixed routing rules without training model weights permitted?
5. May a small number of attributed question examples appear in an academic paper? If separate permission is required, how should we request it?
6. May we redistribute our raw model predictions without questions or references—for example, selected option letters and item IDs—alongside aggregate metrics and run settings? Are there restrictions on such logs?

All option-label examples above are synthetic and do not reproduce benchmark questions. Thank you for helping us use the benchmark correctly and reproducibly.

Best regards,
Antoniy Sarychev, Denis Shesternin
Russian State Agrarian University – Moscow Timiryazev Agricultural Academy, Moscow

References: [MERA metric code](https://github.com/MERA-Evaluation/MERA_Industrial/blob/7752f19d1658ba80f5f34144895c26dd1bf5239d/industrial_tasks/agro_bench/utils.py), [SQuAD normalization](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/data/metrics/squad_metrics.py).
