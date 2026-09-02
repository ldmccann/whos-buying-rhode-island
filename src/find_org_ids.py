import json
import os
import re
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


FILINGS_URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"
CANDIDATES_FILE = "data/candidates.json"
FAILURES_FILE = "data/org_id_failures.json"

PAGE_TIMEOUT = 15000
ACTION_TIMEOUT = 5000


def load_candidates():
    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_candidates(candidates):
    temp_file = CANDIDATES_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            candidates,
            f,
            indent=2,
            ensure_ascii=False
        )

    os.replace(temp_file, CANDIDATES_FILE)


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

def split_name(full_name):
    """
    Convert a candidate's full name into the first/last fields
    expected by the RI ERTS organization search.

    Removes middle initials and suffixes while preserving
    multi-word surnames.
    """

    name = full_name.strip()

    # Normalize commas and whitespace.
    name = re.sub(r",", " ", name)
    name = re.sub(r"\s+", " ", name)

    parts = name.split()

    if len(parts) < 2:
        return name, ""

    suffixes = {
        "JR",
        "JR.",
        "SR",
        "SR.",
        "II",
        "III",
        "IV",
        "V",
    }

    # Remove suffixes from the end.
    while parts and parts[-1].upper() in suffixes:
        parts.pop()

    if len(parts) < 2:
        return parts[0] if parts else "", ""

    # Remove a leading initial.
    # K. Joseph Shekarchi -> Joseph Shekarchi
    # V. Susan Sosnowski  -> Susan Sosnowski
    if re.fullmatch(r"[A-Za-z]\.?", parts[0]):
        parts = parts[1:]

    if len(parts) < 2:
        return parts[0] if parts else "", ""

    first_name = parts[0]

    # Remove middle initials.
    # Joseph J. Solomon -> Joseph Solomon
    # Robert E. Craven  -> Robert Craven
    # Frank A. Ciccone  -> Frank Ciccone
    #
    # A token is considered a middle initial if it is one letter
    # with an optional period.
    remaining = []

    for part in parts[1:]:
        if re.fullmatch(r"[A-Za-z]\.?", part):
            continue
        remaining.append(part)

    if not remaining:
        return first_name, ""

    # Preserve multi-word surnames.
    # Jessica de la Cruz -> Jessica / de la Cruz
    last_name = " ".join(remaining)

    return first_name, last_name

def extract_org_key(page):
    """
    Look for:

        Key: 7476

    anywhere in the page text.
    """

    try:
        text = page.locator("body").inner_text(timeout=ACTION_TIMEOUT)
    except Exception:
        return None

    match = re.search(
        r"\bKey:\s*(\d+)",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def search_candidate(page, first_name, last_name):
    """
    Search the RI ERTS filings page for one candidate.

    The RI site uses ASP.NET WebForms, so we explicitly clear,
    fill, and verify each search field before submitting.
    """

    print("Opening Filings page...")

    try:
        page.goto(
            FILINGS_URL,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )
    except PlaywrightTimeoutError:
        print("Initial page load timed out.")
        return None

    # Wait for BOTH search fields.
    try:
        page.locator("#txtOrgLastName").wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT
        )

        page.locator("#txtOrgFirstName").wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT
        )

    except PlaywrightTimeoutError:
        print("Search fields did not appear.")
        return None

    last_field = page.locator("#txtOrgLastName")
    first_field = page.locator("#txtOrgFirstName")

    print("Searching for:", first_name, last_name)

    # ----------------------------------------------------------
    # CLEAR FIELDS
    # ----------------------------------------------------------

    last_field.fill("")
    first_field.fill("")

    # ----------------------------------------------------------
    # FILL LAST NAME
    # ----------------------------------------------------------

    last_field.fill(last_name)

    # ----------------------------------------------------------
    # FILL FIRST NAME
    # ----------------------------------------------------------

    first_field.fill(first_name)

    # ----------------------------------------------------------
    # VERIFY WHAT THE PAGE ACTUALLY RECEIVED
    # ----------------------------------------------------------

    actual_last = last_field.input_value()
    actual_first = first_field.input_value()

    print("Entered first name:", repr(actual_first))
    print("Entered last name: ", repr(actual_last))

    if actual_first != first_name:
        print("WARNING: First name was misfilled.")
        print("Expected:", repr(first_name))
        print("Actual:  ", repr(actual_first))

        # One retry.
        first_field.fill("")
        first_field.fill(first_name)

        actual_first = first_field.input_value()

    if actual_last != last_name:
        print("WARNING: Last name was misfilled.")
        print("Expected:", repr(last_name))
        print("Actual:  ", repr(actual_last))

        # One retry.
        last_field.fill("")
        last_field.fill(last_name)

        actual_last = last_field.input_value()

    # Final verification.
    if (
        first_field.input_value() != first_name
        or last_field.input_value() != last_name
    ):
        print("ERROR: Could not reliably fill search fields.")
        return None

    print("Search fields verified.")

    # ----------------------------------------------------------
    # SUBMIT SEARCH
    # ----------------------------------------------------------

    print("Clicking Search...")

    try:
        page.locator("#lnkSubSearchOrg").click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT
        )
    except Exception as e:
        print("Search click failed:", repr(e))
        return None

    # ----------------------------------------------------------
    # WAIT FOR RESULTS
    # ----------------------------------------------------------

    org_links = page.locator(
        "a[href*='__doPostBack'][href*='dgdOrgSearchResults']"
    )

    try:
        org_links.first.wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT
        )
    except PlaywrightTimeoutError:
        print("No organization result appeared.")
        return None

    count = org_links.count()

    print("Organization links found:", count)

    target = f"{first_name} {last_name}".strip().upper()

    for i in range(count):

        link = org_links.nth(i)

        try:
            text = link.inner_text().strip().upper()
        except Exception:
            continue

        print("Result:", text)

        if text == target:
            print("MATCH:", text)
            return link

    # If only one result exists, use it.
    if count == 1:
        print("Using only organization result.")
        return org_links.first

    print("No exact organization match.")

    return None

