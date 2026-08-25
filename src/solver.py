import os
import re
from typing import Optional, Dict, Any
from src.logger import log_info, log_error

try:
    from google import genai
    from google.genai import types
    HAS_NEW_GENAI = True
except ImportError:
    HAS_NEW_GENAI = False
    try:
        import google.generativeai as legacy_genai
        HAS_LEGACY_GENAI = True
    except ImportError:
        HAS_LEGACY_GENAI = False


class GeminiSolver:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please provide it in your .env file or environment.")

        if HAS_NEW_GENAI:
            self.client = genai.Client(api_key=self.api_key)
        elif HAS_LEGACY_GENAI:
            legacy_genai.configure(api_key=self.api_key)
            self.client = legacy_genai.GenerativeModel(self.model_name)
        else:
            raise ImportError("Please install google-genai (`pip install google-genai`) to use Gemini.")

    def _clean_code(self, response_text: str) -> str:
        """Strips markdown code blocks, explanatory text, and leading/trailing whitespace."""
        text = response_text.strip()
        
        # Match ```lang ... ``` blocks
        code_block_match = re.search(r"```(?:[a-zA-Z0-9_\-\+]+)?\n?(.*?)```", text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()
            
        return text

    def generate_solution(
        self,
        problem_title: str,
        problem_description: str,
        code_template: str,
        language: str = "python3",
        previous_error: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generates a solution using Gemini AI."""
        
        system_instruction = (
            "You are a competitive programming grandmaster and LeetCode algorithmic specialist.\n"
            "Your task is to write complete, optimal, and 100% bug-free code that passes all test cases on LeetCode.\n"
            "CRITICAL RULES:\n"
            "1. Output ONLY the raw executable code. Do NOT wrap in conversational text or write explanations outside code.\n"
            "2. Preserve the EXACT class name, method name, and parameter types from the provided code template.\n"
            "3. Include all necessary standard library imports at the top (e.g., typing, collections, heapq, bisect, math).\n"
            "4. Ensure optimal time complexity and space complexity (avoid Time Limit Exceeded).\n"
            "5. Account for all edge cases (empty inputs, single elements, negative numbers, boundary constraints).\n"
        )

        user_prompt = f"""
### Problem Title:
{problem_title}

### Problem Description & Constraints:
{problem_description}

### Starter Code Template ({language}):
```{language}
{code_template}
```
"""

        if previous_error:
            user_prompt += f"""
### Previous Submission Result: FAILED
Verdict: {previous_error.get('status_msg')}
Compile / Runtime Error: {previous_error.get('compile_error') or previous_error.get('full_runtime_error') or 'None'}
Failed Input: {previous_error.get('input_formatted') or previous_error.get('last_testcase') or 'N/A'}
Expected Output: {previous_error.get('expected_output') or 'N/A'}
Actual Code Output: {previous_error.get('code_output') or 'N/A'}
Passed Test Cases: {previous_error.get('total_correct', 0)} / {previous_error.get('total_testcases', 0)}

Please carefully analyze the error and the failed test case, fix the algorithm or edge case bug, and provide the corrected complete code solution matching the original template signature.
"""

        log_info(f"Invoking Gemini ({self.model_name}) to generate solution...")

        if HAS_NEW_GENAI:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                )
            )
            raw_output = response.text or ""
        else:
            full_prompt = f"{system_instruction}\n\n{user_prompt}"
            response = self.client.generate_content(
                full_prompt,
                generation_config={"temperature": 0.2}
            )
            raw_output = response.text or ""

        return self._clean_code(raw_output)
