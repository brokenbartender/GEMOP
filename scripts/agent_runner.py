import os
import sys
import json
import requests
import pathlib
import datetime as dt
import google.generativeai as genai
import subprocess # Import subprocess for running shell commands

# --- CONFIGURATION ---
REPO_ROOT = pathlib.Path(r"C:\Users\codym\gemini-op-clean")
LOG_FILE = REPO_ROOT / "agent_runner_debug.log"
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
            log("SUCCESS: Gemini configured with Service Account.")
            return True
        except Exception as e:
            log(f"Service Account config failed: {e}")
    return False

def call_gemini_cloud_sdk(prompt):
    log("ROUTING TO GEMINI CLOUD (SDK / Service Account)")
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Use latest flash for speed
    response = model.generate_content(prompt)
    return response.text

def call_ollama(prompt, model_name):
    log(f"ROUTING TO LOCAL OLLAMA: {model_name}")
    resp = requests.post("http://localhost:11434/api/generate", json={"model": model_name, "prompt": prompt, "stream": False}, timeout=1200)
    resp.raise_for_status()
    return resp.json().get("response", "")

def run_agent(prompt_path, out_md):
    try:
        prompt = pathlib.Path(prompt_path).read_text(encoding="utf-8")
        result = None
        
        if GEMINI_CONFIGURED:
            try: 
                result = call_gemini_cloud_sdk(prompt)
            except Exception as e:
                log(f"Gemini SDK failed: {e}")
                result = None # Ensure fallback

        if not result:
            result = call_ollama(prompt, "phi3:mini")
        
        pathlib.Path(out_md).write_text(result, encoding="utf-8")
        log(f"SUCCESS: {out_md}")
    except Exception as e:
        log(f"CRITICAL FAILURE: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        run_agent(sys.argv[1], sys.argv[2])
    else:
        log("ERROR: Missing arguments for agent_runner.")
        sys.exit(1)
