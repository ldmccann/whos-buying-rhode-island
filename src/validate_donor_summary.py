import csv
import os
from decimal import Decimal, InvalidOperation


INPUT_FILE = "data/donor_summary.csv"


EXPECTED_HEADERS = [
    "Donor",
    "FirstName",
    "LastName",
    "Address",
    "CityStZip",
    "Employer",
    "Candidate",
    "CandidateID",
    "OrgID",
    "Chamber",
    "District",
    "Party",
    "ContributionCount",
    "TotalAmount",
    "FirstContribution",
    "LastContribution",
]


def money(value):
    try:
        return Decimal(
            str(value)
            .strip()
            .replace("$", "")
            .replace(",", "")
        )
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def main():

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — VALIDATE DONOR SUMMARY")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):
        print()
        print("ERROR: File not found:")
        print(INPUT_FILE)
        return

    total_rows = 0
    total_amount = Decimal("0")
    total_contributions = 0

    bad_rows = []
    duplicate_keys = set()
    seen_keys = set()

    candidate_stats = {}

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        headers = reader.fieldnames or []

        print()
        print("Input:", INPUT_FILE)
        print("Columns:", len(headers))

        if headers != EXPECTED_HEADERS:
            print()
            print("HEADER ERROR")
            print()
            print("Expected:")
            print(EXPECTED_HEADERS)
            print()
            print("Found:")
            print(headers)
            return

        for row_number, row in enumerate(reader, start=2):

            total_rows += 1

            donor = row.get("Donor", "").strip()
            candidate = row.get("Candidate", "").strip()
            candidate_id = row.get("CandidateID", "").strip()
            org_id = row.get("OrgID", "").strip()

            amount = money(
                row.get("TotalAmount", "")
            )

            count_text = row.get(
                "ContributionCount",
                ""
            ).strip()

            # -------------------------------------------------
            # Required fields
            # -------------------------------------------------

            if not donor:
                bad_rows.append(
                    (row_number, "missing Donor")
                )

            if not candidate:
                bad_rows.append(
                    (row_number, "missing Candidate")
                )

            if not candidate_id:
                bad_rows.append(
                    (row_number, "missing CandidateID")
                )

            if not org_id:
                bad_rows.append(
                    (row_number, "missing OrgID")
                )

            # -------------------------------------------------
            # Contribution count
            # -------------------------------------------------

            try:
                count = int(count_text)

                if count <= 0:
                    bad_rows.append(
                        (
                            row_number,
                            "invalid ContributionCount"
                        )
                    )

                total_contributions += count

            except ValueError:
                bad_rows.append(
                    (
                        row_number,
                        "invalid ContributionCount"
                    )
                )

            # -------------------------------------------------
            # Amount
            # -------------------------------------------------

            if amount < 0:
                bad_rows.append(
                    (
                        row_number,
                        "negative TotalAmount"
                    )
                )

            total_amount += amount

            # -------------------------------------------------
            # Duplicate donor/candidate relationship
            # -------------------------------------------------

            key = (
                org_id,
                donor.lower()
            )

            if key in seen_keys:
                duplicate_keys.add(key)
            else:
                seen_keys.add(key)

            # -------------------------------------------------
            # Candidate statistics
            # -------------------------------------------------

            if candidate not in candidate_stats:

                candidate_stats[candidate] = {
                    "relationships": 0,
                    "contributions": 0,
                    "amount": Decimal("0"),
                }

            candidate_stats[candidate][
                "relationships"
            ] += 1

            candidate_stats[candidate][
                "contributions"
            ] += count if count_text.isdigit() else 0

            candidate_stats[candidate][
                "amount"
            ] += amount

    # ---------------------------------------------------------
    # Results
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    print()
    print(
        "Donor/candidate relationships:",
        total_rows
    )

    print(
        "Total summarized amount: ${:,.2f}".format(
            total_amount
        )
    )

    print(
        "Underlying contribution count:",
        total_contributions
    )

    print(
        "Unique donor/candidate keys:",
        len(seen_keys)
    )

    print(
        "Duplicate donor/candidate keys:",
        len(duplicate_keys)
    )

    print(
        "Bad rows:",
        len(bad_rows)
    )

    print(
        "Candidates represented:",
        len(candidate_stats)
    )

    # ---------------------------------------------------------
    # Top candidates
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("TOP 20 CANDIDATES BY DONATION AMOUNT")
    print("=" * 60)

    ranked = sorted(
        candidate_stats.items(),
        key=lambda item: item[1]["amount"],
        reverse=True
    )

    for i, (candidate, stats) in enumerate(
        ranked[:20],
        start=1
    ):

        print(
            "{:2}. {:35} {:5} donor rows  ${:12,.2f}".format(
                i,
                candidate,
                stats["relationships"],
                stats["amount"],
            )
        )

    # ---------------------------------------------------------
    # Bad rows
    # ---------------------------------------------------------

    if bad_rows:

        print()
        print("=" * 60)
        print("BAD ROWS")
        print("=" * 60)

        for row_number, reason in bad_rows[:25]:

            print(
                "Row {} -> {}".format(
                    row_number,
                    reason
                )
            )

    # ---------------------------------------------------------
    # Final result
    # ---------------------------------------------------------

    print()
    print("=" * 60)

    if (
        not bad_rows
        and total_amount == Decimal("1681423.50")
        and total_contributions == 6270
    ):

        print("VALIDATION PASSED")

    else:

        print("VALIDATION FAILED")

        if total_amount != Decimal("1681423.50"):
            print(
                "Amount mismatch: expected $1,681,423.50"
            )

        if total_contributions != 6270:
            print(
                "Contribution count mismatch: expected 6270"
            )

    print("=" * 60)


if __name__ == "__main__":
    main()
