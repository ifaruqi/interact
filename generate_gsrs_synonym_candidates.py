"""
Suggest DDInter targets for unmatched BPOM components using FDA GSRS/UNII names.

The FDA UNII Names file lists every name GSRS knows for a substance (INN, USAN,
BAN, common names, ...) under one UNII. If a BPOM component name and a DDInter
drug name share a UNII, they are the same substance, e.g. PARACETAMOL and
Acetaminophen both resolve to UNII 362O9ITL9D.

Source: https://precision.fda.gov/uniisearch/archive -> "UNII List" (UNIIs.zip).
Download it into this folder (zips are git-ignored), then run:

    python3 generate_gsrs_synonym_candidates.py [--unii-zip PATH]

Output is a review file only; nothing is auto-applied to the manual dictionary.
"""

from __future__ import annotations

import argparse
import io
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

from generate_unmatched_mapping_candidates import (
    candidate_forms,
    load_ddinter_vocab,
    normalize,
)


BASE_DIR = Path(__file__).resolve().parent
CANDIDATES_FILE = BASE_DIR / "unmatched_component_mapping_candidates_2026-09-08.csv"
OUTPUT = BASE_DIR / "gsrs_synonym_candidates.csv"

# of = official (INN/USAN/BAN/JAN...), cn = common name, sys = systematic name
# (needed for hydrates such as "Magnesium chloride hexahydrate"). Brand names (bn)
# and codes (cd) are excluded to avoid false bridges.
NAME_TYPES = {"of", "cn", "sys"}

# Only re-examine components the existing pipeline could not place confidently.
RECHECK_CONFIDENCE = {"no_candidate", "low"}


