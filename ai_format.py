"""
Calls the Groq API (free tier, no card required) to turn raw pasted
questions into structured JSON for the PDF builder.
Groq's endpoint is OpenAI-compatible, so we just use plain HTTP requests.
"""
import os
import json
import re
import requests

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"  # check console.groq.com for current model names

PROMPT_TEMPLATE = """You are formatting a school exam question paper. The teacher pasted raw, possibly messy exam content below (it may mix languages, have inconsistent numbering, or informal structure).

Reorganize it into clean structured JSON. Preserve the original language(s) of the actual question text exactly as given (do not translate). Group into logical sections if implied by the source (e.g. by marks or type like MCQ/short/long). Extract instructions if present.

Return ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{{
  "instructions": ["string", ...],
  "sections": [
    {{
      "heading": "string",
      "questions": [
        {{"number": "string", "text": "string", "marks": "string", "options": ["a. ...", ...]}}
      ]
    }}
  ]
}}

Raw content:
\"\"\"
{raw}
\"\"\"
"""

def format_paper(raw_text: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(raw=raw_text)

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()

    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1:
        text = text[first:last + 1]

    return json.loads(text)


CUSTOM_PROMPT_TEMPLATE = """You are a document-formatting assistant. The user described, in their own words, a PDF document they want created (it could be a certificate, notice, letter, worksheet, report, invitation, etc. — NOT necessarily an exam paper).

Read their description and produce clean structured content for it. Preserve their language (do not translate). Fill in reasonable placeholder text only where something is clearly missing and needed for the document to make sense (e.g. blank lines for a name on a certificate) — do not invent facts, numbers, or claims that were not implied by the description.

Return ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{{
  "title": "string",
  "subtitle": "string or empty",
  "sections": [
    {{
      "heading": "string or empty",
      "paragraphs": ["string", ...],
      "bullets": ["string", ...]
    }}
  ]
}}

User's description:
\"\"\"
{desc}
\"\"\"
"""

def generate_custom_document(description: str) -> dict:
    """Free-form document generation for the 'Custom PDF (Chat)' feature —
    the user just describes what they want in plain language."""
    prompt = CUSTOM_PROMPT_TEMPLATE.format(desc=description)

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()

    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1:
        text = text[first:last + 1]

    return json.loads(text)
