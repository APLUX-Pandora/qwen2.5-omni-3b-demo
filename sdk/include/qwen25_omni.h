#ifndef QWEN25_OMNI_H
#define QWEN25_OMNI_H
#include <stdint.h>
#include <stddef.h>
#include "pandora_runtime.h"
#ifdef __cplusplus
extern "C" {
#endif
#define Q25O_SDK_VERSION "1.0.0"
#define Q25O_ABI_VERSION 1u
typedef uint64_t q25o_handle;
typedef struct {uint32_t struct_size;uint32_t abi_version;const char* data;uint64_t size;} q25o_json_options;
typedef int32_t (*q25o_text_callback)(const char* data,uint64_t size,void* user);
enum {Q25O_OK=0,Q25O_INPUT=1,Q25O_UNSUPPORTED=2,Q25O_BUSY=3,Q25O_CLOSED=4,Q25O_INFERENCE=5,
      Q25O_RESOURCE=6,Q25O_BACKEND=7,Q25O_INTERNAL=8};
/* Initialize handle outputs to 0 and char** outputs to NULL before calling.
   Failure leaves these slots empty. Success transfers ownership of each handle:
   close models with q25o_model_close, caches with q25o_cache_close, processors
   with q25o_processor_close, and batches with q25o_batch_close. Release requests
   with q25o_request_release and JSON buffers with q25o_buffer_free.
   q25o_batch_tensor leaves the output view unchanged on failure. A successful
   view borrows batch storage. */
/* Additive upstream-input ABI, revision 1. All tensor views are contiguous,
   synchronous borrows. rank <= 4; nbytes must exactly match shape and dtype.
   Batch tensor pointers remain valid until q25o_batch_close. Copy before close.
   Processor operations do not load graphs; request creation copies its inputs. */
enum {Q25O_U8=1,Q25O_F32=2,Q25O_I64=3};
typedef struct {
 uint32_t struct_size, dtype, rank, reserved;
 const char* name; const void* data; uint64_t nbytes; uint64_t shape[4];
} q25o_tensor_view;
uint32_t q25o_upstream_api_revision(void);
int32_t q25o_processor_open(const q25o_json_options*,q25o_handle*);
int32_t q25o_processor_close(q25o_handle);
int32_t q25o_processor_template(q25o_handle,const q25o_json_options*,char**);
int32_t q25o_processor_decode(q25o_handle,const q25o_json_options*,char**);
int32_t q25o_processor_process(q25o_handle,const q25o_json_options*,const q25o_tensor_view*,uint32_t,q25o_handle*);
int32_t q25o_batch_tensor(q25o_handle,uint32_t,q25o_tensor_view*);
int32_t q25o_batch_close(q25o_handle);
int32_t q25o_request_create_tensors(q25o_handle,const q25o_json_options*,const q25o_tensor_view*,uint32_t,q25o_handle*);
int32_t q25o_model_count_tensors(q25o_handle,const q25o_json_options*,const q25o_tensor_view*,uint32_t,char**);
/* Handles and callbacks are process-local. Options are copied. No model bytes cross this ABI. The additive input ABI exposes token IDs. JSON schemas are documented with the SDK. */
/* Pass NULL for the default Runtime. Keep a supplied handle valid until open returns;
   the loaded model then holds its own Runtime reference. */
int32_t q25o_model_open(const pandora_runtime_t*,const q25o_json_options*,q25o_handle*);
int32_t q25o_model_query(q25o_handle,char**);
int32_t q25o_model_close(q25o_handle);
int32_t q25o_request_create(q25o_handle,const q25o_json_options*,q25o_handle*);
/* Count message tokens using a request JSON with optional cache_handle and
   max_new_tokens. Returns a JSON token plan with fits; does not run inference
   or change the cache. The caller frees the JSON with q25o_buffer_free. */
int32_t q25o_model_count(q25o_handle,const q25o_json_options*,char**);
/* Caches are tied to one model and process. Close caches before their model. */
int32_t q25o_cache_create(q25o_handle model,q25o_handle* cache);
/* Return idle cache validity, turn count and usage as caller-owned JSON. */
int32_t q25o_cache_query(q25o_handle cache,char**);
/* Options contain a local "path" string. Save requires an idle cache with a
   completed turn and writes to a new directory. It returns caller-owned JSON
   with the save metrics. Load requires a compatible snapshot and returns a
   new owned cache bound to the supplied model. Close it with q25o_cache_close.
   An unavailable snapshot directory returns Q25O_RESOURCE. */
int32_t q25o_cache_save(q25o_handle,const q25o_json_options*,char**);
int32_t q25o_cache_load(q25o_handle,const q25o_json_options*,q25o_handle*);
/* Options contain replacement "system" text and zero-based "retain_from_turn".
   Requires an idle, valid cache and an existing completed turn index.
   Returns a new owned cache on the same model; the source stays intact.
   Close each cache separately with q25o_cache_close. */
int32_t q25o_cache_fork(q25o_handle,const q25o_json_options*,q25o_handle*);
int32_t q25o_cache_close(q25o_handle cache);
int32_t q25o_request_plan(q25o_handle request,char**);
/* Callback runs on the model worker and borrows data only for this call.
   Return nonzero to request cooperative cancellation. Do not reenter blocking
   model/cache/query/close calls from this callback; use the caller thread. */
int32_t q25o_request_execute(q25o_handle,q25o_text_callback,void*);
int32_t q25o_request_cancel(q25o_handle);
/* After execution, return caller-owned JSON with text, finish_reason, token
   sequences and statistics. Free the JSON with q25o_buffer_free. */
int32_t q25o_request_result(q25o_handle,char**);
int32_t q25o_request_release(q25o_handle);
/* Borrowed thread-local UTF-8 JSON object after failure, or an empty string
   when no error is recorded. Fields: message (string), code (SDK status),
   native_code (integer, 0 if unavailable), and operation (string, possibly empty).
   Copy before the next call on this thread. The caller does not free this string. */
const char* q25o_last_error(void);
void q25o_buffer_free(void*);
#ifdef __cplusplus
}
#endif
#endif
