import argparse
from pathlib import Path


TEMPLATE = '''# Auto-generated legal compliance test template
# Update decision cases and expected outputs before running.

import json
from pathlib import Path


def load_cases(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_compliance_cases():
    cases = load_cases(Path("{cases_path}"))
    for case in cases:
        inputs = case.get("inputs", {})
        expected = case.get("expected_output")
        # TODO: call your module logic here
        actual = None
        assert actual == expected, f"Mismatch for inputs={inputs}: {actual} != {expected}"
'''


def main():
    ap = argparse.ArgumentParser(description="Generate a legal test_compliance.py template")
    ap.add_argument("--output", required=True, help="Path to write test_compliance.py")
    ap.add_argument("--cases", default="legal_cases.json", help="Path to JSON cases file")
    args = ap.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(TEMPLATE.format(cases_path=args.cases), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
