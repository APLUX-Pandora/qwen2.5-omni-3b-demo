"""Combine two images, audio and text in one ordered user message."""
from pathlib import Path
from pandora_qwen25_omni import LanguageModel

MODEL_DIR = "models"
SAMPLES = Path(__file__).resolve().parents[2] / "demo" / "samples"
SYSTEM = 'You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of perceiving auditory and visual inputs, as well as generating text and speech.'

FIRST_IMAGE = SAMPLES / "first-red-square.png"
SECOND_IMAGE = SAMPLES / "second-blue-circle.png"
AUDIO = SAMPLES / "speech.wav"
QUESTION = "请依次描述两张图的颜色和形状，再转写音频中的英文。"

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": [
        {"type": "image", "image": FIRST_IMAGE},
        {"type": "audio", "audio": AUDIO},
        {"type": "image", "image": SECOND_IMAGE},
        {"type": "text", "text": QUESTION},
    ]},
]
with LanguageModel.from_pretrained(MODEL_DIR) as model:
    result = model.generate(
        messages,
        max_new_tokens=1024,
        do_sample=False,
        repetition_penalty=1.0,
    )
    print(result.text)
