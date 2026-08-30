import os
import json
from google import genai
from google.genai import types
from .prompt_builder import build_system_prompt, build_rca_prompt

class AICallError(Exception):
    """Raised when the AI API call fails (timeout, auth, non-200, missing API key)."""
    pass

class AIResponseParseError(Exception):
    """Raised when the AI response cannot be parsed as JSON."""
    pass

def _clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
        
    return text.strip()

def call_rca_model(evidence_package: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AICallError("GEMINI_API_KEY environment variable is missing or empty.")
        
    client = genai.Client(api_key=api_key)
    model = os.getenv("AI_MODEL", "gemini-2.5-flash")
    
    system_prompt = build_system_prompt()
    user_prompt = build_rca_prompt(evidence_package)
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.2
            )
        )
    except Exception as e:
        raise AICallError(f"Failed to call Gemini API: {str(e)}") from e
        
    if not response.text:
        raise AIResponseParseError("Empty response from Gemini API")
        
    raw_text = response.text
    cleaned_json = _clean_json_response(raw_text)
    
    try:
        return json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        raise AIResponseParseError(f"Failed to parse JSON response: {str(e)}\nRaw Response: {raw_text}") from e
