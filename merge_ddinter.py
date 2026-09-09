from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
SEVERITY_PATTERN = "ddinter_downloads_code_*.csv"
MECHANISM_FILE = "DDInter2_0_mecddi.csv"
OUTPUT_FILE = "ddinter_merged.csv"


def pair_key(left: pd.Series, right: pd.Series) -> pd.DataFrame:
    pairs = pd.concat(
        [left.astype("string").rename("id_1"), right.astype("string").rename("id_2")],
        axis=1,
    )
    return pd.DataFrame(
        {
            "pair_id_1": pairs.min(axis=1),
            "pair_id_2": pairs.max(axis=1),
        }
    )


def main() -> None:
    severity_files = sorted(BASE_DIR.glob(SEVERITY_PATTERN))
    if not severity_files:
        raise FileNotFoundError(f"No files matched {SEVERITY_PATTERN!r}")

    severity_frames = [
        pd.read_csv(
            path,
            dtype={
                "DDInterID_A": "string",
                "Drug_A": "string",
                "DDInterID_B": "string",
                "Drug_B": "string",
                "Level": "string",
            },
        )
        for path in severity_files
    ]
    severity = pd.concat(severity_frames, ignore_index=True).drop_duplicates()
    severity = pd.concat(
        [severity, pair_key(severity["DDInterID_A"], severity["DDInterID_B"])],
        axis=1,
    )

    severity_pairs = (
        severity.sort_values(["pair_id_1", "pair_id_2"])
        .drop_duplicates(["pair_id_1", "pair_id_2"], keep="first")
        .rename(
            columns={
                "DDInterID_A": "drug_a_id",
                "Drug_A": "drug_a_name",
                "DDInterID_B": "drug_b_id",
                "Drug_B": "drug_b_name",
                "Level": "severity",
            }
        )
        [
            [
                "pair_id_1",
                "pair_id_2",
                "drug_a_id",
                "drug_a_name",
                "drug_b_id",
                "drug_b_name",
                "severity",
            ]
        ]
    )

    mechanism = pd.read_csv(
        BASE_DIR / MECHANISM_FILE,
        dtype={
            "ddiname": "string",
            "drug1": "string",
            "drug2": "string",
            "drug1_name": "string",
            "drug2_name": "string",
            "interaction": "string",
        },
        index_col=0,
    )
    mechanism = pd.concat([mechanism, pair_key(mechanism["drug1"], mechanism["drug2"])], axis=1)

    mechanism_pairs = (
        mechanism.sort_values(["pair_id_1", "pair_id_2"])
        .drop_duplicates(["pair_id_1", "pair_id_2"], keep="first")
        .rename(columns={"interaction": "mechanism"})
        [["pair_id_1", "pair_id_2", "drug1", "drug2", "drug1_name", "drug2_name", "mechanism"]]
    )

    merged = severity_pairs.merge(
        mechanism_pairs,
        on=["pair_id_1", "pair_id_2"],
        how="outer",
        indicator=True,
    )

    missing_severity = merged["severity"].isna()
    merged["drug_a_id"] = merged["drug_a_id"].fillna(merged["drug1"])
    merged["drug_a_name"] = merged["drug_a_name"].fillna(merged["drug1_name"])
    merged["drug_b_id"] = merged["drug_b_id"].fillna(merged["drug2"])
    merged["drug_b_name"] = merged["drug_b_name"].fillna(merged["drug2_name"])
    merged["has_mechanism"] = merged["mechanism"].notna()
    merged["severity_source"] = pd.NA
    merged.loc[merged["severity"].notna(), "severity_source"] = "DDInter"
    merged["mechanism_source"] = pd.NA
    merged.loc[merged["mechanism"].notna(), "mechanism_source"] = "MecDDI"
    merged["interaction_id"] = merged["pair_id_1"] + "_" + merged["pair_id_2"]

    output = merged[
        [
            "interaction_id",
            "drug_a_id",
            "drug_a_name",
            "drug_b_id",
            "drug_b_name",
            "severity",
            "severity_source",
            "mechanism",
            "mechanism_source",
            "has_mechanism",
        ]
    ].sort_values(["drug_a_id", "drug_b_id"], ignore_index=True)

    output.to_csv(BASE_DIR / OUTPUT_FILE, index=False)

    both_count = int((merged["_merge"] == "both").sum())
    severity_without_mechanism_count = int((merged["_merge"] == "left_only").sum())
    mechanism_without_severity_count = int((merged["_merge"] == "right_only").sum())

    print(f"Severity files loaded: {len(severity_files)}")
    print(f"Total rows in merged severity data: {len(severity)}")
    print(f"Total rows in mechanism data: {len(mechanism)}")
    print(f"Total unique pairs in final output: {len(output)}")
    print(f"Count of pairs with severity but no mechanism: {severity_without_mechanism_count}")
    print(f"Count of pairs with mechanism but no severity: {mechanism_without_severity_count}")
    print(f"Count of pairs with both: {both_count}")
    print(f"Saved: {BASE_DIR / OUTPUT_FILE}")


if __name__ == "__main__":
    main()
