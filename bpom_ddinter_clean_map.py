"""
BPOM -> DDInter composition cleaning and first-pass mapping
Created: 2026-09-08

Purpose
-------
1. Parse messy BPOM KOMPOSISI text into logical components.
2. Apply conservative cleaning rules.
3. Match components to the DDInter vocabulary.
4. Keep unmatched components visible for manual/synonym mapping.

Input
-----
APP - Master Produk Komoditi Obat-2026-09-08.csv
ddinter_merged.csv
manual_ddinter_dictionary_2026-09-09.csv
bpom_component_resolution_dictionary_2026-09-09.csv

Output
------
APP_Drug_Composition_DDInter_Mapping_Workfile_2026-09-08.csv
APP_Master_Produk_DDInter_Mapped_2026-09-08.csv
"""

import re
import pandas as pd

BPOM_FILE = "APP - Master Produk Komoditi Obat-2026-09-08.csv"
DDINTER_FILE = "ddinter_merged.csv"
MANUAL_DICTIONARY_FILE = "manual_ddinter_dictionary_2026-09-09.csv"
COMPONENT_RESOLUTION_FILE = "bpom_component_resolution_dictionary_2026-09-09.csv"


def normalize_component(value):
    x = re.sub(r"\s+", " ", str(value).upper()).strip(" .")
    x = re.sub(r"[^A-Z0-9]+", " ", x)
    return re.sub(r"\s+", " ", x).strip()

def parse_components(raw):
    """Split composition only on separators/patterns that are reasonably safe."""
    if not raw or not str(raw).strip():
        return []

    x = str(raw)

    # HTML line break = new composition component
    x = re.sub(r"<br\s*/?>", " | ", x, flags=re.I)

    # Period followed by another uppercase term is commonly used as a separator
    x = re.sub(r"\.\s+(?=[A-Z])", " | ", x)

    # Indonesian/English conjunction used between substances
    x = re.sub(r"\s+(?:DAN|AND)\s+", " | ", x, flags=re.I)

    # Rare separator patterns observed in the source
    x = re.sub(r"\s*:\s*", " | ", x)
    x = re.sub(r"\s*&\s*", " | ", x)

    components = []
    for component in x.split("|"):
        component = re.sub(r"\s+", " ", component).strip(" .")
        if not component:
            continue

        # Descriptive Indonesian prefix, not a drug substance
        component = re.sub(
            r"^KOMBINASI\s*[-:]?\s*", "", component, flags=re.I
        ).strip()

        if component:
            components.append(component)

    return components


# Chemical/formulation suffixes that may be removed ONLY when the remaining
# string becomes an exact DDInter drug name. This avoids blindly deleting
# meaningful chemical names.
FORM_SUFFIXES = {
    "HYDROCHLORIDE", "HYDROBROMIDE", "SULFATE", "NITRATE", "ACETATE",
    "PHOSPHATE", "MALEATE", "BESILATE", "MESILATE", "SUCCINATE",
    "FUMARATE", "TARTRATE", "CITRATE", "BROMIDE", "VALERATE",
    "PROPIONATE", "DIETHYLAMINE", "TROMETAMOL", "PAMOATE", "TOSYLATE",
    "TRIHYDRATE", "MONOHYDRATE", "DIHYDRATE", "HEMIHYDRATE",
    "ANHYDROUS", "ANHYDRATE", "SODIUM", "POTASSIUM", "CALCIUM", "HCL"
}

def load_manual_dictionary(dd_set):
    try:
        manual = pd.read_csv(MANUAL_DICTIONARY_FILE, dtype=str).fillna("")
    except FileNotFoundError:
        return {}

    dictionary = {}
    for _, row in manual.iterrows():
        source = normalize_component(row["bpom_component"])
        target = normalize_component(row["ddinter_name"])
        if source and target in dd_set:
            dictionary[source] = dd_set[target]
    return dictionary


def load_component_resolution():
    try:
        resolution = pd.read_csv(COMPONENT_RESOLUTION_FILE, dtype=str).fillna("")
    except FileNotFoundError:
        return {}

    return {
        normalize_component(row["source_component"]): {
            "component_status": row["component_status"],
            "display_message": row["display_message"],
        }
        for _, row in resolution.iterrows()
    }


