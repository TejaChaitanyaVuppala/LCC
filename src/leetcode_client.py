import time
import random
import requests
from typing import Dict, Any, Optional, List, Set
from src.logger import log_info, log_error, log_warning, log_success

class LeetCodeClient:
    BASE_URL = "https://leetcode.com"
    GRAPHQL_URL = "https://leetcode.com/graphql"

    def __init__(self, session_cookie: Optional[str] = None, csrf_token: Optional[str] = None):
        self.session_cookie = session_cookie
        self.csrf_token = csrf_token
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "Origin": "https://leetcode.com",
            "Accept": "*/*",
        }
        self.session.headers.update(self.headers)
        
        self.cookies = {}
        if self.session_cookie:
            self.cookies["LEETCODE_SESSION"] = self.session_cookie
            self.session.cookies.set("LEETCODE_SESSION", self.session_cookie, domain=".leetcode.com")
        if self.csrf_token:
            self.cookies["csrftoken"] = self.csrf_token
            self.headers["x-csrftoken"] = self.csrf_token
            self.session.headers.update({"x-csrftoken": self.csrf_token})
            self.session.cookies.set("csrftoken", self.csrf_token, domain=".leetcode.com")

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
        response = self.session.post(
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
        response = self.session.post(
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

    def run_solution(self, title_slug: str, question_id: str, code: str, sample_testcase: str, lang_slug: str = "python3") -> str:
        """Runs the code solution on LeetCode without submitting to user profile history."""
        if not self.session_cookie or not self.csrf_token:
            raise ValueError("LEETCODE_SESSION and LEETCODE_CSRF_TOKEN must be configured to run solutions.")

        run_url = f"{self.BASE_URL}/problems/{title_slug}/interpret_solution/"
        headers = self.headers.copy()
        headers["Referer"] = f"{self.BASE_URL}/problems/{title_slug}/"
        headers["x-csrftoken"] = self.csrf_token

        payload = {
            "lang": lang_slug,
            "question_id": question_id,
            "typed_code": code,
            "data_input": sample_testcase
        }

        response = self.session.post(
            run_url,
            json=payload,
            headers=headers,
            cookies=self.cookies,
            timeout=20
        )
        
        if response.status_code == 403 or response.status_code == 401:
            raise PermissionError("LeetCode authentication failed. Please verify that your LEETCODE_SESSION and LEETCODE_CSRF_TOKEN cookies are valid and not expired.")
        
        response.raise_for_status()
        res_data = response.json()
        interpret_id = res_data.get("interpret_id")
        
        if not interpret_id:
            raise ValueError(f"Run failed or was rejected. LeetCode response: {res_data}")
            
        return str(interpret_id)

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

        response = self.session.post(
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
            response = self.session.get(
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

    def get_problemset_questions(
        self,
        category_slug: str = "",
        limit: int = 50,
        skip: int = 0,
        difficulty: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries LeetCode problemset question list with filters."""
        query = """
        query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
            problemsetQuestionList: questionList(
                categorySlug: $categorySlug
                limit: $limit
                skip: $skip
                filters: $filters
            ) {
                total: totalNum
                questions: data {
                    frontendQuestionId: questionFrontendId
                    title
                    titleSlug
                    difficulty
                    paidOnly: isPaidOnly
                    acRate
                    topicTags {
                        name
                        slug
                    }
                }
            }
        }
        """
        filters: Dict[str, Any] = {}
        if difficulty and difficulty.upper() in ["EASY", "MEDIUM", "HARD"]:
            filters["difficulty"] = difficulty.upper()
        if tags:
            filters["tags"] = tags
        if search_keyword:
            filters["searchKeywords"] = search_keyword

        variables = {
            "categorySlug": category_slug,
            "limit": limit,
            "skip": skip,
            "filters": filters
        }

        response = self.session.post(
            self.GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=self.headers,
            cookies=self.cookies,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        
        q_data = data.get("data", {}).get("problemsetQuestionList", {})
        return q_data.get("questions", [])

    def get_unsolved_problem(
        self,
        difficulty: Optional[str] = None,
        tags: Optional[List[str]] = None,
        exclude_slugs: Optional[Set[str]] = None,
        category_slug: str = "algorithms",
        lang: str = "python3",
        max_search_pages: int = 5
    ) -> Dict[str, Any]:
        """Finds and returns a random unsolved, non-paid problem with valid starter code."""
        exclude_set = set(exclude_slugs) if exclude_slugs else set()
        
        # If difficulty is RANDOM or not set, pick randomly weighted towards Medium/Easy
        diff_target = difficulty.upper() if difficulty and difficulty.upper() in ["EASY", "MEDIUM", "HARD"] else None
        if not diff_target:
            diff_target = random.choice(["EASY", "MEDIUM", "MEDIUM", "EASY"])

        log_info(f"Searching for an unsolved {diff_target} algorithmic problem...")

        candidate_questions: List[Dict[str, Any]] = []

        # Try random skip offsets to get varied questions
        for page in range(max_search_pages):
            skip = random.randint(0, 15) * 40
            try:
                questions = self.get_problemset_questions(
                    category_slug=category_slug,
                    limit=50,
                    skip=skip,
                    difficulty=diff_target,
                    tags=tags
                )
                
                # Filter out paid-only and already solved
                valid = [
                    q for q in questions
                    if not q.get("paidOnly", False) and q.get("titleSlug") not in exclude_set
                ]
                candidate_questions.extend(valid)
                if len(candidate_questions) >= 15:
                    break
            except Exception as e:
                log_warning(f"Problem search page {page+1} error: {e}")

        if not candidate_questions:
            # Fallback: query without skip
            questions = self.get_problemset_questions(category_slug=category_slug, limit=100, difficulty=diff_target)
            candidate_questions = [
                q for q in questions
                if not q.get("paidOnly", False) and q.get("titleSlug") not in exclude_set
            ]

        if not candidate_questions:
            raise ValueError(f"Could not find any available unsolved {diff_target} problem on LeetCode.")

        # Shuffle candidates and find one that has the required snippet
        random.shuffle(candidate_questions)
        for candidate in candidate_questions:
            slug = candidate["titleSlug"]
            try:
                detail = self.get_question_detail(slug)
                snippets = detail.get("snippets", {})
                if lang in snippets or "python3" in snippets or "python" in snippets:
                    log_info(f"Selected candidate problem: #{detail.get('frontend_id')} - {detail.get('title')} ({detail.get('difficulty')})")
                    return detail
            except Exception as e:
                log_warning(f"Failed to load details for candidate {slug}: {e}")

        raise ValueError(f"Could not find an unsolved {diff_target} problem with code snippet for '{lang}'.")


