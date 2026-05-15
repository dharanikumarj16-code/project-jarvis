import os
import requests
import json
import re


def get_api_key():
    api_key = os.getenv('XAI_API_KEY')
    if not api_key:
        # fallback to config file
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config.txt')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if line.startswith('XAI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break
    return api_key


def _extract_json(text):
    # Try to find a JSON object in the text
    text = text.strip()
    # Remove markdown fences
    text = text.replace('```json', '').replace('```', '')
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Try to parse the whole body as JSON
    try:
        return json.loads(text)
    except Exception:
        return None


def decide_intent(user_input):
    """Detect intent via x.ai (Grok). Returns dict {intent, args, response_text, confidence}

    If `XAI_API_KEY` is not configured, returns an error dict.
    The prompt asks the model to return JSON only to simplify parsing.
    """
    api_key = get_api_key()
    if not api_key:
        return {"intent": "error", "response_text": "XAI API key not configured."}

    # Quick keyword scan: if no automation keywords present, ask for intent only
    automation_keywords = ["open", "click", "type", "press", "paste", "copy", "ctrl", "alt", "win", "double click", "right click", "left click", "shortcut"]
    lower = user_input.lower()
    wants_automation = any(k in lower for k in automation_keywords)

    if wants_automation:
        instruction = (
            "Analyze the user's input and return a JSON object describing the intent. "
            "If the user requests UI or device automation, set intent to 'execute_action' and include an 'args' object with any parameters. "
        )
    else:
        instruction = (
            "Analyze the user's input and return a JSON object with a single 'intent' (chat, add_task, read_tasks, complete_task, open_app, search_web, research_topic, tell_time, tell_date, learn_action, execute_action, complex_goal), an 'args' map (if applicable), a 'response_text' for chat responses, and a numeric 'confidence' between 0 and 1. "
        )

    prompt = f"{instruction}\nUser Input: \"{user_input}\"\n\nReturn ONLY valid JSON. Example: {{\"intent\": \"chat\", \"args\": {{}}, \"response_text\": \"Hello\", \"confidence\": 0.9}}"

    url = "https://api.x.ai/v1/responses"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {"model": "grok-4.20-reasoning", "input": prompt}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return {"intent": "error", "response_text": f"XAI request failed: {e}"}

    # Try to parse JSON from the response body
    try:
        body = r.json()
    except Exception:
        body = None

    # If the service returns simple text, fall back to extracting JSON blob
    if body is None:
        text = r.text
        j = _extract_json(text)
    else:
        # Some XAI responses embed content in different fields; try common ones
        j = None
        # Try direct 'output' or 'result' keys
        for key in ("output", "result", "response", "text"):
            if isinstance(body, dict) and key in body:
                if isinstance(body[key], str):
                    j = _extract_json(body[key]) or j
                elif isinstance(body[key], dict):
                    j = body[key]
        # As a last resort, convert entire body to dict if it matches structure
        if j is None:
            # Look for top-level choices/content
            if isinstance(body, dict):
                # Try to find a text-containing field
                text_fields = []
                for v in body.values():
                    if isinstance(v, str):
                        text_fields.append(v)
                for t in text_fields:
                    j = _extract_json(t)
                    if j:
                        break

    if not j:
        # Couldn't parse JSON; fallback: return chat with raw text
        raw = r.text if body is None else json.dumps(body)
        return {"intent": "chat", "response_text": raw, "confidence": 0.0}

    # Normalize expected fields
    intent = j.get("intent") or j.get("action") or "chat"
    args = j.get("args") or j.get("parameters") or {}
    response_text = j.get("response_text") or j.get("text") or ""
    confidence = float(j.get("confidence", 0.0)) if isinstance(j.get("confidence", 0.0), (int, float)) else 0.0

    return {"intent": intent, "args": args, "response_text": response_text, "confidence": confidence}
