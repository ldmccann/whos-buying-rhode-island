import json
import os
import re
import time

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

FILINGS_URL = "https://ricampaignfinance.com/RIPublic/Filings.aspx"
CANDIDATES_FILE = "data/candidates.json"

PAGE_TIMEOUT = 15000
ACTION_TIMEOUT = 8000


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
            ensure_ascii=False,
        )

    os.replace(temp_file, CANDIDATES_FILE)


def split_name(full_name):
    """
    Convert candidate names into the names we want to search.

    Examples:

        Joseph J. Solomon, Jr. -> Joseph / Solomon
        K. Joseph Shekarchi   -> Joseph / Shekarchi
        Robert E. Craven, Sr. -> Robert / Craven
        John G. Edwards       -> John / Edwards
        Frank A. Ciccone III  -> Frank / Ciccone
        Walter S. Felag Jr.   -> Walter / Felag
        Jessica de la Cruz    -> Jessica / de la Cruz
        Peter A. Appollonio Jr. -> Peter / Appollonio
        V. Susan Sosnowski    -> Susan / Sosnowski
    """

    name = full_name.strip()

    # Remove suffixes.
    name = re.sub(
        r",?\s+(Jr\.?|Sr\.?|II|III|IV|V)$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    parts = name.split()

    if len(parts) < 2:
        return name, ""

    # Skip leading initial:
    # K. Joseph Shekarchi -> Joseph Shekarchi
    # V. Susan Sosnowski -> Susan Sosnowski
    if (
        len(parts[0].rstrip(".")) == 1
        and len(parts) >= 3
    ):
        parts = parts[1:]

    first_name = parts[0]

    # Everything after the first name is treated as the surname.
    last_name = " ".join(parts[1:])

    # Remove middle initials from the beginning of the surname.
    # Joseph J. Solomon -> Joseph / Solomon
    while (
        " " in last_name
        and re.match(r"^[A-Za-z]\.?\s+", last_name)
    ):
        last_name = re.sub(
            r"^[A-Za-z]\.?\s+",
            "",
            last_name,
        )

    return first_name, last_name


def normalize_name(value):
    """
    Normalize an ERTS organization name for comparison.
    """

    value = value.upper()

    # Apostrophes and punctuation become spaces.
    value = re.sub(r"[^A-Z0-9]+", " ", value)

    # Remove common suffixes.
    value = re.sub(
        r"\b(JR|SR|II|III|IV|V)\b",
        "",
        value,
    )

    # Remove standalone middle initials.
    value = re.sub(
        r"\b[A-Z]\b",
        "",
        value,
    )

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract_org_key(page):
    """
    Extract the ERTS organization Key from the organization
    detail page.
    """

    text = page.locator("body").inner_text()

    match = re.search(
        r"\bKey:\s*(\d+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    return None


def search_one_candidate(browser, full_name):
    """
    Process ONE candidate in a completely isolated browser context.

    A new context is created for every candidate.
    """

    first_name, last_name = split_name(full_name)

    print()
    print("=" * 60)
    print("SEARCHING:", full_name)
    print("=" * 60)

    print()
    print("Entered:")
    print("  First:", first_name)
    print("  Last: ", last_name)

    context = None
    page = None

    try:
        # ---------------------------------------------------------
        # BRAND NEW BROWSER CONTEXT
        # ---------------------------------------------------------

        print()
        print("Creating completely fresh browser context...")

        context = browser.new_context()

        page = context.new_page()

        page.set_default_timeout(ACTION_TIMEOUT)
        page.set_default_navigation_timeout(PAGE_TIMEOUT)

        # ---------------------------------------------------------
        # OPEN FILINGS PAGE
        # ---------------------------------------------------------

        print("Opening Filings page...")

        page.goto(
            FILINGS_URL,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        page.locator(
            "#txtOrgLastName"
        ).wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT,
        )

        # ---------------------------------------------------------
        # FILL SEARCH
        # ---------------------------------------------------------

        first_field = page.locator("#txtOrgFirstName")
        last_field = page.locator("#txtOrgLastName")

        first_field.fill("")
        last_field.fill("")

        first_field.fill(first_name)
        last_field.fill(last_name)

        # Verify what Playwright actually entered.
        actual_first = first_field.input_value()
        actual_last = last_field.input_value()

        print()
        print("Search fields verified:")
        print("  First:", repr(actual_first))
        print("  Last: ", repr(actual_last))

        if actual_first != first_name:
            print("ERROR: First name did not stick.")
            return None

        if actual_last != last_name:
            print("ERROR: Last name did not stick.")
            return None

        # ---------------------------------------------------------
        # CLICK SEARCH
        # ---------------------------------------------------------

        print()
        print("Clicking Search...")

        page.locator(
            "#lnkSubSearchOrg"
        ).click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT,
        )

        # The ERTS site uses WebForms postbacks.
        page.wait_for_timeout(1500)

        # ---------------------------------------------------------
        # FIND ORGANIZATION RESULTS
        # ---------------------------------------------------------

        org_links = page.locator(
            "a[href*='__doPostBack'][href*='dgdOrgSearchResults']"
        )

        try:
            org_links.first.wait_for(
                state="visible",
                timeout=ACTION_TIMEOUT,
            )
        except PlaywrightTimeoutError:
            print()
            print("No organization result appeared.")
            return None

        count = org_links.count()

        print()
        print("RESULTS:", count)

        if count == 0:
            return None

        results = []

        for i in range(count):
            link = org_links.nth(i)

            try:
                result_name = link.inner_text().strip()
            except Exception:
                continue

            results.append(
                {
                    "index": i,
                    "name": result_name,
                }
            )

            print("-" * 60)
            print("RESULT", i + 1)
            print("NAME:", result_name)

        # ---------------------------------------------------------
        # DETERMINE BEST RESULT
        # ---------------------------------------------------------

        target_normalized = normalize_name(full_name)

        print()
        print("TARGET NORMALIZED:")
        print(target_normalized)

        matches = []

        for result in results:
            result_normalized = normalize_name(
                result["name"]
            )

            print()
            print(
                "RESULT NORMALIZED:",
                result_normalized,
            )

            if result_normalized == target_normalized:
                matches.append(result)

        # ---------------------------------------------------------
        # ONE RESULT
        # ---------------------------------------------------------

        if count == 1:
            selected_index = 0

            print()
            print("ONE RESULT — USING IT.")

        # ---------------------------------------------------------
        # EXACT NORMALIZED MATCH
        # ---------------------------------------------------------

        elif len(matches) == 1:
            selected_index = matches[0]["index"]

            print()
            print("EXACT NORMALIZED MATCH.")

        # ---------------------------------------------------------
        # AMBIGUOUS
        # ---------------------------------------------------------

        else:
            print()
            print("AMBIGUOUS RESULTS — NOT GUESSING.")

            for result in results:
                print(
                    "  POSSIBLE:",
                    result["name"],
                )

            return None

        selected = org_links.nth(selected_index)

        selected_name = selected.inner_text().strip()

        print()
        print("SELECTED:")
        print(selected_name)

        # ---------------------------------------------------------
        # CLICK ORGANIZATION
        # ---------------------------------------------------------

        print()
        print("Clicking organization...")

        selected.click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT,
        )

        # Give WebForms postback time to populate
        # the organization detail.
        page.wait_for_timeout(1500)

        # ---------------------------------------------------------
        # EXTRACT KEY
        # ---------------------------------------------------------

        org_id = extract_org_key(page)

        if org_id:
            print()
            print("FOUND ORG ID:", org_id)

            # Show confirmation from page.
            try:
                body_text = page.locator(
                    "body"
                ).inner_text()

                key_position = body_text.find(
                    "Key:"
                )

                if key_position >= 0:
                    snippet = body_text[
                        key_position:key_position + 100
                    ]

                    print()
                    print("CONFIRMATION:")
                    print(snippet)

            except Exception:
                pass

            return org_id

        print()
        print("Could not find organization Key.")

        return None

    except PlaywrightTimeoutError as e:
        print()
        print("TIMEOUT:", str(e))
        return None

    except Exception as e:
        print()
        print("ERROR:", repr(e))
        return None

    finally:
        # ---------------------------------------------------------
        # DESTROY EVERYTHING
        # ---------------------------------------------------------

        print()
        print("Closing candidate browser context...")

        if page is not None:
            try:
                page.close()
            except Exception:
                pass

        if context is not None:
            try:
                context.close()
            except Exception:
                pass


