# Ready message to MERA maintainers

Status: **SENT_BY_AUTHOR_REPORTED / WAITING_FOR_MAINTAINER**. Date: 3 October 2026.
Antoniy reported sending the prepared question in the continuation request. Delivery
and any reply have not been independently inspected. The letter is retained as
correspondence evidence; joint research authorship remains Antoniy Sarychev and
Denis Shesternin. No duplicate message should be sent.
Suggested address listed on the MERA website: `mera@a-ai.ru`.

**Subject: ruTXTAgroBench: option A normalization in EM/F1 scoring**

Hello MERA team,

I'm Antoniy Sarychev. I'm running local LLM benchmarks and started using the public ruTXTAgroBench DEV split.

I found a scoring issue in `agro_bench/utils.py::process_results` at commit `7752f19d1658ba80f5f34144895c26dd1bf5239d`. It calls SQuAD EM/F1, whose normalizer removes `a` as an English article. Running the original Transformers v4.57.1 functions gives these results:

- Reference `A`, empty prediction: EM = F1 = 1.
- Reference `A, C`, prediction `C`: EM = F1 = 1.
- Reference `A,C`, prediction `C`: EM = F1 = 0.

These are synthetic option-label examples. They suggest that option A can disappear and whitespace can change the score. For my local measurements, I use exact option-set matching and set F1. I have not submitted predictions to the private evaluation server.

I have three questions:

1. Does the private evaluation server use this normalization, or does its scorer preserve option A?
2. What are the official EM/F1 definitions and required answer format for questions with multiple correct options, including references that use Cyrillic option letters?
3. What license and usage terms apply to the benchmark content and the publication of model predictions and small question examples in research papers?

Thanks for your help.

Best regards,
Antoniy Sarychev

References: [MERA metric code](https://github.com/MERA-Evaluation/MERA_Industrial/blob/7752f19d1658ba80f5f34144895c26dd1bf5239d/industrial_tasks/agro_bench/utils.py), [SQuAD normalization](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/data/metrics/squad_metrics.py).
