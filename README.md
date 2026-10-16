# MSSQ

Research materials for **MSSQ: Benchmarking Modal Solution-Space Reasoning in Large Language Models**.

**Authors:** Chenghang Yu, Cong Wang, and Jun Yu  
**Affiliation:** Department of Automation, University of Science and Technology of China

MSSQ evaluates reasoning about the solution spaces of constraint problems expressed in Chinese and English. For each problem and proposition, four independent prompts request necessity and possibility judgments, a witness, and a counterexample. Exact solution sets and deterministic verification connect these outputs at the instance level.

## Download the complete research package

**[Download MSSQ_materials_20261016.zip](https://github.com/KalSammelYCH/MSSQ/releases/download/v20261016/MSSQ_materials_20261016.zip)** (approximately 274 MB).

The [versioned release](https://github.com/KalSammelYCH/MSSQ/releases/tag/v20261016) also provides [SHA256SUMS.txt](https://github.com/KalSammelYCH/MSSQ/releases/download/v20261016/SHA256SUMS.txt) for checking the archive's integrity.

The complete package contains:

- 576 bilingual prompts covering 24 CSPs, with formal problems and complete solution sets.
- Adopted responses for the main evaluation (4,608), repeated sampling (768), joint prompting (768), feedback experiment (111), and candidate experiment (240).
- Answer-extraction records, deterministic validators, configuration records, and reference results.
- Offline analyses, including CSP bootstrap intervals, assignment-direction checks, and candidate sensitivity analyses.
- A bilingual worked example and a separate programmatic text-constraint check.

## Browse the code and examples

This repository exposes selected files from the complete release for online inspection. Copied code and data are unchanged from version 2026-10-16.

| Path | Contents |
|---|---|
| [reproduce.py](MSSQ_reproduction/reproduce.py) | Offline reproduction entry point |
| [scoring.py](MSSQ_reproduction/scoring.py) | Deterministic construction scoring |
| [formal/](MSSQ_reproduction/formal/) | CSPs, propositions, and complete solution sets |
| [inputs/](MSSQ_reproduction/inputs/) | Prompt index, response contracts, and recorded extraction decisions |
| [prompts_only.jsonl](MSSQ_reproduction/semantic_checks/prompts_only.jsonl) | Texts of the 576 prompts |
| [candidate/](MSSQ_reproduction/candidate/) | Candidate conditions and associated results |
| [reference/](MSSQ_reproduction/reference/) | Reference results for verification |
| [bilingual_example/](MSSQ_supplementary_materials/bilingual_example/) | Worked example in Chinese and English |
| [requirements.txt](MSSQ_reproduction/requirements.txt) | Python dependencies |

**For complete reproduction, use the release archive linked above.** A clone or GitHub's automatic source ZIP contains this browsing subset. It omits the model-response and streaming files, per-response configuration records, individual prompt files, and some generated text-constraint-check records. The original `manifest.json` is retained as the checksum manifest for the complete release; it is not a manifest of this subset.

## Reproduce the results

Download and extract the complete release archive. Use Python 3.11 or later. From the extracted `MSSQ_materials/MSSQ_reproduction` directory, run:

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --output ../MSSQ_recomputed
```

Choose a new output directory. The calculation runs offline, checks file hashes, replays scoring, and compares the results with the supplied references. A successful run writes `verification.json` with `"success": true` and `"bootstrap_replayed": true`.

See the [reproduction guide](MSSQ_reproduction/README.md) for data fields and answer-extraction decisions. The [text-constraint check](MSSQ_reproduction/semantic_checks/README.md) has separate replay commands; run these in a working copy of the complete release. The response dataset contains adopted responses, rather than a complete log of all collection attempts; its resource measurements describe those adopted responses.
