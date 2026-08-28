# Scorer contract corrections

## `mg_basic_002`

The v1.2 native prompt requests a complete top-pair process card but does not
name the MadGraph output directory. The v1.2.1 scorer therefore accepts a valid
`output <directory>` command, including relative or absolute directory names
and the optional `-f` flag. A missing output command, an option without a
directory, and every unrelated process/beam/format requirement still fail as
before.

`mg_debug_002` delegates to the basic scorer. Its wrapper now explicitly
requests the historical reference-name behavior so this patch does not alter
the debugging task. This compatibility wiring is a dependency isolation, not a
change to the debug contract.

## `mg_workflow_005`

The prompt states the process, output directory, event count, seed, beam
energies, proton definition, Pythia8, Delphes, and MadSpin state. It does not
request `analysis=OFF` or a `done` marker. Their presence remains visible in
diagnostic checks but is not pass-critical and cannot reduce score. The
historical 0.02 + 0.02 allocation is represented as contract-neutral credit;
all prompt-stated requirements retain their original weights and enforcement.

Focused regression tests are in
`local_llm_benchmark/tests/test_v121_contract_corrections.py`.
