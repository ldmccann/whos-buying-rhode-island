import csv
import json
from decimal import Decimal
from pathlib import Path
from datetime import datetime
import sys


if len(sys.argv) != 2:
    print("Usage: python src/clean.py <csv_file>")
    raise SystemExit(1)


INPUT = Path(sys.argv[1])

if not INPUT.exists():
    print(f"ERROR: File not found: {INPUT}")
    raise SystemExit(1)


OUTPUT = INPUT.with_suffix(".json")


def campaign_name_from_filename(path):
    name = path.stem

    # Remove the reporting-period suffix.
    name = name.replace("_2026_q1", "")

    # Convert underscores to spaces.
    return name.replace("_", " ").upper()


def parse_date(value):
    if not value or value == "1/1/1900":
        return None

    return datetime.strptime(
        value,
        "%m/%d/%Y"
    ).date().isoformat()


def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        value.replace("\xa0", " ").split()
    )


records = []

with INPUT.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:

    reader = csv.DictReader(f)

    for row in reader:

        amount = Decimal(row["Amount"])

        record = {
            "contribution_id": int(
                row["ContributionID"]
            ),

            "type": clean_text(
                row["ContDesc"]
            ),

            "incomplete": (
                clean_text(
                    row["ViewIncomplete"]
                ) == "Incomplete"
            ),

            "incomplete_reason": clean_text(
                row["IncompleteDesc"]
            ),

            "organization": clean_text(
                row["OrganizationName"]
            ),

            "receipt_date": parse_date(
                row["ReceiptDate"]
            ),

            "deposit_date": parse_date(
                row["DepositDate"]
            ),

            "amount": float(amount),

            "first_name": clean_text(
                row["FirstName"]
            ),

            "last_name": clean_text(
                row["LastName"]
            ),

            "full_name": clean_text(
                row["FullName"]
            ),

            "address": clean_text(
                row["Address"]
            ),

            "city_state_zip": clean_text(
                row["CityStZip"]
            ),

            "employer": clean_text(
                row["EmployerName"]
            ),

            "employer_address": clean_text(
                row["EmpAddress"]
            ),

            "employer_city_state_zip": clean_text(
                row["EmpCityStZip"]
            ),

            "payment_method": clean_text(
                row["ReceiptDesc"]
            ),

            "begin_date": parse_date(
                row["BeginDate"]
            ),

            "end_date": parse_date(
                row["EndDate"]
            ),

            "transaction_type": clean_text(
                row["TransType"]
            ),
        }

        records.append(record)


# Validation

ids = [
    r["contribution_id"]
    for r in records
]

duplicates = sorted({
    x for x in ids
    if ids.count(x) > 1
})

total = sum(
    Decimal(str(r["amount"]))
    for r in records
)

incomplete = sum(
    r["incomplete"]
    for r in records
)


summary = {
    "record_count": len(records),
    "total_contributions": float(total),
    "incomplete_records": incomplete,
    "duplicate_ids": duplicates,
}


campaign = campaign_name_from_filename(INPUT)


output = {
    "campaign": campaign,

    "reporting_period": {
        "begin": "2026-01-01",
        "end": "2026-03-31",
    },

    "summary": summary,

    "contributions": records,
}


with OUTPUT.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        indent=2,
        ensure_ascii=False
    )


print(f"Created: {OUTPUT}")
print(f"Campaign: {campaign}")
print(f"Records: {len(records)}")
print(f"Total: ${total:,.2f}")
print(f"Incomplete: {incomplete}")
print(f"Duplicate IDs: {duplicates}")
