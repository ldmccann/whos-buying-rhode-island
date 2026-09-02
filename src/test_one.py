import re
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


FILINGS_URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"

PAGE_TIMEOUT = 15000
ACTION_TIMEOUT = 8000


TESTS = [
    {
        "name": "K. Joseph Shekarchi",
        "first": "K",
        "last": "Shekarchi",
    },
    {
        "name": "William W.O'Brien",
        "first": "William",
        "last": "O'Brien",
    },
    {
        "name": "John G. Edwards",
        "first": "John",
        "last": "Edwards",
    },
    {
        "name": "V. Susan Sosnowski",
        "first": "V",
        "last": "Sosnowski",
    },
]


def normalize(text):
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def extract_org_id(page):
    text = page.locator("body").inner_text()

    match = re.search(r"\bKey:\s*(\d+)", text, re.IGNORECASE)

    if match:
        return match.group(1)

    return None


def search_one(browser, candidate):
    print()
    print("=" * 60)
    print("SEARCHING:", candidate["name"])
    print("=" * 60)

    print("First:", candidate["first"])
    print("Last: ", candidate["last"])

    context = browser.new_context()

    try:
        page = context.new_page()

        page.set_default_timeout(ACTION_TIMEOUT)
        page.set_default_navigation_timeout(PAGE_TIMEOUT)

        print("Opening Filings page...")

        page.goto(
            FILINGS_URL,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        page.locator("#txtOrgLastName").wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT,
        )

        first = page.locator("#txtOrgFirstName")
        last = page.locator("#txtOrgLastName")

        first.fill(candidate["first"])
        last.fill(candidate["last"])

        print()
        print("Actual values:")
        print("First:", repr(first.input_value()))
        print("Last: ", repr(last.input_value()))

        print()
        print("Clicking Search...")

        page.locator("#lnkSubSearchOrg").click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT,
        )

        time.sleep(1)

        links = page.locator(
            "a[href*='__doPostBack'][href*='dgdOrgSearchResults']"
        )

        count = links.count()

        print()
        print("RESULTS:", count)

        if count == 0:
            print("NO RESULTS")
            return None

        results = []

        for i in range(count):
            text = links.nth(i).inner_text().strip()

            print("-" * 60)
            print("RESULT", i + 1)
            print("NAME:", text)

            results.append(
                {
                    "text": text,
                    "locator": links.nth(i),
                }
            )

        # ---------------------------------------------------------
        # Choose a result.
        #
        # The search fields are intentionally broad enough that
        # suffixes and middle initials may appear in the result.
        # If there is exactly one result, use it.
        # If there are multiple results, look for the safest match.
        # ---------------------------------------------------------

        selected = None

        if len(results) == 1:
            selected = results[0]

            print()
            print("ONE RESULT — USING IT.")

        else:
            target_first = normalize(candidate["first"])
            target_last = normalize(candidate["last"])

            print()
            print("TARGET:")
            print("First:", target_first)
            print("Last: ", target_last)

            possible = []

            for result in results:
                normalized = normalize(result["text"])

                print()
                print("Checking:", result["text"])
                print("Normalized:", normalized)

                words = normalized.split()

                if (
                    target_first in words
                    and target_last in words
                ):
                    possible.append(result)

            if len(possible) == 1:
                selected = possible[0]

                print()
                print("UNIQUE MATCH:")
                print(selected["text"])

            elif len(possible) > 1:
                print()
                print("AMBIGUOUS RESULTS — NOT GUESSING.")

                for result in possible:
                    print("POSSIBLE:", result["text"])

                return None

            else:
                print()
                print("NO SAFE MATCH")

                return None

        print()
        print("SELECTED:", selected["text"])

        print()
        print("Clicking organization...")

        selected["locator"].click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT,
        )

        time.sleep(1)

        org_id = extract_org_id(page)

        if org_id:
            print()
            print("FOUND ORG ID:", org_id)

            print()
            print("CONFIRMATION:")

            body = page.locator("body").inner_text()

            key_match = re.search(
                r"(Key:\s*\d+)",
                body,
                re.IGNORECASE,
            )

            if key_match:
                print(key_match.group(1))

            status_match = re.search(
                r"(Status:\s*\w+)",
                body,
                re.IGNORECASE,
            )

            if status_match:
                print(status_match.group(1))

            return org_id

        print()
        print("COULD NOT FIND ORG ID")

        return None

    except PlaywrightTimeoutError as e:
        print()
        print("TIMEOUT:", e)

        return None

    except Exception as e:
        print()
        print("ERROR:", repr(e))

        return None

    finally:
        print()
        print("Closing browser context...")

        context.close()


def main():
    print("=" * 60)
    print("RI CAMPAIGN FINANCE — FOUR REMAINING ORG IDS")
    print("=" * 60)

    with sync_playwright() as p:
        print()
        print("Starting browser...")

        browser = p.chromium.launch(
            headless=False
        )

        try:
            for candidate in TESTS:
                org_id = search_one(
                    browser,
                    candidate,
                )

                print()
                print("=" * 60)

                if org_id:
                    print(
                        candidate["name"],
                        "->",
                        org_id,
                    )
                else:
                    print(
                        candidate["name"],
                        "-> FAILED",
                    )

                print("=" * 60)

                time.sleep(1)

        finally:
            browser.close()

    print()
    print("DONE")


if __name__ == "__main__":
    main()
