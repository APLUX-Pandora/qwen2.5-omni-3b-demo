# Python API

`pandora_qwen25_omni` · Generate text from ordered text, images, and audio.

## Quick start

Follow the repository README for [installation](../README.md#1-install) and
[model download](../README.md#2-get-the-model). Run this example from the delivery
root in the same activated repository-local `.venv`, with the model files verified. It loads the local package, prints the answer
and closes the model when the context ends.

```python
from pandora_qwen25_omni import LanguageModel

with LanguageModel.from_pretrained("models") as model:
    messages = [{"role": "user", "content": "请用一句话介绍你自己。"}]
    result = model.generate(messages, max_new_tokens=256, do_sample=False)
    print(result.text, result.finish_reason)
```

The import name is `pandora_qwen25_omni`. Text, local images and audio can be combined in
ordered messages. Responses contain text. Basic use lets the SDK manage Runtime
configuration. Complete runnable scenarios are in the [examples index](../examples/README.md).

## API overview

Generation options apply to the current call. Synchronous generation returns
when the answer completes. Streaming returns a managed iterator whose updates
arrive during generation.

| Public entry | Use | Return | Example or detailed contract |
| --- | --- | --- | --- |
| `LanguageModel.from_pretrained(model_dir, *, runtime=None)` | Load a local package | `LanguageModel` | [Text chat](../examples/python/text_chat.py) |
| `model.generate(messages, *, max_new_tokens=None, do_sample=None, temperature=None, top_p=None, top_k=None, repetition_penalty=None, return_audio=False, past_key_values=None)` | Generate a complete answer from ordered messages | `GenerationResult` | [Mixed image/audio](../examples/python/image_audio_chat.py) |
| `model.generate_stream(messages, *, max_new_tokens=None, do_sample=None, temperature=None, top_p=None, top_k=None, repetition_penalty=None, return_audio=False, past_key_values=None)` | Consume answer increments from ordered messages | Managed stream with `stream.result` | [Streaming](#streaming-and-early-exit) |
| `DynamicCache()` | Create an empty cache for explicit cross-turn reuse | `DynamicCache` | [Three-turn chat](../examples/python/kv_cache_chat.py) |
| `cache.query()`, `cache.rebuild(*, system, retain_from_turn)` | Inspect cache usage or rebuild a suffix | Read-only mapping or new `DynamicCache` | [Context management](#context-management-and-snapshots) |
| `cache.save(path)`, `DynamicCache.load(path, model)` | Save and restore a completed conversation | Read-only save metrics or new `DynamicCache` | [Context management](#context-management-and-snapshots) |
| `model.count_tokens(messages, *, past_key_values=None, max_new_tokens=None)` | Plan the token budget before generation | Read-only mapping | [Token planning](#token-planning) |
| `model.capabilities` | Inspect supported inputs, outputs, generation controls, streaming and cache support | Recursively read-only mapping | [Inputs and limits](#ordered-messages-and-media) |
| `model.close()`, `cache.close()`, `stream.close()` | Release the corresponding owned resource | `None` | [Results and cleanup](#results-and-cleanup) |

## Parameters

### Loading

| Parameter | Type and default | Meaning and restrictions |
| --- | --- | --- |
| `model_dir` | Required local `str` or text-valued `os.PathLike` | Package root containing `models.json`. Relative paths use the caller's working directory. |
| `runtime` | This SDK's `Runtime` or `None` | `None` creates a model-owned default Runtime. An explicit Runtime is caller-owned. See [Runtime](RUNTIME_API.md). |

The loader discovers the single complete local resource set described by
models.json. Model loading initializes the language model and both media tower
contexts. Requests reuse those contexts until the model is closed.
Prepare one resource set per model directory using the
[model setup guide](../docs/MODEL_SETUP.md#folder-layout).

### Ordered messages and media

`messages` is required. Pass a nonempty list or tuple of dictionaries containing
exactly `role` and `content`. An optional initial `system` message precedes
alternating `user` and `assistant` messages. The final message is `user`.
Plain text content is a string. Mixed content is an ordered list or tuple of
items containing `type` and its matching field.

| Item | Value | Example |
| --- | --- | --- |
| `text` | String without template control markers such as `<|` | `{"type": "text", "text": "Describe both pictures."}` |
| `image` | Local JPEG/PNG path as `str` or text-valued `os.PathLike` | `{"type": "image", "image": "demo/samples/first-red-square.png"}` |
| `audio` | Local WAV path as `str` or text-valued `os.PathLike` | `{"type": "audio", "audio": "demo/samples/speech.wav"}` |

Media belongs in user messages. Item order determines media placement. The SDK
prepares inputs and decodes the generated answer. The bundled image/audio examples
include the original Omni multimodal system prompt. A supplied system message is
preserved. Omitting it uses the SDK's default helpful-assistant message. Instructions
and response-language preferences can be expressed in message text.

- Each user message accepts up to eight images and one audio file, within the
  shared context budget. See [single/multiple images](../examples/python/image_chat.py),
  [audio](../examples/python/audio_chat.py) and [mixed input](../examples/python/image_audio_chat.py).
- Images must be JPEG or PNG, at most 40 megapixels each. The model uses fixed
  image-size buckets. Per-request resizing or visual-token-budget controls are
  outside the public generation interface.
- Audio must be mono 16 kHz WAV, PCM16 or float32, with 400–320000 finite samples
  (0.025–20 seconds). Audio is accepted at its supplied rate and length.
- For the supplied model, usable context is 8160 tokens out of 8192 physical
  tokens. Input, media, history and reserved output share that budget.
  Over-budget requests fail. Media and history are preserved without implicit
  truncation or resampling.
- Each call handles one conversation. Video, generated speech, remote media URLs
  and multi-sample batching are unsupported.

### Generation parameters

`generate()` and `generate_stream()` accept the same keyword-only controls.
Omitted values or `None` resolve to the defaults below for each call. Request
overrides apply only to that call.

| Parameter | Type | Default / allowed values | Effect |
| --- | --- | --- | --- |
| `max_new_tokens` | `int` or `None` | `None` resolves to `256`. Positive integer fitting the shared context budget. | Maximum newly generated text tokens, excluding input. |
| `do_sample` | `bool` or `None` | `None` resolves to `False`. | Select greedy decoding or sampling. |
| `temperature` | Finite `int`/`float` or `None` | `None` resolves to `1.0`. Must be positive. | Scale the sampling distribution. |
| `top_p` | Finite `int`/`float` or `None` | `None` resolves to `1.0`. Range `(0, 1]`. | Cumulative-probability filter. `1` disables filtering. |
| `top_k` | `int` or `None` | `None` resolves to `0`. Range `0..2147483647`. | Ranked candidate filter. `0` disables filtering. |
| `repetition_penalty` | Finite `int`/`float` or `None` | `None` resolves to `1.0`. Must be positive. | Penalize repetitions across the logical prompt, cached history and generated text. `1` disables the penalty. |
| `return_audio` | `bool` | `False`. This model accepts only `False`. | `True` raises `UnsupportedFeatureError`. Result audio remains `None`. |
| `past_key_values` | This SDK's `DynamicCache` or `None` | `None` starts an independent request. | Pass a cache explicitly for cross-turn reuse. |

Booleans are rejected for numeric controls. Explicit `temperature`, `top_p` or
`top_k` with effective `do_sample=False` raises `InputError`, even when the
explicit value matches its default. Set `do_sample=True` on the same call.
Repetition penalty also applies to greedy decoding. Unsupported generation
keywords raise `TypeError`. Select the controls declared in `model.capabilities`.

Within an open model, request sampling with the desired overrides:

```python
result = model.generate(
    [{"role": "user", "content": "Name three fruits briefly."}],
    max_new_tokens=256,
    do_sample=True,
    temperature=0.7,
    top_p=0.9,
    top_k=20,
    repetition_penalty=1.1,
)
print(result.text)
```


### Token planning

`model.count_tokens(...)` uses the same messages, media sizing and
`max_new_tokens` default as generation. Pass `past_key_values` to include
its cached turns. Counting reserves the model while it prepares inputs but
runs no inference and leaves the cache unchanged, including an unbound cache.

The returned mapping contains `fits` (boolean), `input_tokens` (total logical
input including history, media and fixed prefix), `cached_tokens` (reused
prefix/history), `new_prefill_tokens`, `prefix_tokens`, `reserved_output_tokens`,
`context_capacity` and `context_usable_tokens`. It also reports `media_tokens`,
`image_count`, `audio_count`, `image_tokens`, `audio_tokens`, `vision_buckets`
(ordered bucket names) and `vision_bucket` (first bucket or empty string).
Counts are integers. `fits=False` means the request exceeds the usable budget.
Invalid input, cache binding or output budget raises `InputError`. Input that
exceeds the model's physical context also raises `InputError`. See [Errors](#errors).

`model.capabilities` declares the boolean flags `token_count`, `cache_query`,
`cache_snapshot`, `cache_rebuild` and `generation_statistics`.

## Results and cleanup

### `GenerationResult`

`generate()` returns an immutable `GenerationResult`. Streaming produces
immutable `GenerationUpdate` values and provides its final `GenerationResult`
through `stream.result` after completion or successful close.

| Field | Type | Meaning |
| --- | --- | --- |
| `result.text` | `str` | New answer text for this call. |
| `result.audio` | `None` | This model outputs text. |
| `result.finish_reason` | `str` | `stop` for normal completion, `length` for an output-budget stop, or `cancelled` for confirmed cancellation. |
| `result.statistics` | Read-only mapping | Token usage, timings and effective generation settings for this request. |
| `update.delta` | `str` | Unicode text added by this update. |
| `update.text` | `str` | Cumulative generated text. |
| `update.finish_reason` | `None` or `str` | `None` during generation, then the actual terminal reason. |
| `update.audio_delta` | `None` | This model streams text. |

A fully consumed stream delivers exactly one terminal update. Concatenated text
increments agree with the final answer. Reading `stream.result` before completion
or close raises `BusyError`. Inference errors propagate as exceptions.


Statistics are detached from the model and can be read after closing it. Counts
include `context_tokens` and `new_prefill_tokens`, which correspond to the token
plan, plus prompt, media, generated and cached token counts. Timing fields use
milliseconds. Standalone dialogs and the caches that reuse them measure
`lm_ttft_ms` from query submission through sampling the first token.
`decode_tokens_per_second` measures the rate between the first and last sampled
tokens when at least two are sampled. Profiled dialogs report the backend's
token timings. `generation_config` contains the resolved generation options.
Fields depend on the input and the stages completed, so check for a key before
reading an optional metric.

### Errors

| Exception | Typical cause | Caller action |
| --- | --- | --- |
| `InputError` | Invalid structure, path, numeric value, budget or unusable cache chain. | Correct the request. Use a new cache after an incomplete turn. |
| `UnsupportedFeatureError` | Unsupported media format, video, speech output or backend control. | Use a capability supported by the loaded model. |
| `BusyError` | An active operation owns the model/cache, or the final result is unavailable. | Finish/close the owning operation before retrying. |
| `ClosedError` | A closed resource or a handle inherited after fork. | Create resources in the current process. |
| `InferenceError` | Native inference failure. | Preserve the error, close affected resources and reopen the model as needed. |
| `ResourceError` | Model package resources are missing, invalid, or unreadable. | Check the model directory and download the target for your device. |
| `BackendError` | The native backend rejected a setting or operation. | Check the Runtime settings and capture the backend diagnostics. |
| `InternalError` | Unexpected SDK failure. | Capture the error and release the affected resources. |
| `TypeError` | Unknown public keyword or calling the model constructor directly. | Use a documented signature and `from_pretrained()`. |

SDK-specific errors derive from `OmniError`. Native errors can expose `operation`
and `native_code`. Keep these diagnostics with the failing request.

### Lifecycle

#### Streaming and early exit

A short normal-streaming example keeps the model open until the stream closes:

```python
with LanguageModel.from_pretrained("models") as model:
    with model.generate_stream(
        [{"role": "user", "content": "Explain on-device AI briefly."}],
        max_new_tokens=256,
    ) as stream:
        for update in stream:
            print(update.delta, end="", flush=True)
    result = stream.result
    print(result.finish_reason)
```

For early exit, leave the stream context after the first nonempty increment:

```python
with LanguageModel.from_pretrained("models") as model:
    with model.generate_stream(
        [{"role": "user", "content": "Write a long story about a robot."}],
        max_new_tokens=256,
    ) as stream:
        for update in stream:
            print(update.delta, end="", flush=True)
            if update.delta:
                break
    result = stream.result
    print(result.text, result.finish_reason)
```

Closing requests cancellation and waits for in-flight native work before releasing
its resources. An interrupted request reports `cancelled` with the delivered
Unicode prefix. A request that already finished keeps its actual terminal result.
A release failure raises an exception. Retry close before reusing or releasing
related resources. The stream is single-use and single-consumer.

#### Cache state and ownership

Create `DynamicCache()` for a new conversation and pass the same object as
`past_key_values` on each turn. It starts empty and binds to the model instance
and process on first use. The first cached call accepts an optional system and
one user message. Later calls pass only the new user message and its media.
Repeated history and a replacement system in a continuation are rejected.

A `stop` result commits the turn. `length`, cancellation or execution failure
ends that cache chain. Rebuild the conversation with a new cache and application
history. An input validation error before execution preserves an already
completed cache. See the [three-turn example](../examples/python/kv_cache_chat.py).

Without `past_key_values`, calls are independent. Applications can explicitly
supply complete user/assistant history for an uncached multi-turn conversation.

Finish streams, close caches, close models, then close any caller-owned Runtime.
Models release their default Runtime. Explicit Runtime objects stay caller-owned.
Model and cache contexts call `close()` on exit. Repeated successful close is
safe. Same-model overlap and premature close of an active model/cache raise
`BusyError`. Cross-model caches are rejected. Handles inherited after fork are
rejected. Create SDK objects independently in the destination process.


#### Context management and snapshots

| Operation | Parameters and result |
| --- | --- |
| `cache.query()` | Returns a read-only mapping. All caches report `bound` and `valid` (booleans) and `turns` (completed turn count). A bound cache also reports `logical_history_tokens`, `effective_kv_tokens`, `pending_eos_tokens`, `context_capacity`, `context_usable_tokens` and `kv_logical_payload_bytes`. `snapshot_restore` is empty on a fresh cache and reports `total_restore_ms`, `total_bytes`, `history_tokens` and `historical_prefill_tokens` after restore. |
| `cache.save(path)` | Pass a new local directory path as a `str` or text-valued `os.PathLike`. The idle cache must have a completed turn. Returns read-only `path` (absolute destination string), `total_bytes`, `save_ms` and `history_tokens`. An existing destination raises `InputError`. |
| `DynamicCache.load(path, model)` | Pass the saved directory path and an open `LanguageModel` with the matching model package. Returns a separate cache bound to that model instance in the calling process, ready for the next user message. An unavailable directory raises `ResourceError`. An invalid or incompatible snapshot raises `InputError`. |
| `cache.rebuild(*, system, retain_from_turn)` | Pass the new system text (no template control markers or NUL) and the zero-based integer index of an existing completed turn. Returns a new cache on the same model containing that turn and all later completed turns. The source remains usable. An invalid index, input or unusable source raises `InputError`. |

Snapshots contain private conversation data. Save them in a private location
and load snapshots from trusted sources. Keep the directory intact and manage
its lifetime separately from the model and cache. A snapshot can be loaded in a
new process with a matching model package. Cache handles remain process-local.

Query, save, load and rebuild require the relevant resources to be idle and
raise `BusyError` during a conflicting operation or `ClosedError` for a closed
or inherited handle. Close each cache returned by load or rebuild separately,
before closing the model. Read-only mappings are ordinary Python values and
require no release.

## Advanced

### Complete examples and Runtime

The [examples index](../examples/README.md) links five independent, directly
runnable Python scripts for text, single/multiple images, audio, mixed image/audio
and three-round cache reuse. The [SDK integration guide](README.md) links back to
this reference. Hardware configuration and explicit Runtime ownership are described
in [Runtime](RUNTIME_API.md).

### C integration

The [C ABI guide](../docs/C_ABI.md), [public header](include/qwen25_omni.h)
and [C example](../examples/c/infer_tensors.c) cover direct native integration.
