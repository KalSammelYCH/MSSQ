# MSSQ reproduction materials

This archive contains the inputs and adopted answers underlying the manuscript. It supports offline score verification and reconstruction of the reported analyses.

## Run

Use Python 3.11 or later with NumPy and SciPy installed. Run from this folder, selecting a new output folder outside it:

```sh
python -B reproduce.py --output ../MSSQ_recomputed
```

The default run checks package hashes, recounts the stored solution sets, replays answer extraction with recorded adjudications, verifies constructions, and reconstructs MAIN, S-01, S-02, S-05 and candidate results. It also computes the exact CSP-block re-pairing reference, 10,000-draw CSP intervals and leave-one-CSP summaries. `verification.json` is written only after all checks pass. `--skip-bootstrap` omits interval and extended sensitivity calculations.

## Contents

| Path | Contents |
|---|---|
| `inputs/` | 576 bilingual task prompts, prompt index and response contracts |
| `formal/` | CSPs, propositions and complete stored solution sets |
| `responses/` | Adopted MAIN (4,608), S-01 (768), S-02 (768), S-05 (111) and candidate (240) records |
| `streams/` | Adopted streaming responses linked from the response records |
| `configuration/` | Per-response MAIN configuration index and configuration records |
| `candidate/` | Supplied assignments, paired results, candidate-check errors and explicit constructions |
| `reference/` | Manuscript analysis results used for verification |
| `scoring.py`, `first_family_other_models_formal/` | Deterministic construction verifiers |
| `extraction_replay.py` and related modules | Programmatic extraction and recorded case decisions |

Each response record links an item, the returned text and its extracted answer. Recorded case decisions remain inspectable alongside the text; the verifier determines correctness after extraction. Missing or unfinished answers remain in their task denominators. NONE is a nonexistence claim, not a construction. Resource fields describe adopted responses; reported reasoning-token counts are preserved, including zero or unavailable values. The package is an adopted-response dataset, not a complete attempt log. Machine-local paths and HTTP response headers are omitted, and collection bookkeeping labels are normalized; response texts, prompts, generation parameters, usage and answer-extraction decisions are preserved.

The re-pairing range is an exact reference distribution over the six within-stratum CSP mappings. It is distinct from the CSP bootstrap intervals. The stored Gold sets are recounted; generating new CSPs and rerunning model APIs are outside this offline entry point.

## Version and supplementary checks

Release 2026-10-16 accompanies the manuscript and supplementary PDF, supplied separately. The default entry point also writes `additional_checks/assignment_direction.json` (Supplement B-B) and `additional_checks/candidate_leave_one_out.json` (Supplement E-C), including the six single-question omissions and joint omission of E02/E03. Reference results are supplied for comparison.

`semantic_checks/README.md` describes the separate text–constraint check and its replay commands. `supplementary_results/` contains the solution-count and Gold-modality tables with field definitions. `configuration/item_configuration_index.csv` links MAIN tasks to settings; response records preserve available returned identifiers and timestamps.
