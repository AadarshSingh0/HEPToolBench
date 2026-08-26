# HEPToolBench v1.2 native-interface local-response review package

This package contains the canonical stored responses from the 30 locally served model deployments used in HEPToolBench v1.2. It covers eight native-interface tasks, for 240 responses in total. API outputs are intentionally excluded.

Each task directory contains the complete model-facing prompt and 30 model-labelled raw response files. The response text is preserved exactly as stored and may contain malformed commands, Markdown, explanations, reasoning text, or other model-generated material. No response has been manually corrected.

Scores and failure labels come from the deterministic HEPToolBench scorers. Use the task directories to compare models on one request, and use [manifest.csv](manifest.csv) for provenance, hashes, scores, and verification status. [CHECKSUMS.sha256](CHECKSUMS.sha256) covers the package documentation, prompts, manifest, and responses.

| Task ID | Task | Responses | Directory |
|---|---|---:|---|
| `mg_basic_001` | Drell-Yan process card from template | 30 | [mg_basic_001/](mg_basic_001/) |
| `mg_basic_002` | Top-pair MadGraph card from free-form instruction | 30 | [mg_basic_002/](mg_basic_002/) |
| `mg_basic_003` | Higgs plus jet MadGraph card from free-form instruction | 30 | [mg_basic_003/](mg_basic_003/) |
| `mg_runcard_004` | MadGraph run-card settings for Drell-Yan with cuts | 30 | [mg_runcard_004/](mg_runcard_004/) |
| `mg_workflow_005` | MadGraph workflow script with Pythia8 and Delphes | 30 | [mg_workflow_005/](mg_workflow_005/) |
| `mg_debug_001` | Repair a broken Drell-Yan MadGraph card | 30 | [mg_debug_001/](mg_debug_001/) |
| `mg_debug_002` | Repair a broken top-pair MadGraph card | 30 | [mg_debug_002/](mg_debug_002/) |
| `mg_debug_003` | Repair Higgs plus jet MadGraph card | 30 | [mg_debug_003/](mg_debug_003/) |

## Additional repeated-generation experiment

This separate experiment uses one `qwen2.5-coder:7b` deployment, one identical top-pair prompt, and 100 generations to study run-to-run syntax variation. The 100 repeated generations are **not included** in the 240 canonical response count and are not additional models or benchmark tasks.

See the [additional repeated-generation experiment](additional_experiments/freeform_ttbar_qwen2_5_coder_7b_100/) for its exact prompt, preserved responses, provenance manifest, copied metadata, and textual/syntax audit files.
