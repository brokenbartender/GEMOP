import os
import sys
import json
import pathlib
import datetime as dt
import google.genai as genai

# --- CONFIGURATION ---
REPO_ROOT = pathlib.Path(r"C:\Users\codym\gemini-op-clean")
LOG_FILE = REPO_ROOT / "deputy_processor.log"
GCLOUD_KEY_FILE = REPO_ROOT / "gcloud_service_key.json"
# --- END CONFIGURATION ---

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now().isoformat()}] {msg}\n")

def configure_gemini():
    if GCLOUD_KEY_FILE.exists():
        try:
            with open(GCLOUD_KEY_FILE, 'r') as f:
                credentials_info = json.load(f)
            credentials = genai.Credentials.from_service_account_info(credentials_info)
            genai.configure(credentials=credentials)
            log("DEPUTY: SUCCESS: Gemini configured with Service Account.")
            return True
        except Exception as e:
            log(f"DEPUTY: Service Account config failed: {e}")
    return False

def get_gemini_response(prompt):
    log("DEPUTY: Routing to Gemini Cloud (gemini-1.5-flash-latest)")
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(prompt)
    return response.text

# --- MAIN EXECUTION ---
GEMINI_CONFIGURED = configure_gemini()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_prompt = sys.argv[1]
        if GEMINI_CONFIGURED:
            try:
                response_text = get_gemini_response(user_prompt)
                print(response_text)
            except Exception as e:
                log(f"DEPUTY: CRITICAL FAILURE: {e}")
                print("Deputy encountered a critical cloud error. Check logs.")
        else:
            log("DEPUTY: ERROR: No valid Gemini credentials. Deputy is offline.")
            print("Deputy is offline. No valid credentials.")
    else:
        print("Deputy is listening.")
