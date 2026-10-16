# Text–constraint checks

Coverage: 576 final prompts, their numbered constraints, domains, counting groups, proposition expressions and four request directions. The expressions are parsed from the prompt sentences before comparison with formal records. This is an LLM-assisted programmatic check, not independent human review or a claim of complete narrative equivalence.

`prompts_only.jsonl` contains the source prompts; `text_interpretations.jsonl` retains sentences and interpreted expressions. `alignment_rows.jsonl` reports comparisons; `interpretation_validation.json` contains logical-boundary checks and stored-solution replay.

To rerun in a working copy (the scripts refresh their output files):

```sh
python -B parse_prompts.py
python -B compare_formal.py
python -B verify_interpretations.py
```

The parser imports no generator, renderer or scoring verifier. The comparison adapter reads `../formal/`, `../configs/` and `../candidate/`. Stored-solution replay checks proposition support without re-enumerating the solution space.
