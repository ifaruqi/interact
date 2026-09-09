from __future__ import annotations

import html
import re
import difflib
from collections import Counter, defaultdict, deque
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
WORKFILE = BASE_DIR / "APP_Drug_Composition_DDInter_Mapping_Workfile_2026-09-08.csv"
DDINTER_FILE = BASE_DIR / "ddinter_merged.csv"
RXNORM_CONSO = BASE_DIR / "RxNorm_full_prescribe_09082026" / "rrf" / "RXNCONSO.RRF"
RXNORM_REL = BASE_DIR / "RxNorm_full_prescribe_09082026" / "rrf" / "RXNREL.RRF"
OUTPUT = BASE_DIR / "unmatched_component_mapping_candidates_2026-09-08.csv"

FORM_SUFFIXES = {
    "HYDROCHLORIDE",
    "HYDROBROMIDE",
    "DIHYDROCHLORIDE",
    "MONOHYDROCHLORIDE",
    "SULFATE",
    "SULPHATE",
    "NITRATE",
    "ACETATE",
    "PHOSPHATE",
    "MALEATE",
    "BESILATE",
    "BESYLATE",
    "MESILATE",
    "MESYLATE",
    "SUCCINATE",
    "FUMARATE",
    "TARTRATE",
    "CITRATE",
    "BROMIDE",
    "VALERATE",
    "PROPIONATE",
    "DIETHYLAMINE",
    "TROMETAMOL",
    "PAMOATE",
    "TOSYLATE",
    "TRIHYDRATE",
    "MONOHYDRATE",
    "DIHYDRATE",
    "HEMIHYDRATE",
    "ANHYDROUS",
    "ANHYDRATE",
    "BISULFATE",
    "BITARTRATE",
    "OXALATE",
    "ARGININE",
    "CILEXETIL",
    "PALMITATE",
    "ACETONIDE",
    "DIPROPIONATE",
    "BENZOATE",
    "XINAFOATE",
    "MEDOXOMIL",
    "PROPANEDIOL",
    "OLAMINE",
    "HCL",
}

NON_MAPPABLE_PATTERNS = [
    r"\bWATER FOR INJECTION\b",
    r"\bAQUA PRO INJECTIONE\b",
    r"\bSTERILE WATER\b",
    r"\bBUFFERED WITH\b",
    r"\bEMULSION\b",
    r"\bEXTRACT\b",
    r"\bFLAVOU?R\b",
    r"\bPARFUM\b",
    r"\bVIRUS\b",
    r"\bSTRAIN\b",
    r"\bSURFACE ANTIGEN\b",
    r"\bTOXOID\b",
    r"\bPOLYSACCHARIDE CONJUGATED\b",
]

