# Qwen2.5-Omni-3B SDK

Load the encrypted Qwen2.5-Omni-3B model and generate text from ordered text, image, and audio messages.

## What's included

| Path | Content |
| --- | --- |
| `pandora_qwen25_omni/` | Python package (`from pandora_qwen25_omni import LanguageModel`) |
| `include/` | C header |
| `lib/` | Prebuilt native library with its QNN runtime |
| `SHA256SUMS` | Checksums of the shipped files |

## Install

In your application's activated Python 3.10–3.12 environment, from the Demo root:

```bash
python -m pip install sdk/wheels/pandora_runtime-*.whl
python -m pip install ./sdk
```

The device must pass `sudo lms check`. The SDK does not install LMS or drivers and does not download models; see [Get the model](../README.md#2-get-the-model).

## Usage

```python
from pandora_qwen25_omni import LanguageModel

with LanguageModel.from_pretrained("models") as model:
    messages = [{"role": "user", "content": "请用一句话介绍你自己。"}]
    result = model.generate(
        messages,
        max_new_tokens=1024,
        do_sample=False,
        repetition_penalty=1.0,
    )
    print(result.text)
```

The Demo requests up to 1024 new tokens with greedy decoding. See the Python API reference for the SDK defaults.

## Documentation

- [Python API](PYTHON_API.md)
- [C ABI](../docs/C_ABI.md)
- [Examples](../examples/README.md)
- [Licensing](../LICENSING.md)
