# MSSQ

Research materials for **MSSQ: Benchmarking Modal Solution-Space Reasoning in Large Language Models**.

**Authors:** Chenghang Yu, Cong Wang, and Jun Yu  
**Affiliation:** Department of Automation, University of Science and Technology of China

MSSQ evaluates reasoning about the solution spaces of constraint problems expressed in Chinese and English. For each problem and proposition, four independent prompts request necessity and possibility judgments, a witness, and a counterexample. Exact solution sets and deterministic verification connect these outputs at the instance level.

## Download

Download **MSSQ_materials_20261016.zip** from this repository's **Releases** section and extract it. This is the complete research package; GitHub's automatically generated source archives do not contain the response data.

The package contains:

- 576 bilingual prompts covering 24 CSPs, with formal problems and complete solution sets.
- Adopted responses for the main evaluation (4,608), repeated sampling (768), joint prompting (768), feedback experiment (111), and candidate experiment (240).
- Answer-extraction records, deterministic validators, configuration records, and reference results.
- Offline analyses, including CSP bootstrap intervals, assignment-direction checks, and candidate sensitivity analyses.
- A bilingual worked example and a separate programmatic text-constraint check.

## Reproduce

Use Python 3.11 or later. In the extracted `MSSQ_materials/MSSQ_reproduction` directory, run:

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --output ../MSSQ_recomputed
```

Choose a new output directory. The calculation runs offline, checks file hashes, replays scoring, and compares the results with the supplied references. A successful run writes `verification.json` with `"success": true` and `"bootstrap_replayed": true`.

See the README files inside the package for data fields, answer-extraction decisions, and the separate text-constraint check. The response dataset contains adopted responses, rather than a complete log of all collection attempts; its resource measurements describe those adopted responses.
