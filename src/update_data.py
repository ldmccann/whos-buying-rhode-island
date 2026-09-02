import subprocess
import sys


STEPS = [
    [
        sys.executable,
        "src/download_all_contributions.py",
        "--force",
    ],
    [
        sys.executable,
        "src/build_contributions.py",
    ],
    [
        sys.executable,
        "src/build_contributions_json.py",
    ],
    [
        sys.executable,
        "src/build_donor_summary.py",
    ],
    [
        sys.executable,
        "src/build_web_data.py",
    ],
]


def main():
    print("=" * 60)
    print("RI CAMPAIGN FINANCE — FULL DATA UPDATE")
    print("=" * 60)

    for step_number, command in enumerate(STEPS, start=1):

        print()
        print("=" * 60)
        print(f"STEP {step_number} OF {len(STEPS)}")
        print("=" * 60)
        print("Running:", " ".join(command))
        print()

        result = subprocess.run(command)

        if result.returncode != 0:
            print()
            print("=" * 60)
            print("UPDATE FAILED")
            print("=" * 60)
            print("Failed step:", step_number)
            print("Exit code:", result.returncode)
            sys.exit(result.returncode)

    print()
    print("=" * 60)
    print("FULL DATA UPDATE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
