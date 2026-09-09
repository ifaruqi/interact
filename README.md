# Drug Interaction Checker

Static prototype for checking medication interactions using:

- DDInter bulk-download severity data
- MecDDI mechanism text
- BPOM product composition data for Indonesian product-name lookup

The publishable GitHub Pages site is in `docs/`.

## Rebuild Site Data

Run this whenever `ddinter_merged.csv` or the BPOM product CSV changes:

```bash
python3 build_github_pages_data.py
```

The script writes browser-ready JSON files into `docs/data/`.

## Preview Locally

From the repository folder:

```bash
cd docs
python3 -m http.server 8000
```

Open `http://localhost:8000`.

## GitHub Pages

Create a GitHub repository, push this folder, then configure GitHub Pages:

- Source: deploy from branch
- Branch: `main`
- Folder: `/docs`

The app is fully static and runs in the browser. It does not need a backend.

## Clinical Safety

This is a prototype using public/free/research datasets. Missing records are absence of local data, not proof of safety. Clinically important findings should be cross-checked with a pharmacist or clinical drug reference.
