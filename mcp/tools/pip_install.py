import subprocess
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Agentic Package Manager")
    parser.add_argument("packages", nargs="+", help="Packages to install")
    args = parser.parse_args()

    print(f"?? GEMINI INSTALLER: Attempting to install {', '.join(args.packages)}...")
    
    try:
        # We use -m pip to ensure we use the correct python instance
        subprocess.check_call([sys.executable, "-m", "pip", "install", *args.packages])
        print(f"? SUCCESS: {', '.join(args.packages)} installed.")
    except Exception as e:
        print(f"? FAILED: Could not install packages. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
