# C ABI

`sdk/include/qwen25_omni.h` · `sdk/lib/libqwen25_omni.so` · Native inference with the local encrypted model package.

## Build and link

From the Demo root, compile against the shipped header and library; the library carries its QNN runtime:

Follow the [SDK installation steps](../sdk/README.md#install) in the active Python environment before compiling. For deployments without Python, put the wheel's Runtime shared library where the system loader can find it.

```bash
runtime_dir=$(python -c "import pathlib,pandora_runtime; print(pathlib.Path(pandora_runtime.__file__).parent)")
cc -std=c99 -I sdk/include your_app.c -L sdk/lib -L"$runtime_dir" -Wl,--no-as-needed -l:libpandora_runtime.so.5 -Wl,--as-needed -Wl,-rpath,"$runtime_dir" -lqwen25_omni -Wl,-rpath,'$ORIGIN/sdk/lib' -o your_app
```

## Lifecycle

```text
Runtime → model → optional cache → request → execute → result
                                     release request → close cache → close model → close Runtime
```

For tensor input, open a processor, prepare a batch, and create the request from the batch views. Release the batch after request creation returns. The processor can be used to prepare inputs without opening the model. Supply `q25o_json_options` with the correct structure size, ABI version, and UTF-8 JSON length. Pass `NULL` as the Runtime handle to apply the default settings. To use explicit settings, see [Runtime](../sdk/RUNTIME_API.md) and [the shared C header](../sdk/include/pandora_runtime.h). Keep the supplied handle valid until model loading returns. The loaded model takes its own reference.

## Functions

| Function | Purpose | Returns |
| --- | --- | --- |
| `pandora_runtime_create`, `pandora_runtime_get_status`, `pandora_runtime_destroy` | Create a Runtime, query hardware settings, or release the caller’s reference | Status |
| `pandora_runtime_last_error` | Read the last Runtime error on this thread | Borrowed message |
| `q25o_upstream_api_revision` | Report the native tensor API revision | Revision number |
| `q25o_model_open`, `q25o_model_query`, `q25o_model_close` | Open the model, read capabilities and state, or close it | Status |
| `q25o_model_count`, `q25o_model_count_tensors` | Check token budget for messages or prepared tensors | Status |
| `q25o_processor_open`, `q25o_processor_close` | Open or close a processor for tokenization and media preprocessing | Status |
| `q25o_processor_template`, `q25o_processor_decode` | Render/tokenize messages or decode token IDs | Status |
| `q25o_processor_process`, `q25o_batch_tensor`, `q25o_batch_close` | Prepare, inspect, and release an input tensor batch | Status |
| `q25o_cache_create`, `q25o_cache_query`, `q25o_cache_close` | Create, inspect, or close one model's cache | Status |
| `q25o_cache_save`, `q25o_cache_load`, `q25o_cache_fork` | Save an idle completed cache, restore a cache, or rebuild a suffix into a separate cache | Status |
| `q25o_request_create`, `q25o_request_create_tensors`, `q25o_request_plan` | Create a request from messages or tensors and inspect its token plan | Status |
| `q25o_request_execute`, `q25o_request_cancel`, `q25o_request_result`, `q25o_request_release` | Execute, cancel, read the result, and release the request | Status |
| `q25o_last_error` | Read the last error on this thread | Borrowed JSON |
| `q25o_buffer_free` | Release an SDK-allocated result buffer | Void |

Prepared tensors are contiguous row-major views. Image inputs use unsigned 8-bit HWC RGB, and audio inputs use mono float32 at 16 kHz. Name the inputs by modality and index, such as `image_0` and `audio_0`. The result JSON contains `sequences`, `text`, `finish_reason`, and `statistics`. The C request defaults use up to 256 new tokens and greedy decoding.

### JSON options

Options are UTF-8 JSON objects. The length excludes the terminating NUL. An
optional generation value may be omitted or set to JSON `null` for its default.

| Function | Required keys | Optional keys and defaults |
| --- | --- | --- |
| `q25o_model_open` | None | `model_dir` (string) defaults to `models`, where the SDK uses the manifest at the root or discovers a single package in an immediate child. `target` (string) selects a manifest target. Omit it to select the complete local target for the device. |
| `q25o_processor_open` | `model_dir` (string) | `target` (string), Omit it to select the sole complete local target for preprocessing. |
| `q25o_request_create`, `q25o_model_count` | One of `messages` (array) or `prompt` (string) | Generation options below. `cache_handle` (integer) selects a cache from this model. `images` (string or array of strings) and `audio` (string) are local paths for the final user message and cannot be combined with media in `messages`. |
| `q25o_request_create_tensors`, `q25o_model_count_tensors` | None. Pass the prepared tensor views as separate C arguments. | Generation options below and `cache_handle` (integer) from the same model. |
| `q25o_cache_save` | `path` (string), a new destination directory | None |
| `q25o_cache_load` | `path` (string), a saved snapshot directory | None |
| `q25o_cache_fork` | `system` (string), `retain_from_turn` (integer, zero-based index of the first completed turn to retain) | None |
| `q25o_processor_template` | `conversation` (array), with the message structure below | `add_generation_prompt` (boolean, default `false`). When true, the last message must be from the user. Media items mark where tensors are inserted during processing. |
| `q25o_processor_process` | `text` (string), the rendered template | None. Supply media tensors as separate C arguments, in modality order with zero-based names. |
| `q25o_processor_decode` | `sequences` (array of integer token arrays) | `skip_special_tokens` (boolean, default `false`). |

Each message has a string `role` and a `content` value. Start with an optional
`system` message, then alternate `user` and `assistant`. A generation request
ends in `user`. Use a plain string for text or an ordered array of objects.
Each object has `type` equal to `text`, `image`, or `audio` and a same-named
member with its text or local media path. The template function only uses the
type for media placeholders. The processor receives media data separately. Only user messages may contain
media. A cached generation takes one new user message, with an optional system
message only before the first turn.

| Generation key | Type and allowed values | Default |
| --- | --- | --- |
| `max_new_tokens` | Positive integer, subject to the context budget | `256` |
| `do_sample` | Boolean | `false` |
| `temperature` | Finite number greater than zero | `1.0` |
| `top_p` | Number in `(0, 1]` | `1.0` |
| `top_k` | Nonnegative 32-bit signed integer. Zero disables top-k filtering. | `0` |
| `repetition_penalty` | Finite number greater than zero | `1.0` |
| `frequency_penalty`, `presence_penalty` | Finite numbers | `0.0` |
| `use_cache` | Boolean. False recomputes context for inference. | `true` |

Explicit non-null `temperature`, `top_p`, or `top_k` requires
`"do_sample": true`. Count calls report `fits` for the requested output budget.

### JSON results

| Function | Fields |
| --- | --- |
| `q25o_model_query` | Model capabilities in `inputs`, `text_streaming`, `max_images_per_message`, `max_audio_per_message`, `mixed_image_audio`, `multimodal_messages`, `generation_parameters`, `use_cache_values`, and `do_sample_values`. The loaded model reports `target`, `lm_shards`, `position_revision`, `encrypted_graphs_required`, `context_capacity`, `context_usable_tokens`, and `context_buckets`. Generation defaults use the `default_` prefix. The worker reports `cpu_ids`, `model_worker_tid`, `worker_observed_cpu_ids`, and `worker_affinity_match`. |
| `q25o_request_plan` | Integer `input_tokens`, `cached_tokens`, `new_prefill_tokens`, `context_capacity`, and `context_usable_tokens`. Read before executing the request. |
| `q25o_model_count`, `q25o_model_count_tensors` | Plan fields plus `media_tokens`, `image_tokens`, `audio_tokens`, `reserved_output_tokens`, and boolean `fits`. The message path also returns `image_count`, `audio_count`, `vision_buckets`, `vision_bucket`, and `prefix_tokens`. |
| `q25o_request_result` | `text` (newly generated text), `sequences` (input and generated token IDs), `finish_reason` (`stop`, `length`, or `cancelled`), and `statistics` (object). |
| `q25o_cache_query` | `valid`, `turns`, `logical_history_tokens`, `pending_eos_tokens`, backend occupancy `n_past`, context limits and `kv_logical_payload_bytes` and `kv_capacity_logical_payload_bytes`. A live cache also reports `valid_kv_tokens`, `n_prompt`, `n_generated`, `last_token`, `last_is_eos`, and `pending`. `snapshot_restore` holds restore diagnostics when available. |
| `q25o_cache_save` | `path`, `total_bytes`, `files` (relative names mapped to `bytes` and `sha256`), `save_ms`, `n_past`, and `history_tokens`. |
| `q25o_processor_template` | `text` (rendered template) and `input_ids` (integer token array). |
| `q25o_processor_decode` | Array of strings, one per input sequence. |

Generation statistics include `context_tokens`, `new_prefill_tokens`,
`media_tokens`, and `generation_config` with the resolved sampling settings
when generation is reached. Further timing, token and cache counters depend on
the request and how far execution progressed.


### Token planning and cache operations

Message and tensor count calls reserve the model while preparing input. They
run no inference and leave cache history unchanged. Use `fits` to check the
usable budget. Invalid options, cache binding or output budget and input that
exceeds the physical context return `Q25O_INPUT`.

Save requires an idle, valid cache with a completed turn and a new destination
directory. If the destination cannot be written, save returns `Q25O_RESOURCE`
and leaves the output pointer null. Load accepts a directory saved from the
matching model package, including in a previous process. An unavailable
snapshot directory returns `Q25O_RESOURCE`. An incompatible or invalid
snapshot returns `Q25O_INPUT`. Both saving and loading require the model directory's
`SHA256SUMS` file. If it is missing or unreadable, the operation returns `Q25O_RESOURCE`.
Snapshots contain private conversation data. Keep the directory intact in a
private location and load snapshots from trusted sources.

Fork requires an idle, valid cache and an existing completed turn index. It
replaces the system message and retains the indexed turn and its suffix in a
new cache on the same model. The source is unchanged. Invalid input, an
unusable cache, an existing save destination or an out-of-range turn returns
`Q25O_INPUT`. An active operation returns `Q25O_BUSY`. A closed handle or a call
from a forked process returns `Q25O_CLOSED`. Close each cache returned by load
or fork separately. Free each returned JSON buffer with `q25o_buffer_free`.

## Error codes

| Code | Meaning | What the caller should do |
| --- | --- | --- |
| `Q25O_OK` | Success | Use the returned result. |
| `Q25O_INPUT` | Invalid input or budget | Correct the request. |
| `Q25O_UNSUPPORTED` | The operation or input is unsupported | Use supported media or settings. |
| `Q25O_BUSY` | The resource is still in use | Finish or release the active operation before retrying. |
| `Q25O_CLOSED` | The handle is closed or inherited across processes | Open a new handle in this process. |
| `Q25O_INFERENCE` | Inference failed during execution | Copy the error and release the affected resources. |
| `Q25O_RESOURCE` | Model resources are missing, invalid, or unreadable | Check the model directory and download the target for your device. |
| `Q25O_BACKEND` | The inference backend rejected a setting or operation | Check the Runtime settings and capture the backend diagnostics. |
| `Q25O_INTERNAL` | Unexpected SDK failure | Capture the error and release the affected resources. |

## Threads and ownership

Handles are process-local. Requests reserve their model until released. The text callback runs on the model worker and borrows UTF-8 bytes until it returns. A nonzero callback return requests cancellation. Use the caller thread for blocking model or cache operations.

Processor input views are synchronous borrows. A batch owns the views returned by `q25o_batch_tensor` until the batch closes. Request creation copies its input tensors. Do not close a batch while another thread is borrowing a view.

### Failure and ownership

Initialize each handle output to `0` and each JSON buffer output to `NULL`.
A failed call leaves the initialized output empty. A successful call transfers
ownership of the output to the caller.

| Output | Release after success |
| --- | --- |
| Model from `q25o_model_open` | `q25o_model_close` |
| Cache from `q25o_cache_create`, `q25o_cache_load`, or `q25o_cache_fork` | `q25o_cache_close` |
| Request from `q25o_request_create` or `q25o_request_create_tensors` | `q25o_request_release` |
| Processor from `q25o_processor_open` | `q25o_processor_close` |
| Batch from `q25o_processor_process` | `q25o_batch_close` |
| JSON buffer from query, count, plan, result, save, template, or decode | `q25o_buffer_free` |

`q25o_batch_tensor` leaves the view unchanged on failure. On success it borrows
the batch's storage. `q25o_last_error()` returns borrowed, thread-local UTF-8 JSON
after a failure. The object has `message` (string), `code` (SDK status integer),
`native_code` (integer, zero if unavailable), and `operation` (string, possibly empty).
An empty string means there is no recorded error. Copy the borrowed data before
another SDK call on the same thread.

## Example

A complete program is in [examples/c/infer_tensors.c](../examples/c/infer_tensors.c).
