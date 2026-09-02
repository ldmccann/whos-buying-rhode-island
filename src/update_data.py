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
    print("PUBLISHING UPDATED DATA")
    print("=" * 60)

    result = subprocess.run([
        "git", "add",
        "data/candidates.json",
        "data/contributions_all.json",
        "data/donor_summary.json",
    ])

    if result.returncode != 0:
        print("GIT ADD FAILED")
        sys.exit(result.returncode)

    result = subprocess.run(["git", "diff", "--cached", "--quiet"])

    if result.returncode == 0:
        print("No public data changes to publish.")
    elif result.returncode == 1:
        print("Changes detected. Committing and pushing...")
        
        result = subprocess.run([
            "git", "commit", "-m", "Update campaign finance data"
        ])

        if result.returncode != 0:
            print("GIT COMMIT FAILED")
            sys.exit(result.returncode)

        result = subprocess.run(["git", "push"])

        if result.returncode != 0:
            print("GIT PUSH FAILED")
            sys.exit(result.returncode)
    else:
        print("GIT STATUS CHECK FAILED")
        sys.exit(result.returncode)

        print("Running:", " ".join(command))
        result = subprocess.run(command)
        if result.returncode != 0:
            print()
            print("=" * 60)
            print("GIT PUBLISH FAILED")
            print("=" * 60)
            print("Failed command:", " ".join(command))
            print("Exit code:", result.returncode)
            sys.exit(result.returncode)

    print()
    print("=" * 60)
    print("FULL DATA UPDATE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
