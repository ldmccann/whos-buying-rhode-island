import csv
import json
import os
from decimal import Decimal, InvalidOperation


CANDIDATES_FILE = "data/candidates.json"
CONTRIBUTIONS_DIR = "data/contributions"
OUTPUT_FILE = "data/contributions_all.csv"

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


# ============================================================
# HELPERS
# ============================================================

def filename_key(name):
    return "".join(
        c for c in name.lower()
        if c.isalnum()
    )


def money(value):
    try:
        return Decimal(
            value.strip()
            .replace("$", "")
            .replace(",", "")
        )
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def is_historical_file(filename):
    return "_01-01-2020_12-31-2026.csv" in filename


def is_q1_file(filename):
    return (
        "_01-01-2026_03-31-2026.csv" in filename
        or "_2026_q1.csv" in filename
    )


def candidate_stem(filename):
    """
    Convert a contribution filename into the candidate portion.
    """

    stem = filename[:-4]

    suffixes = [
        "_01-01-2020_12-31-2026",
        "_01-01-2026_03-31-2026",
        "_2026_q1",
    ]

    for suffix in suffixes:
        if stem.endswith(suffix):
            return stem[:-len(suffix)]

    return stem


def read_repaired_csv(filepath):
    """
    Read an RI Campaign Finance CSV while repairing records
    that contain physical newlines inside a CSV record.

    RI's export sometimes produces records like:

        902482,...,Payment of Fundraising expense Food and Beverage to
        Ciro's Tavern 42 Cherry St Woonsocket RI 02895,...

    The second physical line is actually part of the same
    contribution record.

    A new record is identified by a numeric ContributionID
    at the beginning of the physical line.
    """

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        physical_lines = f.readlines()

    if not physical_lines:
        return [], []

    header_line = physical_lines[0].rstrip("\r\n")

    records = []
    current_record = None
    current_start_line = None

    for line_number, line in enumerate(
        physical_lines[1:],
        start=2
    ):
        line = line.rstrip("\r\n")

        if not line:
            continue

        first_field = line.split(",", 1)[0].strip()

        # ----------------------------------------------------
        # New contribution record
        # ----------------------------------------------------
        if first_field.isdigit():

            if current_record is not None:
                records.append(
                    (
                        current_start_line,
                        current_record
                    )
                )

            current_record = line
            current_start_line = line_number

        # ----------------------------------------------------
        # Continuation of previous contribution
        # ----------------------------------------------------
        else:

            if current_record is None:
                continue

            current_record += " " + line

    # Save final record.
    if current_record is not None:
        records.append(
            (
                current_start_line,
                current_record
            )
        )

    return header_line, records


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — BUILD UNIFIED CONTRIBUTIONS")
    print("=" * 60)

    # --------------------------------------------------------
    # Load candidates
    # --------------------------------------------------------

    with open(
        CANDIDATES_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        candidates = json.load(f)

    candidate_map = {}

    for candidate in candidates:

        if not candidate.get("org_id"):
            continue

        key = filename_key(
            candidate["name"]
        )

        candidate_map[key] = candidate

    print()
    print(
        "Candidates with Org ID:",
        len(candidate_map)
    )

    # --------------------------------------------------------
    # Find CSV files
    # --------------------------------------------------------

    all_csv_files = sorted(
        filename
        for filename in os.listdir(
            CONTRIBUTIONS_DIR
        )
        if filename.lower().endswith(".csv")
    )

    print()
    print(
        "Input CSV files:",
        len(all_csv_files)
    )

    # --------------------------------------------------------
    # Include historical and Q1 files
    # --------------------------------------------------------

    historical_candidates = set()

    for filename in all_csv_files:
        if is_historical_file(filename):
            stem = candidate_stem(filename)
            historical_candidates.add(
                filename_key(stem)
            )

    csv_files = []

    for filename in all_csv_files:
        csv_files.append(filename)

    skipped_q1 = []

    print()
    print(
        "Historical files:",
        len(historical_candidates)
    )

    print(
        "Q1 files skipped",
        len(skipped_q1)
    )

    print(
        "Files selected for unified build:",
        len(csv_files)
    )

    # --------------------------------------------------------
    # Output fields
    # --------------------------------------------------------

    output_headers = [
        "candidate",
        "org_id",
        "candidate_id",
        "chamber",
        "district",
        "party",
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

    rows_written = 0
    total_amount = Decimal("0")

    contribution_ids = set()

    unknown_files = []
    bad_rows = []
    duplicate_ids = []

    repaired_records = 0

    # --------------------------------------------------------
    # Build unified CSV
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline=""
    ) as output:

        writer = csv.DictWriter(
            output,
            fieldnames=output_headers
        )

        writer.writeheader()

        for filename in csv_files:

            stem = candidate_stem(
                filename
            )

            key = filename_key(
                stem
            )

            candidate = candidate_map.get(
                key
            )

            if not candidate:

                unknown_files.append(
                    filename
                )

                continue

            filepath = os.path.join(
                CONTRIBUTIONS_DIR,
                filename
            )

            try:

                header_line, records = (
                    read_repaired_csv(
                        filepath
                    )
                )

                # ------------------------------------------------
                # Validate header
                # ------------------------------------------------

                try:

                    parsed_header = next(
                        csv.reader(
                            [header_line]
                        )
                    )

                except Exception:

                    parsed_header = []

                if parsed_header != EXPECTED_HEADERS:

                    print()
                    print(
                        "BAD HEADERS:",
                        filename
                    )

                    unknown_files.append(
                        filename
                    )

                    continue

                # ------------------------------------------------
                # Process repaired records
                # ------------------------------------------------

                for physical_line, record in records:
                    try:
                        values = next(
                            csv.reader([record])
                        )

                        # RI ERTS occasionally exports a donor name containing
                        # an unescaped double quote. This can cause the CSV
                        # parser to split the LastName and FullName fields.
                        #
                        # Repair the known 23-field pattern back to 22 fields.
                        if len(values) == len(EXPECTED_HEADERS) + 1:
                            if (
                                len(values) >= 14
                                and values[10]
                                and values[11]
                                and values[12] == values[11].replace('"', '')
                                and values[13].startswith(" ")
                                and values[13].endswith('"')
                            ):
                                values[12] = (
                                    values[11]
                                    + ","
                                    + values[13].strip('"')
                                )
                                del values[13]

                    except Exception as e:
                        bad_rows.append({
                            "file": filename,
                            "row": physical_line,
                            "reason": repr(e),
                        })
                        continue

                    if len(values) != len(EXPECTED_HEADERS):
                        bad_rows.append({
                            "file": filename,
                            "row": physical_line,
                            "field_count": len(values),
                            "expected": len(EXPECTED_HEADERS),
                        })
                        continue
                    row = dict(
                        zip(
                            EXPECTED_HEADERS,
                            values
                        )
                    )

                    # ------------------------------------------------
                    # Detect whether the repair was necessary
                    # ------------------------------------------------

                    if "\n" in record or "\r" in record:

                        repaired_records += 1

                    # ------------------------------------------------
                    # Contribution ID
                    # ------------------------------------------------

                    contribution_id = (
                        row.get(
                            "ContributionID",
                            ""
                        ) or ""
                    ).strip()

                    if not contribution_id:

                        bad_rows.append({
                            "file": filename,
                            "row": physical_line,
                            "reason": (
                                "missing ContributionID"
                            ),
                        })

                        continue

                    # ------------------------------------------------
                    # Duplicate protection
                    # ------------------------------------------------

                    if contribution_id in contribution_ids:

                        duplicate_ids.append({
                            "ContributionID":
                                contribution_id,
                            "file": filename,
                            "candidate":
                                candidate["name"],
                        })

                        continue

                    contribution_ids.add(
                        contribution_id
                    )

                    # ------------------------------------------------
                    # Amount
                    # ------------------------------------------------

                    amount = money(
                        row.get(
                            "Amount",
                            ""
                        )
                    )

                    total_amount += amount

                    # ------------------------------------------------
                    # Build output row
                    # ------------------------------------------------

                    output_row = {
                        "candidate": candidate.get(
                            "name",
                            ""
                        ),

                        "org_id": candidate.get(
                            "org_id",
                            ""
                        ),

                        "candidate_id": candidate.get(
                            "candidate_id",
                            ""
                        ),

                        "chamber": candidate.get(
                            "chamber",
                            ""
                        ),

                        "district": candidate.get(
                            "district",
                            ""
                        ),

                        "party": candidate.get(
                            "party",
                            ""
                        ),
                    }

                    for header in EXPECTED_HEADERS:

                        output_row[header] = (
                            row.get(
                                header,
                                ""
                            )
                        )

                    writer.writerow(
                        output_row
                    )

                    rows_written += 1

            except Exception as e:

                bad_rows.append({
                    "file": filename,
                    "reason": repr(e),
                })

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)

    print()

    print(
        "Input CSV files:",
        len(all_csv_files)
    )

    print(
        "Files selected:",
        len(csv_files)
    )

    print(
        "Q1 files skipped:",
        len(skipped_q1)
    )

    print(
        "Rows written:",
        rows_written
    )

    print(
        "Unique Contribution IDs:",
        len(contribution_ids)
    )

    print(
        "Total amount:",
        "${:,.2f}".format(
            total_amount
        )
    )

    print(
        "Duplicate rows skipped:",
        len(duplicate_ids)
    )

    print(
        "Repaired multiline records:",
        repaired_records
    )

    print(
        "Unknown files:",
        len(unknown_files)
    )

    if unknown_files:

        print()

        for filename in unknown_files:

            print(
                " ",
                filename
            )

    print()

    print(
        "Bad rows:",
        len(bad_rows)
    )

    if bad_rows:

        print()

        for item in bad_rows[:30]:

            print(
                " ",
                item
            )

        if len(bad_rows) > 30:

            print(
                " ",
                "...",
                len(bad_rows) - 30,
                "more"
            )

    print()

    print(
        "Output:",
        OUTPUT_FILE
    )

    if os.path.exists(
        OUTPUT_FILE
    ):

        size = os.path.getsize(
            OUTPUT_FILE
        )

        print(
            "File size:",
            "{:,.1f} KB".format(
                size / 1024
            )
        )

    print()

    print("=" * 60)


if __name__ == "__main__":
    main()
