from __future__ import annotations

import csv
import html
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "docs"
DATA_DIR = SITE_DIR / "data"
INTERACTION_DIR = DATA_DIR / "interactions"
DDI_FILE = BASE_DIR / "ddinter_merged.csv"
BPOM_FILE = BASE_DIR / "APP - Master Produk Komoditi Obat-2026-09-08.csv"
MAPPED_BPOM_FILE = BASE_DIR / "APP_Master_Produk_DDInter_Mapped_2026-09-08.csv"
MANUAL_DICTIONARY_FILE = BASE_DIR / "manual_ddinter_dictionary_2026-09-09.csv"

SALT_SUFFIXES = [
    "SODIUM CLATHRATE",
    "HYDROCHLORIDE",
    "DIHYDROCHLORIDE",
    "MONOHYDROCHLORIDE",
    "HYDROBROMIDE",
    "BESILATE",
    "BESYLATE",
    "MESYLATE",
    "MALEATE",
    "FUMARATE",
    "PHOSPHATE",
    "DIPHOSPHATE",
    "SULFATE",
    "SULPHATE",
    "ACETATE",
    "CITRATE",
    "TARTRATE",
    "SUCCINATE",
    "LACTATE",
    "NITRATE",
    "CARBONATE",
    "POTASSIUM",
    "SODIUM",
    "CALCIUM",
    "MAGNESIUM",
]

INGREDIENT_SYNONYMS = {
    "PARACETAMOL": "ACETAMINOPHEN",
}


def compact_json_dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)


def display_text(value) -> str:
    if pd.isna(value):
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<\s*br\s*/?\s*>", " | ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name(value) -> str:
    text = display_text(value).upper()
    text = text.replace("µ", "U")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_composition(value) -> list[str]:
    text = display_text(value)
    if not text:
        return []
    text = re.sub(r"(?<=[A-Za-z])\.\s+(?=[A-Za-z])", " | ", text)
    parts = re.split(r"\s*(?:\||;|\+|<BR>|<br>|\bDAN\b|\bAND\b)\s*", text, flags=re.I)
    cleaned = []
    for part in parts:
        part = part.strip(" .,\t\r\n")
        if not part:
            continue
        cleaned.append(part)
    return cleaned


def split_joined_components(value) -> list[str]:
    text = display_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(" + ") if part.strip()]