def map_component(component, dd_set, manual_dictionary):
    """Return (DDInter name, method). Empty name means no match."""
    x = normalize_component(component)

    if x in dd_set:
        return dd_set[x], "exact"

    if x in manual_dictionary:
        return manual_dictionary[x], "reviewed-manual-dictionary"

    # Remove clearly descriptive formulation wording.
    y = re.sub(r"\bBUFFERED WITH\b.*$", "", x).strip()
    y = re.sub(r"\b(?:STERILE|LYOPHILIZED)\b", "", y).strip()
    y = re.sub(r"\s+", " ", y).strip(" .")

    if y in dd_set:
        return dd_set[y], "descriptor-normalized"

    # Strip trailing chemical/form tokens only if this produces an exact
    # DDInter vocabulary match.
    tokens = y.split()
    for n in range(1, min(4, len(tokens)) + 1):
        tail = tokens[-n:]
        if all(token in FORM_SUFFIXES for token in tail):
            candidate = " ".join(tokens[:-n]).strip()
            if candidate in dd_set:
                return dd_set[candidate], "salt/form-normalized"

    # A few common multi-token chemical forms.
    special = [
        "SODIUM PHOSPHATE",
        "SODIUM SUCCINATE",
        "SODIUM BICARBONATE",
        "CALCIUM CARBONATE",
        "MAGNESIUM TRIHYDRATE",
    ]
    for suffix in special:
        if y.endswith(" " + suffix):
            candidate = y[:-(len(suffix) + 1)].strip()
            if candidate in dd_set:
                return dd_set[candidate], "salt/form-normalized"

    return "", "unmatched"


def main():
    bp = pd.read_csv(BPOM_FILE, dtype=str).fillna("")
    dd = pd.read_csv(
        DDINTER_FILE,
        usecols=["drug_a_name", "drug_b_name"],
        dtype=str
    ).fillna("")

    dd_vocab = sorted(
        set(dd["drug_a_name"].str.strip()) |
        set(dd["drug_b_name"].str.strip())
    )
    dd_set = {name.upper(): name for name in dd_vocab if name.strip()}
    manual_dictionary = load_manual_dictionary(dd_set)
    component_resolution = load_component_resolution()

    rows = []

    for _, row in bp.iterrows():
        raw = row["KOMPOSISI"]
        components = parse_components(raw)
        clean = " + ".join(components)

        matches = []
        unmatched = []
        methods = []

        for component in components:
            match, method = map_component(component, dd_set, manual_dictionary)

            if match:
                if match not in matches:
                    matches.append(match)
                methods.append(method)
            else:
                unmatched.append(component)
                methods.append(method)

        if not components:
            status = "blank"
            overall_method = ""
        elif not unmatched:
            status = "all_components_matched"
            overall_method = (
                "exact" if all(m == "exact" for m in methods)
                else "normalized"
            )
        elif matches:
            status = "partial_match"
            overall_method = "partial"
        else:
            status = "no_ddinter_match"
            overall_method = "unmatched"

        unmatched_statuses = []
        unmatched_messages = []
        for component in unmatched:
            resolution = component_resolution.get(normalize_component(component), {})
            unmatched_statuses.append(
                resolution.get(
                    "component_status",
                    "recognized_bpom_component_absent_from_current_ddinter_mecddi",
                )
            )
            unmatched_messages.append(
                resolution.get(
                    "display_message",
                    "Recognized drug ingredient, but absent from current DDInter/MecDDI interaction dataset.",
                )
            )

        rows.append({
            "NAMA PRODUK": row["NAMA PRODUK"],
            "NIE": row["NIE"],
            "KOMPOSISI_RAW": raw,
            "KOMPOSISI_CLEAN": clean,
            "DDINTER_MATCH": " + ".join(matches),
            "UNMATCHED_COMPONENTS": " + ".join(unmatched),
            "UNMATCHED_COMPONENT_STATUS": " + ".join(unmatched_statuses),
            "UNMATCHED_COMPONENT_MESSAGE": " + ".join(dict.fromkeys(unmatched_messages)),
            "MATCH_STATUS": status,
            "MATCH_METHOD": overall_method,
        })

    out = pd.DataFrame(rows)

    out.to_csv(
        "APP_Drug_Composition_DDInter_Mapping_Workfile_2026-09-08.csv",
        index=False
    )

    master = bp.copy()
    master["KOMPOSISI_CLEAN"] = out["KOMPOSISI_CLEAN"]
    master["DDINTER_MATCH"] = out["DDINTER_MATCH"]
    master["UNMATCHED_COMPONENTS"] = out["UNMATCHED_COMPONENTS"]
    master["UNMATCHED_COMPONENT_STATUS"] = out["UNMATCHED_COMPONENT_STATUS"]
    master["UNMATCHED_COMPONENT_MESSAGE"] = out["UNMATCHED_COMPONENT_MESSAGE"]
    master["MATCH_STATUS"] = out["MATCH_STATUS"]
    master["MATCH_METHOD"] = out["MATCH_METHOD"]

    master.to_csv(
        "APP_Master_Produk_DDInter_Mapped_2026-09-08.csv",
        index=False
    )

if __name__ == "__main__":
    main()
