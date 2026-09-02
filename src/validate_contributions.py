import csv
import json
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

CANDIDATES_FILE = "data/candidates.json"
CONTRIBUTIONS_DIR = "data/contributions"

EXPECTED_HEADERS = [
    "ContributionID",
    "ContDesc",
    "IncompleteDesc",
    "OrganizationName",
    "ViewIncomplete",
    "ReceiptDate",
    "DepositDate",
    "Amount",
    "ContribExplanation",
    "MPFMatchAmount",
    "FirstName",
    "LastName",
    "FullName",
    "Address",
    "CityStZip",
    "EmployerName",
    "EmpAddress",
    "EmpCityStZip",
    "ReceiptDesc",
    "BeginDate",
    "EndDate",
    "TransType",
]


def filename_key(name):
    """
    Normalize names for filename matching.

    Removes spaces, punctuation, periods, apostrophes, etc.
    This allows:

        William W.O'Brien
        william_w_o_brien

    to match.
    """
    return re.sub(r"[^a-z0-9]", "", name.strip().lower())


def money(value):
    try:
        return Decimal(
            value.strip()
            .replace("$", "")
            .replace(",", "")
        )
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def main():
    print("=" * 60)
    print("RI CAMPAIGN FINANCE — CONTRIBUTION DATA VALIDATION")
    print("=" * 60)

    # ---------------------------------------------------------
    # Load candidates
    # ---------------------------------------------------------

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    print()
    print("Candidates:", len(candidates))

    with_org = [
        c for c in candidates
        if c.get("org_id")
    ]

    print("With Org ID:", len(with_org))

    # ---------------------------------------------------------
    # Build expected filename map
    # ---------------------------------------------------------

    expected = {}

    for candidate in candidates:
        if not candidate.get("org_id"):
            continue

        key = filename_key(candidate["name"])

        expected[key] = {
            "name": candidate["name"],
            "candidate_id": candidate.get("candidate_id"),
            "org_id": candidate.get("org_id"),
            "chamber": candidate.get("chamber"),
            "district": candidate.get("district"),
            "party": candidate.get("party"),
        }

    # ---------------------------------------------------------
    # Find CSV files
    # ---------------------------------------------------------

    csv_files = sorted(
        f
        for f in os.listdir(CONTRIBUTIONS_DIR)
        if f.lower().endswith(".csv")
    )

    print()
    print("CSV files:", len(csv_files))

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------

    valid_files = []
    bad_files = []
    unknown_files = []

    total_rows = 0
    total_amount = Decimal("0")

    contribution_ids = defaultdict(list)

    candidate_stats = {}

    for candidate in candidates:
        if candidate.get("org_id"):
            candidate_stats[candidate["name"]] = {
                "org_id": candidate.get("org_id"),
                "rows": 0,
                "amount": Decimal("0"),
            }

    # ---------------------------------------------------------
    # Validate each file
    # ---------------------------------------------------------

    for filename in csv_files:
        filepath = os.path.join(
            CONTRIBUTIONS_DIR,
            filename
        )

        stem = filename[:-4]

        if stem.endswith("_2026_q1"):
            stem = stem[:-8]

        candidate = expected.get(filename_key(stem))

        if not candidate:
            unknown_files.append(filename)

        file_ok = True
        file_rows = 0
        file_amount = Decimal("0")

        try:
            with open(
                filepath,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as f:

                reader = csv.reader(f)

                try:
                    headers = next(reader)
                except StopIteration:
                    bad_files.append({
                        "file": filename,
                        "reason": "empty file",
                    })
                    continue

                if headers != EXPECTED_HEADERS:
                    bad_files.append({
                        "file": filename,
                        "reason": "unexpected headers",
                        "header_count": len(headers),
                        "headers": headers,
                    })
                    continue

                for row_number, row in enumerate(reader, start=2):

                    if not row:
                        continue

                    if len(row) != len(EXPECTED_HEADERS):
                        file_ok = False

                        bad_files.append({
                            "file": filename,
                            "reason": "wrong column count",
                            "row": row_number,
                            "columns": len(row),
                        })

                        # Stop checking this file after five
                        # malformed rows.
                        malformed_count = sum(
                            1
                            for x in bad_files
                            if x["file"] == filename
                        )

                        if malformed_count >= 5:
                            break

                        continue

                    record = dict(
                        zip(headers, row)
                    )

                    contribution_id = record.get(
                        "ContributionID",
                        ""
                    )

                    if contribution_id:
                        contribution_ids[
                            contribution_id
                        ].append(filename)

                    amount = money(
                        record.get("Amount", "")
                    )

                    file_amount += amount
                    total_amount += amount

                    file_rows += 1
                    total_rows += 1

            if file_ok:
                valid_files.append(filename)

            # -------------------------------------------------
            # Candidate statistics
            # -------------------------------------------------

            if candidate:
                stats = candidate_stats[candidate["name"]]

                stats["rows"] += file_rows
                stats["amount"] += file_amount

        except Exception as e:

            bad_files.append({
                "file": filename,
                "reason": repr(e),
            })

    # ---------------------------------------------------------
    # Duplicate IDs
    # ---------------------------------------------------------

    duplicates = {
        cid: files
        for cid, files in contribution_ids.items()
        if len(files) > 1
    }

    unique_ids = len(contribution_ids)

    # ---------------------------------------------------------
    # Candidate coverage
    # ---------------------------------------------------------

    candidates_with_transactions = [
        name
        for name, stats in candidate_stats.items()
        if stats["rows"] > 0
    ]

    candidates_without_transactions = [
        name
        for name, stats in candidate_stats.items()
        if stats["rows"] == 0
    ]

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("FILE VALIDATION")
    print("=" * 60)

    print()
    print("Valid CSV files:", len(valid_files))
    print("Bad CSV files:", len(bad_files))
    print("Unknown CSV files:", len(unknown_files))

    if unknown_files:
        print()
        print("UNKNOWN FILES:")
        for filename in unknown_files:
            print(" ", filename)

    if bad_files:
        print()
        print("BAD FILES / ROWS:")
        for item in bad_files:
            print(" ", item)

    print()
    print("=" * 60)
    print("TRANSACTION TOTALS")
    print("=" * 60)

    print()
    print("Total transaction rows:", total_rows)
    print("Unique Contribution IDs:", unique_ids)
    print("Duplicate Contribution IDs:", len(duplicates))
    print(
        "Total amount: ${:,.2f}".format(total_amount)
    )

    if duplicates:
        print()
        print("DUPLICATE IDS:")
        for cid, files in duplicates.items():
            print(" ", cid, "->", files)

    print()
    print("=" * 60)
    print("CANDIDATE COVERAGE")
    print("=" * 60)

    print()
    print(
        "Candidates with transactions:",
        len(candidates_with_transactions)
    )

    print(
        "Candidates with no transaction rows:",
        len(candidates_without_transactions)
    )

    if candidates_without_transactions:
        print()
        print("NO TRANSACTION ROWS:")

        for name in candidates_without_transactions:
            stats = candidate_stats[name]

            print(
                " ",
                name,
                "(Org ID {})".format(stats["org_id"])
            )

    # ---------------------------------------------------------
    # Top 20
    # ---------------------------------------------------------

    ranked = sorted(
        candidate_stats.items(),
        key=lambda item: item[1]["amount"],
        reverse=True
    )

    print()
    print("=" * 60)
    print("TOP 20 BY CONTRIBUTION AMOUNT")
    print("=" * 60)

    print()

    for index, (name, stats) in enumerate(
        ranked[:20],
        start=1
    ):
        print(
            "{:2}. {:35} {:5} rows  ${:12,.2f}".format(
                index,
                name,
                stats["rows"],
                stats["amount"]
            )
        )

    # ---------------------------------------------------------
    # Save JSON report
    # ---------------------------------------------------------

    report = {
        "candidates": len(candidates),
        "with_org_id": len(with_org),
        "csv_files": len(csv_files),
        "valid_csv_files": len(valid_files),
        "bad_csv_files": len(bad_files),
        "unknown_csv_files": len(unknown_files),
        "unknown_files": unknown_files,
        "total_transaction_rows": total_rows,
        "unique_contribution_ids": unique_ids,
        "duplicate_contribution_ids": len(duplicates),
        "total_amount": str(total_amount),
        "candidates_with_transactions": len(
            candidates_with_transactions
        ),
        "candidates_without_transactions": len(
            candidates_without_transactions
        ),
        "candidate_stats": {
            name: {
                "org_id": stats["org_id"],
                "rows": stats["rows"],
                "amount": str(stats["amount"]),
            }
            for name, stats in candidate_stats.items()
        },
    }

    report_file = "data/contribution_validation.json"

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            report,
            f,
            indent=2
        )

    print()
    print("=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)

    print()
    print("Report saved:", report_file)


if __name__ == "__main__":
    main()
