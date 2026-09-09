from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REVIEW_FILE = BASE_DIR / "high-medium-reviewed - Sheet1.csv"
MANUAL_OUTPUT = BASE_DIR / "manual_ddinter_dictionary_2026-09-09.csv"
RESOLUTION_OUTPUT = BASE_DIR / "bpom_component_resolution_dictionary_2026-09-09.csv"


def main() -> None:
    reviewed = pd.read_csv(REVIEW_FILE, dtype="string").fillna("")
    reviewed["review_result_norm"] = reviewed["review_result"].str.strip().str.upper()

    confirmed = reviewed[reviewed["review_result_norm"].eq("Y")].copy()
    confirmed = confirmed[
        [
            "source_component",
            "frequency",
            "suggested_ddinter_id",
            "suggested_ddinter_name",
            "confidence",
            "evidence_source",
            "reason",
        ]
    ].rename(
        columns={
            "source_component": "bpom_component",
            "suggested_ddinter_id": "ddinter_id",
            "suggested_ddinter_name": "ddinter_name",
        }
    )
    confirmed["mapping_status"] = "confirmed_manual_mapping"
    confirmed["review_result"] = "Y"
    confirmed.to_csv(MANUAL_OUTPUT, index=False)

    resolution = reviewed.copy()
    resolution["component_status"] = "recognized_bpom_component_absent_from_current_ddinter_mecddi"
    resolution.loc[
        resolution["review_result_norm"].eq("Y"),
        "component_status",
    ] = "confirmed_manual_mapping"
    resolution.loc[
        resolution["confidence"].eq("not_mappable"),
        "component_status",
    ] = "not_mappable_to_interaction_ingredient"

    resolution["display_message"] = (
        "Recognized drug ingredient, but absent from current DDInter/MecDDI interaction dataset."
    )
    resolution.loc[
        resolution["component_status"].eq("confirmed_manual_mapping"),
        "display_message",
    ] = "Confirmed manual mapping to DDInter ingredient."
    resolution.loc[
        resolution["component_status"].eq("not_mappable_to_interaction_ingredient"),
        "display_message",
    ] = "Component is not suitable for DDInter/MecDDI ingredient interaction checking."

    resolution = resolution[
        [
            "source_component",
            "frequency",
            "component_status",
            "suggested_ddinter_id",
            "suggested_ddinter_name",
            "confidence",
            "evidence_source",
            "reason",
            "review_status",
            "review_result",
            "display_message",
        ]
    ]
    resolution.to_csv(RESOLUTION_OUTPUT, index=False)

    print(f"Confirmed manual mappings: {len(confirmed)}")
    print(f"Confirmed mapping occurrences: {confirmed['frequency'].astype(int).sum()}")
    print("")
    print("Component status counts:")
    print(resolution["component_status"].value_counts().to_string())
    print("")
    print("Component status weighted by frequency:")
    print(
        resolution.assign(freq=resolution["frequency"].astype(int))
        .groupby("component_status")["freq"]
        .sum()
        .sort_values(ascending=False)
        .to_string()
    )
    print("")
    print(f"Saved: {MANUAL_OUTPUT}")
    print(f"Saved: {RESOLUTION_OUTPUT}")


if __name__ == "__main__":
    main()
