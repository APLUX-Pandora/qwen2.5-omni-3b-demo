# Model setup

## Device requirements

- A compatible Linux device with Aidlux LMS (`sudo lms check` returns true), drivers, DSP firmware and BSP/FastRPC support.
- Python 3.10–3.12 in the Demo environment (see [Install](../README.md#1-install)).
- The SDK includes its QNN runtime libraries. Do not install QNN separately or set QNN paths.

## Targets

On the device, read its SoC ID and choose the matching target folder:

```bash
cat /sys/devices/soc0/soc_id
```

| SoC ID | SoC | Target folder |
| --- | --- | --- |
| 603 | QCS8550 | `qcs8550_qnn248` |
| 702 | QCS8625 | `qcs8625_qnn248` |
| 675 | QCS8275 | `qcs8275_qnn248` (also accepts `qcs8625_qnn248`) |
| 676 | QCS9075 | `qcs9075_qnn248` |

## Download

From the Demo root, in the activated environment, download the shared resources once and then one target:

```bash
hf download APLUX-Pandora/Qwen2.5-Omni-3B --local-dir models --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/Qwen2.5-Omni-3B --local-dir models --include "targets/<target-folder>/*"
```

Run `hf auth login` first if the repository is private. Keep one target per model folder: to switch devices, move the old `targets/` folder out or download into a new folder.

Replace `<target-folder>` with the folder for your SoC.

## Folder layout

After the download, `models/` looks like this:

```text
models/
  models.json
  SHA256SUMS
  tokenizer.json
  embedding_fp32.bin
  prefix/
  processor/
  vision/
  targets/
    <target-folder>/
      *.bin.aidem
```

The SDK reads `models.json`, checks that the shared resources and one complete target are present, and reports what is missing. `hf download` verifies each large file's checksum.

The SDK selects the target for the device's SoC and checks file sizes during loading. It reads the Genie dialog and HTP settings from the encrypted model package.

## Troubleshooting

| Message or symptom | What to do |
| --- | --- |
| Missing resource or incomplete target | Repeat both download commands in the same model folder and check the target name. |
| More than one complete target for the device | Keep one matching target in the model folder. |
| Model target does not match the device | Check the device SoC and download its target into a fresh model folder. |
| LMS activation fails | Check activation on the device before retrying. |