MANUAL_CANDIDATES = {
    "PARACETAMOL": ("Acetaminophen", "high", "regional synonym: paracetamol is acetaminophen"),
    "CHLORPHENAMINE MALEATE": ("Chlorpheniramine", "high", "regional name plus salt form"),
    "DRIED ALUMINIUM HYDROXIDE GEL": ("Aluminum hydroxide", "high", "UK spelling/formulation phrase maps to aluminum hydroxide"),
    "ACICLOVIR": ("Acyclovir", "high", "spelling variant"),
    "DEXTROSE MONOHYDRATE": ("Dextrose, unspecified form", "medium", "hydrate form maps to broader dextrose concept"),
    "DEXTROSE ANHYDRATE": ("Dextrose, unspecified form", "medium", "anhydrous form maps to broader dextrose concept"),
    "CLOPIDOGREL BISULFATE": ("Clopidogrel", "high", "salt form"),
    "PANTOPRAZOLE SODIUM SESQUIHYDRATE": ("Pantoprazole", "high", "salt/hydrate form"),
    "PANTOPRAZOLE SODIUM SESQUIHYDRATE LYOPHILIZED": ("Pantoprazole", "high", "salt/hydrate form with formulation descriptor"),
    "BETAMETHASONE DIPROPIONATE": ("Betamethasone", "medium", "ester form maps to parent corticosteroid"),
    "DESOXIMETASONE": ("Desoximetasone (topical)", "medium", "DDInter has topical-specific concept"),
    "CHLORAMPHENICOL PALMITATE": ("Chloramphenicol", "medium", "ester/prodrug form maps to parent antibiotic"),
    "TRIAMCINOLONE ACETONIDE": ("Triamcinolone", "medium", "ester form maps to parent corticosteroid"),
    "SODIUM VALPROATE": ("Valproic acid", "high", "valproate salt maps to valproic acid"),
    "DIVALPROEX SODIUM": ("Valproic acid", "medium", "valproate complex maps to valproic acid"),
    "CEFTRIAXONE SODIUM SESQUATERHYDRATE": ("Ceftriaxone", "high", "salt/hydrate form"),
    "METRONIDAZOLE BENZOATE": ("Metronidazole", "medium", "ester form maps to parent drug"),
    "NOREPINEPHRINE BITARTRATE MONOHYDRATE": ("Norepinephrine", "high", "salt/hydrate form"),
    "EPINEPHRINE BITARTRATE": ("Epinephrine", "high", "salt form"),
    "BOTULINUM TOXIN TYPE A": ("Botulinum toxin type A", "high", "hyphenation variant"),
    "BOTULINUM TOXIN TYPE-A": ("Botulinum toxin type A", "high", "hyphenation variant"),
    "LEVOCETIRIZINE DIHYDROCHLORIDE": ("Levocetirizine", "high", "salt form"),
    "PRAMIPEXOLE DIHYDROCHLORIDE MONOHYDRATE": ("Pramipexole", "high", "salt/hydrate form"),
    "PERINDOPRIL ARGININE": ("Perindopril", "high", "salt form"),
    "ESCITALOPRAM OXALATE": ("Escitalopram", "high", "salt form"),
    "METAMIZOLE SODIUM": ("Dipyrone", "medium", "international synonym, DDInter target is dipyrone"),
    "METAMIZOLE SODIUM MONOHYDRATE": ("Dipyrone", "medium", "international synonym plus hydrate"),
    "ALUMINIUM HYDROXIDE GEL": ("Aluminum hydroxide", "high", "UK spelling/formulation phrase maps to aluminum hydroxide"),
    "MAGNESIUM HYDROXIDE PASTE": ("Magnesium hydroxide", "medium", "formulation phrase maps to magnesium hydroxide"),
    "SOMATROPIN": ("Somatotropin", "high", "common synonym/spelling variant"),
    "BECLOMETASONE DIPROPIONATE": ("Beclomethasone dipropionate", "high", "spelling variant"),
    "ACETYL CYSTEINE": ("Acetylcysteine", "high", "spacing variant"),
}


