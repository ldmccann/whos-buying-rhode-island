from playwright.sync_api import sync_playwright


URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"


with sync_playwright() as p:

    print("Starting Playwright...")

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    print("Opening Filings page...")

    response = page.goto(
        URL,
        wait_until="domcontentloaded"
    )

    print("HTTP status:", response.status)
    print("Title:", page.title())

    page.wait_for_timeout(3000)

    print()
    print("=" * 60)
    print("PAGE TEXT")
    print("=" * 60)
    print()

    text = page.locator("body").inner_text()

    print(text)

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