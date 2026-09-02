import argparse
import csv
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# CONFIGURATION
# ============================================================

REPORT_URL = "https://ricampaignfinance.com/RIPublic/Reporting/TransactionReport.aspx"

CANDIDATES_FILE = "data/candidates.json"
OUTPUT_DIR = "data/contributions"
FAILURES_FILE = "data/contribution_download_failures.json"

from datetime import datetime

DEFAULT_BEGIN_DATE = "01/01/2020"
DEFAULT_END_DATE = datetime.now().strftime("%m/%d/%Y")

PAGE_TIMEOUT = 30000
ACTION_TIMEOUT = 15000

# Set to True to download files that already exist.
# Normally leave this False so the script can safely resume.
FORCE_REDOWNLOAD = False


# ============================================================
# HELPERS
# ============================================================

def load_candidates():
    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_failures():
    if not os.path.exists(FAILURES_FILE):
        return []

    try:
        with open(FAILURES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_failures(failures):
    with open(FAILURES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            failures,
            f,
            indent=2,
            ensure_ascii=False
        )


def safe_filename(text):
    """
    Convert a candidate name into a safe filename.
    """

    text = text.strip().lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text
    )

    text = text.strip("_")

    return text

def output_filename(candidate, begin_date, end_date):
    """
    Return the stable source CSV filename for a candidate.

    The date range is intentionally not included in the filename,
    because each successful ERTS download is a replacement snapshot.
    """

    name = safe_filename(
        candidate.get("name", "")
    )

    return os.path.join(
        OUTPUT_DIR,
        f"{name}.csv"
    )

def build_report_url(
    org_id,
    begin_date,
    end_date
):
    """
    Build the same TransactionReport URL that successfully
    produced the Shekarchi report.
    """

    begin_date = quote(begin_date)
    end_date = quote(end_date)

    url = (
        f"{REPORT_URL}"
        f"?OrgID={org_id}"
        f"&BeginDate={begin_date}"
        f"&EndDate={end_date}"
        f"&LastName="
        f"&FirstName="
        f"&ContType=0"
        f"&State="
        f"&City="
        f"&ZIPCode="
        f"&EmployerName="
        f"&Amount=0"
        f"&ReportType=Contrib"
        f"&CFStatus=F"
        f"&MPFStatus=A"
        f"&Level=S"
        f"&SumBy=Type"
        f"&Sort1=ReceiptDate"
        f"&Direct1=desc"
        f"&Sort2=None"
        f"&Direct2=asc"
        f"&Sort3=None"
        f"&Direct3=asc"
        f"&Site=Public"
        f"&Incomplete=A"
        f"&ContSource=CF"
    )

    return url


