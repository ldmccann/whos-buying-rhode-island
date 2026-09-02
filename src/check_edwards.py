from playwright.sync_api import sync_playwright
import time
import re

FILINGS_URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    try:
        context = browser.new_context()
        page = context.new_page()

        page.goto(
            FILINGS_URL,
            wait_until="domcontentloaded",
            timeout=15000,
        )

        page.locator("#txtOrgLastName").fill("Edwards")
        page.locator("#txtOrgFirstName").fill("John")

        page.locator("#lnkSubSearchOrg").click(
            no_wait_after=True,
            timeout=8000,
        )

        time.sleep(1)

        links = page.locator(
            "a[href*='__doPostBack'][href*='dgdOrgSearchResults']"
        )

        print()
        print("=" * 60)
        print("EDWARDS RESULTS")
        print("=" * 60)

        count = links.count()

        print("Results:", count)

        for i in range(count):
            print()
            print("RESULT", i + 1)
            print("NAME:", links.nth(i).inner_text().strip())

        for i in range(count):
            print()
            print("=" * 60)
            print("OPENING RESULT", i + 1)
            print("=" * 60)

            # Re-run the search because clicking the organization
            # changes the page into the organization detail view.
            if i > 0:
                page.goto(
                    FILINGS_URL,
                    wait_until="domcontentloaded",
                    timeout=15000,
                )

                page.locator("#txtOrgLastName").fill("Edwards")
                page.locator("#txtOrgFirstName").fill("John")

                page.locator("#lnkSubSearchOrg").click(
                    no_wait_after=True,
                    timeout=8000,
                )

                time.sleep(1)

                links = page.locator(
                    "a[href*='__doPostBack'][href*='dgdOrgSearchResults']"
                )

            name = links.nth(i).inner_text().strip()

            print("NAME:", name)

            links.nth(i).click(
                no_wait_after=True,
                timeout=8000,
            )

            time.sleep(1)

            body = page.locator("body").inner_text()

            print()
            print("DETAILS:")
            print()

            # Print the important organization fields.
            for label in [
                "Name:",
                "Address:",
                "City, State Zip:",
                "Key:",
                "Status:",
                "Telephone:",
                "Email:",
            ]:
                match = re.search(
                    re.escape(label) + r".*",
                    body,
                    re.IGNORECASE,
                )

                if match:
                    print(match.group(0))

            print()

        context.close()

    finally:
        browser.close()
