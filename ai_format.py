import os
import json
import re
from groq import Groq

# Groq API is 100% free with no credit card requirement
client = Groq(api_key=os.environ["GROQ_API_KEY"])

PROMPT_TEMPLATE = """You are an expert exam question paper formatter. Convert the raw pasted text into clean, structured JSON.
CRITICAL RULES:
1. Preserve the original language(s) of the text exactly (do not translate).
2. Group into logical sections if present or implied.
3. Extract instructions into a list if present.
4. Output STRICT JSON ONLY. No markdown, no prose, no extra characters.

JSON Schema:
{{
  "instructions": ["string"],
  "sections": [
    {{
      "heading": "string",
      "questions": [
        {{
          "number": "string",
          "text": "string",
          "marks": "string",
          "options": ["string"]
        }}
      ]
    }}
  ]
}}

Raw Content:
\"\"\"
{raw}
\"\"\"
"""

def format_paper(raw_text: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(raw=raw_text)
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    text = response.choices[0].message.content.strip()
    return json.loads(text)
