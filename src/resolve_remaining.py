import json
import os
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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
            ensure_ascii=False
        )

    os.replace(temp_file, CANDIDATES_FILE)


def split_name(full_name):
    """
    Convert a candidate name into the first and last name
    we should use for the ERTS search.

    Examples:

        Joseph J. Solomon, Jr. -> Joseph / Solomon
        K. Joseph Shekarchi   -> Joseph / Shekarchi
        Robert E. Craven, Sr. -> Robert / Craven
        William W. O'Brien    -> William / O'Brien
        John G. Edwards       -> John / Edwards
        Frank A. Ciccone III  -> Frank / Ciccone
        Walter S. Felag Jr.   -> Walter / Felag
        Jessica de la Cruz    -> Jessica / de la Cruz
        Peter A. Appollonio Jr. -> Peter / Appollonio
        V. Susan Sosnowski    -> Susan / Sosnowski
    """

    name = full_name.strip()

    # Remove commas around suffixes.
    name = re.sub(
        r",\s*(Jr\.?|Sr\.?|II|III|IV|V)\s*$",
        "",
        name,
        flags=re.IGNORECASE
    )

    # Remove suffix without comma.
    name = re.sub(
        r"\s+(Jr\.?|Sr\.?|II|III|IV|V)\s*$",
        "",
        name,
        flags=re.IGNORECASE
    )

    parts = name.split()

    if len(parts) < 2:
        return name, ""

    # The last word is normally the surname.
    last_name = parts[-1]

    # Handle "de la Cruz", etc.
    if len(parts) >= 4:
        possible_prefix = parts[-3].lower()

        if possible_prefix in {
            "de",
            "del",
            "la",
            "van",
            "von",
            "da",
            "di"
        }:
            last_name = " ".join(parts[-3:])

    # The first actual given name is usually the first non-initial.
    first_name = parts[0]

    if re.fullmatch(r"[A-Za-z]\.?", first_name):
        if len(parts) >= 3:
            first_name = parts[1]

    return first_name, last_name


def normalize_name(name):
    """
    Normalize an organization name for comparison.
    """

    name = name.upper()

    # Remove punctuation.
    name = re.sub(r"[^A-Z0-9\s]", " ", name)

    # Collapse whitespace.
    name = re.sub(r"\s+", " ", name).strip()

    return name


