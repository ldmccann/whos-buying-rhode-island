import json
import re
from pathlib import Path

import pandas as pd


HOUSE_URL = "https://webserver.rilegislature.gov/HVotes/representatives.xlsx"
SENATE_URL = "https://webserver.rilegislature.gov/SVotes/senators.xls"

OUTPUT = Path("data/candidates.json")


def clean_text(value):
    if pd.isna(value):
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_name(name):
    """
    Convert:

        Representative Edith H. Ajello
        Senator Jacob E. Bissaillon

    into:

        Edith H. Ajello
        Jacob E. Bissaillon
    """

    name = clean_text(name)

    name = re.sub(
        r"^(Representative|Senator)\s+",
        "",
        name,
        flags=re.IGNORECASE,
    )

    return name.strip()


def make_candidate_id(chamber, district):
    """
    Stable ID based on chamber + district.

    Example:

        ri-house-36
        ri-senate-14
    """

    return f"ri-{chamber.lower()}-{int(district)}"


def load_house():
    print("Downloading House roster...")

    df = pd.read_excel(HOUSE_URL)

    candidates = []

    for _, row in df.iterrows():
        district = row["House District"]

        if pd.isna(district):
            continue

        name = normalize_name(row["Name"])

        if not name:
            continue

        candidates.append(
            {
                "candidate_id": make_candidate_id(
                    "House",
                    district,
                ),
                "name": name,
                "chamber": "House",
                "district": int(district),
                "party": clean_text(
                    row["Party Affiliation"]
                ),
                "communities": clean_text(
                    row["City/Town Represented"]
                ),
                "email": clean_text(
                    row["E-mail Address"]
                ),
            }
        )

    return candidates


def load_senate():
    print("Downloading Senate roster...")

    df = pd.read_excel(
        SENATE_URL,
        engine="xlrd",
    )

    candidates = []

    for _, row in df.iterrows():
        district = row["Senate District"]

        if pd.isna(district):
            continue

        name = normalize_name(row["Name"])

        if not name:
            continue

        candidates.append(
            {
                "candidate_id": make_candidate_id(
                    "Senate",
                    district,
                ),
                "name": name,
                "chamber": "Senate",
                "district": int(district),
                "party": clean_text(
                    row["Party Affiliation"]
                ),
                "communities": clean_text(
                    row["City/Town Represented"]
                ),
                "email": clean_text(
                    row["E-mail Address"]
                ),
            }
        )

    return candidates


def main():
    house = load_house()
    senate = load_senate()

    candidates = house + senate

    candidates.sort(
        key=lambda c: (
            c["chamber"],
            c["district"],
        )
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            candidates,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("ROSTER COMPLETE")
    print("=" * 60)
    print(f"House:  {len(house)}")
    print(f"Senate: {len(senate)}")
    print(f"Total:  {len(candidates)}")
    print()
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
