import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_health_check(health_script_path: Path) -> dict:
    """Runs the PowerShell health check script and returns its JSON output."""
    try:
        result = subprocess.run(
            ['pwsh', '-ExecutionPolicy', 'Bypass', str(health_script_path)],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running health script: {e}", file=sys.stderr)
        print(f"Stdout: {e.stdout}", file=sys.stderr)
        print(f"Stderr: {e.stderr}", file=sys.stderr)
        return {"status": "ERROR", "message": f"Health script failed: {e.stderr}"}
    except json.JSONDecodeError as e:
        print(f"Error parsing health script output: {e}", file=sys.stderr)
        print(f"Raw output: {result.stdout if 'result' in locals() else 'N/A'}", file=sys.stderr)
        return {"status": "ERROR", "message": f"Invalid JSON output from health script: {e}"}

def generate_report_markdown(health_data: dict, run_dir: Path) -> str:
    """Generates a Markdown report from health check data."""
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = [
        "# Automated Health Check Report",
        "",
        f"Generated At: {report_time}",
        f"Run Directory: `{run_dir}`",
        "",
        "## Overall Status",
        f"Status: **{health_data.get('status', 'UNKNOWN').upper()}**",
        f"Message: {health_data.get('message', 'No specific message provided.')}",
        "",
    ]

    if "checks" in health_data:
        md.append("## Individual Checks")
        for check_name, check_result in health_data["checks"].items():
            md.append(f"### {check_name}")
            md.append(f"- Status: **{check_result.get('status', 'UNKNOWN').upper()}**")
            md.append(f"- Details: {check_result.get('details', 'No details.')}")
            if "value" in check_result:
                md.append(f"- Value: `{check_result['value']}`")
            md.append("")
    
    md.append("---")
    md.append("This report is automatically generated. Do not edit directly.")

    return "\n".join(md)

def main():
    parser = argparse.ArgumentParser(description="Automated Health Check Reporter.")
    parser.add_argument("--repo-root", required=True, help="Path to the repository root.")
    parser.add_argument("--run-dir", required=True, help="Path to the current run directory.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    run_dir = Path(args.run_dir)

    health_script_path = repo_root / "scripts" / "health.ps1"
    output_report_path = repo_root / "docs" / "live_health.md"

    health_data = run_health_check(health_script_path)
    report_markdown = generate_report_markdown(health_data, run_dir)

    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(report_markdown, encoding="utf-8")
    print(json.dumps({"ok": True, "report_path": str(output_report_path)}, indent=2))

if __name__ == "__main__":
    main()