def extract_org_id(page):
    """
    Extract:

        Key: 7476

    from the organization detail page.
    """

    text = page.locator("body").inner_text()

    match = re.search(
        r"\bKey:\s*(\d+)",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def search_candidate(context, candidate_name):
    """
    Search one candidate using a completely isolated browser context.
    """

    first_name, last_name = split_name(candidate_name)

    print()
    print("=" * 60)
    print("SEARCHING:", candidate_name)
    print("=" * 60)

    print()
    print("Entered:")
    print("  First:", first_name)
    print("  Last: ", last_name)

    page = context.new_page()

    page.set_default_timeout(ACTION_TIMEOUT)
    page.set_default_navigation_timeout(PAGE_TIMEOUT)

    try:
        print()
        print("Opening Filings page...")

        page.goto(
            FILINGS_URL,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

        # Wait specifically for the search form.
        page.locator("#txtOrgLastName").wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT
        )

        page.locator("#txtOrgFirstName").wait_for(
            state="visible",
            timeout=ACTION_TIMEOUT
        )

        print("Search fields verified.")

        # Fill FIRST name.
        first_field = page.locator("#txtOrgFirstName")
        first_field.fill("")
        first_field.fill(first_name)

        # Fill LAST name.
        last_field = page.locator("#txtOrgLastName")
        last_field.fill("")
        last_field.fill(last_name)

        # Verify what actually got entered.
        actual_first = first_field.input_value()
        actual_last = last_field.input_value()

        print()
        print("Actual fields:")
        print("  First:", repr(actual_first))
        print("  Last: ", repr(actual_last))

        if actual_first != first_name or actual_last != last_name:
            print()
            print("WARNING: Search fields did not retain expected values.")

            return None

        print()
        print("Clicking Search...")

        page.locator("#lnkSubSearchOrg").click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT
        )

        # Give the ASP.NET WebForms postback a moment.
        page.wait_for_timeout(1000)

        # Find organization result links.
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

        print()
        print("RESULTS:", count)

        if count == 0:
            print("No organization results.")
            return None

        results = []

        for i in range(count):
            try:
                result_name = org_links.nth(i).inner_text().strip()
            except Exception:
                continue

            results.append(result_name)

            print("-" * 60)
            print("RESULT", i + 1)
            print("NAME:", result_name)

        # Normalize the search target.
        target_first = normalize_name(first_name)
        target_last = normalize_name(last_name)

        print()
        print("TARGET:")
        print("  First:", target_first)
        print("  Last: ", target_last)

        # ---------------------------------------------------------
        # SINGLE RESULT
        # ---------------------------------------------------------

        if len(results) == 1:
            selected_link = org_links.first
            selected_name = results[0]

            print()
            print("ONE RESULT — USING IT.")
            print()
            print("SELECTED:")
            print(selected_name)

        # ---------------------------------------------------------
        # MULTIPLE RESULTS
        # ---------------------------------------------------------

        else:
            print()
            print("MULTIPLE RESULTS.")

            exact_matches = []

            for i, result_name in enumerate(results):
                normalized = normalize_name(result_name)

                print()
                print("RESULT NORMALIZED:")
                print(normalized)

                # Require the candidate's first and last names to
                # appear as separate words.
                first_match = re.search(
                    r"\b" + re.escape(target_first) + r"\b",
                    normalized
                )

                last_match = re.search(
                    r"\b" + re.escape(target_last) + r"\b",
                    normalized
                )

                if first_match and last_match:
                    exact_matches.append(i)

            if len(exact_matches) == 1:
                selected_index = exact_matches[0]
                selected_link = org_links.nth(selected_index)
                selected_name = results[selected_index]

                print()
                print("ONE STRONG MATCH FOUND.")
                print("SELECTED:", selected_name)

            else:
                print()
                print("AMBIGUOUS RESULTS — NOT GUESSING.")

                for result_name in results:
                    print("  POSSIBLE:", result_name)

                return None

        # ---------------------------------------------------------
        # OPEN ORGANIZATION
        # ---------------------------------------------------------

        print()
        print("Clicking organization...")

        selected_link.click(
            no_wait_after=True,
            timeout=ACTION_TIMEOUT
        )

        # Allow the WebForms postback to update the DOM.
        page.wait_for_timeout(1200)

        # Extract the organization key.
        org_id = extract_org_id(page)

        if not org_id:
            print()
            print("Could not find Key/OrgID on organization page.")
            return None

        print()
        print("FOUND ORG ID:", org_id)

        # Verify that the key appears on the current page.
        page_text = page.locator("body").inner_text()

        if not re.search(
            r"\bKey:\s*" + re.escape(org_id) + r"\b",
            page_text,
            re.IGNORECASE
        ):
            print("WARNING: Could not verify OrgID.")
            return None

        print()
        print("CONFIRMATION:")
        print("Key:", org_id)

        status_match = re.search(
            r"\bStatus:\s*([^\n]+)",
            page_text,
            re.IGNORECASE
        )

        if status_match:
            print("Status:", status_match.group(1).strip())

        return int(org_id)

    except PlaywrightTimeoutError as e:
        print()
        print("TIMEOUT:", str(e))
        return None

    except Exception as e:
        print()
        print("ERROR:", repr(e))
        return None

    finally:
        try:
            page.close()
        except Exception:
            pass


def main():
    print("=" * 60)
    print("RI CAMPAIGN FINANCE — ISOLATED ORG ID RETRY")
    print("=" * 60)

    candidates = load_candidates()

    # Only process candidates that do not already have an OrgID.
    remaining = []

    for candidate in candidates:
        existing = (
            candidate.get("org_id")
            or candidate.get("orgId")
            or candidate.get("ertS_org_id")
            or candidate.get("erts_org_id")
        )

        if not existing:
            remaining.append(candidate)

    print()
    print("Candidates needing Org ID:", len(remaining))

    if not remaining:
        print()
        print("Nothing to do.")
        return

    successful = 0
    failed = 0

    with sync_playwright() as p:

        print()
        print("Starting Playwright...")

        browser = p.chromium.launch(
            headless=False
        )

        try:

            for index, candidate in enumerate(remaining):

                name = candidate.get("name", "").strip()

                print()
                print(
                    f"[{index + 1}/{len(remaining)}] {name}"
                )

                print()
                print("Creating completely fresh browser context...")

                context = browser.new_context()

                try:
                    org_id = search_candidate(
                        context,
                        name
                    )

                    if org_id is not None:

                        candidate["org_id"] = org_id

                        save_candidates(candidates)

                        successful += 1

                        print()
                        print(
                            "SAVED:",
                            name,
                            "->",
                            org_id
                        )

                    else:

                        failed += 1

                        print()
                        print(
                            "FAILED:",
                            name
                        )

                finally:

                    print()
                    print(
                        "Closing candidate browser context..."
                    )

                    try:
                        context.close()
                    except Exception:
                        pass

        finally:

            browser.close()

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
