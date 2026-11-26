# Qwen2.5-Omni-3B

<p align="center">
  <a href="https://huggingface.co/APLUX-Pandora/Qwen2.5-Omni-3B"><img src="https://img.shields.io/badge/Hugging%20Face-QWEN2.5--OMNI--3B-E3B800?style=for-the-badge&amp;logo=huggingface&amp;logoColor=FFD21E&amp;labelColor=555555" alt="Hugging Face: Qwen2.5-Omni-3B"></a>
  <a href="https://github.com/APLUX-Pandora/qwen2.5-omni-3b-demo"><img src="https://img.shields.io/badge/GitHub-QWEN2.5--OMNI--3B-000000?style=for-the-badge&amp;logo=github&amp;logoColor=white&amp;labelColor=555555" alt="GitHub: Qwen2.5-Omni-3B"></a>
</p>

Chat with Qwen2.5-Omni-3B on a compatible device using text, images, or audio and read its streamed text replies.

Based on [Qwen2.5-Omni-3B](https://huggingface.co/Qwen/Qwen2.5-Omni-3B).

**Demo recording**

https://github.com/user-attachments/assets/2eee1b22-95d4-4225-8053-d9cce4e6c598

English walkthrough on QCS8550 (46 seconds). The demo answers a text prompt, describes an image, then previews and transcribes a spoken English clip.

## 1. Install

Clone the Demo and enter its root directory:

```bash
git clone https://github.com/APLUX-Pandora/qwen2.5-omni-3b-demo.git
cd qwen2.5-omni-3b-demo
```

### Prepare the device

Use a compatible Linux device with Aidlux LMS and the required drivers, DSP firmware and BSP/FastRPC support. The SDK includes its QNN runtime libraries; no separate QNN installation or path configuration is required.

Check the activation:

```bash
sudo lms check
```

Continue only when it returns true.

Install the system packages the Demo needs:

```bash
sudo apt install python3-venv
```

### Install the Demo and SDK

Use Python 3.10–3.12. Create and activate the Demo environment, then install:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

This installs the SDK, the Web Demo and the Hugging Face CLI. To use only the SDK in your own application, see the [SDK installation](sdk/README.md#install).

## 2. Get the model

Download the shared files and one device target. The commands below use QCS8550; for another device, use the folder in the [targets table](docs/MODEL_SETUP.md#targets).

For a private model, run `hf auth login` first.

```bash
hf download APLUX-Pandora/Qwen2.5-Omni-3B --local-dir models --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/Qwen2.5-Omni-3B --local-dir models --include "targets/qcs8550_qnn248/*"
```

## 3. Run the Web Demo

```bash
sh demo/start.sh --port 7860
```

Open `http://<device-ip>:7860/` and send text or attach images or a WAV recording. Stop it with `Ctrl+C`. To record from a microphone, use [HTTPS and the microphone check](demo/README.md#record-with-a-microphone).

## 4. Python Usage

In the same environment, from the Demo root:

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

Run the text example from the repository root:

```bash
python examples/python/text_chat.py
```

More in the [Python API](sdk/PYTHON_API.md) and [examples](examples/README.md).

## Documentation

- [Model setup](docs/MODEL_SETUP.md): device requirements, targets, download and folder layout
- [Python API](sdk/PYTHON_API.md): every public class, method and parameter
- [C ABI](docs/C_ABI.md): native integration
- [Examples](examples/README.md): runnable Python and C examples

- [Runtime](sdk/RUNTIME_API.md): CPU affinity and performance options

## License

See [LICENSING.md](LICENSING.md), [NOTICE](NOTICE) and [LICENSES](LICENSES/).
