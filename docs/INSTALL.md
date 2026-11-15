# Install

## Requirements

- Python 3.10+ (3.11–3.13 tested)
- Network access for PubChem / Fisher / TCI enrichment
- Optional: licensed HSPiP + `.sofx` data for D/P/H/RER
- Bundled `data/p2oasys_score_lookup.sqlite` for expert harvest + automatic TURI hazard scores (override with `P2OASYS_SCORE_LOOKUP_DB`)

## Steps

```bash
cd live-solvent-assess
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
# optional editable install:
pip install -e .
```

Without editable install, set `PYTHONPATH` to the repo root:

```bash
# Linux/macOS
export PYTHONPATH=/path/to/live-solvent-assess

# Windows (cmd)
set PYTHONPATH=C:\path\to\live-solvent-assess
```

(`scripts/run_doss_streamlit.py` sets `PYTHONPATH` to the repository root for you.)

## Run

```bash
python scripts/run_doss_streamlit.py
```

Browser: http://localhost:8502

## Data seeds

Seed CSVs and the score-lookup / harvest sqlite files ship under `data/`. Point `EXPERT_P2OASYS_CSV` / `P2OASYS_SCORE_LOOKUP_DB` / `HSPIP_DATA` at overrides as needed.

**TURI hazard scores:** six science categories scored 0–10; overall = max of those category maxima. Expert scores and automatic scores are labelled separately (not averaged).
