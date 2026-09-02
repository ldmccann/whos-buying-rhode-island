from playwright.sync_api import sync_playwright

URL = (
    "https://www.ricampaignfinance.com/RIPublic/Reporting/TransactionReport.aspx?"
    "OrgID=7476&"
    "BeginDate=01%2F01%2F2026&"
    "EndDate=03%2F31%2F2026&"
    "LastName=&"
    "FirstName=&"
    "ContType=0&"
    "State=&"
    "City=&"
    "ZIPCode=&"
    "EmployerName=&"
    "Amount=0&"
    "ReportType=Contrib&"
    "CFStatus=F&"
    "MPFStatus=A&"
    "Level=S&"
    "SumBy=Type&"
    "Sort1=ReceiptDate&"
    "Direct1=desc&"
    "Sort2=None&"
    "Direct2=asc&"
    "Sort3=None&"
    "Direct3=asc&"
    "Site=Public&"
    "Incomplete=A&"
    "ContSource=CF"
)


def log_response(response):
    if "DownloadFile" in response.url:
        print()
        print("=== DOWNLOAD RESPONSE ===")
        print("URL:", response.url)
        print("Status:", response.status)
        print("Content-Type:", response.headers.get("content-type"))
        print(
            "Content-Disposition:",
            response.headers.get("content-disposition")
        )


with sync_playwright() as p:

    print("Starting Playwright...")

    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        accept_downloads=True
    )

    context.on("response", log_response)

    page = context.new_page()

    print("Opening ERTS report...")

    response = page.goto(
        URL,
        wait_until="domcontentloaded"
    )

    print("Navigation completed.")
    print("Title:", page.title())
    print("HTTP status:", response.status)

    export_button = page.locator("#lnkExport")

    print("Export button count:", export_button.count())

    print()
    print("Clicking Export...")

    with page.expect_popup() as popup_info:
        export_button.click()

    popup = popup_info.value

    print()
    print("POPUP CREATED")
    print("Popup URL:", popup.url)
    print("Popup title:", popup.title())

    # Wait for the Download File page to load.
    popup.wait_for_load_state("domcontentloaded")

    print()
    print("Looking for View/Save link...")

    view_save = popup.locator("#hypFileDownload")

    print("View/Save count:", view_save.count())

    if view_save.count() == 0:
        print("ERROR: View/Save link was not found.")
        input("Press Enter to close...")
        browser.close()
        raise SystemExit(1)

    print()
    print("Clicking View/Save...")

    with popup.expect_download() as download_info:
        view_save.click()

    download = download_info.value

    print()
    print("=== ACTUAL DOWNLOAD ===")
    print("Suggested filename:", download.suggested_filename)
    print("Failure:", download.failure())

    output_path = "data/jacquelyn_baginski_2026_q1.csv"

    download.save_as(output_path)

    print()
    print("SUCCESS!")
    print("Saved:", output_path)

    input("\nPress Enter to close...")

    browser.close()