def process_candidate(browser, candidate):
    """
    Process exactly ONE candidate using a completely fresh page.
    """

    name = candidate.get("name", "").strip()

    first_name, last_name = split_name(name)

    print()
    print("=" * 60)
    print("SEARCHING:", name)
    print("=" * 60)

    print("First name:", first_name)
    print("Last name: ", last_name)

    # IMPORTANT:
    # Completely fresh page for every candidate.
    page = browser.new_page()

    page.set_default_timeout(ACTION_TIMEOUT)
    page.set_default_navigation_timeout(PAGE_TIMEOUT)

    try:
        org_link = search_candidate(
            page,
            first_name,
            last_name
        )

        if org_link is None:
            print("NO ORGANIZATION FOUND")
            return None, "not_found"

        print()
        print("Organization:", org_link.inner_text().strip())

        print()
        print("Clicking organization...")

        try:
            org_link.click(
                no_wait_after=True,
                timeout=ACTION_TIMEOUT
            )
        except Exception as e:
            print("Organization click failed:", repr(e))
            return None, "click_error"

        # The WebForms postback needs a moment to update the DOM.
        time.sleep(0.75)

        # Try immediately first.
        org_id = extract_org_key(page)

        if org_id:
            print("FOUND ORG ID:", org_id)
            return org_id, "success"

        # If it isn't there yet, give it a few short chances.
        for attempt in range(4):
            time.sleep(0.75)

            org_id = extract_org_key(page)

            if org_id:
                print("FOUND ORG ID:", org_id)
                return org_id, "success"

        print("Could not find OrgID.")

        return None, "no_key"

    except PlaywrightTimeoutError as e:
        print("TIMEOUT:", str(e))
        return None, "timeout"

    except Exception as e:
        print("ERROR:", repr(e))
        return None, "error"

    finally:
        # ALWAYS close the page before moving to the next candidate.
        try:
            page.close()
        except Exception:
            pass


def main():

    print("=" * 60)
    print("RI CAMPAIGN FINANCE — ORG ID DISCOVERY")
    print("=" * 60)

    candidates = load_candidates()
    failures = load_failures()

    print()
    print("Loaded", len(candidates), "candidates.")

    successful = 0
    skipped = 0
    failed = 0

    with sync_playwright() as p:

        print()
        print("Starting Playwright...")

        browser = p.chromium.launch(
            headless=False
        )

        try:

            for index, candidate in enumerate(candidates):

                name = candidate.get("name", "").strip()

                print()
                print(
                    f"[{index + 1}/{len(candidates)}] "
                    f"Processing {name}"
                )

                # --------------------------------------------------
                # SKIP ALREADY PROCESSED
                # --------------------------------------------------

                existing = (
                    candidate.get("org_id")
                    or candidate.get("orgId")
                    or candidate.get("erts_org_id")
                    or candidate.get("ertS_org_id")
                )

                if existing:

                    print(
                        "Already has OrgID:",
                        existing
                    )

                    skipped += 1

                    continue

                # --------------------------------------------------
                # PROCESS ONE CANDIDATE
                # --------------------------------------------------

                org_id, status = process_candidate(
                    browser,
                    candidate
                )

                # --------------------------------------------------
                # SUCCESS
                # --------------------------------------------------

                if status == "success":

                    candidate["org_id"] = int(org_id)

                    save_candidates(candidates)

                    successful += 1

                    print()
                    print(
                        "SAVED:",
                        name,
                        "->",
                        org_id
                    )

                # --------------------------------------------------
                # FAILURE
                # --------------------------------------------------

                else:

                    failed += 1

                    already_recorded = any(
                        item.get("name") == name
                        for item in failures
                    )

                    if not already_recorded:

                        failures.append({
                            "name": name,
                            "status": status
                        })

                        save_failures(failures)

                    print(
                        "FAILED:",
                        name,
                        "(" + status + ")"
                    )

                # Small pause between candidates.
                time.sleep(0.5)

        finally:

            browser.close()

    print()
    print("=" * 60)
    print("ORG ID DISCOVERY COMPLETE")
    print("=" * 60)

    print()
    print("Successful:", successful)
    print("Skipped:   ", skipped)
    print("Failed:    ", failed)

    print()
    print("Candidates saved to:")
    print(CANDIDATES_FILE)

    print()
    print("Failures saved to:")
    print(FAILURES_FILE)


if __name__ == "__main__":
    main()
