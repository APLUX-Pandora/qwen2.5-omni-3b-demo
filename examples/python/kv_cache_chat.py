"""Reuse one explicit native KV cache for three dependent turns."""
from pandora_qwen25_omni import DynamicCache, LanguageModel

MODEL_DIR = "models"
QUESTIONS = ("我叫小秦。", "我叫什么？", "用英文回答上一题。")

with LanguageModel.from_pretrained(MODEL_DIR) as model, DynamicCache() as cache:
    for question in QUESTIONS:
        result = model.generate(
            [{"role": "user", "content": question}],
            past_key_values=cache,
            max_new_tokens=256,
            do_sample=False,
        )
        print("User:", question)
        print("Assistant:", result.text)
        print("finish_reason:", result.finish_reason)
        if result.finish_reason != "stop":
            break
