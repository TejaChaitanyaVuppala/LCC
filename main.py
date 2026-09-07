import os
import sys
import time
import argparse
import re
from typing import Optional
from dotenv import load_dotenv

from src.logger import console, log_info, log_success, log_warning, log_error, print_banner, HAS_RICH
from src.leetcode_client import LeetCodeClient
from src.solver import GeminiSolver
from src.groq_solver import GroqSolver
from src.notifier import send_email_report
from src.history_tracker import HistoryTracker

def extract_slug(input_str: Optional[str]) -> Optional[str]:
    """Extracts the LeetCode question titleSlug from a slug or full URL."""
    if not input_str:
        return None
    cleaned = input_str.strip().strip("'\"")
    # If it's a URL (e.g., https://leetcode.com/problems/two-sum/ or http://...)
    match = re.search(r'leetcode\.com/problems/([^/?#\s]+)', cleaned)
    if match:
        return match.group(1).strip("/")
    # If it's a path like problems/two-sum/
    if "/" in cleaned:
        parts = [p for p in cleaned.split("/") if p and p not in ["http:", "https:", "www.leetcode.com", "leetcode.com", "description", "solutions"]]
        if "problems" in parts:
            idx = parts.index("problems")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return parts[-1]
    return cleaned

if HAS_RICH:
    from rich.panel import Panel
    from rich.syntax import Syntax

