# Оборудование и следующий модельный этап

Дата: 30.09.2026. Два разных устройства; их результаты нельзя смешивать.

## Текущий ноутбук — инструментально наблюдалось

7,73 GiB RAM; 8 logical CPU; PROCESSOR_IDENTIFIER Intel64 Family 6 Model 186 Stepping 3, GenuineIntel; Windows build 26200. Модель CPU и GPU/VRAM полностью не установлены: WMI чтение отклонено. Свободный диск при первом чтении ≈219,7 GB. Python 3.12.14; CPU llama.cpp b11292; one slot, four threads, context4096; text-only GGUF Q4_K_M. LM Studio CLI найден, доступных весов на этом ноутбуке не обнаружено.

## ПК — данные пользователя, не удалённая проверка

RTX 5060 Ti **16 GB VRAM**, **32 GB RAM**, Ryzen 7 8700 (точное обозначение записано со слов пользователя). Модели в LM Studio:

| Название / publisher из inventory | Quant | File GB, со слов пользователя |
|---|---|---:|
| abenzerps/qwen-image-2.1-uncensored | Q6_K | 5.9 |
| ggml-org/qwen3-omni-30b-a3b-instruct | Q4_K_M | 20.8 |
| unsloth/qwen3.8-27b | Q4_K_M | 17.4 |
| openbmb/minicpm5-1b | Q8_0 | 1.2 |
| unsloth/gemma-4-12b-it | Q4_K_S | 7.0 |
| mradermacher/webworld-8b-i1 | Q6_K | 6.7 |
| mudler/vibevoice.cpp-models | Q8_0 | 1.7 |
| unsloth/granite-4.1-8b | Q4_K_M | 5.3 |
| unsloth/gpt-oss-20b | Q8_0 | 12.1 |
| inclusionAI/dr-venus-4b-rl | Q4_K_M | 2.7 |
| unsloth/gemma-4-26b-a4b-it | IQ4_NL_XL | 16.8 |
| chris0173/voxtral-4b-tts-2603 | Q8_0 | 4.7 |
| unsloth/qwen3-coder-next | Q3_K_S | 33.3 |
| HauhauCS/qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive | Q4_K_M | 22.1 |
| unsloth/qwen3.5-35b-a3b | Q4_K_L | 22.0 |
| unsloth/qwen3.5-9b | Q8_0 | 11.4 |
| Qwen/qwen3-vl-8b-instruct | Q8_0 | 9.9 |
| TeichAI/qwen3-8b-deepseek-v3.2-speciale-distill | Q4_K_M | 5.0 |

Названия из inventory не автоматически равны official upstream release ID; модельные metadata, filename/hash, architecture, base/finetune и license нужно проверить при будущем подключении. Наличие qwen3.8-27b в пользовательском inventory сохраняется как факт сообщения, а не отвергается на основании более старой известной версии Qwen.

## План на потом — без текущего подключения/загрузки

Первая тройка для общего text-answer сравнения: Qwen3.5-9B Q8_0, Gemma-4-12B Q4_K_S и GPT-OSS-20B Q8_0. Их указанные файлы меньше VRAM, но веса + KV/runtime могут превысить бюджет; реальные GPU layers/context фиксировать отдельно. Сначала warm-up и smoke, затем новый dev/calibration протокол и новый untouched test. GPT-OSS отличается reasoning/template behavior; response_format и общий generation budget необходимо проверить.

Qwen3.8-27B и Gemma26B-A4B — отдельная offload-конфигурация: файлы уже больше 16 GB, поэтому нельзя обещать полную загрузку в VRAM или сравнивать их скорость с full-GPU без оговорок. MoE active parameters не уменьшают необходимость хранить все эксперты. Модель 33,3 GB потребует памяти больше одного указанного файла и не является первым выбором для 32 GB RAM.

Image generation, TTS/audio и coding-specialist модели не включать в основной text-agronomy baseline без отдельной гипотезы. Для будущего multimodal исследования можно использовать Qwen3-VL; fine-tunes/uncensored варианты сравнивать отдельной абляцией с проверкой происхождения.

Выводы ноутбучного пилота относятся только к конкретным 0.8B/2B CPU конфигурациям. Они ничего не доказывают о качестве или скорости перечисленных ПК-моделей. Пользователь явно отложил этот этап; текущая сессия не предпринимает действий на ПК.