def find_unii_zip(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    matches = sorted(BASE_DIR.glob("UNIIs*.zip"))
    if not matches:
        raise SystemExit(
            "No UNIIs*.zip found. Download 'UNII List' from "
            "https://precision.fda.gov/uniisearch/archive into this folder."
        )
    return matches[-1]


def load_unii_names(zip_path: Path) -> tuple[pd.DataFrame, str]:
    with zipfile.ZipFile(zip_path) as archive:
        member = next(n for n in archive.namelist() if n.startswith("UNII_Names") and n.endswith(".txt"))
        with archive.open(member) as handle:
            names = pd.read_csv(
                io.TextIOWrapper(handle, encoding="utf-8"),
                sep="\t",
                dtype="string",
                keep_default_na=False,
                quoting=3,
            )
    names = names[names["TYPE"].isin(NAME_TYPES)].copy()
    names["norm"] = names["NAME"].map(normalize)
    return names, member


def build_index(names: pd.DataFrame):
    norm_to_uniis: dict[str, set[str]] = defaultdict(set)
    norm_to_type: dict[tuple[str, str], str] = {}
    for norm, unii, name_type in names[["norm", "UNII", "TYPE"]].itertuples(index=False):
        norm_to_uniis[norm].add(unii)
        # Prefer "of" if the same string appears as both official and common.
        if norm_to_type.get((norm, unii)) != "of":
            norm_to_type[(norm, unii)] = name_type
    display = dict(names[["UNII", "DISPLAY_NAME"]].drop_duplicates("UNII").itertuples(index=False))
    return norm_to_uniis, norm_to_type, display


def resolve_uniis(form: str, norm_to_uniis, display) -> set[str]:
    """Normalization drops stereo prefixes, so "(+)-KETOPROFEN" (dexketoprofen)
    collides with "KETOPROFEN". When a form hits several UNIIs, keep the one whose
    preferred name is exactly that form."""
    uniis = norm_to_uniis.get(form, set())
    if len(uniis) > 1:
        exact = {u for u in uniis if normalize(display.get(u, "")) == form}
        if exact:
            return exact
    return uniis


def map_ddinter_to_unii(ddinter_vocab: pd.DataFrame, norm_to_uniis, display) -> dict[str, set[tuple[str, str]]]:
    unii_to_ddinter: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for ddinter_id, name in ddinter_vocab.itertuples(index=False):
        # Route-specific concepts like "Acyclovir (topical)" are left to manual review.
        if "(" in str(name):
            continue
        for _, form in candidate_forms(str(name)):
            for unii in resolve_uniis(form, norm_to_uniis, display):
                unii_to_ddinter[unii].add((str(ddinter_id), str(name)))
    return unii_to_ddinter


def match_component(component: str, norm_to_uniis, norm_to_type, display, unii_to_ddinter) -> dict:
    found_unii = None
    for method, form in candidate_forms(component):
        uniis = resolve_uniis(form, norm_to_uniis, display)
        if not uniis:
            continue
        found_unii = found_unii or (method, form, sorted(uniis))
        targets = {t for unii in uniis for t in unii_to_ddinter.get(unii, ())}
        if len({t[0] for t in targets}) == 1:
            unii = next(u for u in sorted(uniis) if unii_to_ddinter.get(u))
            ddinter_id, ddinter_name = next(iter(targets))
            name_type = norm_to_type[(form, unii)]
            confidence = "high" if method in {"raw", "salt_form_removed"} and name_type == "of" else "medium"
            return {
                "gsrs_status": "ddinter_target_found",
                "suggested_ddinter_id": ddinter_id,
                "suggested_ddinter_name": ddinter_name,
                "confidence": confidence,
                "unii": unii,
                "unii_display_name": display.get(unii, ""),
                "reason": f"{method}: {form} ({name_type}) shares UNII {unii} with {ddinter_name}",
            }
        if len({t[0] for t in targets}) > 1:
            return {
                "gsrs_status": "ambiguous",
                "confidence": "",
                "unii": ";".join(sorted(uniis)),
                "reason": f"{method}: {form} links to several DDInter drugs: "
                + "; ".join(sorted(t[1] for t in targets)),
            }

    if found_unii:
        method, form, uniis = found_unii
        return {
            "gsrs_status": "substance_known_not_in_ddinter",
            "confidence": "",
            "unii": ";".join(uniis),
            "unii_display_name": "; ".join(display.get(u, "") for u in uniis),
            "reason": f"{method}: {form} is a known substance but has no DDInter interaction data",
        }
    return {"gsrs_status": "name_not_in_gsrs", "confidence": "", "reason": "no UNII name match"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--unii-zip", help="path to UNIIs*.zip from the FDA UNII archive")
    args = parser.parse_args()

    zip_path = find_unii_zip(args.unii_zip)
    names, member = load_unii_names(zip_path)
    norm_to_uniis, norm_to_type, display = build_index(names)

    ddinter_vocab, _ = load_ddinter_vocab()
    unii_to_ddinter = map_ddinter_to_unii(ddinter_vocab, norm_to_uniis, display)

    candidates = pd.read_csv(CANDIDATES_FILE, dtype="string").fillna("")
    todo = candidates[candidates["confidence"].isin(RECHECK_CONFIDENCE)]

    rows = []
    for component, frequency, previous in todo[["source_component", "frequency", "confidence"]].itertuples(index=False):
        result = match_component(component, norm_to_uniis, norm_to_type, display, unii_to_ddinter)
        rows.append(
            {
                "source_component": component,
                "frequency": int(frequency),
                "previous_confidence": previous,
                "suggested_ddinter_id": "",
                "suggested_ddinter_name": "",
                "unii": "",
                "unii_display_name": "",
                **result,
                "evidence_source": f"FDA_UNII_shared_identifier ({member})",
                "review_status": "pending_review" if result["gsrs_status"] == "ddinter_target_found" else "not_for_auto_mapping",
            }
        )

    out = pd.DataFrame(rows).sort_values(["gsrs_status", "frequency"], ascending=[True, False])
    out.to_csv(OUTPUT, index=False)

    print(f"UNII source: {zip_path.name} / {member}")
    print(f"DDInter drugs linked to a UNII: {len({t for s in unii_to_ddinter.values() for t in s})} of {len(ddinter_vocab)}")
    print(f"Components re-checked: {len(out)}")
    print("")
    print(out.groupby("gsrs_status")["frequency"].agg(components="count", occurrences="sum").to_string())
    print("")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
