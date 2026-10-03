# Идентичность локальных весов: приложение к DEV screen

3 октября 2026. Статус — **DEV / reproducibility evidence**. Все десять основных GGUF из screen имеют проверенные полные локальные SHA256 и размер. Для восьми файлов найдено совпадение с текущими публичными HF LFS metadata; для двух Gemma — точное совпадение с историческими ревизиями. Модели не скачивались заново и не заменялись во время исследования.

Исходная проверка [текущих upstream файлов](../results/20261003_local_screen_571682f5/weight_upstream_identity.json) сохранена: она действительно дала8/10. Новый отдельный [исторический receipt](../results/20261003_local_screen_571682f5/weight_upstream_historical_verified.json) разрешает оставшиеся два случая. Независимый QA и root повторно проверили SHA256+размер через публичные metadata, без чтения содержимого весов из сети и без inference. Машинные утверждения и hashes находятся в [новой provenance](../manuscript/CLAIM_PROVENANCE_SCREEN_UPSTREAM_20261003.json).

| Проверенная конфигурация | Backend label | GGUF bytes | Историческая HF revision | Локальный SHA256 |
|---|---|---:|---|---|
| Gemma4 12B IT | Q4_K_S | 6764524960 | `faacc07cd184152e87f520a91e1112947b0751da` | `e6ba1b5d22ede511b45562d85a8e72251e7661a5046f13e2d99a48bf4e9d333f` |
| Gemma4 26B-A4B IT | IQ4_NL_XL | 14556687680 | `b68961b3c96e42475123a39fe3f8aa149163cf8b` | `c1ac61e3af04b40c7688dfe0686c54d68ff5ed26178a56f0b18c8a0e2b94db83` |

Закреплённые страницы именно этих файлов: [Gemma12 GGUF](https://huggingface.co/unsloth/gemma-4-12b-it-GGUF/blob/faacc07cd184152e87f520a91e1112947b0751da/gemma-4-12b-it-Q4_K_S.gguf), [Gemma26 GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/blob/b68961b3c96e42475123a39fe3f8aa149163cf8b/gemma-4-26B-A4B-it-UD-IQ4_NL_XL.gguf). Ссылка на `latest` или display name не определяет идентичность измеренной конфигурации.

Это подтверждение опубликованного file artifact. Оно не восстанавливает ревизию репозитория в момент установки, историю обучения, семантическую эквивалентность новых и старых bytes или точную причину их изменения. Эти сведения остаются **UNKNOWN**. В исследовании сохраняются реально измеренные веса и их hashes.

Названия quantization также не означают однородное хранение всех tensor elements. [Прочитанные GGUF descriptors](../results/20261003_local_screen_571682f5/installed_gguf_tensor_types.json) показывают смешанные типы: например, у GPTOSS20 native label `Q8_0`, но91.3723% stored elements имеют MXFP4,8.5838% — Q8_0,0.0439% — F32. У Gemma26 смешаны IQ3_S, IQ4_NL, Q8_0 и F32. Эти доли относятся к stored tensor elements, а не к active parameters. Разбор использовал закреплённые [GGUF specification](https://github.com/ggml-org/ggml/blob/353b63b439f27ab2cc19dac97ab1681ba6d2d084/docs/gguf.md) и [ggml type enum](https://github.com/ggml-org/ggml/blob/353b63b439f27ab2cc19dac97ab1681ba6d2d084/include/ggml.h); содержимое весов не изменялось.

Разрешение двух исторических идентичностей усиливает воспроизводимость текущего DEV screen. Оно не превращает DEV в независимую научную валидацию и не разрешает private TEST или распространение вопросов ruTXTAgroBench.