def verify_csv(filename):
    """
    Check that the downloaded file is actually a CSV and
    not the HTML 'Your file has...' page or another error page.

    Returns:

        (True, row_count)

    or:

        (False, reason)
    """

    if not os.path.exists(filename):
        return False, "file does not exist"

    size = os.path.getsize(filename)

    if size < 100:
        return False, f"file too small ({size} bytes)"

    try:
        with open(
            filename,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as f:

            reader = csv.reader(f)

            headers = next(reader, None)

            if not headers:
                return False, "no CSV headers"

            # The real RI contribution export has ContributionID.
            if "ContributionID" not in headers:
                return False, (
                    "missing ContributionID header; "
                    "probably HTML instead of CSV"
                )

            rows = sum(1 for _ in reader)

            return True, rows

    except UnicodeDecodeError:
        return False, "file is not UTF-8 text"

    except Exception as e:
        return False, repr(e)


def record_failure(failures, candidate, reason):
    name = candidate.get("name", "")

    # Don't create duplicate failure records.
    for item in failures:
        if item.get("name") == name:
            item["status"] = reason
            save_failures(failures)
            return

    failures.append({
        "name": name,
        "org_id": candidate.get("org_id"),
        "status": reason
    })

    save_failures(failures)


# ============================================================
# DOWNLOAD ONE CANDIDATE
# ============================================================

def download_candidate(
    browser,
    candidate,
    begin_date,
    end_date
):
    """
    Download one candidate's contribution report.

    A completely fresh browser context is created for every
    candidate because the RI ERTS site uses old ASP.NET
    WebForms behavior and can retain state between reports.
    """

    name = candidate.get("name", "").strip()
    org_id = candidate.get("org_id")

    if not name:
        return False, "missing candidate name"

    if not org_id:
        return False, "missing org_id"

    output_file = output_filename(
        candidate,
        begin_date,
        end_date
    )

    print()
    print("=" * 60)
    print("SEARCHING:", name)
    print("=" * 60)
    print("Org ID:", org_id)
    print("Output:", output_file)

    # --------------------------------------------------------
    # Resume protection
    # --------------------------------------------------------

    if os.path.exists(output_file) and not FORCE_REDOWNLOAD:
        valid, result = verify_csv(output_file)

        if valid:
            print()
            print("ALREADY DOWNLOADED.")
            print("CSV rows:", result)
            print("Skipping.")

            return True, "already_exists"

        print()
        print("Existing file is invalid.")
        print("Reason:", result)
        print("Downloading again...")

    # --------------------------------------------------------
    # Completely fresh browser context
    # --------------------------------------------------------

    print()
    print("Creating completely fresh browser context...")

    context = browser.new_context(
        accept_downloads=True
    )

    page = context.new_page()

    page.set_default_timeout(
        ACTION_TIMEOUT
    )

    page.set_default_navigation_timeout(
        PAGE_TIMEOUT
    )

    try:

        # ----------------------------------------------------
        # Open report
        # ----------------------------------------------------

        url = build_report_url(
            org_id,
            begin_date,
            end_date
        )

        print()
        print("Opening TransactionReport...")

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

        if response:
            print(
                "HTTP status:",
                response.status
            )

        print(
            "Page title:",
            page.title()
        )

        # Give the report a moment to finish rendering.
        time.sleep(2)

        body_text = page.locator(
            "body"
        ).inner_text()

        if "No Contributions were found" in body_text:

            print()
            print("NO CONTRIBUTIONS FOUND")

            return False, "no_contributions"

        if "Public Contribution Report" not in body_text:

            print()
            print("WARNING: Expected contribution report text")
            print("was not found.")

            print()
            print("Current URL:")
            print(page.url)

            return False, "unexpected_report_page"

        print()
        print("Report loaded.")

        # ----------------------------------------------------
        # Find Export
        # ----------------------------------------------------

        export_buttons = page.locator(
            "input[value='Export'], "
            "input[type='submit'][value*='Export'], "
            "button:has-text('Export'), "
            "a:has-text('Export')"
        )

        export_count = export_buttons.count()

        print()
        print("Export controls found:", export_count)

        if export_count == 0:

            print()
            print("Could not find Export button.")

            return False, "export_button_not_found"

        # ----------------------------------------------------
        # Click Export and capture popup
        # ----------------------------------------------------

        print()
        print("Clicking Export...")

        popup = None

        try:

            with page.expect_popup(
                timeout=ACTION_TIMEOUT
            ) as popup_info:

                export_buttons.first.click(
                    timeout=ACTION_TIMEOUT
                )

            popup = popup_info.value

            print("Export popup opened.")

            try:
                popup.wait_for_load_state(
                    "domcontentloaded",
                    timeout=ACTION_TIMEOUT
                )
            except PlaywrightTimeoutError:
                pass

        except PlaywrightTimeoutError:

            print()
            print("No popup detected.")

            return False, "export_popup_timeout"

        # ----------------------------------------------------
        # Inspect popup
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("POPUP")
        print("=" * 60)

        print("Popup URL:")
        print(popup.url)

        popup_text = ""

        try:
            popup_text = popup.locator(
                "body"
            ).inner_text()

            print()
            print("Popup content:")
            print(
                popup_text[:1000]
            )

        except Exception as e:

            print(
                "Could not read popup body:",
                repr(e)
            )

        # ----------------------------------------------------
        # Find View/Save link
        # ----------------------------------------------------

        print()
        print("Finding View/Save link...")

        view_save = popup.locator(
            "a"
        ).filter(
            has_text=re.compile(
                r"View/Save",
                re.IGNORECASE
            )
        )

        link_count = view_save.count()

        print(
            "View/Save links found:",
            link_count
        )

        if link_count == 0:

            print()
            print(
                "Could not find View/Save link."
            )

            return False, "view_save_link_not_found"

        link = view_save.first

        print()
        print(
            "View/Save href:",
            link.get_attribute("href")
        )

        # ----------------------------------------------------
        # THIS IS THE IMPORTANT PART
        #
        # The popup itself does NOT contain the CSV.
        # Clicking View/Save causes the browser to download
        # the generated CSV.
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("CAPTURING BROWSER DOWNLOAD")
        print("=" * 60)

        try:

            with popup.expect_download(
                timeout=PAGE_TIMEOUT
            ) as download_info:

                link.click(
                    timeout=ACTION_TIMEOUT
                )

            download = download_info.value

            print()
            print("ACTUAL CSV DOWNLOAD CAPTURED!")

            print(
                "Suggested filename:",
                download.suggested_filename
            )

            print(
                "Download failure:",
                download.failure()
            )

            if download.failure():

                return False, (
                    "browser_download_failed: "
                    + str(download.failure())
                )

            # ------------------------------------------------
            # Save actual downloaded file
            # ------------------------------------------------

            os.makedirs(
                OUTPUT_DIR,
                exist_ok=True
            )

            temp_output_file = output_file + ".tmp"

            # Remove any leftover temporary file from a previous interrupted run.
            if os.path.exists(temp_output_file):
                os.remove(temp_output_file)

            download.save_as(
                temp_output_file
            )

            print()

            print(
                "DOWNLOADED TEMP FILE:",
                temp_output_file
            )

        except PlaywrightTimeoutError:

            print()
            print(
                "Timed out waiting for browser download."
            )

            return False, "download_timeout"

        # ----------------------------------------------------
        # Verify CSV
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("VERIFYING CSV")
        print("=" * 60)

        valid, result = verify_csv(
            temp_output_file
        )

        if not valid:

            print()
            print("CSV VERIFICATION FAILED")
            print("Reason:", result)

            return False, (
                "invalid_csv: "
                + str(result)
            )

        print()
        print("CSV VERIFIED.")
        print("Rows:", result)

        # ----------------------------------------------------
        # Replace existing candidate snapshot only after
        # successful CSV verification.
        # ----------------------------------------------------

        os.replace(
            temp_output_file,
            output_file
        )

        print()

        print("REPLACED:", output_file)

        # ----------------------------------------------------
        # Show headers
        # ----------------------------------------------------

        try:

            with open(
                output_file,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as f:

                reader = csv.reader(f)

                headers = next(
                    reader,
                    []
                )

                print()
                print("Headers:")
                print(headers)

        except Exception:
            pass

        return True, "success"

    except PlaywrightTimeoutError as e:

        print()
        print("TIMEOUT:")
        print(str(e))

        return False, "timeout"

    except Exception as e:

        print()
        print("ERROR:")
        print(repr(e))

        return False, (
            "error: "
            + repr(e)
        )

    finally:

        print()
        print(
            "Closing candidate browser context..."
        )

        try:
            page.close()
        except Exception:
            pass

        try:
            context.close()
        except Exception:
            pass


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Download RI campaign finance contribution reports."
    )

    parser.add_argument(
        "--begin-date",
        default=DEFAULT_BEGIN_DATE,
        help="Beginning date in MM/DD/YYYY format."
    )

    parser.add_argument(
        "--end-date",
        default=DEFAULT_END_DATE,
        help="Ending date in MM/DD/YYYY format."
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload reports even if valid CSV files already exist."
    )

    parser.add_argument(
        "--candidate",
        help="Download only the named candidate."
    )

    args = parser.parse_args()

    global FORCE_REDOWNLOAD
    FORCE_REDOWNLOAD = args.force

    begin_date = args.begin_date
    end_date = args.end_date

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — BATCH CONTRIBUTION DOWNLOAD")
    print("=" * 60)

    print()
    print("Date:", begin_date, "through", end_date)
    print("Candidates file:", CANDIDATES_FILE)
    print("Output directory:", OUTPUT_DIR)

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    candidates = load_candidates()
    failures = []
    save_failures(failures)

    print()
    print("Total candidates:", len(candidates))

    # --------------------------------------------------------
    # Only candidates with Org IDs
    # --------------------------------------------------------

    candidates_with_org_ids = [
        candidate
        for candidate in candidates
        if candidate.get("org_id")
    ]

    # --------------------------------------------------------
    # Optional single-candidate filter
    # --------------------------------------------------------

    if args.candidate:
        requested = args.candidate.strip().lower()

        candidates_with_org_ids = [
            candidate
            for candidate in candidates_with_org_ids
            if candidate.get("name", "").strip().lower() == requested
        ]

        if not candidates_with_org_ids:
            print()
            print("Candidate not found:", args.candidate)
            return

    print(
        "Candidates with Org ID:",
        len(candidates_with_org_ids)
    )

    print(
        "Candidates without Org ID:",
        len(candidates)
        - len(candidates_with_org_ids)
    )

    if not candidates_with_org_ids:

        print()
        print("Nothing to download.")
        return

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    successful = 0
    already_exists = 0
    failed = 0

    # --------------------------------------------------------
    # Playwright
    # --------------------------------------------------------

    with sync_playwright() as p:

        print()
        print("Starting browser...")

        browser = p.chromium.launch(
            headless=False
        )

        try:

            total = len(
                candidates_with_org_ids
            )

            for index, candidate in enumerate(
                candidates_with_org_ids,
                start=1
            ):

                name = candidate.get(
                    "name",
                    ""
                ).strip()

                print()
                print()
                print(
                    "#" * 60
                )

                print(
                    f"[{index}/{total}] {name}"
                )

                print(
                    "#" * 60
                )

                attempts = 3
                success = False
                status = None

                for attempt in range(1, attempts + 1):

                    if attempt > 1:
                        print()
                        print(
                            f"RETRY {attempt}/{attempts}:",
                            name
                        )
                        time.sleep(3)

                    success, status = download_candidate(
                        browser,
                        candidate,
                        begin_date,
                        end_date
                    )

                    if success:
                        break

                    # No-contribution results are legitimate and
                    # should not be retried.
                    if status == "no_contributions":
                        break

                if success:
                    if status == "already_exists":
                        already_exists += 1
                    else:
                        successful += 1

                    print()
                    print(
                        "SUCCESS:",
                        name
                    )

                else:
                    failed += 1

                    record_failure(
                        failures,
                        candidate,
                        status
                    )

                    print()
                    print(
                        "FAILED:",
                        name
                    )

                    print(
                        "Reason:",
                        status
                    )

                    print()
                    print(
                        "FAILED:",
                        name
                    )

                    print(
                        "Reason:",
                        status
                    )

                # Small pause between candidates.
                time.sleep(0.5)

        finally:

            print()
            print(
                "Closing browser..."
            )

            browser.close()

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("BATCH DOWNLOAD COMPLETE")
    print("=" * 60)

    print()
    print("Total with Org ID:",
          len(candidates_with_org_ids))

    print(
        "Downloaded this run:",
        successful
    )

    print(
        "Already existed:",
        already_exists
    )

    print(
        "Failed:",
        failed
    )

    print()
    print(
        "CSV files:",
        OUTPUT_DIR
    )

    print(
        "Failures:",
        FAILURES_FILE
    )

    print()


if __name__ == "__main__":
    main()
