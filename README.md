# Live Solvent Assess

Live solvent **safety and performance** evaluator for discovery workflows.

Enter a CAS number → get a structured assessment (physchem, GHS/NFPA when available, P2OASys hazard scores, optional SDS enrichment and Hansen parameters). Exports remain compatible with classic DoSS-shaped spreadsheets where useful.

Research software from **TURI / UMass Lowell**. MIT-licensed code; third-party tools (HSPiP, vendor sites) stay optional and are not redistributed here.

## Quick start

```bash
git clone https://github.com/glsalierno/live-solvent-assess.git
cd live-solvent-assess
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_doss_streamlit.py
```

Open http://localhost:8502

## What it does

| Capability | Notes |
|------------|--------|
| CAS → live assessment | Streamlit UI |
| PubChem | Identity, physchem, GHS, NFPA baseline |
| P2OASys scores | Expert CSV overlay + bundled lookup sqlite (expert/auto) |
| Fisher / TCI SDS | Optional on-demand enrichment (best-effort; never invents values) |
| HSPiP | Optional local `.sofx` / licensed CLI (not shipped) |
| CSV export | DoSS-compatible column layout |

## Data included

- `data/priority_expert_p2oasys_scores.csv` — curated expert overlay
- `data/p2oasys_score_lookup.sqlite` — bundled harvest lookup for broader CAS coverage
- Small Fisher catalog seed for SDS part numbers

Values are never invented. Missing evidence stays blank / `needs_HSPiP` / similar explicit gaps.

## Optional local tools

- **HSPiP:** install yourself; set `HSPIP_PATH` / `HSPIP_DATA` or use the in-app path prompt.
- **P2OASys DB override:** `P2OASYS_SCORE_LOOKUP_DB`

See `docs/INSTALL.md` and `docs/HSPiP_CLI.md`.

## License & collaboration

MIT for this repository's code — see [LICENSE](LICENSE). HSPiP software, CLI licenses, and `.sofx` data libraries are NOT covered by this MIT license. Obtain them separately from Hansen Solubility / HSPiP. See [NOTICE.md](NOTICE.md). PubChem and supplier SDS sites have their own terms.

Built at TURI / UMass Lowell. Collaboration inquiries via the maintainer's GitHub profile.