def normalize(value: str) -> str:
    text = html.unescape(str(value or "")).upper()
    text = re.sub(r"<\s*br\s*/?\s*>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def candidate_forms(component: str) -> list[tuple[str, str]]:
    original = normalize(component)
    forms: list[tuple[str, str]] = []
    seen = set()

    def add(method: str, value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in seen:
            forms.append((method, value))
            seen.add(value)

    add("raw", original)
    stripped = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:MG|MCG|G|GRAM|ML|IU|UI|%)\b", " ", original
    )
    stripped = re.sub(r"\b(?:EQ|SETARA|EQUIVALENT|LYOPHILIZED)\b", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    add("strength_descriptor_removed", stripped)

    tokens = stripped.split()
    for n in range(1, min(5, len(tokens)) + 1):
        tail = tokens[-n:]
        if all(token in FORM_SUFFIXES for token in tail):
            add("salt_form_removed", " ".join(tokens[:-n]))

    return forms


def load_unmatched_components() -> Counter[str]:
    work = pd.read_csv(WORKFILE, dtype="string").fillna("")
    counts: Counter[str] = Counter()
    for cell in work["UNMATCHED_COMPONENTS"]:
        for component in [part.strip() for part in cell.split(" + ") if part.strip()]:
            counts[component] += 1
    return counts


def load_ddinter_vocab():
    ddi = pd.read_csv(
        DDINTER_FILE,
        dtype="string",
        usecols=["drug_a_id", "drug_a_name", "drug_b_id", "drug_b_name"],
    )
    vocab = pd.concat(
        [
            ddi[["drug_a_id", "drug_a_name"]].rename(
                columns={"drug_a_id": "id", "drug_a_name": "name"}
            ),
            ddi[["drug_b_id", "drug_b_name"]].rename(
                columns={"drug_b_id": "id", "drug_b_name": "name"}
            ),
        ]
    ).dropna().drop_duplicates()
    name_to_record = {normalize(name): (str(ddinter_id), str(name)) for ddinter_id, name in vocab.itertuples(index=False)}
    return vocab, name_to_record


def load_rxnorm_bridge(ddinter_vocab: pd.DataFrame):
    if not RXNORM_CONSO.exists():
        return {}, {}

    conso_cols = [
        "RXCUI",
        "LAT",
        "TS",
        "LUI",
        "STT",
        "SUI",
        "ISPREF",
        "RXAUI",
        "SAUI",
        "SCUI",
        "SDUI",
        "SAB",
        "TTY",
        "CODE",
        "STR",
        "SRL",
        "SUPPRESS",
        "CVF",
    ]
    rx = pd.read_csv(
        RXNORM_CONSO,
        sep="|",
        names=conso_cols + [""],
        usecols=conso_cols,
        dtype="string",
    )
    rx = rx[(rx["LAT"] == "ENG") & (rx["SUPPRESS"] == "N")]

    str_to_rxcui: dict[str, set[str]] = defaultdict(set)
    for rxcui, text in rx[["RXCUI", "STR"]].dropna().itertuples(index=False):
        str_to_rxcui[normalize(text)].add(str(rxcui))

    rxcui_to_ddinter: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for ddinter_id, name in ddinter_vocab.itertuples(index=False):
        for _, form in candidate_forms(str(name)):
            for rxcui in str_to_rxcui.get(form, []):
                rxcui_to_ddinter[rxcui].add((str(ddinter_id), str(name)))

    graph: dict[str, set[str]] = defaultdict(set)
    if RXNORM_REL.exists():
        rel_cols = [
            "RXCUI1",
            "RXAUI1",
            "STYPE1",
            "REL",
            "RXCUI2",
            "RXAUI2",
            "STYPE2",
            "RELA",
            "RUI",
            "SRUI",
            "SAB",
            "SL",
            "DIR",
            "RG",
            "SUPPRESS",
            "CVF",
        ]
        rel = pd.read_csv(
            RXNORM_REL,
            sep="|",
            names=rel_cols + [""],
            usecols=rel_cols,
            dtype="string",
        )
        useful_relas = {
            "has_active_ingredient",
            "has_active_moiety",
            "active_ingredient_of",
            "active_moiety_of",
        }
        rel = rel[
            rel["RELA"].isin(useful_relas)
            & rel["RXCUI1"].notna()
            & rel["RXCUI2"].notna()
            & (rel["SUPPRESS"].fillna("N") != "O")
        ]
        for left, right in rel[["RXCUI1", "RXCUI2"]].itertuples(index=False):
            left, right = str(left), str(right)
            graph[left].add(right)
            graph[right].add(left)

    same_bridge = {}
    relation_bridge = {}
    all_forms = set()
    for form in str_to_rxcui:
        all_forms.add(form)
    for form in all_forms:
        same_hits = []
        for rxcui in str_to_rxcui.get(form, []):
            same_hits.extend((rxcui, ddinter_id, name) for ddinter_id, name in rxcui_to_ddinter.get(rxcui, []))
        if same_hits:
            same_bridge[form] = sorted(set(same_hits))

        rxcuies = set(str_to_rxcui.get(form, set()))
        expanded = set(rxcuies)
        for rxcui in list(rxcuies):
            expanded.update(graph.get(rxcui, set()))
        rel_hits = []
        for rxcui in expanded - rxcuies:
            rel_hits.extend((rxcui, ddinter_id, name) for ddinter_id, name in rxcui_to_ddinter.get(rxcui, []))
        if rel_hits:
            relation_bridge[form] = sorted(set(rel_hits))

    return same_bridge, relation_bridge


def is_non_mappable(component: str) -> bool:
    normalized = normalize(component)
    return any(re.search(pattern, normalized, flags=re.I) for pattern in NON_MAPPABLE_PATTERNS)


def choose_manual(component: str, name_to_record):
    manual = MANUAL_CANDIDATES.get(normalize(component))
    if not manual:
        return None
    target_name, confidence, reason = manual
    target = name_to_record.get(normalize(target_name))
    if not target:
        return None
    return {
        "suggested_ddinter_id": target[0],
        "suggested_ddinter_name": target[1],
        "confidence": confidence,
        "evidence_source": "curated_ai_candidate",
        "reason": reason,
    }


def choose_rx(component: str, same_bridge, relation_bridge):
    for method, form in candidate_forms(component):
        hits = same_bridge.get(form)
        if hits and len({hit[1] for hit in hits}) == 1:
            rxcui, ddinter_id, name = hits[0]
            return {
                "suggested_ddinter_id": ddinter_id,
                "suggested_ddinter_name": name,
                "confidence": "high",
                "evidence_source": "RxNorm_same_RxCUI",
                "reason": f"{method}: {form}; RxCUI {rxcui}",
            }
    for method, form in candidate_forms(component):
        hits = relation_bridge.get(form)
        if hits and len({hit[1] for hit in hits}) == 1:
            rxcui, ddinter_id, name = hits[0]
            return {
                "suggested_ddinter_id": ddinter_id,
                "suggested_ddinter_name": name,
                "confidence": "medium",
                "evidence_source": "RxNorm_active_ingredient_or_moiety_relation",
                "reason": f"{method}: {form}; related RxCUI {rxcui}",
            }
    return None


def choose_low_fuzzy(component: str, ddinter_vocab: pd.DataFrame):
    component_norm = normalize(component)
    if len(component_norm) < 8:
        return None

    best = []
    for ddinter_id, name in ddinter_vocab.itertuples(index=False):
        name_norm = normalize(name)
        ratio = difflib.SequenceMatcher(None, component_norm, name_norm).ratio()
        if ratio >= 0.97:
            best.append((ratio, str(ddinter_id), str(name)))

    if not best:
        return None

    best.sort(reverse=True)
    if len({name for _, _, name in best[:3]}) > 1 and best[0][0] - best[1][0] < 0.02:
        return None

    ratio, ddinter_id, name = best[0]
    return {
        "suggested_ddinter_id": ddinter_id,
        "suggested_ddinter_name": name,
        "confidence": "low",
        "evidence_source": "string_similarity_candidate",
        "reason": f"very close normalized-string match; similarity={ratio:.3f}",
    }


def choose_direct(component: str, name_to_record):
    for method, form in candidate_forms(component):
        target = name_to_record.get(form)
        if target:
            return {
                "suggested_ddinter_id": target[0],
                "suggested_ddinter_name": target[1],
                "confidence": "high" if method in {"raw", "salt_form_removed"} else "medium",
                "evidence_source": "DDInter_vocabulary_after_normalization",
                "reason": f"{method}: {form}",
            }
    return None


def main() -> None:
    unmatched_counts = load_unmatched_components()
    ddinter_vocab, name_to_record = load_ddinter_vocab()
    same_bridge, relation_bridge = load_rxnorm_bridge(ddinter_vocab)

    rows = []
    for component, frequency in unmatched_counts.most_common():
        candidate = (
            choose_manual(component, name_to_record)
            or choose_direct(component, name_to_record)
            or choose_rx(component, same_bridge, relation_bridge)
        )
        if candidate is None and is_non_mappable(component):
            candidate = {
                "suggested_ddinter_id": "",
                "suggested_ddinter_name": "",
                "confidence": "not_mappable",
                "evidence_source": "rule_based_exclusion",
                "reason": "formulation, excipient, vaccine strain/antigen, or regulatory descriptor",
            }
        if candidate is None:
            candidate = choose_low_fuzzy(component, ddinter_vocab)
        if candidate is None:
            candidate = {
                "suggested_ddinter_id": "",
                "suggested_ddinter_name": "",
                "confidence": "no_candidate",
                "evidence_source": "",
                "reason": "no credible DDInter target found by current rules",
            }
        rows.append(
            {
                "source_component": component,
                "frequency": frequency,
                **candidate,
                "review_status": "pending_review"
                if candidate["confidence"] in {"high", "medium", "low"}
                else "not_for_auto_mapping",
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT, index=False)

    print(f"Input unmatched unique components: {len(out)}")
    print(f"Input unmatched total occurrences: {int(out['frequency'].sum())}")
    print("")
    print("Confidence counts by unique component:")
    print(out["confidence"].value_counts(dropna=False).to_string())
    print("")
    print("Confidence counts weighted by occurrence:")
    print(out.groupby("confidence")["frequency"].sum().sort_values(ascending=False).to_string())
    print("")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
