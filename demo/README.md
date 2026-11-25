# Pandora Qwen2.5-Omni Web Demo

A local chat interface with text, up to eight images and one WAV per message and streamed text
output. It includes durable conversation history, native KV snapshots, automatic
context compaction, a circular context indicator, Chinese/English interface choice,
media previews, Stop and expandable inference statistics. Microphone capture and
speech output are outside this demo.

## Run

Complete [Install](../README.md#1-install) and [Download the model](../docs/MODEL_SETUP.md).
Run from the delivery root in the activated environment:

```sh
sh demo/start.sh --port 7860
```

Open `http://<device-ip>:7860/`. Stop the service with `Ctrl+C`.
The defaults are `.venv/bin/python`, `models/`, and `run/` in this checkout.
Use `OMNI_PYTHON`, `OMNI_MODEL_DIR`, and `OMNI_RUN_DIR` to set alternate paths.
Keep `run/history/` across restarts to reopen saved conversations.

## Inputs and model behavior

- Text: nonempty, up to 8,000 characters, subject to the selected target context budget (8192 physical / 8160 usable).
- Up to eight JPG/PNG images per message: each up to 10 MiB and 40 megapixels, subject to the shared context budget; five-bucket routing is native.
- One WAV: 16 kHz mono PCM16/Float32, 0.025–20 seconds; no silent resampling/truncation.
- One active model operation globally; overlapping operations return HTTP 409.

The presets are project-authored; provenance is in `samples/SOURCES.json`.
Uploaded and preset WAVs can be played in the page. The Web Demo requests up to 256 new tokens with greedy decoding. The native SDK handles templates, prefix3, mRoPE, R1,
embeddings and model execution; generation uses the public LM v1 API. The service uses private SDK helpers for
admission, snapshot persistence and diagnostics. These helpers are internal to
this matching Demo/SDK.

## Conversations and loading

New chat preserves saved conversations in the sidebar. A new conversation appears
in history after its first completed turn. Each browser owner can keep up to
100 saved conversations. To archive all saved conversations, stop the service and move
its `history/` directory out of the configured run directory, then restart the service.
Keep the archive if you want to restore it later.

The application keeps one active native cache. After an EOS-completed turn it saves a native
snapshot and private metadata, retaining two snapshot generations. Selecting a
conversation restores KV without re-running historical prompts or media towers.
Images/WAVs are retained separately for previews. Cancelled/partial turns do not
become model memory.

A random browser-held owner capability and the selected conversation are kept in
localStorage. The same browser can recover its history after service/model
restart. Clearing browser storage or using another browser does not automatically
recover that owner's list. There is no account login or cross-device sync.
History is private local conversation data, not part of the encrypted HF model
package: directories are 0700, metadata/media/snapshot files 0600. Secret
capabilities are carried in POST bodies, not media URLs. The page renders user
content as text, not HTML.

Restoring and compacting display explicit loading messages and disable messaging,
attachments, New chat and history switching. The server rejects concurrent
requests. The target cache is constructed before the old cache is released, so a
restore failure preserves the previous conversation. Stop during ordinary
inference waits for native work and restores the last committed state. Shutdown
joins active work and synchronous restoration before closing caches and the model.
Idle native sessions may be unloaded. Conversations with saved messages stay on
disk and can be restored. An empty conversation is deleted when it is closed,
when its retention period expires, or when it is evicted to make room at the
empty conversation limit. Once deleted, it cannot be restored.

## Context and language

The small circle in the input toolbar shows actual usage; hover or click for
details. Logical history includes prefix3, template/media rows and pending EOS;
effective KV is shown separately and AR128 padding is excluded. Each turn reserves
256 output tokens. Before exceeding the selected target usable context budget, old turns are summarized and the two
newest completed turns retain their raw token/media embeddings. Older media can
only contribute facts retained in text; re-upload for new details.

The header selector switches Chinese/English UI and persists `omni-ui-language`.
Loading, errors, context and statistics labels follow this setting. Prompts,
model responses, filenames and existing conversation titles are not translated;
changing UI language does not change model context.

## Transport

- `GET /api/health`, `/api/presets`, `/api/presets/{id}/asset`.
- `POST /api/owner`: create a random browser history capability.
- `POST /api/history`: list conversations belonging to that owner capability.
- `POST /api/sessions`: create a conversation for an owner.
- `POST /api/sessions/{id}/restore`: load history/KV using its capability.
- `POST /api/sessions/{id}/context`: read usage; reports whether it is active.
- `POST /api/sessions/{id}/media/{name}`: retrieve an owned historical upload.
- `DELETE /api/sessions/{id}`: unload the session. Conversations with saved
  messages can still be restored. Empty conversations are deleted and cannot be
  restored.
- `POST /api/uploads`, `DELETE /api/uploads/{id}`: temporary upload ownership.
- `POST /api/generate`: owned conversation/prompt/media, streamed through SSE.
- `POST /api/jobs/{id}/cancel`: cancel and await the owned request.

Production journals record timings and counters, not message/summary contents.
`OMNI_WEB_DIAGNOSTICS=1` enables summary-body logging for synthetic validation;
leave it unset for normal use. Conversation contents are stored only in the private
history store. This is an internal local-network demo, not a public account service.

## Multiple attachments and Runtime

Image selection supports multiple files, additional selections, mixed image/WAV
uploads, individual removal and drag/drop. Each message permits up to eight images
and one WAV; later turns may upload new media. WAV uploads and presets can be
played in the composer and history. The server validates the entire ownership and
count batch before consuming temporary uploads. History preserves all media IDs,
and old single-attachment messages remain readable.

The exact SDK token plan, not image count alone, controls context admission. Web
reserves and requests 256 output tokens. At overflow it compacts older turns and
retains the latest two complete turns; if that still does not fit it rejects the
input. Restoring and compacting show blocking status; sending, changing sessions,
and changing attachments are disabled until completion.

The Demo builds canonical typed Omni messages and passes explicit past_key_values. Memory summaries, retained-turn policy and compression admission stay in this application. SDK reset is not used.
