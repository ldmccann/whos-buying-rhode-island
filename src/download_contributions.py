import csv
import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


REPORT_URL = "https://ricampaignfinance.com/RIPublic/Reporting/TransactionReport.aspx"

ORG_ID = 6824
BEGIN_DATE = "01/01/2026"
END_DATE = "03/31/2026"

OUTPUT_FILE = "data/shekarchi_2026_q1.csv"

PAGE_TIMEOUT = 30000
ACTION_TIMEOUT = 15000


def main():

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — CONTRIBUTION DOWNLOAD")
    print("=" * 60)
    print()

    print("Org ID:", ORG_ID)
    print("Date:", BEGIN_DATE, "through", END_DATE)
    print()

    os.makedirs("data", exist_ok=True)

    with sync_playwright() as p:

        print("Starting browser...")

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            accept_downloads=True
        )

        page = context.new_page()

        page.set_default_timeout(ACTION_TIMEOUT)
        page.set_default_navigation_timeout(PAGE_TIMEOUT)

        # ---------------------------------------------------------
        # BUILD TRANSACTION REPORT URL
        # ---------------------------------------------------------

        url = (
            f"{REPORT_URL}"
            f"?OrgID={ORG_ID}"
            f"&BeginDate={BEGIN_DATE.replace('/', '%2F')}"
            f"&EndDate={END_DATE.replace('/', '%2F')}"
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

        # ---------------------------------------------------------
        # OPEN REPORT
        # ---------------------------------------------------------

        print()
        print("Opening TransactionReport...")

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

        if response:
            print("HTTP status:", response.status)

        print("Page title:", page.title())
        print()

        print("Waiting for report...")

        time.sleep(2)

        body_text = page.locator("body").inner_text()

        if "No Contributions were found" in body_text:

            print()
            print("NO CONTRIBUTIONS FOUND")
            print()
            print(body_text[:3000])

            browser.close()
            return

        print()
        print("Report loaded.")

        # ---------------------------------------------------------
        # REPORT PREVIEW
        # ---------------------------------------------------------

        print()
        print("=" * 60)
        print("REPORT PREVIEW")
        print("=" * 60)

        print(body_text[:4000])

        # ---------------------------------------------------------
        # FIND EXPORT BUTTON
        # ---------------------------------------------------------

        export_buttons = page.locator(
            "input[value='Export'], "
            "input[type='submit'][value*='Export'], "
            "button:has-text('Export'), "
            "a:has-text('Export')"
        )

        count = export_buttons.count()

        print()
        print("Export controls found:", count)

        if count == 0:

            print()
            print("Could not find Export button.")

            browser.close()
            return

        # ---------------------------------------------------------
        # EXPORT
        # ---------------------------------------------------------

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

        except PlaywrightTimeoutError:

            print()
            print("No popup detected.")

        # ---------------------------------------------------------
        # WAIT FOR POPUP
        # ---------------------------------------------------------

        if popup:

            try:

                popup.wait_for_load_state(
                    "domcontentloaded",
                    timeout=ACTION_TIMEOUT
                )

            except PlaywrightTimeoutError:

                print(
                    "Popup load-state timeout; "
                    "continuing."
                )

            print()
            print("Popup URL:")
            print(popup.url)

            # -----------------------------------------------------
            # INSPECT POPUP
            # -----------------------------------------------------

            try:

                popup_text = popup.locator(
                    "body"
                ).inner_text()

                print()
                print("=" * 60)
                print("POPUP CONTENT")
                print("=" * 60)

                print(popup_text[:2000])

            except Exception as e:

                print(
                    "Could not read popup text:",
                    repr(e)
                )

        # ---------------------------------------------------------
        # THE RI SITE USES A TWO-STEP DOWNLOAD
        #
        # Step 1:
        # Export creates DownloadFile.aspx.
        #
        # Step 2:
        # DownloadFile.aspx displays a "View/Save" link.
        #
        # We must click View/Save to get the actual CSV.
        # ---------------------------------------------------------

        if popup:

            print()
            print("=" * 60)
            print("FINDING VIEW/SAVE LINK")
            print("=" * 60)

            # Find all links in the popup.
            links = popup.locator("a")

            print(
                "Links in popup:",
                links.count()
            )

            view_save = None

            for i in range(links.count()):

                link = links.nth(i)

                try:
                    text = link.inner_text().strip()
                except Exception:
                    text = ""

                try:
                    href = link.get_attribute("href")
                except Exception:
                    href = None

                print()
                print("LINK", i + 1)
                print("Text:", repr(text))
                print("Href:", repr(href))

                if "view/save" in text.lower():

                    view_save = link

            if view_save is None:

                print()
                print(
                    "ERROR: Could not find View/Save link."
                )

                browser.close()
                return

            print()
            print("FOUND VIEW/SAVE LINK")

            try:

                href = view_save.get_attribute(
                    "href"
                )

                print(
                    "View/Save href:",
                    href
                )

            except Exception:

                pass

            # -----------------------------------------------------
            # CLICK VIEW/SAVE AND CAPTURE THE REAL DOWNLOAD
            # -----------------------------------------------------

            print()
            print("=" * 60)
            print("CLICKING VIEW/SAVE")
            print("=" * 60)

            try:

                with popup.expect_download(
                    timeout=PAGE_TIMEOUT
                ) as download_info:

                    view_save.click(
                        timeout=ACTION_TIMEOUT
                    )

                download = download_info.value

                print()
                print("ACTUAL CSV DOWNLOAD CAPTURED!")

                print(
                    "Suggested filename:",
                    download.suggested_filename
                )

                failure = download.failure()

                print(
                    "Download failure:",
                    failure
                )

                if failure:

                    raise RuntimeError(
                        "Playwright reported a "
                        "download failure: "
                        + str(failure)
                    )

                download.save_as(
                    OUTPUT_FILE
                )

                print()
                print(
                    "SAVED:",
                    OUTPUT_FILE
                )

            except PlaywrightTimeoutError as e:

                print()
                print(
                    "ERROR: View/Save did not trigger "
                    "a browser download."
                )

                print(
                    repr(e)
                )

                browser.close()
                return

        else:

            print()
            print(
                "ERROR: Export did not create a popup."
            )

            browser.close()
            return

        # ---------------------------------------------------------
        # VERIFY FILE
        # ---------------------------------------------------------

        print()
        print("=" * 60)
        print("VERIFYING CSV")
        print("=" * 60)

        if not os.path.exists(OUTPUT_FILE):

            print()
            print(
                "CSV FILE WAS NOT CREATED:"
            )

            print(
                OUTPUT_FILE
            )

            browser.close()
            return

        file_size = os.path.getsize(
            OUTPUT_FILE
        )

        print()
        print(
            "File:",
            OUTPUT_FILE
        )

        print(
            "Size:",
            file_size,
            "bytes"
        )

        if file_size == 0:

            print(
                "ERROR: CSV file is empty."
            )

            browser.close()
            return

        # ---------------------------------------------------------
        # READ CSV
        # ---------------------------------------------------------

        try:

            with open(
                OUTPUT_FILE,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as f:

                reader = csv.reader(f)

                rows = list(reader)

            print()
            print(
                "CSV rows:",
                len(rows)
            )

            if not rows:

                print(
                    "ERROR: CSV contains no rows."
                )

                browser.close()
                return

            print()
            print("HEADERS:")
            print(rows[0])

            if len(rows) > 1:

                print()
                print("FIRST RECORD:")
                print(rows[1])

            # -----------------------------------------------------
            # MAKE SURE THIS IS ACTUALLY CSV
            # -----------------------------------------------------

            first_cell = rows[0][0].strip()

            if (
                first_cell.startswith("<!")
                or first_cell.lower().startswith("<html")
                or first_cell.lower().startswith("<head")
            ):

                print()
                print(
                    "ERROR: Downloaded file is HTML, "
                    "not CSV."
                )

                browser.close()
                return

        except Exception as e:

            print()
            print(
                "CSV READ ERROR:",
                repr(e)
            )

            browser.close()
            return

        # ---------------------------------------------------------
        # DONE
        # ---------------------------------------------------------

        print()
        print("=" * 60)
        print("DOWNLOAD COMPLETE")
        print("=" * 60)

        print()
        print(
            "Org ID:",
            ORG_ID
        )

        print(
            "Output:",
            OUTPUT_FILE
        )

        print(
            "Rows:",
            len(rows)
        )

        print()

        try:

            popup.close()

        except Exception:

            pass

        browser.close()


if __name__ == "__main__":
    main()
