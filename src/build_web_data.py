import csv
import json
import os
from decimal import Decimal


CANDIDATES_FILE = "data/candidates.json"
SUMMARY_FILE = "data/donor_summary.csv"
OUTPUT_FILE = "data/donor_summary.json"


def money(value):
    try:
        return Decimal(str(value).replace("$", "").replace(",", ""))
    except Exception:
        return Decimal("0")


def main():

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — BUILD WEBSITE DATA")
    print("=" * 60)

    # ---------------------------------------------------------
    # Load candidates
    # ---------------------------------------------------------

    with open(
        CANDIDATES_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        candidates = json.load(f)

    print()
    print("Candidates:", len(candidates))

    # ---------------------------------------------------------
    # Load donor summary
    # ---------------------------------------------------------

    print("Reading:", SUMMARY_FILE)

    candidate_data = {}

    with open(
        SUMMARY_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            candidate_id = row["CandidateID"]

            if candidate_id not in candidate_data:

                candidate_data[candidate_id] = {
                    "candidate": row["Candidate"],
                    "candidate_id": candidate_id,
                    "org_id": row["OrgID"],
                    "chamber": row["Chamber"],
                    "district": row["District"],
                    "party": row["Party"],
                    "donor_count": 0,
                    "total_amount": Decimal("0"),
                    "donors": []
                }

            candidate = candidate_data[candidate_id]

            amount = money(row["TotalAmount"])

            candidate["donor_count"] += 1
            candidate["total_amount"] += amount

            candidate["donors"].append({
                "name": row["Donor"],
                "first_name": row["FirstName"],
                "last_name": row["LastName"],
                "address": row["Address"],
                "city_state_zip": row["CityStZip"],
                "employer": row["Employer"],
                "contribution_count": int(
                    row["ContributionCount"]
                ),
                "total_amount": float(amount),
                "first_contribution": row["FirstContribution"],
                "last_contribution": row["LastContribution"]
            })

    # ---------------------------------------------------------
    # Add candidates that have no contributions
    # ---------------------------------------------------------

    for candidate in candidates:

        candidate_id = candidate.get("candidate_id")

        if not candidate_id:
            continue

        if candidate_id not in candidate_data:

            candidate_data[candidate_id] = {
                "candidate": candidate.get("name", ""),
                "candidate_id": candidate_id,
                "org_id": str(candidate.get("org_id", "")),
                "chamber": candidate.get("chamber", ""),
                "district": candidate.get("district", ""),
                "party": candidate.get("party", ""),
                "donor_count": 0,
                "total_amount": 0.0,
                "donors": []
            }

    # ---------------------------------------------------------
    # Sort donors within each candidate
    # ---------------------------------------------------------

    for candidate in candidate_data.values():

        candidate["donors"].sort(
            key=lambda donor: (
                -donor["total_amount"],
                donor["name"].lower()
            )
        )

        if isinstance(candidate["total_amount"], Decimal):
            candidate["total_amount"] = float(
                candidate["total_amount"]
            )

    # ---------------------------------------------------------
    # Sort candidates
    # ---------------------------------------------------------

    sorted_candidates = sorted(
        candidate_data.values(),
        key=lambda candidate: (
            candidate["candidate"].lower()
        )
    )

    # ---------------------------------------------------------
    # Build final website object
    # ---------------------------------------------------------

    output = {
        "period": "2026 Q1",
        "candidate_count": len(sorted_candidates),
        "candidates_with_contributions": sum(
            1
            for candidate in sorted_candidates
            if candidate["donor_count"] > 0
        ),
        "candidates": sorted_candidates
    }

    # ---------------------------------------------------------
    # Write JSON
    # ---------------------------------------------------------

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------

    total_donors = sum(
        candidate["donor_count"]
        for candidate in sorted_candidates
    )

    total_amount = sum(
        Decimal(str(candidate["total_amount"]))
        for candidate in sorted_candidates
    )

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print()
    print(
        "Candidates:",
        len(sorted_candidates)
    )
    print(
        "Candidates with contributions:",
        output["candidates_with_contributions"]
    )
    print(
        "Donor/candidate relationships:",
        total_donors
    )
    print(
        "Total amount:",
        f"${total_amount:,.2f}"
    )
    print()
    print("Output:", OUTPUT_FILE)

    if os.path.exists(OUTPUT_FILE):

        size = os.path.getsize(OUTPUT_FILE)

        print(
            "File size:",
            f"{size / 1024:.1f} KB"
        )


if __name__ == "__main__":
    main()
