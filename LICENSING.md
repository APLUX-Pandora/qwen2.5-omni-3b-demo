# Licensing scope

| Component | Terms |
|---|---|
| APLUX-authored Web/business code, examples, public C header and thin Python binding | Apache-2.0 where designated; third-party portions excluded |
| APLUX proprietary contributions to the compiled SDK core | Pandora Model SDK terms, only to the extent APLUX has the rights to license them |
| Bundled OpenCV, nlohmann JSON, libpng, libjpeg-turbo and zlib | Their respective upstream terms. Notices accompany the installed SDK |
| Tokenizer | The tokenizer includes Qualcomm's Genie C wrapper under applicable Qualcomm terms and Hugging Face Tokenizers under Apache-2.0. See the [Apache-2.0 text](sdk/python/pandora_qwen25_omni/LICENSES/Apache-2.0.txt) and [tokenizer dependency notices](sdk/python/pandora_qwen25_omni/LICENSES/Tokenizer-Third-Party-Notices.txt). |
| Qwen model weights and derivatives, supplied separately on Hugging Face | Qwen Research License and applicable upstream terms. The Qwen Research License permits non-commercial research and evaluation. |
| Bundled Qualcomm QNN runtime | See the [vendor license](sdk/lib/qnn248/LICENSE.pdf) and [third-party notices](sdk/lib/qnn248/NOTICE.txt) |
| Aidlux LMS, FastRPC, driver and DSP firmware | Device prerequisites under their own terms |
| Preset text/images and speech example | Project-authored text and geometric images. The synthetic WAV uses the Carnegie Mellon University Flite kal16 voice. See [sample sources](demo/samples/SOURCES.json) and the [Flite notice](LICENSES/Flite.txt). |

See the full texts for [Apache-2.0](LICENSES/Apache-2.0.txt), [Pandora Chinese](LICENSES/Pandora-Model-SDK.zh-CN.txt), [Pandora English](LICENSES/Pandora-Model-SDK.en.txt), [Qwen Research License](LICENSES/Qwen-Research-LICENSE.txt).
