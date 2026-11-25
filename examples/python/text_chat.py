"""Run from the delivery root with python examples/python/text_chat.py."""
from pandora_qwen25_omni import LanguageModel

MODEL_DIR = "models"
QUESTION = "请用一句话介绍你自己。"

with LanguageModel.from_pretrained(MODEL_DIR) as model:
    result = model.generate([{"role": "user", "content": QUESTION}], max_new_tokens=256, do_sample=False)
    print(result.text)
    print("finish_reason:", result.finish_reason)
