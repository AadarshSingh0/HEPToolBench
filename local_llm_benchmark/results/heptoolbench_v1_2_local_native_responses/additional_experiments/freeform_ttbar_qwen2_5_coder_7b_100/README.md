# Additional experiment: 100 repeated Qwen2.5-Coder 7B generations

This is a separate repeated-generation experiment, not part of the 240 canonical native-interface responses. It uses one `qwen2.5-coder:7b` deployment to answer one identical top-pair request 100 times. It studies run-to-run syntax variation for that one request; these are not 100 models or 100 benchmark tasks.

- Model: `qwen2.5-coder:7b`
- Generations: 100
- Prompt: [prompt.txt](prompt.txt)
- Provenance: [manifest.csv](manifest.csv), with source records identified as `manifest.jsonl` lines.
- Copied metadata: [experiment_config.json](experiment_config.json), [model_metadata.json](model_metadata.json).
- Deterministic/textual audits: [textual_classification.csv](textual_classification.csv), [detailed_syntax_audit.csv](detailed_syntax_audit.csv), and [near_miss_report.txt](near_miss_report.txt).

The prompt is the complete preserved experiment request. All 100 Ollama records have the same model and identical prompt-token prefixes; the prompt text is preserved in `experiment_config.json` and saved verbatim as `prompt.txt`. Responses are preserved exactly as stored, with no correction or normalization. Classifications come from the accompanying deterministic/textual audit. The copied `model_metadata.json` retains the model metadata while generalizing one machine-local model-blob path as `<LOCAL_MODEL_BLOB_PATH>`; this does not alter any response.

