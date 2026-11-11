# Smart System Costing

A skill for turning client material (planning documents, floor plans, requirement lists) into a **deliverable trio** — proposal DOCX, cost estimate XLSX, pitch PPTX — whose numbers actually reconcile.

It does not help you write prettier prose. It solves four things that break projects:

1. **Where do the quantities come from** (density assumptions → counts → capacity formulas)
2. **How is the price built** (Chinese BOQ pricing: GB/T 50500-2024 fee chain)
3. **Where is the boundary** (what's excluded, who owns what, what triggers a change order)
4. **Why is the other quote half the price** (same-scope normalization, not list-price comparison)

> Scope note: the pricing rules follow China's GB/T 50500-2024. Unit rates in `references/05` are Shandong-region experience values for 2026. For other regions, apply the coefficient table — and always re-quote the top 20% of line items before submitting.

## What's inside

| File | Purpose |
|---|---|
| `SKILL.md` | Five iron rules, four modes, six gates, stop rules, output contract |
| `references/01` | Unit-density assumptions, storage/bandwidth/UPS/fiber formulas, 28-subsystem skeleton |
| `references/02` | Fee chain, baseline example, five cross-checks, control amount, options, delivery layers |
| `references/03` | Trio structure, Office automation, eight Windows pitfalls, client-vs-internal drafting |
| `references/04` | Same-scope normalization (÷1.22), cut-item mapping, cost-rate table, margin model |
| `references/05` | Unit-rate baseline, region coefficients, year indices, when to re-quote |
| `scripts/costing_check.py` | Recompute the fee chain, 8 checks, reads a BOQ CSV directly |
| `scripts/consistency_check.py` | Amount consistency across DOCX/XLSX/PPTX + placeholder residue |
| `scripts/capacity.py` | Storage / bandwidth / UPS / fiber calculations with boundary notes |
| `scripts/margin_model.py` | Gross and net margin with three sensitivity scenarios |
| `scripts/split_layers.py` | Split a BOQ into "must-be-ready-for-production" vs "operational extras" |
| `scripts/reconcile.py` | Two-quote reconciliation: normalize, per-category diff, top-3 drivers |
| `scripts/deliverable_qc.py` | TOC freshness, blank tail pages, tables split across pages, PPTX shape overflow |
| `templates/` | Param sheets, option switches, internal margin memo, `docx_kit.py` (keeps tables on one page) |
| `tests/` | 14 regression tests, zero external dependencies |
| `tools/gitsafe/` | Pre-commit secret blocking, full-history scan, CI job |

## Quick start

```bash
# 1. Sanity check the environment
python scripts/costing_check.py --selftest

# 2. Price a BOQ directly
python scripts/costing_check.py --boq examples/items.csv --json out.json

# 3. Before delivery: numbers match, no placeholders left
python scripts/consistency_check.py --docx proposal.docx --xlsx estimate.xlsx --pptx deck.pptx \
    --expect 1982.85,1412.37,1109.57

# 4. Layout and structure sanity
python scripts/deliverable_qc.py --docx proposal.docx --pdf proposal.pdf --pptx deck.pptx

# 5. Internal only: how much do we actually make
python scripts/margin_model.py --params examples/margin.csv

# 6. Regression
python -m unittest discover -s tests -v
```

Baseline (keep it passing before trusting your own numbers):

```
equipment 750.61 / material 290.15 / software 203.84 / service 167.77
→ direct 1412.37 → install 145.71 / commissioning 62.23 / management 48.61
→ work items 1668.92 → preliminaries 66.76 / contingency 83.45
→ pre-tax 1819.12 → VAT 163.72 → gross 1982.84
```

## Why not just reuse an existing skill

| Existing | Strong at | Missing |
|---|---|---|
| Bid-document skills | requirement ledgers, zero-invention, commitment tiers | explicitly out of scope for cost estimation and margin |
| Presales skill suites | proposal pipelines, PPTX generation | no quantities, no fee chain |
| Construction skill packs (221) | BIM analysis, cost estimation, document control | IFC/Western conventions, no Chinese BOQ pricing |

This repo fills that gap: **the layer where quantities become money, and money becomes a defensible document.**

## License

MIT.