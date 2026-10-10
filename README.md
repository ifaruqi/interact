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

- Interaction pairs: `235,821`
- DDInter/MecDDI drug concepts: `1,971`
- BPOM product rows: `23,481`
- Interaction shards: `1,895`

Source files used by the local build:

- `ddinter_merged.csv`
- `APP - Master Produk Komoditi Obat-2026-09-08.csv`
- `APP_Master_Produk_DDInter_Mapped_2026-09-08.csv`
- `manual_ddinter_dictionary_2026-09-09.csv`

The raw CSV files are intentionally not committed to the repository. The generated static JSON files under `docs/data/` are committed so GitHub Pages can run without a backend.

## Data Provenance

Severity data:

- Source: DDInter 2.0 bulk CSV files, `ddinter_downloads_code_<ATC>.csv`
- Coverage used here: `234,981` drug-drug pairs across all 14 ATC-category files: A, B, C, D, G, H, J, L, M, N, P, R, S, V
- The download page at `ddinter2.scbdd.com/download/` links only A, B, D, H, L, P, R, V. The C, G, J, M, N, S files are served from the same path (`/static/media/download/`) with the same columns and were added on 2026-10-10. No pair has conflicting severity levels across files.
- Field attribution: `severity_source = DDInter`

Mechanism/explanation data:

- Source: MecDDI, accessed via the `acai233/pkag-ddi` HuggingFace dataset file `DDInter2_0_mecddi.csv`
- Coverage used here: `152,887` drug-drug pairs
- Field attribution: `mechanism_source = MecDDI`

Merged interaction dataset:

- Total unique pairs: `235,821`
- Severity and mechanism: `152,047`
- Severity only: `82,934`
- Mechanism only: `840`

Important interpretation note: this project should be described as using the DDInter 2.0 bulk-download severity export plus MecDDI mechanism text. DDInter's drug-food and drug-disease interactions are not included.

Many drugs commonly sold in Indonesia are not in DDInter at all, for example domperidone, metamizole, etoricoxib, ambroxol, bromhexine, guaifenesin, candesartan, and mometasone. Products containing them are shown with those ingredients unchecked.

## License And Attribution

DDInter data is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The generated interaction data in `docs/data/` is an adaptation of it, so this site must credit DDInter, stay non-commercial, and share the adapted data under the same license. The site footer carries this attribution.

DDInter 2.0 reference: Nucleic Acids Research 53(D1):D1356, 2025, doi:[10.1093/nar/gkae726](https://doi.org/10.1093/nar/gkae726).

## BPOM Product Mapping

BPOM product composition text is regulatory free text, not a standardized ingredient list. The mapping pipeline handles common issues such as:

- HTML line breaks like `<br>`
- separators such as period-space, `DAN`, and `AND`
- salt forms such as hydrochloride, sulfate, sodium, phosphate, maleate, besilate, and succinate
- reviewed manual mappings, such as `PARACETAMOL -> Acetaminophen`

Current BPOM matching result after reviewed mappings:

- Rows with nonblank composition: `19,608`
- Full DDInter ingredient match: `13,697` (`69.9%`)
- Full or partial match: `15,429` (`78.7%`)

When a component is recognized in BPOM/RxNorm-style nomenclature but absent from the current DDInter/MecDDI interaction dataset, the UI should communicate that absence directly. Absence from this dataset must never be treated as proof of safety.

## Clinical Safety

This is a prototype built from public/free/research datasets. It is not a validated clinical decision support system.

Do not use this project to make diagnoses, prescriptions, dose changes, substitutions, or treatment decisions. All findings, especially missing or unrated results, must be verified with a qualified clinician, pharmacist, or validated clinical drug reference before patient care use.

## Rebuild The Static Data

From the repository root, run the pipeline in order:

```bash
python3 merge_ddinter.py
python3 bpom_ddinter_clean_map.py
python3 build_github_pages_data.py
```

- `merge_ddinter.py` combines every `ddinter_downloads_code_*.csv` with `DDInter2_0_mecddi.csv` into `ddinter_merged.csv`.
- `bpom_ddinter_clean_map.py` re-maps BPOM compositions against that vocabulary and the reviewed dictionaries. `build_github_pages_data.py` reads its output, so skipping this step leaves product mappings stale.
- `build_github_pages_data.py` writes the browser data.

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
