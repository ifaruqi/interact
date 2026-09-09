# interact.

`interact.` is a static drug interaction checker prototype built for quick medication-combination lookup in a browser.

It supports two input styles:

- Indonesian product or brand names from BPOM product data, such as `Sanmol` or `Teosal`
- Recognized ingredient names mapped to DDInter ingredients, such as `Acetaminophen`, `Salbutamol`, or `Theophylline`

The public GitHub Pages app is served from `docs/`.

## Live Site

GitHub Pages:

```text
https://ifaruqi.github.io/interact/
```

If the URL was enabled recently, GitHub Pages may take a few minutes to finish its first build.

## What The App Does

1. Loads a local browser-ready drug/product index.
2. Lets the user choose two or more medicines.
3. Resolves BPOM product names into mapped ingredients when possible.
4. Checks all unique ingredient pairs against the local interaction dataset.
5. Ranks results so higher-attention findings appear first.
6. Shows source labels for severity and mechanism fields separately.

The app is fully static. It does not send medicine names to a server and does not require a backend API.

## Current Dataset

Current generated browser dataset:

- Interaction pairs: `214,987`
- DDInter/MecDDI drug concepts: `1,959`
- BPOM product rows: `23,481`
- Interaction shards: `1,885`

Source files used by the local build:

- `ddinter_merged.csv`
- `APP - Master Produk Komoditi Obat-2026-09-08.csv`
- `APP_Master_Produk_DDInter_Mapped_2026-09-08.csv`
- `manual_ddinter_dictionary_2026-09-09.csv`

The raw CSV files are intentionally not committed to the repository. The generated static JSON files under `docs/data/` are committed so GitHub Pages can run without a backend.

## Data Provenance

Severity data:

- Source: DDInter bulk CSV download from `ddinter2.scbdd.com/download/`
- Coverage used here: `160,235` drug-drug pairs across 8 ATC-category files: A, B, D, H, L, P, R, V
- Field attribution: `severity_source = DDInter`

Mechanism/explanation data:

- Source: MecDDI, accessed via the `acai233/pkag-ddi` HuggingFace dataset file `DDInter2_0_mecddi.csv`
- Coverage used here: `152,887` drug-drug pairs
- Field attribution: `mechanism_source = MecDDI`

Merged interaction dataset:

- Total unique pairs: `214,987`
- Severity and mechanism: `98,135`
- Severity only: `62,100`
- Mechanism only: `54,752`

Important interpretation note: this project should be described as using the DDInter bulk-download severity export plus MecDDI mechanism text. It should not be described as complete DDInter 2.0 coverage.

## BPOM Product Mapping

BPOM product composition text is regulatory free text, not a standardized ingredient list. The mapping pipeline handles common issues such as:

- HTML line breaks like `<br>`
- separators such as period-space, `DAN`, and `AND`
- salt forms such as hydrochloride, sulfate, sodium, phosphate, maleate, besilate, and succinate
- reviewed manual mappings, such as `PARACETAMOL -> Acetaminophen`

Current BPOM matching result after reviewed mappings:

- Rows with nonblank composition: `19,608`
- Full DDInter ingredient match: `13,695` (`69.8%`)
- Full or partial match: `15,427` (`78.7%`)

When a component is recognized in BPOM/RxNorm-style nomenclature but absent from the current DDInter/MecDDI interaction dataset, the UI should communicate that absence directly. Absence from this dataset must never be treated as proof of safety.

## Clinical Safety

This is a prototype built from public/free/research datasets. It is not a validated clinical decision support system.

Do not use this project to make diagnoses, prescriptions, dose changes, substitutions, or treatment decisions. All findings, especially missing or unrated results, must be verified with a qualified clinician, pharmacist, or validated clinical drug reference before patient care use.

## Rebuild The Static Data

From the repository root:

```bash
python3 build_github_pages_data.py
```

This regenerates:

- `docs/data/drugs.json`
- `docs/data/products.json`
- `docs/data/metadata.json`
- `docs/data/interactions/*.json`

Rebuild whenever the merged interaction CSV, BPOM source file, BPOM mapped workfile, or manual dictionary changes.

## Preview Locally

From the repository root:

```bash
cd docs
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

Use the local HTTP server rather than opening `docs/index.html` directly with `file://`, because browser security rules can block JSON loading from local files.

## Publish With GitHub Pages

This repository is configured as a static GitHub Pages project:

- Branch: `main`
- Folder: `/docs`

Useful commands:

```bash
git status
git add README.md docs build_github_pages_data.py
git commit -m "Update site documentation"
git push
```

If Pages needs to be configured again:

```bash
gh api repos/ifaruqi/interact/pages -X POST -f 'source[branch]=main' -f 'source[path]=/docs'
```

## Repository Layout

```text
docs/
  index.html
  styles.css
  app.js
  data/
    drugs.json
    products.json
    metadata.json
    interactions/
build_github_pages_data.py
merge_ddinter.py
bpom_ddinter_clean_map.py
build_reviewed_component_dictionaries.py
generate_unmatched_mapping_candidates.py
interaction_checker.py
```

## License And Attribution

Before use beyond internal prototyping, review the license and attribution requirements for:

- DDInter
- MecDDI
- PKAG-DDI / HuggingFace dataset distribution
- BPOM source data
- RxNorm, if RxNorm-derived mapping files are later incorporated
