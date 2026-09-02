import csv
import json


INPUT_FILE = "data/contributions_all.csv"
OUTPUT_FILE = "data/contributions_all.json"


def money(value):
    try:
        return float(
            str(value or "")
            .replace("$", "")
            .replace(",", "")
        )
    except Exception:
        return 0.0


def nullable(value):
    value = str(value or "").strip()
    return value if value else None


def main():
    print("=" * 60)
    print("RI CAMPAIGN FINANCE — BUILD CONTRIBUTIONS JSON")
    print("=" * 60)

    contributions = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            contribution = {
                "candidate":
                    row.get("candidate", ""),
                "org_id":
                    row.get("org_id", ""),
                "candidate_id":
                    row.get("candidate_id", ""),
                "chamber":
                    row.get("chamber", ""),
                "district":
                    row.get("district", ""),
                "party":
                    row.get("party", ""),

                "contribution_id":
                    int(row["ContributionID"])
                    if row.get("ContributionID", "").strip().isdigit()
                    else None,

                "type":
                    row.get("ContDesc", ""),
                "incomplete":
                    bool(row.get("ViewIncomplete", "").strip()),
                "incomplete_reason":
                    row.get("IncompleteDesc", ""),

                "organization":
                    row.get("OrganizationName", ""),

                "receipt_date":
                    nullable(row.get("ReceiptDate")),
                "deposit_date":
                    nullable(row.get("DepositDate")),

                "amount":
                    money(row.get("Amount")),

                "contrib_explanation":
                    row.get("ContribExplanation", ""),
                "mpf_match_amount":
                    money(row.get("MPFMatchAmount")),

                "first_name":
                    row.get("FirstName", ""),
                "last_name":
                    row.get("LastName", ""),
                "full_name":
                    row.get("FullName", ""),

                "address": "",
                "city_state_zip": "",

                "employer":
                    row.get("EmployerName", ""),
                "employer_address":
                    row.get("EmpAddress", ""),
                "employer_city_state_zip":
                    row.get("EmpCityStZip", ""),

                "payment_method":
                    row.get("ReceiptDesc", ""),

                "begin_date":
                    nullable(row.get("BeginDate")),
                "end_date":
                    nullable(row.get("EndDate")),

                "transaction_type":
                    row.get("TransType", ""),

                "campaign":
                    row.get("candidate", "")
            }

            contributions.append(contribution)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            contributions,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print()
    print("Records:", len(contributions))
    print("Output:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