def solve_single_problem(
    problem_data: dict,
    lc_client: LeetCodeClient,
    gemini_solver: GeminiSolver,
    groq_solver: GroqSolver,
    args: argparse.Namespace,
    history_tracker: HistoryTracker,
    mode: str = "potd",
    extra_index: int = None
) -> bool:
    """Handles solving, testing, submitting, recording, and reporting a single LeetCode problem."""
    mode_title = "📅 Today's Daily Challenge" if mode == "potd" else (f"🚀 Extra Problem #{extra_index}" if extra_index else "🚀 Extra Problem")

    info_panel = f"""
[bold yellow]Date:[/bold yellow] {problem_data.get('date', 'N/A')}
[bold yellow]Category:[/bold yellow] {mode_title}
[bold yellow]Problem:[/bold yellow] #{problem_data['frontend_id']} - {problem_data['title']}
[bold yellow]Difficulty:[/bold yellow] [{('green' if problem_data['difficulty']=='Easy' else 'yellow' if problem_data['difficulty']=='Medium' else 'red')}]{problem_data['difficulty']}[/]
[bold yellow]Tags:[/bold yellow] {', '.join(problem_data['tags']) if problem_data.get('tags') else 'N/A'}
[bold yellow]URL:[/bold yellow] {problem_data['link']}
"""
    if HAS_RICH:
        console.print(Panel(info_panel.strip(), title=mode_title, border_style="cyan"))
    else:
        console.print(f"\n--- {mode_title} ---\n{info_panel.strip()}\n-------------------------\n")

    # Step: Get Starter Code Template
    snippets = problem_data.get("snippets", {})
    target_lang = args.lang
    code_template = snippets.get(target_lang)
    if not code_template:
        if "python3" in snippets:
            target_lang = "python3"
            code_template = snippets["python3"]
        elif "python" in snippets:
            target_lang = "python"
            code_template = snippets["python"]
        else:
            available = list(snippets.keys())
            raise ValueError(f"No code snippet found for '{args.lang}'. Available: {available}")

    attempt = 1
    gemini_prev_err = None
    groq_prev_err = None
    solution_accepted = False

    gemini_code = None
    groq_code = None
    gemini_run_verdict = None
    groq_run_verdict = None
    gemini_verdict = None
    groq_verdict = None
    submitted_model = None
    winner_name = None

    while attempt <= args.max_retries and not solution_accepted:
        log_info(f"Solving problem #{problem_data['frontend_id']} (Attempt {attempt}/{args.max_retries})...")
        
        gemini_code = None
        groq_code = None

        if gemini_solver:
            try:
                gemini_code = gemini_solver.generate_solution(
                    problem_title=problem_data["title"],
                    problem_description=problem_data["content"],
                    code_template=code_template,
                    language=target_lang,
                    previous_error=gemini_prev_err
                )
                if HAS_RICH:
                    console.print(Panel(
                        Syntax(gemini_code, target_lang, theme="monokai", line_numbers=True),
                        title=f"🤖 Gemini Generated Code ({target_lang}) - Attempt {attempt}",
                        border_style="green"
                    ))
                else:
                    console.print(f"\n--- Gemini Generated Code ({target_lang}) Attempt {attempt} ---\n{gemini_code}\n----------------------------------\n")
            except Exception as e:
                log_error(f"Gemini failed to generate solution: {str(e)}")

        if groq_solver:
            try:
                groq_code = groq_solver.generate_solution(
                    problem_title=problem_data["title"],
                    problem_description=problem_data["content"],
                    code_template=code_template,
                    language=target_lang,
                    previous_error=groq_prev_err
                )
                if HAS_RICH:
                    console.print(Panel(
                        Syntax(groq_code, target_lang, theme="monokai", line_numbers=True),
                        title=f"⚡ Groq Generated Code ({target_lang}) - Attempt {attempt}",
                        border_style="cyan"
                    ))
                else:
                    console.print(f"\n--- Groq Generated Code ({target_lang}) Attempt {attempt} ---\n{groq_code}\n----------------------------------\n")
            except Exception as e:
                log_error(f"Groq failed to generate solution: {str(e)}")

        gemini_passed = 0
        gemini_total = 0
        groq_passed = 0
        groq_total = 0

        if not args.dry_run:
            # Test Gemini
            if gemini_code:
                try:
                    log_info("Testing Gemini solution against sample testcases...")
                    run_id = lc_client.run_solution(
                        title_slug=problem_data["slug"],
                        question_id=problem_data["id"],
                        code=gemini_code,
                        sample_testcase=problem_data.get("sample_testcase", ""),
                        lang_slug=target_lang
                    )
                    gemini_run_verdict = lc_client.check_submission_status(run_id)
                    gemini_passed = gemini_run_verdict.get("total_correct", 0) or 0
                    gemini_total = gemini_run_verdict.get("total_testcases", 0) or 0
                    log_info(f"Gemini Test Run: {gemini_passed}/{gemini_total} testcases passed. Status: {gemini_run_verdict.get('status_msg')}")
                except Exception as e:
                    log_error(f"Gemini test run failed: {str(e)}")

            # Test Groq
            if groq_code:
                try:
                    if gemini_code:
                        log_info("Sleeping 5 seconds before running Groq test to avoid rate limits...")
                        time.sleep(5)
                    log_info("Testing Groq solution against sample testcases...")
                    run_id = lc_client.run_solution(
                        title_slug=problem_data["slug"],
                        question_id=problem_data["id"],
                        code=groq_code,
                        sample_testcase=problem_data.get("sample_testcase", ""),
                        lang_slug=target_lang
                    )
                    groq_run_verdict = lc_client.check_submission_status(run_id)
                    groq_passed = groq_run_verdict.get("total_correct", 0) or 0
                    groq_total = groq_run_verdict.get("total_testcases", 0) or 0
                    log_info(f"Groq Test Run: {groq_passed}/{groq_total} testcases passed. Status: {groq_run_verdict.get('status_msg')}")
                except Exception as e:
                    log_error(f"Groq test run failed: {str(e)}")

        if args.dry_run:
            log_success("Dry-run complete! Skipping submission to LeetCode.")
            return True

        # Compare and choose the best one to submit
        best_model = None
        if gemini_code and groq_code:
            g_ratio = gemini_passed / gemini_total if gemini_total > 0 else 0
            q_ratio = groq_passed / groq_total if groq_total > 0 else 0
            if g_ratio > q_ratio:
                best_model = "Gemini"
            elif q_ratio > g_ratio:
                best_model = "Groq"
            else:
                best_model = "Gemini"
        elif gemini_code:
            best_model = "Gemini"
        elif groq_code:
            best_model = "Groq"

        submitted_model = best_model
        submitted_code = gemini_code if best_model == "Gemini" else groq_code
        submitted_verdict = None

        if submitted_code:
            try:
                log_info(f"Submitting {submitted_model} solution as the best code...")
                sub_id = lc_client.submit_solution(
                    title_slug=problem_data["slug"],
                    question_id=problem_data["id"],
                    code=submitted_code,
                    lang_slug=target_lang
                )
                submitted_verdict = lc_client.check_submission_status(sub_id)
                if best_model == "Gemini":
                    gemini_verdict = submitted_verdict
                else:
                    groq_verdict = submitted_verdict
            except Exception as e:
                log_error(f"{submitted_model} submission failed: {str(e)}")

        # Check if accepted, if not, try fallback
        is_accepted = submitted_verdict and submitted_verdict.get("status_msg") == "Accepted"
        
        fallback_model = "Groq" if submitted_model == "Gemini" else "Gemini"
        fallback_code = groq_code if submitted_model == "Gemini" else gemini_code

        if not is_accepted and fallback_code:
            log_warning(f"{submitted_model} solution was not accepted. Trying fallback {fallback_model} solution...")
            try:
                log_info("Sleeping 10 seconds before fallback submission to avoid rate limits...")
                time.sleep(10)
                sub_id = lc_client.submit_solution(
                    title_slug=problem_data["slug"],
                    question_id=problem_data["id"],
                    code=fallback_code,
                    lang_slug=target_lang
                )
                fallback_verdict = lc_client.check_submission_status(sub_id)
                if fallback_model == "Gemini":
                    gemini_verdict = fallback_verdict
                else:
                    groq_verdict = fallback_verdict
            except Exception as e:
                log_error(f"{fallback_model} submission failed: {str(e)}")

        gemini_accepted = gemini_verdict and gemini_verdict.get("status_msg") == "Accepted"
        groq_accepted = groq_verdict and groq_verdict.get("status_msg") == "Accepted"

        if gemini_accepted or groq_accepted:
            solution_accepted = True
            
            g_runtime = gemini_verdict.get("status_runtime", "N/A") if gemini_verdict else "N/A"
            g_mem = gemini_verdict.get("status_memory", "N/A") if gemini_verdict else "N/A"
            g_runtime_pct = gemini_verdict.get("runtime_percentile", 0) if (gemini_verdict and gemini_verdict.get("runtime_percentile") is not None) else 0
            g_mem_pct = gemini_verdict.get("memory_percentile", 0) if (gemini_verdict and gemini_verdict.get("memory_percentile") is not None) else 0

            q_runtime = groq_verdict.get("status_runtime", "N/A") if groq_verdict else "N/A"
            q_mem = groq_verdict.get("status_memory", "N/A") if groq_verdict else "N/A"
            q_runtime_pct = groq_verdict.get("runtime_percentile", 0) if (groq_verdict and groq_verdict.get("runtime_percentile") is not None) else 0
            q_mem_pct = groq_verdict.get("memory_percentile", 0) if (groq_verdict and groq_verdict.get("memory_percentile") is not None) else 0

            if gemini_accepted and groq_accepted:
                winner_name = "Gemini" if g_runtime_pct >= q_runtime_pct else "Groq"
            elif gemini_accepted:
                winner_name = "Gemini"
            elif groq_accepted:
                winner_name = "Groq"

            # Record to history tracker
            history_tracker.record_solution(
                title_slug=problem_data["slug"],
                title=problem_data["title"],
                frontend_id=problem_data["frontend_id"],
                difficulty=problem_data["difficulty"],
                mode=mode,
                winner_model=winner_name
            )
            today_stats = history_tracker.get_today_progress()

            report = f"""
[bold green]Solution Succeeded! 🎉[/bold green]

[bold yellow]🤖 Gemini Results:[/bold yellow]
- Runtime: {g_runtime} (Beats {round(g_runtime_pct, 1) if isinstance(g_runtime_pct, (int, float)) else g_runtime_pct}%)
- Memory: {g_mem} (Beats {round(g_mem_pct, 1) if isinstance(g_mem_pct, (int, float)) else g_mem_pct}%)

[bold yellow]⚡ Groq Results:[/bold yellow]
- Runtime: {q_runtime} (Beats {round(q_runtime_pct, 1) if isinstance(q_runtime_pct, (int, float)) else q_runtime_pct}%)
- Memory: {q_mem} (Beats {round(q_mem_pct, 1) if isinstance(q_mem_pct, (int, float)) else q_mem_pct}%)

[bold cyan]🏆 Winner: {winner_name or 'N/A'}![/bold cyan]
[bold cyan]📊 Today's Progress: POTD: {today_stats.get('potd', 0)} | Extra: {today_stats.get('extra', 0)}/5 | Total: {today_stats.get('total', 0)}[/bold cyan]
"""
            send_email_report(
                problem_details=problem_data,
                submitted_code=submitted_code or (gemini_code if winner_name == "Gemini" else groq_code),
                submitted_verdict=gemini_verdict if (gemini_accepted and submitted_model == "Gemini") else (groq_verdict or gemini_verdict),
                submitted_model=submitted_model or winner_name,
                winner=winner_name,
                mode=mode,
                extra_index=extra_index,
                today_stats=today_stats
            )

            if HAS_RICH:
                console.print(Panel(report.strip(), title=f"🏆 Result: #{problem_data['frontend_id']} {problem_data['title']}", border_style="green"))
            else:
                console.print(f"\n--- Result: #{problem_data['frontend_id']} {problem_data['title']} ---\n{report.strip()}\n--------------------------------------\n")
            return True
        else:
            if gemini_verdict:
                log_error(f"Gemini submission verdict: {gemini_verdict.get('status_msg')}")
                gemini_prev_err = gemini_verdict
            if groq_verdict:
                log_error(f"Groq submission verdict: {groq_verdict.get('status_msg')}")
                groq_prev_err = groq_verdict
            
            attempt += 1

    if not args.dry_run and not solution_accepted:
        err_msg = f"Failed to achieve 'Accepted' verdict after {args.max_retries} attempts."
        today_stats = history_tracker.get_today_progress()
        send_email_report(
            problem_details=problem_data,
            submitted_code=submitted_code or gemini_code or groq_code,
            submitted_verdict=gemini_prev_err or groq_prev_err,
            submitted_model=submitted_model,
            error_message=err_msg,
            mode=mode,
            extra_index=extra_index,
            today_stats=today_stats
        )
        log_error(err_msg)
        return False

    return True