def main():
    print("=" * 60)
    print("RI CAMPAIGN FINANCE — ISOLATED ORG ID RETRY")
    print("=" * 60)

    candidates = load_candidates()

    missing = []

    for candidate in candidates:
        existing = (
            candidate.get("org_id")
            or candidate.get("orgId")
            or candidate.get("ertS_org_id")
            or candidate.get("erts_org_id")
        )

        if not existing:
            missing.append(candidate)

    print()
    print(
        "Candidates needing Org ID:",
        len(missing),
    )

    if not missing:
        print()
        print("Nothing to do.")
        return

    successful = 0
    failed = 0

    with sync_playwright() as p:

        print()
        print("Starting Playwright...")

        # Only the browser itself is shared.
        #
        # Each candidate gets a NEW context.
        browser = p.chromium.launch(
            headless=False
        )

        try:

            for index, candidate in enumerate(missing):

                name = candidate.get(
                    "name",
                    "",
                ).strip()

                print()
                print(
                    f"[{index + 1}/{len(missing)}] {name}"
                )

                org_id = search_one_candidate(
                    browser,
                    name,
                )

                if org_id:

                    candidate["org_id"] = int(
                        org_id
                    )

                    save_candidates(
                        candidates
                    )

                    successful += 1

                    print()
                    print(
                        "SAVED:",
                        name,
                        "->",
                        org_id,
                    )

                else:

                    failed += 1

                    print()
                    print(
                        "FAILED:",
                        name,
                    )

                # Small pause between completely
                # isolated browser contexts.
                time.sleep(0.5)

        finally:

            try:
                browser.close()
            except Exception:
                pass

    print()
    print("=" * 60)
    print("ISOLATED RETRY COMPLETE")
    print("=" * 60)

    print()
    print("Successful:", successful)
    print("Failed:    ", failed)

    print()
    print("Candidates saved to:")
    print(CANDIDATES_FILE)


if __name__ == "__main__":
    main()