| Generation | Classification | Response |
|---:|---|---|
| 1 | `unrecognized_process_syntax` | [response_001.txt](responses/response_001.txt) |
| 2 | `unrecognized_process_syntax` | [response_002.txt](responses/response_002.txt) |
| 3 | `textually_correct_antitop` | [response_003.txt](responses/response_003.txt) |
| 4 | `unrecognized_process_syntax` | [response_004.txt](responses/response_004.txt) |
| 5 | `other_antitop_token` | [response_005.txt](responses/response_005.txt) |
| 6 | `invalid_antitop_name` | [response_006.txt](responses/response_006.txt) |
| 7 | `missing_generate_command` | [response_007.txt](responses/response_007.txt) |
| 8 | `unrecognized_process_syntax` | [response_008.txt](responses/response_008.txt) |
| 9 | `invalid_antitop_name` | [response_009.txt](responses/response_009.txt) |
| 10 | `unrecognized_process_syntax` | [response_010.txt](responses/response_010.txt) |
| 11 | `unrecognized_process_syntax` | [response_011.txt](responses/response_011.txt) |
| 12 | `invalid_antitop_name` | [response_012.txt](responses/response_012.txt) |
| 13 | `invalid_antitop_name` | [response_013.txt](responses/response_013.txt) |
| 14 | `textually_correct_antitop` | [response_014.txt](responses/response_014.txt) |
| 15 | `textually_correct_antitop` | [response_015.txt](responses/response_015.txt) |
| 16 | `textually_correct_antitop` | [response_016.txt](responses/response_016.txt) |
| 17 | `missing_generate_command` | [response_017.txt](responses/response_017.txt) |
| 18 | `unrecognized_process_syntax` | [response_018.txt](responses/response_018.txt) |
| 19 | `missing_generate_command` | [response_019.txt](responses/response_019.txt) |
| 20 | `textually_correct_antitop` | [response_020.txt](responses/response_020.txt) |
| 21 | `other_antitop_token` | [response_021.txt](responses/response_021.txt) |
| 22 | `missing_generate_command` | [response_022.txt](responses/response_022.txt) |
| 23 | `missing_generate_command` | [response_023.txt](responses/response_023.txt) |
| 24 | `other_antitop_token` | [response_024.txt](responses/response_024.txt) |
| 25 | `textually_correct_antitop` | [response_025.txt](responses/response_025.txt) |
| 26 | `unrecognized_process_syntax` | [response_026.txt](responses/response_026.txt) |
| 27 | `invalid_antitop_name` | [response_027.txt](responses/response_027.txt) |
| 28 | `invalid_antitop_name` | [response_028.txt](responses/response_028.txt) |
| 29 | `unrecognized_process_syntax` | [response_029.txt](responses/response_029.txt) |
| 30 | `invalid_antitop_name` | [response_030.txt](responses/response_030.txt) |
| 31 | `unrecognized_process_syntax` | [response_031.txt](responses/response_031.txt) |
| 32 | `unrecognized_process_syntax` | [response_032.txt](responses/response_032.txt) |
| 33 | `missing_generate_command` | [response_033.txt](responses/response_033.txt) |
| 34 | `invalid_antitop_name` | [response_034.txt](responses/response_034.txt) |
| 35 | `invalid_antitop_name` | [response_035.txt](responses/response_035.txt) |
| 36 | `missing_generate_command` | [response_036.txt](responses/response_036.txt) |
| 37 | `textually_correct_antitop` | [response_037.txt](responses/response_037.txt) |
| 38 | `unrecognized_process_syntax` | [response_038.txt](responses/response_038.txt) |
| 39 | `unrecognized_process_syntax` | [response_039.txt](responses/response_039.txt) |
| 40 | `missing_generate_command` | [response_040.txt](responses/response_040.txt) |
| 41 | `invalid_antitop_name` | [response_041.txt](responses/response_041.txt) |
| 42 | `missing_generate_command` | [response_042.txt](responses/response_042.txt) |
| 43 | `textually_correct_antitop` | [response_043.txt](responses/response_043.txt) |
| 44 | `textually_correct_antitop` | [response_044.txt](responses/response_044.txt) |
| 45 | `other_antitop_token` | [response_045.txt](responses/response_045.txt) |
| 46 | `unrecognized_process_syntax` | [response_046.txt](responses/response_046.txt) |
| 47 | `unrecognized_process_syntax` | [response_047.txt](responses/response_047.txt) |
| 48 | `missing_generate_command` | [response_048.txt](responses/response_048.txt) |
| 49 | `unrecognized_process_syntax` | [response_049.txt](responses/response_049.txt) |
| 50 | `unrecognized_process_syntax` | [response_050.txt](responses/response_050.txt) |
| 51 | `missing_generate_command` | [response_051.txt](responses/response_051.txt) |
| 52 | `invalid_antitop_name` | [response_052.txt](responses/response_052.txt) |
| 53 | `textually_correct_antitop` | [response_053.txt](responses/response_053.txt) |
| 54 | `textually_correct_antitop` | [response_054.txt](responses/response_054.txt) |
| 55 | `other_antitop_token` | [response_055.txt](responses/response_055.txt) |
| 56 | `textually_correct_antitop` | [response_056.txt](responses/response_056.txt) |
| 57 | `invalid_antitop_name` | [response_057.txt](responses/response_057.txt) |
| 58 | `invalid_antitop_name` | [response_058.txt](responses/response_058.txt) |
| 59 | `unrecognized_process_syntax` | [response_059.txt](responses/response_059.txt) |
| 60 | `missing_generate_command` | [response_060.txt](responses/response_060.txt) |
| 61 | `invalid_antitop_name` | [response_061.txt](responses/response_061.txt) |
| 62 | `unrecognized_process_syntax` | [response_062.txt](responses/response_062.txt) |
| 63 | `unrecognized_process_syntax` | [response_063.txt](responses/response_063.txt) |
| 64 | `unrecognized_process_syntax` | [response_064.txt](responses/response_064.txt) |
| 65 | `invalid_antitop_name` | [response_065.txt](responses/response_065.txt) |
| 66 | `textually_correct_antitop` | [response_066.txt](responses/response_066.txt) |
| 67 | `unrecognized_process_syntax` | [response_067.txt](responses/response_067.txt) |
| 68 | `textually_correct_antitop` | [response_068.txt](responses/response_068.txt) |
| 69 | `unrecognized_process_syntax` | [response_069.txt](responses/response_069.txt) |
| 70 | `textually_correct_antitop` | [response_070.txt](responses/response_070.txt) |
| 71 | `missing_generate_command` | [response_071.txt](responses/response_071.txt) |
| 72 | `invalid_antitop_name` | [response_072.txt](responses/response_072.txt) |
| 73 | `textually_correct_antitop` | [response_073.txt](responses/response_073.txt) |
| 74 | `textually_correct_antitop` | [response_074.txt](responses/response_074.txt) |
| 75 | `invalid_antitop_name` | [response_075.txt](responses/response_075.txt) |
| 76 | `missing_generate_command` | [response_076.txt](responses/response_076.txt) |
| 77 | `unrecognized_process_syntax` | [response_077.txt](responses/response_077.txt) |
| 78 | `invalid_antitop_name` | [response_078.txt](responses/response_078.txt) |
| 79 | `missing_generate_command` | [response_079.txt](responses/response_079.txt) |
| 80 | `unrecognized_process_syntax` | [response_080.txt](responses/response_080.txt) |
| 81 | `missing_generate_command` | [response_081.txt](responses/response_081.txt) |
| 82 | `missing_generate_command` | [response_082.txt](responses/response_082.txt) |
| 83 | `unrecognized_process_syntax` | [response_083.txt](responses/response_083.txt) |
| 84 | `textually_correct_antitop` | [response_084.txt](responses/response_084.txt) |
| 85 | `textually_correct_antitop` | [response_085.txt](responses/response_085.txt) |
| 86 | `unrecognized_process_syntax` | [response_086.txt](responses/response_086.txt) |
| 87 | `invalid_antitop_name` | [response_087.txt](responses/response_087.txt) |
| 88 | `textually_correct_antitop` | [response_088.txt](responses/response_088.txt) |
| 89 | `textually_correct_antitop` | [response_089.txt](responses/response_089.txt) |
| 90 | `textually_correct_antitop` | [response_090.txt](responses/response_090.txt) |
| 91 | `textually_correct_antitop` | [response_091.txt](responses/response_091.txt) |
| 92 | `invalid_antitop_name` | [response_092.txt](responses/response_092.txt) |
| 93 | `invalid_antitop_name` | [response_093.txt](responses/response_093.txt) |
| 94 | `unrecognized_process_syntax` | [response_094.txt](responses/response_094.txt) |
| 95 | `invalid_antitop_name` | [response_095.txt](responses/response_095.txt) |
| 96 | `invalid_antitop_name` | [response_096.txt](responses/response_096.txt) |
| 97 | `textually_correct_antitop` | [response_097.txt](responses/response_097.txt) |
| 98 | `unrecognized_process_syntax` | [response_098.txt](responses/response_098.txt) |
| 99 | `missing_generate_command` | [response_099.txt](responses/response_099.txt) |
| 100 | `unrecognized_process_syntax` | [response_100.txt](responses/response_100.txt) |
