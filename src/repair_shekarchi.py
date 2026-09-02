import csv
import os

INPUT_FILE = "data/contributions/k_joseph_shekarchi_2026_q1.csv"
TEMP_FILE = INPUT_FILE + ".tmp"

EXPECTED_COLUMNS = 22

print("=" * 60)
print("REPAIRING SHEKARCHI CSV")
print("=" * 60)
print()

with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))

header = rows[0]
data = rows[1:]

print("Expected columns:", EXPECTED_COLUMNS)
print("Original physical data rows:", len(data))
print()

fixed = []
i = 0
repaired = 0

while i < len(data):
    row = data[i]

    # Normal transaction row
    if len(row) == EXPECTED_COLUMNS:
        fixed.append(row)
        i += 1
        continue

    # Interest / capital-gain record starts with the ContributionID
    # and contains the first 9 columns.
    if len(row) == 9 and row[0].isdigit():
        contribution_id = row[0]

        # Start with the nine fields already present.
        combined = row[:]

        i += 1

        # Continuation rows follow until the final 14-column row.
        while i < len(data):
            continuation = data[i]

            if len(continuation) == EXPECTED_COLUMNS:
                break

            if len(continuation) == 14:
                combined.extend(continuation)
                i += 1
                break

            # One-column continuation such as:
            # LMBS- $226.95
            # GSIE- $177.68
            combined[8] += continuation[0]
            i += 1

        if len(combined) == EXPECTED_COLUMNS:
            fixed.append(combined)
            repaired += 1
            print(
                f"REPAIRED {contribution_id}: "
                f"{row[1]} ${row[7]}"
            )
        else:
            print(
                f"WARNING: Could not fully repair "
                f"{contribution_id}; got {len(combined)} columns"
            )

        continue

    print(
        f"WARNING: Unexpected row at position {i + 2}: "
        f"{len(row)} columns"
    )
    i += 1

print()
print("Repaired records:", repaired)
print("Final transaction rows:", len(fixed))
print()

# Write repaired file.
with open(TEMP_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(fixed)

os.replace(TEMP_FILE, INPUT_FILE)

print("REPAIRED FILE:", INPUT_FILE)
print("=" * 60)
