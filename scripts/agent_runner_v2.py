import os
import sys
import json
import requests
import pathlib
import datetime as dt
import google.generativeai as genai

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
            # Use the correct method for service account authentication
            credentials = genai.Credentials.from_service_account_info(credentials_info)
            genai.configure(credentials=credentials)
            log("SUCCESS: Gemini configured with Service Account.")
            return True
        except Exception as e:
            log(f"Service Account config failed: {e}")
    return False

def call_gemini_cloud_sdk(prompt):
    log("ROUTING TO GEMINI CLOUD (SDK / Service Account)")
    # Use standard model names and attempt latest versions.
    # The SDK should handle endpoint details.
    models = ['gemini-1.5-pro', 'gemini-1.5-flash'] 
    for model_name in models:
        try:
            log(f"Attempting Gemini Tier: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                log(f"SUCCESS with Gemini Tier: {model_name}")
                return response.text
            else:
                log(f"Warning: {model_name} returned an empty response.")
        except Exception as e:
            log(f"Gemini Tier {model_name} failed: {e}. Falling back...")
    
    raise ValueError("All Gemini Cloud tiers failed.")

def call_groq(prompt):
    log("ROUTING TO GROQ (Ultra-Speed)")
    # Corrected Groq model name and structure based on common OpenAI compatibility
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {KEYS.get('GROQ_API_KEY')}", "Content-Type": "application/json"},
        json={
            "model": "llama3-70b-8192", # Adjusted model name
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def call_ollama(prompt, model_name):
    log(f"ROUTING TO LOCAL OLLAMA: {model_name}")
    resp = requests.post("http://localhost:11434/api/generate", json={"model": model_name, "prompt": prompt, "stream": False}, timeout=1200)
    resp.raise_for_status()
    return resp.json().get("response", "")

def run_agent(prompt_path, out_md):
    try:
        prompt = pathlib.Path(prompt_path).read_text(encoding="utf-8")
        result = None
        
        if check_internet():
            # TIER 0: SERVICE ACCOUNT (Gemini)
            if GEMINI_CONFIGURED:
                try: 
                    result = call_gemini_cloud_sdk(prompt)
                except Exception as e:
                    log(f"Gemini cloud SDK failed: {e}")
                    result = None # Ensure fallback

            # TIER 1: GROQ
            if not result and KEYS.get("GROQ_API_KEY"):
                try: 
                    result = call_groq(prompt)
                except Exception as e:
                    log(f"Groq failed: {e}")
                    result = None

        # Fallback to Ollama if all cloud providers fail
        if not result:
            result = call_ollama(prompt, "phi3:mini")
        
        pathlib.Path(out_md).write_text(result, encoding="utf-8")
        log(f"SUCCESS: {out_md}")
    except Exception as e:
        log(f"CRITICAL FAILURE: {e}")
        sys.exit(1)

# --- MAIN EXECUTION ---
GEMINI_CONFIGURED = configure_gemini()

if __name__ == "__main__":
    if len(sys.argv) > 2:
        run_agent(sys.argv[1], sys.argv[2])
    else:
        log("ERROR: Missing arguments for agent_runner.")
        sys.exit(1)
