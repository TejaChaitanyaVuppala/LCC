import time
import requests
from typing import Dict, Any, Optional
from src.logger import log_info, log_error, log_warning, log_success

class LeetCodeClient:
    BASE_URL = "https://leetcode.com"
    GRAPHQL_URL = "https://leetcode.com/graphql"

    def __init__(self, session_cookie: Optional[str] = None, csrf_token: Optional[str] = None):
        self.session_cookie = session_cookie
        self.csrf_token = csrf_token
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "Origin": "https://leetcode.com",
        }
        
        self.cookies = {}
        if self.session_cookie:
            self.cookies["LEETCODE_SESSION"] = self.session_cookie
        if self.csrf_token:
            self.cookies["csrftoken"] = self.csrf_token
            self.headers["x-csrftoken"] = self.csrf_token

    def get_daily_challenge(self) -> Dict[str, Any]:
        """Fetches the official Daily Coding Challenge from LeetCode GraphQL."""
        query = """
        query questionOfToday {
            activeDailyCodingChallengeQuestion {
                date
                userStatus
                link
                question {
                    questionId
                    questionFrontendId
                    title
                    titleSlug
                    content
                    difficulty
                    codeSnippets {
                        lang
                        langSlug
                        code
                    }
                    sampleTestCase
                    topicTags {
                        name
                        slug
                    }
                }
            }
        }
        """
        response = requests.post(
            self.GRAPHQL_URL,
            json={"query": query},
            headers=self.headers,
            cookies=self.cookies,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        challenge_data = data.get("data", {}).get("activeDailyCodingChallengeQuestion")
        if not challenge_data or not challenge_data.get("question"):
            raise ValueError("Failed to retrieve daily coding challenge data from LeetCode API.")
            
        question = challenge_data["question"]
        return {
            "date": challenge_data.get("date"),
            "user_status": challenge_data.get("userStatus"),
            "link": self.BASE_URL + challenge_data.get("link", ""),
            "id": question["questionId"],
            "frontend_id": question["questionFrontendId"],
            "title": question["title"],
            "slug": question["titleSlug"],
            "content": question["content"],
            "difficulty": question["difficulty"],
            "snippets": {s["langSlug"]: s["code"] for s in question.get("codeSnippets", []) if s.get("langSlug")},
            "sample_testcase": question.get("sampleTestCase"),
            "tags": [t["name"] for t in question.get("topicTags", [])]
        }

    def get_question_detail(self, title_slug: str) -> Dict[str, Any]:
        """Fetches details of a specific problem by its title slug."""
        query = """
        query getQuestionDetail($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                questionFrontendId
                title
                titleSlug
                content
                difficulty
                codeSnippets {
                    lang
                    langSlug
                    code
                }
                sampleTestCase
                topicTags {
                    name
                    slug
                }
            }
        }
        """
        response = requests.post(
            self.GRAPHQL_URL,
            json={"query": query, "variables": {"titleSlug": title_slug}},
            headers=self.headers,
            cookies=self.cookies,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        question = data.get("data", {}).get("question")
        if not question:
            raise ValueError(f"Failed to retrieve question details for '{title_slug}' from LeetCode API.")
            
        return {
            "date": "Custom / Historical",
            "user_status": None,
            "link": f"{self.BASE_URL}/problems/{title_slug}/",
            "id": question["questionId"],
            "frontend_id": question["questionFrontendId"],
            "title": question["title"],
            "slug": question["titleSlug"],
            "content": question["content"],
            "difficulty": question["difficulty"],
            "snippets": {s["langSlug"]: s["code"] for s in question.get("codeSnippets", []) if s.get("langSlug")},
            "sample_testcase": question.get("sampleTestCase"),
            "tags": [t["name"] for t in question.get("topicTags", [])]
        }

    def submit_solution(self, title_slug: str, question_id: str, code: str, lang_slug: str = "python3") -> str:
        """Submits the code solution to LeetCode."""
        if not self.session_cookie or not self.csrf_token:
            raise ValueError("LEETCODE_SESSION and LEETCODE_CSRF_TOKEN must be configured to submit solutions.")

        submit_url = f"{self.BASE_URL}/problems/{title_slug}/submit/"
        headers = self.headers.copy()
        headers["Referer"] = f"{self.BASE_URL}/problems/{title_slug}/"
        headers["x-csrftoken"] = self.csrf_token

        payload = {
            "lang": lang_slug,
            "question_id": question_id,
            "typed_code": code
        }

        response = requests.post(
            submit_url,
            json=payload,
            headers=headers,
            cookies=self.cookies,
            timeout=20
        )
        
        if response.status_code == 403 or response.status_code == 401:
            raise PermissionError("LeetCode authentication failed. Please verify that your LEETCODE_SESSION and LEETCODE_CSRF_TOKEN cookies are valid and not expired.")
        
        response.raise_for_status()
        res_data = response.json()
        submission_id = res_data.get("submission_id")
        
        if not submission_id:
            raise ValueError(f"Submission failed or was rejected. LeetCode response: {res_data}")
            
        return str(submission_id)

    def check_submission_status(self, submission_id: str, timeout_seconds: int = 40) -> Dict[str, Any]:
        """Polls LeetCode check endpoint until evaluation is complete."""
        check_url = f"{self.BASE_URL}/submissions/detail/{submission_id}/check/"
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            response = requests.get(
                check_url,
                headers=self.headers,
                cookies=self.cookies,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            state = data.get("state")
            
            if state == "SUCCESS":
                return data
            elif state in ["PENDING", "STARTED"]:
                log_info(f"Evaluation in progress (state: {state})...")
            else:
                log_warning(f"Unexpected evaluation state: {state}")
                
        raise TimeoutError(f"Submission status polling timed out after {timeout_seconds} seconds.")
