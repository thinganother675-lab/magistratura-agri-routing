# 16 приоритетных научных источников для исследовательской статьи

02.10.2026. Подборка связывает источники с конкретными утверждениями статьи. Из прежнего реестра 69 кандидатов выбраны 15 работ, дополнительно включён Gemma 4 Technical Report. **Метаданные и доступные abstracts проверены; полное чтение всех 16 работ не заявляется.** Это рабочий список для чтения, а не готовая библиография рукописи. GitHub, model cards и API docs в эти 16 не входят.

| № | Научный источник | Для чего использовать / ограничение |
|---|---|---|
| 1 | [RouteLLM: Learning to Route LLMs with Preference Data, 2024](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html) | Preference routing; источник различия между learned router и нашим детерминированным валидатором. |
| 2 | [Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing, 2024](https://arxiv.org/abs/2404.14618) | Quality/cost tradeoff; отдельная инструментальная абляция в нашем исследовании. |
| 3 | [A Unified Approach to Routing and Cascading for LLMs, 2024](https://proceedings.mlr.press/v267/dekoninck25a.html) | Routing и cascade различаются; latency суммирует последовательные ступени. |
| 4 | [RouterBench: A Benchmark for Multi-LLM Routing System, 2024](https://arxiv.org/abs/2403.12031) | Сопоставимые routing baselines; не переносить leaderboard score на аграрную выборку. |
| 5 | [AutoMix: Automatically Mixing Language Models, 2023](https://arxiv.org/abs/2310.12963) | Self-verification/cascade; наш substring verifier не является calibrated confidence. |
| 6 | [Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs, 2024](https://arxiv.org/abs/2406.15927) | Ограничения cheap hallucination detection; hidden-state probes у нас не измерялись. |
| 7 | [Know Your Limits: A Survey of Abstention in Large Language Models, 2024](https://arxiv.org/abs/2407.18418) | Abstention и coverage должны оцениваться отдельно; у нашего gold нет ABSTAIN. |
| 8 | [PLLaMa: An Open-source Large Language Model for Plant Science, 2024](https://arxiv.org/abs/2401.01600) | Plant-science domain model; scientific domain baseline исследован, веса не добавлены. |
| 9 | [AgriGPT: a Large Language Model Ecosystem for Agriculture, 2025](https://arxiv.org/abs/2508.08632) | Аграрный corpus и domain evaluation; собственная supplied-context выборка существенно уже. |
| 10 | [AgroLLM: Connecting Farmers and Agricultural Practices through Large Language Models for Enhanced Knowledge Transfer and Practical Application, 2025](https://arxiv.org/abs/2503.04788) | Аграрный knowledge-transfer/RAG; retrieval и field outcomes у нас не проверялись. |
| 11 | [AgriAgent: Contract-Driven Planning and Capability-Aware Tool Orchestration in Real-World Agriculture, 2026](https://arxiv.org/abs/2601.08308) | Contract/capability agricultural tool orchestration; обоснование отдельного deterministic gate. |
| 12 | [AgroTools: A Benchmark for Tool-Augmented Multimodal Agents in Agriculture, 2026](https://arxiv.org/abs/2605.22366) | Agricultural executable-tool benchmark; process/outcome не смешивать. |
| 13 | [$\tau$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains, 2024](https://arxiv.org/abs/2406.12045) | Tool-agent reliability и state-based evaluation; один проход не измеряет repeat reliability. |
| 14 | [ToolACE: Winning the Points of LLM Function Calling, 2024](https://arxiv.org/abs/2409.00920) | Synthetic tool-data verification; наш synthetic holdout не доказывает natural distribution quality. |
| 15 | [The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits, 2024](https://arxiv.org/abs/2402.17764) | Native ternary обучение отличается от post-training IQ1; дальнейший CPU baseline. |
| 16 | [Gemma 4 Technical Report, 2026](https://arxiv.org/abs/2607.02770) | Выбранная Gemma4 architecture; paper scores не переносятся на наш IQ4 quantization. |

Обязательный следующий этап: для≥15 окончательных ссылок прочитать sections methods/results/limitations, проверить редакцию/venue и библиографический формат. Опубликованный статус не предполагается из самого наличия arXiv. Цифры чужих benchmarks не служат оценкой наших моделей. FAO56 для формул добавляется как обоснованный старый источник и не заменяет современный AI related work. Машинная подборка с provenance: `results/literature_20261002_article16/selection.json`.
