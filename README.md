# HEPToolBench

HEPToolBench evaluates language-model-assisted workflows for high-energy-
physics software and provides a deterministic local HEP agent.

## Beginner quick start

The benchmark supports Ubuntu/Debian Linux and macOS. The agent installer
supports Ubuntu/Debian x86_64 and macOS on Intel or Apple Silicon, including
MadGraph, Pythia8, ROOT, Delphes, and MadAnalysis 5.

```bash
git clone https://github.com/AadarshSingh0/HEPToolBench.git
cd HEPToolBench
chmod +x install.sh uninstall.sh run_agent.sh run_benchmark.sh
./install.sh
```

On macOS, the installer uses a pinned Miniforge environment containing
Python 3.11 and the required compiler tools. Current Ollama requires both
Apple Silicon and macOS 14 or newer. Intel Macs and older macOS releases can
run the complete HEP stack locally while using Ollama on another computer:

```bash
./install.sh --agent-only \
  --install-system-deps \
  --with-pythia8 \
  --with-delphes \
  --with-madanalysis5 \
  --deep-doctor \
  --ollama-host http://OTHER-COMPUTER:11434
```

On Ubuntu/Debian, or on Apple Silicon with macOS 14 or newer and Homebrew,
the complete local installation is:

```bash
./install.sh --full
```

`--full` ends with a model-free 10-event acceptance test through MadGraph,
Pythia8, DelphesHepMC2, and MadAnalysis5. This checks the actual LHE, HepMC,
Delphes ROOT, and MadAnalysis artifacts rather than only checking whether the
executables exist.

For Pythia8 on Apple Silicon, the installer builds HepMC2 and Pythia8 with the
same Apple Clang and native `libc++` runtime. This avoids both MadGraph's
pre-Apple-Silicon HepMC2 architecture check and a shutdown crash caused by
mixing Conda and native C++ runtimes. Intel macOS and Linux continue to use
their existing paths.

If Pythia8 was installed by an earlier HEPToolBench macOS package, rerunning
the following command automatically detects and replaces only that Pythia8
stack:

```bash
HEP_AGENT_TOOL_TIMEOUT_SECONDS=7200 \
  ./install.sh --agent-only --with-pythia8 --yes
```

After installation:

```bash
./run_agent.sh
```

opens the local HEP-agent web interface, while:

```bash
./run_benchmark.sh
```

opens a guided local-model benchmark menu.

To validate an installed HEP stack without contacting Ollama:

```bash
source local_hep_agent/.venv/bin/activate
python local_hep_agent/scripts/validate_full_stack.py
```

This fixed 20-event check verifies MadGraph event generation, Pythia8 HepMC
output, a Delphes ROOT file, and MadAnalysis reports and plots.

The same validation can be requested at installation time without using
`--full`:

```bash
./install.sh --agent-only \
  --with-pythia8 \
  --with-delphes \
  --with-madanalysis5 \
  --validate-full-stack
```

To remove the isolated environment, Miniforge, MadGraph, Pythia8, ROOT,
Delphes, MadAnalysis 5, and generated machine configuration:

```bash
./uninstall.sh
```

Results are preserved by default. Use `./uninstall.sh --purge-results` to
also delete locally generated agent and benchmark runs. Ollama, other models,
and operating-system packages are never removed implicitly; one explicitly
named local model can be removed with `--remove-model NAME`.

The benchmark creates a separate folder for every invocation and automatically
writes:

```text
local_llm_benchmark/runs/<run_id>/individual_scores.csv
local_llm_benchmark/runs/<run_id>/score_matrix.csv
local_llm_benchmark/runs/<run_id>/summary_by_model.csv
local_llm_benchmark/runs/<run_id>/summary_by_task.csv
local_llm_benchmark/results/all_runs_long.csv
```

Existing runs are never overwritten. Interrupted runs can be resumed.

## Repository structure

### `local_llm_benchmark/`

The frozen HEPToolBench v1.2 suite, including 31 tasks, validators, local and
cloud runners, result-analysis utilities, and the beginner benchmark launcher.

### `local_hep_agent/`

A deterministic local HEP agent that converts natural-language requests into
validated and executable workflows with optional MadGraph, Pythia8, Delphes,
and MadAnalysis 5 stages.

## Advanced examples

Run all installed Ollama models on all 31 tasks:

```bash
./run_benchmark.sh \
  --models all-installed \
  --suite full31 \
  --yes
```

Use a remote Ollama server:

```bash
./run_benchmark.sh \
  --ollama-host http://HOST:11434 \
  --models llama3:8b qwen3:8b \
  --suite full31 \
  --yes
```

Resume an interrupted run:

```bash
./run_benchmark.sh --resume RUN_ID
```

See `local_llm_benchmark/docs/RUN_LOCAL_MODELS.md` for the full benchmark
guide and `local_hep_agent/docs/INSTALL_FOR_EVERYONE.md` for agent installation
details.

## Project status

This repository is under active research development. Generated event files,
local benchmark runs, machine-specific paths, runtime logs, secrets, and model
weights are not tracked in Git.