def main():
    load_dotenv()
    print_banner()

    parser = argparse.ArgumentParser(description="Autonomous LeetCode Daily Streak & Multi-Problem Solver")
    parser.add_argument("--mode", choices=["potd", "extra", "batch"], default=os.getenv("SOLVER_MODE", "potd"),
                        help="Solver mode: 'potd' (Problem of the Day), 'extra' (solve an extra unsolved problem), or 'batch' (solve multiple)")
    parser.add_argument("--count", type=int, default=int(os.getenv("PROBLEM_COUNT", "1")),
                        help="Number of problems to solve when running in 'extra' or 'batch' mode (default: 1)")
    parser.add_argument("--difficulty", default=os.getenv("EXTRA_PROBLEM_DIFFICULTY", "RANDOM"),
                        help="Difficulty filter for extra problems: EASY, MEDIUM, HARD, or RANDOM (default: RANDOM)")
    parser.add_argument("--tag", default=os.getenv("PROBLEM_TAG", None),
                        help="Optional topic tag filter for extra problems (e.g. array, dynamic-programming, tree)")
    parser.add_argument("--slug", "--url", "--problem", dest="slug", default=os.getenv("PROBLEM_URL", os.getenv("PROBLEM_SLUG", None)),
                        help="LeetCode problem URL or slug to solve a specific problem (e.g. https://leetcode.com/problems/two-sum/ or two-sum)")
    parser.add_argument("--extra-index", type=int, default=None,
                        help="Index of the extra problem (1 to 5) for tracking and email labeling")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and solve problem without submitting to LeetCode")
    parser.add_argument("--lang", default=os.getenv("PROGRAMMING_LANGUAGE", "python3"), help="Programming language (default: python3)")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts if submission is not Accepted")
    args = parser.parse_args()

    session_cookie = os.getenv("LEETCODE_SESSION")
    csrf_token = os.getenv("LEETCODE_CSRF_TOKEN")
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    if not gemini_api_key and not groq_api_key:
        log_error("Neither GEMINI_API_KEY nor GROQ_API_KEY is set in environment or .env file.")
        log_info("Please get a key and set at least one of them.")
        sys.exit(1)

    if not args.dry_run and (not session_cookie or not csrf_token):
        log_warning("LeetCode session cookies (LEETCODE_SESSION, LEETCODE_CSRF_TOKEN) are missing.")
        log_info("Running in DRY-RUN mode (will solve without submitting).")
        args.dry_run = True

    history_tracker = HistoryTracker()
    lc_client = LeetCodeClient(session_cookie=session_cookie, csrf_token=csrf_token)
    gemini_solver = GeminiSolver(api_key=gemini_api_key, model_name=gemini_model) if gemini_api_key else None
    groq_solver = GroqSolver(api_key=groq_api_key, model_name=groq_model) if groq_api_key else None

    target_slug = extract_slug(args.slug)

    # Determine tasks to run based on mode
    try:
        if target_slug:
            log_info(f"Targeting specific problem: '{target_slug}'...")
            problem = lc_client.get_question_detail(target_slug)
            success = solve_single_problem(problem, lc_client, gemini_solver, groq_solver, args, history_tracker, mode="extra", extra_index=args.extra_index)
            if not success:
                sys.exit(1)

        elif args.mode == "potd":
            log_info("Fetching today's LeetCode Daily Challenge (POTD)...")
            daily = lc_client.get_daily_challenge()
            success = solve_single_problem(daily, lc_client, gemini_solver, groq_solver, args, history_tracker, mode="potd")
            if not success:
                sys.exit(1)

        elif args.mode == "extra":
            extra_idx = args.extra_index or (history_tracker.get_today_progress().get("extra", 0) + 1)
            log_info(f"Finding an unsolved problem for Extra #{extra_idx} (Difficulty: {args.difficulty})...")
            
            tags = [args.tag] if args.tag else None
            problem = lc_client.get_unsolved_problem(
                difficulty=args.difficulty,
                tags=tags,
                exclude_slugs=history_tracker.get_solved_slugs(),
                lang=args.lang
            )
            success = solve_single_problem(problem, lc_client, gemini_solver, groq_solver, args, history_tracker, mode="extra", extra_index=extra_idx)
            if not success:
                sys.exit(1)

        elif args.mode == "batch":
            count = args.count if args.count > 0 else 5
            log_info(f"Running batch mode to solve {count} problems...")
            
            # First, solve POTD if not already solved today
            today_stats = history_tracker.get_today_progress()
            if today_stats.get("potd", 0) == 0:
                log_info("Solving POTD as part of daily batch...")
                try:
                    daily = lc_client.get_daily_challenge()
                    solve_single_problem(daily, lc_client, gemini_solver, groq_solver, args, history_tracker, mode="potd")
                    time.sleep(5)
                except Exception as e:
                    log_error(f"Failed to solve POTD in batch: {e}")
            
            # Then solve remaining extra problems
            tags = [args.tag] if args.tag else None
            for i in range(1, count + 1):
                log_info(f"Solving Batch Extra Problem #{i} of {count}...")
                try:
                    problem = lc_client.get_unsolved_problem(
                        difficulty=args.difficulty,
                        tags=tags,
                        exclude_slugs=history_tracker.get_solved_slugs(),
                        lang=args.lang
                    )
                    solve_single_problem(problem, lc_client, gemini_solver, groq_solver, args, history_tracker, mode="extra", extra_index=i)
                except Exception as e:
                    log_error(f"Failed to solve Extra Problem #{i}: {e}")
                if i < count:
                    log_info("Sleeping 10 seconds before next problem...")
                    time.sleep(10)

    except Exception as e:
        err_msg = f"Execution failed: {str(e)}"
        log_error(err_msg)
        try:
            today_stats = history_tracker.get_today_progress()
            send_email_report(
                problem_details={"title": "Error Notification", "frontend_id": "ERR", "difficulty": "N/A", "link": "https://leetcode.com"},
                error_message=err_msg,
                mode=args.mode,
                extra_index=args.extra_index,
                today_stats=today_stats
            )
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
