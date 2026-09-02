from playwright.sync_api import sync_playwright


URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"


with sync_playwright() as p:

    print("Starting Playwright...")

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    print("Opening Filings page...")

    page.goto(
        URL,
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(1500)

    print("Searching for Jacquelyn Baginski...")

    # Enter last name
    page.locator("#txtOrgLastName").fill("Baginski")

    # Enter first name
    page.locator("#txtOrgFirstName").fill("Jacquelyn")

    # Select State Representative
    page.locator("#lstOffice").select_option(
        label="State Representative"
    )

    print("Clicking Search...")

    page.locator("#lnkSubSearchOrg").click()

    # Give the ASP.NET page time to process the search
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)

    print()
    print("=" * 60)
    print("SEARCH RESULTS")
    print("=" * 60)
    print()

    print("URL:")
    print(page.url)

    print()
    print("PAGE TEXT:")
    print()

    print(page.locator("body").inner_text())

    print()
    print("=" * 60)
    print("LINKS")
    print("=" * 60)
    print()

    links = page.locator("a")

    print("Link count:", links.count())

    for i in range(links.count()):

        link = links.nth(i)

        try:
            text = link.inner_text().strip()
        except:
            text = ""

        href = link.get_attribute("href")

        if text or href:
            print()
            print("TEXT:", text)
            print("HREF:", href)

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    input("Press Enter to close...")

    browser.close()