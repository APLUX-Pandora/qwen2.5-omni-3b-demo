# Examples

## Overview

| Example | What it shows |
| --- | --- |
| [python/text_chat.py](python/text_chat.py) | Ask a text question. |
| [python/image_chat.py](python/image_chat.py) | Ask a question about a red square, then compare it with a blue circle. |
| [python/audio_chat.py](python/audio_chat.py) | Ask about the weather and suggested activity in the WAV recording. |
| [python/image_audio_chat.py](python/image_audio_chat.py) | Send two images, a WAV recording, and text in an ordered user message. |
| [python/kv_cache_chat.py](python/kv_cache_chat.py) | Reuse one `DynamicCache` across three turns. Pass one new question each time. |
| [c/infer_tensors.c](c/infer_tensors.c) | Prepare input tensors, generate text, and read the result through the C ABI. |

The media examples use the geometric images and English speech in [demo/samples](../demo/samples/).

## Before you run

Complete [Install](../README.md#1-install) and [Get the model](../README.md#2-get-the-model). Run every command from the Demo root in the activated environment. Stop the Web Demo first; examples and the Web Demo share the NPU.

## Python examples

### text_chat.py

Ask a text question.

```bash
python examples/python/text_chat.py
```

Example output:

```text
我是来自阿里云的超大规模语言模型，我叫通义千问。
finish_reason: stop
```

### image_chat.py

Ask a question about a red square, then compare it with a blue circle.

```bash
python examples/python/image_chat.py
```

Example output:

```text
Single image: 这个图形是红色的，形状是一个正方形。如果还有其他问题，欢迎随时问我。
finish_reason: stop
Two images: 第一张图片里是红色的正方形，第二张图片里是蓝色的圆形。如果还有啥疑问，尽管跟我说哈。
finish_reason: stop
```

### audio_chat.py

Ask about the weather and suggested activity in the WAV recording.

```bash
python examples/python/audio_chat.py
```

The script prints its answer and the final generation status.

### image_audio_chat.py

Send two images, a WAV recording, and text in an ordered user message.

```bash
python examples/python/image_audio_chat.py
```

The script prints its answer and the final generation status.

### kv_cache_chat.py

Reuse one `DynamicCache` across three turns. Pass one new question each time.

```bash
python examples/python/kv_cache_chat.py
```

Example output:

```text
User: 我叫什么？
Assistant: 你叫小秦。
finish_reason: stop
```

## C example

### infer_tensors.c

Prepare the inputs for a short greeting and read the generated text and token IDs.

Build against the headers and prebuilt library in `sdk/`:

```bash
runtime_dir=$(python -c 'from pathlib import Path; import pandora_runtime; print(Path(pandora_runtime.__file__).parent)') && \
cc -std=c99 -Wall -Wextra -Werror -I sdk/include examples/c/infer_tensors.c \
  -L sdk/lib -lqwen25_omni -L"$runtime_dir" \
  -Wl,--no-as-needed -l:libpandora_runtime.so.5 -Wl,--as-needed \
  -Wl,-rpath-link,"$runtime_dir" -Wl,-rpath,"$runtime_dir" \
  -Wl,-rpath,'$ORIGIN/../../sdk/lib' -o examples/c/infer_tensors
examples/c/infer_tensors models
```

The program prints a `C_RESULT_JSON=` line with the answer, token IDs, and finish reason.

See [C ABI](../docs/C_ABI.md) for ownership and error handling.
