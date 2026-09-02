import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


FILINGS_URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"

PAGE_TIMEOUT = 15000
ACTION_TIMEOUT = 8000


def normalize(value):
    value = value.upper()
    value = re.sub(r"[^A-Z0-9 ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def search(page, first_name, last_name):

    print()
    print("=" * 60)
    print(f"SEARCHING: {first_name} {last_name}")
    print("=" * 60)

    page.goto(
        FILINGS_URL,
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT
    )

    page.locator("#txtOrgLastName").wait_for(
        state="visible",
        timeout=ACTION_TIMEOUT
    )

    first = page.locator("#txtOrgFirstName")
    last = page.locator("#txtOrgLastName")

    first.fill("")
    last.fill("")

    first.fill(first_name)
    last.fill(last_name)

    print("Entered:")
    print("  First:", first.input_value())
    print("  Last: ", last.input_value())

    page.locator("#lnkSubSearchOrg").click(
        timeout=ACTION_TIMEOUT
    )

    links = page.locator(
        "a[href*='dgdOrgSearchResults']"
    )

    try:
        links.first.wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT
        )
    except PlaywrightTimeoutError:
        print("No results.")
        return

    count = links.count()

    print()
    print("RESULTS:", count)

    for i in range(count):

        link = links.nth(i)

        try:
            name = link.inner_text().strip()
        except Exception:
            continue

        print()
        print("-" * 60)
        print("RESULT", i + 1)
        print("NAME:", name)

        # Click this specific organization.
        try:

            link.click(
                no_wait_after=True,
                timeout=ACTION_TIMEOUT
            )

            page.wait_for_timeout(1000)

            text = page.locator("body").inner_text()

            # Look for the Key.
            match = re.search(
                r"\bKey:\s*(\d+)",
                text,
                re.IGNORECASE
            )

            if match:
                print("ORG ID:", match.group(1))
            else:
                print("ORG ID: NOT FOUND")

            # Print the organization information section.
            lines = text.splitlines()

            for line in lines:

                stripped = line.strip()

                if (
                    stripped.startswith("Name:")
                    or stripped.startswith("Address:")
                    or stripped.startswith("City, State Zip:")
                    or stripped.startswith("Key:")
                    or stripped.startswith("Status:")
                ):
                    print(stripped)

        except Exception as e:

            print("ERROR:", repr(e))

        # Return to the search page for the next result.
        try:

            page.goto(
                FILINGS_URL,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )

        except Exception:
            pass

        try:
            page.locator("#txtOrgLastName").wait_for(
                state="visible",
                timeout=ACTION_TIMEOUT
            )
        except Exception:
            pass

        # Re-run the search so the result links are available.
        try:

            page.locator("#txtOrgFirstName").fill(first_name)
            page.locator("#txtOrgLastName").fill(last_name)

            page.locator("#lnkSubSearchOrg").click(
                timeout=ACTION_TIMEOUT
            )

            links = page.locator(
                "a[href*='dgdOrgSearchResults']"
            )

            links.first.wait_for(
                state="visible",
                timeout=ACTION_TIMEOUT
            )

        except Exception:

            print("Could not restore search results.")
            return


def main():

    candidates = [
        ("Joseph", "Solomon"),
        ("Robert", "Craven"),
        ("John", "Edwards"),
    ]

    with sync_playwright() as p:

        print("Starting Playwright...")

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        page.set_default_timeout(ACTION_TIMEOUT)
        page.set_default_navigation_timeout(PAGE_TIMEOUT)

        try:

            for first, last in candidates:

                try:
                    search(page, first, last)

                except PlaywrightTimeoutError as e:

                    print()
                    print("TIMEOUT:", str(e))

                except Exception as e:

                    print()
                    print("ERROR:", repr(e))

        finally:

            browser.close()


if __name__ == "__main__":
    main()
