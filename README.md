# Live Solvent Assess

Live solvent safety and performance evaluator for discovery workflows: enter a CAS number and get a structured assessment (physchem, GHS/NFPA when available, TURI hazard scores, optional SDS enrichment and Hansen parameters).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Research software from **TURI / UMass Lowell**. This repository’s code is MIT-licensed. Third-party tools (HSPiP, vendor sites) stay optional and are not redistributed here.

There is currently **no GitHub Actions workflow** in this repository, so there is no CI badge.

<!-- TODO: add a Capabilities (or pytest) workflow like turi-safe-chem-db, then add that badge. -->

## What it does

| Capability | Notes |
|------------|--------|
| CAS → live assessment | Streamlit UI on port **8502** |
| PubChem | Identity, physchem, GHS, NFPA baseline |
| TURI hazard scores | Six science categories (0–10); overall = max of those category maxima. Expert CSV overlay plus bundled lookup SQLite (expert scores and automatic scores, labelled separately) |
| Fisher / TCI SDS | Optional on-demand enrichment (best-effort; never invents values) |
| HSPiP | Optional local `.sofx` / licensed CLI (not shipped) |
| CSV export | DoSS-compatible column layout |

This public tree is a shareable carve-out of the DoSS on-demand app. Related repository: [turi-safe-chem-db](https://github.com/glsalierno/turi-safe-chem-db) (same family, public).

## Quick start

Python **≥ 3.10** (`requires-python` in `pyproject.toml`; 3.11–3.13 tested per `docs/INSTALL.md`).

```bash
git clone https://github.com/glsalierno/live-solvent-assess.git
cd live-solvent-assess
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
# optional: pip install -e .

python scripts/run_doss_streamlit.py
```

Open http://localhost:8502

The launcher sets `PYTHONPATH` to this repository’s root and runs `apps/doss_ondemand/app.py` on port 8502. If you skip `pip install -e .` and call Streamlit yourself, set `PYTHONPATH` to **this** repository’s root (not a sister checkout).

Developer extras: `pip install -r requirements-dev.txt` (pytest, vulture). With the repo root on `PYTHONPATH` (or after `pip install -e .`), `pytest` runs the smoke/lookup suite (`tests/test_p2oasys_lookup.py`, `tests/test_smoke_imports.py`; 5 tests passed in this environment).

## Example

**Demo CAS: `67-64-1` (acetone)** — present in the curated expert overlay (`data/priority_expert_p2oasys_scores.csv`) and covered by the bundled lookup SQLite. Lookup resolves it with source `expert` / detail `expert_csv` (see `tests/test_p2oasys_lookup.py`).

1. Start the app as above.
2. Enter `67-64-1`.
3. Expect identity / GHS / physchem from PubChem when the network is up, and a TURI hazard score with source labelled `expert` (not averaged with automatic scores).
4. Missing evidence stays blank or is an explicit gap such as `needs_HSPiP`. Values are never invented. Glove HSP flags, when shown, are labelled as HSP-predicted (not breakthrough time).

<!-- TODO: paste a short (non-invented) CSV export snippet from a real UI run when available. -->

## Configuration

Current technical identifiers (unchanged in this documentation pass; renaming is a separate follow-up):

| Variable or path | Purpose |
|------------------|---------|
| `P2OASYS_SCORE_LOOKUP_DB` | Override the bundled score-lookup SQLite |
| `EXPERT_P2OASYS_CSV` | Override the curated expert overlay CSV |
| `HSPIP_PATH` / `HSPIP_DATA` | Local HSPiP executable and `.sofx` data (the in-app path prompt also works) |
| `data/priority_expert_p2oasys_scores.csv` | Curated expert overlay |
| `data/p2oasys_score_lookup.sqlite` | Bundled harvest lookup (~1,250 CAS) |
| `data/fisher_catalog_by_cas.csv` | SDS part-number lookup seed |

See [docs/INSTALL.md](docs/INSTALL.md) and [docs/HSPiP_CLI.md](docs/HSPiP_CLI.md).

## Outputs

- On-screen structured assessment for a CAS number.
- CSV in a DoSS-compatible column layout (includes score and score-source columns).

**Source rules:** values are never invented. Missing evidence stays blank or is flagged (`needs_HSPiP` and similar). Automatic scores are labelled separately from expert scores (source column: `expert` | `auto` | `-`); they are not averaged. Predicted values that appear in the UI (for example HSP-predicted glove flags) are flagged as predicted.

## Limits

- HSPiP is optional and not shipped; you must install and license it yourself.
- Fisher/TCI enrichment depends on the network and may be blocked.
- PubChem is rate-limited.
- This is research software, not a regulatory determination.
- Automated tests are currently a small smoke/lookup set; there is no CI badge yet.

## Citation

If you use this tooling in publications or internal reports, please acknowledge:

> Toxics Use Reduction Institute (TURI), University of Massachusetts Lowell — Live Solvent Assess.

See [CITATION.cff](CITATION.cff). <!-- TODO: add a Zenodo DOI if archived. -->

Maintainer: [glsalierno](https://github.com/glsalierno).

## License

MIT for this repository’s code — see [LICENSE](LICENSE). PubChem, supplier SDS sites, and HSPiP have their own terms.
