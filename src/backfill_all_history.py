import argparse
import json
import os
import time

from playwright.sync_api import sync_playwright

from download_all_contributions import (
    download_candidate,
    load_candidates,
)

CANDIDATES_FILE = "data/candidates.json"


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical RI campaign finance contribution data."
    )

    parser.add_argument(
        "--begin-date",
        default="01/01/2020",
        help="Beginning date in MM/DD/YYYY format.",
    )

    parser.add_argument(
        "--end-date",
        default="12/31/2026",
        help="Ending date in MM/DD/YYYY format.",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — HISTORICAL BACKFILL")
    print("=" * 60)

    print()
    print("Date range:")
    print(args.begin_date, "through", args.end_date)

    candidates = load_candidates()

    candidates_with_org = [
        c for c in candidates
        if c.get("org_id")
    ]

    print()
    print("Candidates:", len(candidates))
    print("Candidates with Org ID:", len(candidates_with_org))

    if not candidates_with_org:
        print()
        print("No candidates with Org IDs.")
        return

    successful = 0
    already_exists = 0
    no_contributions = 0
    failed = 0

    with sync_playwright() as p:

        print()
        print("Starting browser...")

        browser = p.chromium.launch(
            headless=False
        )

        try:

            total = len(candidates_with_org)

            for index, candidate in enumerate(
                candidates_with_org,
                start=1
            ):

                name = candidate.get(
                    "name",
                    ""
                ).strip()

                print()
                print("#" * 60)
                print(
                    f"[{index}/{total}] {name}"
                )
                print("#" * 60)

                success, status = download_candidate(
                    browser,
                    candidate,
                    args.begin_date,
                    args.end_date
                )

                if success:

                    if status == "already_exists":
                        already_exists += 1

                    else:
                        successful += 1

                    print()
                    print("SUCCESS:", name)

                else:

                    if status == "no_contributions":

                        no_contributions += 1

                        print()
                        print(
                            "NO CONTRIBUTIONS:",
                            name
                        )

                    else:

                        failed += 1

                        print()
                        print(
                            "FAILED:",
                            name
                        )

                        print(
                            "Reason:",
                            status
                        )

                time.sleep(0.5)

        finally:

            print()
            print("Closing browser...")

            browser.close()

    print()
    print("=" * 60)
    print("HISTORICAL BACKFILL COMPLETE")
    print("=" * 60)

    print()
    print(
        "Total with Org ID:",
        len(candidates_with_org)
    )

    print(
        "Downloaded this run:",
        successful
    )

    print(
        "Already existed:",
        already_exists
    )

    print(
        "No contributions:",
        no_contributions
    )

    print(
        "Failed:",
        failed
    )

    print()
    print("CSV files: data/contributions")


if __name__ == "__main__":
    main()
