import csv
import json
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation


CANDIDATES_FILE = "data/candidates.json"
INPUT_FILE = "data/contributions_all.csv"
OUTPUT_FILE = "data/donor_summary.csv"
# Campaign-finance exports sometimes use a different version
# of a candidate's name than candidates.json.
ALTERNATE_ORGANIZATION_NAMES = {
    "matthew s dawson": "Matt S. Dawson",
    "robert e craven jr": "Robert E. Craven, Sr.",
}

def normalize_name(value):
    """
    Normalize a candidate/organization name for matching.

    Examples:
        K. Joseph Shekarchi -> k joseph shekarchi
        K Joseph Shekarchi  -> k joseph shekarchi
        TINA  SPEARS        -> tina spears
    """

    value = value or ""

    value = value.lower().strip()

    value = value.replace("'", "")
    value = value.replace("’", "")

    value = re.sub(r"[^a-z0-9]+", " ", value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


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


def clean(value):
    if value is None:
        return ""
    return str(value).strip()

def main():

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — BUILD DONOR SUMMARY")
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

    candidates_with_org = [
        c for c in candidates
        if c.get("org_id")
    ]

    print(
        "Candidates with Org ID:",
        len(candidates_with_org)
    )

    # ---------------------------------------------------------
    # Read unified contribution file
    # ---------------------------------------------------------

    print()
    print("Reading:", INPUT_FILE)

    relationships = {}

    total_rows = 0
    total_amount = Decimal("0")

    matched_rows = 0
    unmatched_rows = 0

    unmatched_orgs = defaultdict(int)

    # ---------------------------------------------------------
    # Process transactions
    # ---------------------------------------------------------

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            total_rows += 1

            amount = money(
                row.get("Amount", "")
            )

            total_amount += amount

            # -------------------------------------------------
            # Candidate information is already present in the
            # unified contributions file.
            # -------------------------------------------------

            candidate_name = clean(
                row.get("candidate")
            )

            candidate_id = clean(
                row.get("candidate_id")
            )

            if not candidate_name or not candidate_id:

                unmatched_rows += 1

                unmatched_orgs[
                    candidate_name or "(missing candidate)"
                ] += 1

                continue

            matched_rows += 1

            # -------------------------------------------------
            # Donor information
            # -------------------------------------------------

            first_name = clean(
                row.get("FirstName")
            )

            last_name = clean(
                row.get("LastName")
            )

            full_name = clean(
                row.get("FullName")
            )

            if not full_name:

                full_name = " ".join(
                    x
                    for x in [
                        first_name,
                        last_name
                    ]
                    if x
                )

            address = ""

            city_st_zip = ""

            employer = clean(
                row.get("EmployerName")
            )

            # -------------------------------------------------
            # Relationship identity
            #
            # Same donor + same candidate = one relationship.
            # Address changes do NOT create a new relationship.
            # -------------------------------------------------

            relationship_key = (
                candidate_id,
                normalize_name(full_name)
            )

            # -------------------------------------------------
            # Create relationship
            # -------------------------------------------------

            if relationship_key not in relationships:

                relationships[
                    relationship_key
                ] = {
                    "Donor": full_name,
                    "FirstName": first_name,
                    "LastName": last_name,
                    "Address": address,
                    "CityStZip": city_st_zip,
                    "Employer": employer,
                    "Candidate":
                        candidate_name,
                    "CandidateID":
                        candidate_id,
                    "OrgID":
                        clean(row.get("org_id")),
                    "Chamber":
                        clean(row.get("chamber")),
                    "District":
                        clean(row.get("district")),
                    "Party":
                        clean(row.get("party")),

                    "ContributionCount": 0,

                    "TotalAmount":
                        Decimal("0"),

                    "FirstContribution":
                        clean(
                            row.get("ReceiptDate")
                        ),

                    "LastContribution":
                        clean(
                            row.get("ReceiptDate")
                        ),
                }

            relationship = relationships[
                relationship_key
            ]

            relationship[
                "ContributionCount"
            ] += 1

            relationship[
                "TotalAmount"
            ] += amount

            # -------------------------------------------------
            # Update dates
            # -------------------------------------------------

            receipt_date = clean(
                row.get("ReceiptDate")
            )

            if receipt_date:

                first_date = relationship[
                    "FirstContribution"
                ]

                last_date = relationship[
                    "LastContribution"
                ]

                if (
                    not first_date
                    or receipt_date < first_date
                ):

                    relationship[
                        "FirstContribution"
                    ] = receipt_date

                if (
                    not last_date
                    or receipt_date > last_date
                ):

                    relationship[
                        "LastContribution"
                    ] = receipt_date

    # ---------------------------------------------------------
    # Write summary
    # ---------------------------------------------------------

    fieldnames = [
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

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        sorted_relationships = sorted(
            relationships.values(),
            key=lambda x: (
                x["Candidate"].lower(),
                -x["TotalAmount"],
                x["Donor"].lower(),
            )
        )

        for relationship in sorted_relationships:

            writer.writerow({

                "Donor":
                    relationship["Donor"],

                "FirstName":
                    relationship["FirstName"],

                "LastName":
                    relationship["LastName"],

                "Address":
                    relationship["Address"],

                "CityStZip":
                    relationship["CityStZip"],

                "Employer":
                    relationship["Employer"],

                "Candidate":
                    relationship["Candidate"],

                "CandidateID":
                    relationship["CandidateID"],

                "OrgID":
                    relationship["OrgID"],

                "Chamber":
                    relationship["Chamber"],

                "District":
                    relationship["District"],

                "Party":
                    relationship["Party"],

                "ContributionCount":
                    relationship[
                        "ContributionCount"
                    ],

                "TotalAmount":
                    f"{relationship['TotalAmount']:.2f}",

                "FirstContribution":
                    relationship[
                        "FirstContribution"
                    ],

                "LastContribution":
                    relationship[
                        "LastContribution"
                    ],
            })

    # ---------------------------------------------------------
    # Calculate matched amount
    # ---------------------------------------------------------

    matched_amount = sum(
        r["TotalAmount"]
        for r in relationships.values()
    )

    unmatched_amount = (
        total_amount - matched_amount
    )

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)

    print()
    print(
        "Input transaction rows:",
        total_rows
    )

    print(
        "Total transaction amount:",
        f"${total_amount:,.2f}"
    )

    print(
        "Matched transaction rows:",
        matched_rows
    )

    print(
        "Matched transaction amount:",
        f"${matched_amount:,.2f}"
    )

    print(
        "Unmatched transaction rows:",
        unmatched_rows
    )

    print(
        "Unmatched amount:",
        f"${unmatched_amount:,.2f}"
    )

    print(
        "Donor/candidate relationships:",
        len(relationships)
    )

    print(
        "Unmatched organizations:",
        len(unmatched_orgs)
    )

    if unmatched_orgs:

        print()
        print(
            "UNMATCHED ORGANIZATIONS:"
        )

        for name, count in sorted(
            unmatched_orgs.items(),
            key=lambda x: (-x[1], x[0])
        ):

            print(
                f"  {name!r} -> {count} rows"
            )

    print()
    print("Output:", OUTPUT_FILE)

    if os.path.exists(OUTPUT_FILE):

        size = os.path.getsize(
            OUTPUT_FILE
        )

        print(
            "File size:",
            f"{size / 1024:.1f} KB"
        )


if __name__ == "__main__":
    main()