def strip_strength_noise(value: str) -> str:
    text = normalize_name(value)
    text = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:MG|MCG|G|GRAM|ML|IU|UI|%)\b", " ", text)
    text = re.sub(r"\b(?:EQ|SETARA|EQUIVALENT|ANHYDROUS)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def base_candidates(value: str) -> list[tuple[str, str]]:
    original = normalize_name(value)
    no_strength = strip_strength_noise(value)
    candidates = [("exact", original)]
    if no_strength and no_strength != original:
        candidates.append(("normalized", no_strength))

    for suffix in SALT_SUFFIXES:
        for source in [original, no_strength]:
            if source.endswith(" " + suffix):
                candidate = source[: -len(suffix)].strip()
                if candidate:
                    candidates.append(("salt_stripped", candidate))

    for _, source in list(candidates):
        synonym = INGREDIENT_SYNONYMS.get(source)
        if synonym:
            candidates.append(("synonym", synonym))

    seen = set()
    unique = []
    for method, candidate in candidates:
        if candidate and candidate not in seen:
            unique.append((method, candidate))
            seen.add(candidate)
    return unique


def build_drug_indexes(ddi: pd.DataFrame):
    id_to_name = {}
    name_to_id = {}
    for id_col, name_col in [("drug_a_id", "drug_a_name"), ("drug_b_id", "drug_b_name")]:
        for ddinter_id, name in ddi[[id_col, name_col]].dropna().drop_duplicates().itertuples(index=False):
            ddinter_id = str(ddinter_id).strip()
            name = str(name).strip()
            id_to_name.setdefault(ddinter_id, name)
            name_to_id.setdefault(normalize_name(name), ddinter_id)
    drugs = [
        {"id": ddinter_id, "name": id_to_name[ddinter_id]}
        for ddinter_id in sorted(id_to_name, key=lambda x: (len(x), x))
    ]
    return drugs, id_to_name, name_to_id


def load_manual_dictionary() -> dict[str, str]:
    if not MANUAL_DICTIONARY_FILE.exists():
        return {}
    manual = pd.read_csv(MANUAL_DICTIONARY_FILE, dtype="string").fillna("")
    return {
        normalize_name(row.bpom_component): str(row.ddinter_name).strip()
        for row in manual.itertuples(index=False)
        if str(row.bpom_component).strip() and str(row.ddinter_name).strip()
    }


def resolve_ingredient(raw_ingredient: str, name_to_id: dict[str, str], id_to_name: dict[str, str]):
    for method, candidate in base_candidates(raw_ingredient):
        ddinter_id = name_to_id.get(candidate)
        if ddinter_id:
            return {
                "raw": raw_ingredient,
                "ddinterId": ddinter_id,
                "ddinterName": id_to_name[ddinter_id],
                "matchedAs": candidate.title(),
                "method": method,
            }
    return {"raw": raw_ingredient}


def resolve_with_manual(
    raw_ingredient: str,
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    manual_dictionary: dict[str, str],
):
    manual_target = manual_dictionary.get(normalize_name(raw_ingredient))
    if manual_target:
        ddinter_id = name_to_id.get(normalize_name(manual_target))
        if ddinter_id:
            return {
                "raw": raw_ingredient,
                "ddinterId": ddinter_id,
                "ddinterName": id_to_name[ddinter_id],
                "matchedAs": id_to_name[ddinter_id],
                "method": "reviewed_manual_dictionary",
            }
    return resolve_ingredient(raw_ingredient, name_to_id, id_to_name)


def find_raw_component_for_match(
    target_name: str,
    components: list[str],
    used_indexes: set[int],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    manual_dictionary: dict[str, str],
) -> tuple[str, str]:
    target_norm = normalize_name(target_name)
    for index, component in enumerate(components):
        if index in used_indexes:
            continue
        resolved = resolve_with_manual(component, name_to_id, id_to_name, manual_dictionary)
        if normalize_name(resolved.get("ddinterName", "")) == target_norm:
            used_indexes.add(index)
            return component, resolved.get("method", "mapped_workfile")
    return target_name, "mapped_workfile"


def build_products(
    bpom: pd.DataFrame,
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    manual_dictionary: dict[str, str],
):
    products = []
    for row in bpom.itertuples(index=False):
        row_data = dict(zip(bpom.columns, row))
        if "DDINTER_MATCH" in bpom.columns:
            ingredients = []
            components = split_joined_components(row_data.get("KOMPOSISI_CLEAN"))
            used_component_indexes: set[int] = set()
            for name in split_joined_components(row_data.get("DDINTER_MATCH")):
                ddinter_id = name_to_id.get(normalize_name(name))
                if ddinter_id:
                    raw_component, method = find_raw_component_for_match(
                        name,
                        components,
                        used_component_indexes,
                        name_to_id,
                        id_to_name,
                        manual_dictionary,
                    )
                    ingredients.append(
                        {
                            "raw": raw_component,
                            "ddinterId": ddinter_id,
                            "ddinterName": id_to_name[ddinter_id],
                            "matchedAs": id_to_name[ddinter_id],
                            "method": method,
                        }
                    )
            unmatched_raw = split_joined_components(row_data.get("UNMATCHED_COMPONENTS"))
            unmatched_status = split_joined_components(row_data.get("UNMATCHED_COMPONENT_STATUS"))
            unmatched_ingredients = []
            for index, component in enumerate(unmatched_raw):
                unmatched_ingredients.append(
                    {
                        "raw": component,
                        "status": unmatched_status[index]
                        if index < len(unmatched_status)
                        else "recognized_bpom_component_absent_from_current_ddinter_mecddi",
                        "message": display_text(row_data.get("UNMATCHED_COMPONENT_MESSAGE"))
                        or "Recognized drug ingredient, but absent from current DDInter/MecDDI interaction dataset.",
                    }
                )
        else:
            raw_parts = split_composition(row_data.get("KOMPOSISI"))
            ingredients = [resolve_ingredient(part, name_to_id, id_to_name) for part in raw_parts]
            unmatched_ingredients = [
                {
                    "raw": ingredient["raw"],
                    "status": "recognized_bpom_component_absent_from_current_ddinter_mecddi",
                    "message": "Recognized drug ingredient, but absent from current DDInter/MecDDI interaction dataset.",
                }
                for ingredient in ingredients
                if "ddinterId" not in ingredient
            ]
        products.append(
            {
                "productName": display_text(row_data.get("NAMA PRODUK")),
                "nie": display_text(row_data.get("NIE")),
                "dosageForm": display_text(row_data.get("BENTUK SEDIAAN")),
                "package": display_text(row_data.get("KEMASAN")),
                "composition": display_text(row_data.get("KOMPOSISI")),
                "registrant": display_text(row_data.get("PENDAFTAR")),
                "ingredients": ingredients,
                "unmatchedIngredients": unmatched_ingredients,
                "matchStatus": display_text(row_data.get("MATCH_STATUS")),
                "matchMethod": display_text(row_data.get("MATCH_METHOD")),
            }
        )
    return products


def build_interaction_shards(ddi: pd.DataFrame):
    if INTERACTION_DIR.exists():
        shutil.rmtree(INTERACTION_DIR)
    INTERACTION_DIR.mkdir(parents=True, exist_ok=True)

    shards = defaultdict(dict)
    for row in ddi.itertuples(index=False):
        drug_a_id = str(row.drug_a_id)
        drug_b_id = str(row.drug_b_id)
        pair = sorted([drug_a_id, drug_b_id])
        severity = "" if pd.isna(row.severity) else str(row.severity)
        mechanism = "" if pd.isna(row.mechanism) else str(row.mechanism)
        severity_source = "" if pd.isna(row.severity_source) else str(row.severity_source)
        mechanism_source = "" if pd.isna(row.mechanism_source) else str(row.mechanism_source)
        shards[pair[0]][pair[1]] = {
            "severity": severity,
            "severitySource": severity_source,
            "mechanism": mechanism,
            "mechanismSource": mechanism_source,
        }

    for shard_id, records in shards.items():
        compact_json_dump(INTERACTION_DIR / f"{shard_id}.json", records)
    return len(shards)


def main() -> None:
    ddi = pd.read_csv(DDI_FILE, dtype="string")
    bpom_path = MAPPED_BPOM_FILE if MAPPED_BPOM_FILE.exists() else BPOM_FILE
    bpom = pd.read_csv(bpom_path, dtype="string", encoding="utf-8-sig")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    drugs, id_to_name, name_to_id = build_drug_indexes(ddi)
    manual_dictionary = load_manual_dictionary()
    products = build_products(bpom, name_to_id, id_to_name, manual_dictionary)
    shard_count = build_interaction_shards(ddi)

    compact_json_dump(DATA_DIR / "drugs.json", drugs)
    compact_json_dump(DATA_DIR / "products.json", products)
    compact_json_dump(
        DATA_DIR / "metadata.json",
        {
            "builtFrom": {
                "interactions": DDI_FILE.name,
                "bpomProducts": BPOM_FILE.name,
                "bpomMappedProducts": bpom_path.name,
            },
            "interactionRows": int(len(ddi)),
            "bpomRows": int(len(bpom)),
            "drugCount": int(len(drugs)),
            "interactionShardCount": int(shard_count),
        },
    )

    matched_rows = sum(
        any("ddinterId" in ingredient for ingredient in product["ingredients"]) for product in products
    )
    print(f"Drugs: {len(drugs)}")
    print(f"BPOM products: {len(products)}")
    print(f"BPOM rows with at least one DDInter ingredient match: {matched_rows}")
    print(f"Interaction rows: {len(ddi)}")
    print(f"Interaction shards: {shard_count}")
    print(f"Site data written to: {DATA_DIR}")


if __name__ == "__main__":
    csv.field_size_limit(10_000_000)
    main()
