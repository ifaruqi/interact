"""
Simple drug interaction checker (MVP prototype).

Usage:
    python interaction_checker.py

Requires: pandas
Expects a merged CSV with columns:
    interaction_id, drug_a_id, drug_a_name, drug_b_id, drug_b_name,
    severity, severity_source, mechanism
(built by joining DDInter severity files + MecDDI mechanism file)

Note on severity values:
    - "Unknown" (with severity_source = "DDInter") means DDInter reviewed the
      pair but could not classify a risk level. This is NOT the same as a
      blank severity, which means no DDInter severity record exists for
      this pair at all. The script reports these differently.
"""

import pandas as pd
import sys

DATA_PATH = "ddinter_merged.csv"  # change to your actual merged file path


def load_data(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str)
    except FileNotFoundError:
        print(f"ERROR: could not find '{path}'. Update DATA_PATH to your merged CSV.")
        sys.exit(1)

    # Normalize names for matching (lowercase, stripped)
    df["drug_a_name_norm"] = df["drug_a_name"].str.strip().str.lower()
    df["drug_b_name_norm"] = df["drug_b_name"].str.strip().str.lower()
    return df


def build_drug_index(df: pd.DataFrame):
    """Return a sorted list of unique drug names (for suggestions)."""
    names = pd.concat([df["drug_a_name"], df["drug_b_name"]]).dropna().unique()
    return sorted(set(n.strip() for n in names))


def suggest_drugs(query: str, drug_list, limit: int = 10):
    """Return drug names containing the query substring (case-insensitive)."""
    q = query.strip().lower()
    if not q:
        return []
    matches = [d for d in drug_list if q in d.lower()]
    return matches[:limit]


def pick_drug(drug_list) -> str:
    """Interactive: type letters, see suggestions, pick one."""
    while True:
        query = input("  Type part of drug name (or 'done' to finish): ").strip()
        query = query.strip("'\"")  # strip stray quotes if pasted/typed
        if query.lower() == "done":
            return None
        matches = suggest_drugs(query, drug_list)
        if not matches:
            print("  No matches found. Try again.")
            continue
        print("  Suggestions:")
        for i, m in enumerate(matches, 1):
            print(f"    {i}. {m}")
        choice = input("  Pick a number ('done' to finish, blank to search again): ").strip()
        choice = choice.strip("'\"")
        if choice.lower() == "done":
            return None
        if not choice:
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                return matches[idx]
        except ValueError:
            pass
        print("  Invalid choice, try again.")


def collect_drug_list(label: str, drug_list) -> list:
    print(f"\n--- Enter {label} (one at a time) ---")
    selected = []
    while True:
        drug = pick_drug(drug_list)
        if drug is None:
            break
        selected.append(drug)
        print(f"  Added: {drug}")
    return selected


def find_interaction(df: pd.DataFrame, drug1: str, drug2: str):
    """Look up interaction(s) between two drug names, either order."""
    d1, d2 = drug1.strip().lower(), drug2.strip().lower()
    match = df[
        ((df["drug_a_name_norm"] == d1) & (df["drug_b_name_norm"] == d2))
        | ((df["drug_a_name_norm"] == d2) & (df["drug_b_name_norm"] == d1))
    ]
    return match


def check_all_interactions(df: pd.DataFrame, current_meds: list, new_meds: list):
    print("\n" + "=" * 60)
    print("INTERACTION CHECK RESULTS")
    print("=" * 60)

    if not current_meds or not new_meds:
        print("Need at least one current medication and one new medication.")
        return

    found_any = False
    for new_drug in new_meds:
        for current_drug in current_meds:
            match = find_interaction(df, current_drug, new_drug)
            if match.empty:
                print(f"\n[{new_drug}] vs [{current_drug}]: No interaction record found "
                      f"(NOT the same as 'confirmed safe' — absence of data, not absence of risk).")
                continue

            found_any = True
            for _, row in match.iterrows():
                raw_severity = row.get("severity")
                sev_source = row.get("severity_source") or None
                mechanism = row.get("mechanism") or None

                if pd.isna(raw_severity) or not str(raw_severity).strip():
                    severity_display = "No severity record (DDInter has no rating for this pair)"
                elif str(raw_severity).strip().lower() == "unknown":
                    severity_display = "Unknown (DDInter reviewed this pair but could not classify risk)"
                else:
                    severity_display = f"{raw_severity}  (source: {sev_source})"

                mechanism_display = mechanism if (mechanism and str(mechanism).strip() and not pd.isna(mechanism)) \
                    else "No mechanism description available (source: MecDDI has no entry for this pair)"

                print(f"\n[{new_drug}] vs [{current_drug}]")
                print(f"  Severity   : {severity_display}")
                print(f"  Mechanism  : {mechanism_display}")

    if not found_any:
        print("\nNo interactions found in database for any pair checked. "
              "Verify against a clinical reference before relying on this result.")

    print("\n" + "=" * 60)
    print("Reminder: this is a prototype using free/research datasets "
          "(DDInter + MecDDI), not a clinical-grade source. Cross-check "
          "significant findings with a pharmacist or Lexicomp/Micromedex.")
    print("=" * 60)


def main():
    print("Loading interaction database...")
    df = load_data(DATA_PATH)
    drug_list = build_drug_index(df)
    print(f"Loaded {len(df)} interaction records covering {len(drug_list)} drugs.\n")

    current_meds = collect_drug_list("CURRENT medications the patient is taking", drug_list)
    new_meds = collect_drug_list("DRUG(S) TO BE PRESCRIBED", drug_list)

    check_all_interactions(df, current_meds, new_meds)


if __name__ == "__main__":
    main()
