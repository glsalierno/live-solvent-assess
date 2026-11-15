# data/

Small **seed** files and bundled hazard-score sqlite DBs:

| File | Role |
|------|------|
| `priority_cas_list.txt` | Priority solvent CAS list |
| `priority_expert_p2oasys_scores.csv` | 62-set expert Auto6 maxes (CSV overlay; wins over sqlite) |
| `p2oasys_score_lookup.sqlite` | Harvest expert + auto Auto6 / subcategory lookup (~1,250 CAS) |
| `p2oasys_harvest.sqlite` | Canonical harvest pages 1–101 split (single-CAS chosen; mixtures parked) |
| `fisher_catalog_by_cas.csv` | Fisher part numbers / product URLs |
| `priority_solvents_queue.csv` | Queue metadata for batch runs |

**TURI hazard scores:** six science categories (0–10); overall = max of category maxima. Expert scores and automatic scores are stored/labelled separately.

## Do not commit here

- Raw harvest page CSVs / GHaz* trees
- `*.sofx`, HSPiP binaries
- Runtime SQLite caches (`cache/*.db`)
- Batch report CSVs with hundreds of rows (keep locally)

Override paths with `EXPERT_P2OASYS_CSV`, `P2OASYS_SCORE_LOOKUP_DB`, `HSPIP_DATA`.
