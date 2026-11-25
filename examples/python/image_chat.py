"""Single-image and two-image questions using the installed SDK."""
from pathlib import Path
from pandora_qwen25_omni import LanguageModel

MODEL_DIR = "models"
SAMPLES = Path(__file__).resolve().parents[2] / "demo" / "samples"
SYSTEM = 'You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of perceiving auditory and visual inputs, as well as generating text and speech.'

FIRST_IMAGE = SAMPLES / "first-red-square.png"
SECOND_IMAGE = SAMPLES / "second-blue-circle.png"

with LanguageModel.from_pretrained(MODEL_DIR) as model:
    single_image = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "image", "image": FIRST_IMAGE},
            {"type": "text", "text": "请说出图片中图形的颜色和形状。"},
        ]},
    ]
    result = model.generate(single_image, max_new_tokens=256, do_sample=False)
    print("Single image:", result.text)
    print("finish_reason:", result.finish_reason)

    multiple_images = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "image", "image": FIRST_IMAGE},
            {"type": "image", "image": SECOND_IMAGE},
            {"type": "text", "text": "请依次说出两张图片中图形的颜色和形状。"},
        ]},
    ]
    result = model.generate(multiple_images, max_new_tokens=256, do_sample=False)
    print("Two images:", result.text)
    print("finish_reason:", result.finish_reason)
