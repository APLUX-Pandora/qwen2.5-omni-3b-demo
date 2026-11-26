"""Ask about the bundled audio and print the text answer."""
from pathlib import Path
from pandora_qwen25_omni import LanguageModel

MODEL_DIR = "models"
SAMPLES = Path(__file__).resolve().parents[2] / "demo" / "samples"
SYSTEM = 'You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of perceiving auditory and visual inputs, as well as generating text and speech.'

AUDIO = SAMPLES / "speech.wav"
QUESTION = "What is the weather in the recording, and what activity does the speaker suggest?"

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": [
        {"type": "audio", "audio": AUDIO},
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
