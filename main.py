import os
import sys
import argparse
from dotenv import load_dotenv

from src.logger import console, log_info, log_success, log_warning, log_error, print_banner, HAS_RICH
from src.leetcode_client import LeetCodeClient
from src.solver import GeminiSolver
from src.groq_solver import GroqSolver
from src.notifier import send_email_report

if HAS_RICH:
    from rich.panel import Panel
    from rich.syntax import Syntax

def main():
    load_dotenv()
    print_banner()

    parser = argparse.ArgumentParser(description="Autonomous LeetCode Daily Streak Solver")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and solve problem without submitting to LeetCode")
    parser.add_argument("--lang", default=os.getenv("PROGRAMMING_LANGUAGE", "python3"), help="Programming language (default: python3)")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts if submission is not Accepted")
    parser.add_argument("--slug", help="LeetCode problem slug to solve a specific problem (e.g. two-sum)")
    args = parser.parse_args()

    session_cookie = os.getenv("LEETCODE_SESSION")
    csrf_token = os.getenv("LEETCODE_CSRF_TOKEN")
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not gemini_api_key and not groq_api_key:
        log_error("Neither GEMINI_API_KEY nor GROQ_API_KEY is set in environment or .env file.")
        log_info("Please get a key and set at least one of them.")
        sys.exit(1)

    if not args.dry_run and (not session_cookie or not csrf_token):
        log_warning("LeetCode session cookies (LEETCODE_SESSION, LEETCODE_CSRF_TOKEN) are missing.")
        log_info("Running in DRY-RUN mode (will solve without submitting).")
        args.dry_run = True

    try:
        # Step 1: Initialize clients
        lc_client = LeetCodeClient(session_cookie=session_cookie, csrf_token=csrf_token)
        
        gemini_solver = GeminiSolver(api_key=gemini_api_key, model_name=gemini_model) if gemini_api_key else None
        groq_solver = GroqSolver(api_key=groq_api_key, model_name=groq_model) if groq_api_key else None

        # Step 2: Fetch Problem
        if args.slug:
            log_info(f"Fetching LeetCode problem details for '{args.slug}'...")
            daily = lc_client.get_question_detail(args.slug)
        else:
            log_info("Fetching today's LeetCode Daily Challenge...")
            daily = lc_client.get_daily_challenge()
        
        info_panel = f"""
[bold yellow]Date:[/bold yellow] {daily['date']}
[bold yellow]Problem:[/bold yellow] #{daily['frontend_id']} - {daily['title']}
[bold yellow]Difficulty:[/bold yellow] [{('green' if daily['difficulty']=='Easy' else 'yellow' if daily['difficulty']=='Medium' else 'red')}]{daily['difficulty']}[/]
[bold yellow]Tags:[/bold yellow] {', '.join(daily['tags']) if daily['tags'] else 'N/A'}
[bold yellow]URL:[/bold yellow] {daily['link']}
"""
        if HAS_RICH:
            console.print(Panel(info_panel.strip(), title="📅 Today's Challenge", border_style="cyan"))
        else:
            console.print(f"\n--- Today's Challenge ---\n{info_panel.strip()}\n-------------------------\n")

        # Step 3: Get Starter Code Template
        snippets = daily.get("snippets", {})
        code_template = snippets.get(args.lang)
        if not code_template:
            # Fallback to python3 if requested lang not found
            if "python3" in snippets:
                args.lang = "python3"
                code_template = snippets["python3"]
            elif "python" in snippets:
                args.lang = "python"
                code_template = snippets["python"]
            else:
                available = list(snippets.keys())
                raise ValueError(f"No code snippet found for '{args.lang}'. Available: {available}")

        # Step 4: AI Solution Generation and Auto-Retry Loop
        attempt = 1
        gemini_prev_err = None
        groq_prev_err = None
        solution_accepted = False

        while attempt <= args.max_retries and not solution_accepted:
            log_info(f"Solving problem (Attempt {attempt}/{args.max_retries})...")
            
            gemini_code = None
            groq_code = None

            if gemini_solver:
                try:
                    gemini_code = gemini_solver.generate_solution(
                        problem_title=daily["title"],
                        problem_description=daily["content"],
                        code_template=code_template,
                        language=args.lang,
                        previous_error=gemini_prev_err
                    )
                    if HAS_RICH:
                        console.print(Panel(
                            Syntax(gemini_code, args.lang, theme="monokai", line_numbers=True),
                            title=f"🤖 Gemini Generated Code ({args.lang}) - Attempt {attempt}",
                            border_style="green"
                        ))
                    else:
                        console.print(f"\n--- Gemini Generated Code ({args.lang}) Attempt {attempt} ---\n{gemini_code}\n----------------------------------\n")
                except Exception as e:
                    log_error(f"Gemini failed to generate solution: {str(e)}")

            if groq_solver:
                try:
                    groq_code = groq_solver.generate_solution(
                        problem_title=daily["title"],
                        problem_description=daily["content"],
                        code_template=code_template,
                        language=args.lang,
                        previous_error=groq_prev_err
                    )
                    if HAS_RICH:
                        console.print(Panel(
                            Syntax(groq_code, args.lang, theme="monokai", line_numbers=True),
                            title=f"⚡ Groq Generated Code ({args.lang}) - Attempt {attempt}",
                            border_style="cyan"
                        ))
                    else:
                        console.print(f"\n--- Groq Generated Code ({args.lang}) Attempt {attempt} ---\n{groq_code}\n----------------------------------\n")
                except Exception as e:
                    log_error(f"Groq failed to generate solution: {str(e)}")

            if args.dry_run:
                log_success("Dry-run complete! Skipping submission to LeetCode.")
                break

            gemini_verdict = None
            groq_verdict = None

            # Submit Gemini Solution
            if gemini_code:
                try:
                    log_info(f"Submitting Gemini solution to LeetCode for problem '{daily['slug']}'...")
                    sub_id = lc_client.submit_solution(
                        title_slug=daily["slug"],
                        question_id=daily["id"],
                        code=gemini_code,
                        lang_slug=args.lang
                    )
                    log_info(f"Gemini submission queued with ID: {sub_id}. Waiting for evaluation...")
                    gemini_verdict = lc_client.check_submission_status(sub_id)
                except Exception as e:
                    log_error(f"Gemini submission failed: {str(e)}")

            # Submit Groq Solution
            if groq_code:
                try:
                    if gemini_code:
                        log_info("Sleeping 10 seconds to avoid LeetCode submission rate limits...")
                        import time
                        time.sleep(10)
                    log_info(f"Submitting Groq solution to LeetCode for problem '{daily['slug']}'...")
                    sub_id = lc_client.submit_solution(
                        title_slug=daily["slug"],
                        question_id=daily["id"],
                        code=groq_code,
                        lang_slug=args.lang
                    )
                    log_info(f"Groq submission queued with ID: {sub_id}. Waiting for evaluation...")
                    groq_verdict = lc_client.check_submission_status(sub_id)
                except Exception as e:
                    log_error(f"Groq submission failed: {str(e)}")

            # Evaluate Results
            gemini_accepted = gemini_verdict and gemini_verdict.get("status_msg") == "Accepted"
            groq_accepted = groq_verdict and groq_verdict.get("status_msg") == "Accepted"

            if gemini_accepted or groq_accepted:
                solution_accepted = True
                
                # Format metrics
                g_runtime = gemini_verdict.get("status_runtime", "N/A") if gemini_verdict else "N/A"
                g_mem = gemini_verdict.get("status_memory", "N/A") if gemini_verdict else "N/A"
                g_runtime_pct = gemini_verdict.get("runtime_percentile", 0) if (gemini_verdict and gemini_verdict.get("runtime_percentile") is not None) else 0
                g_mem_pct = gemini_verdict.get("memory_percentile", 0) if (gemini_verdict and gemini_verdict.get("memory_percentile") is not None) else 0

                q_runtime = groq_verdict.get("status_runtime", "N/A") if groq_verdict else "N/A"
                q_mem = groq_verdict.get("status_memory", "N/A") if groq_verdict else "N/A"
                q_runtime_pct = groq_verdict.get("runtime_percentile", 0) if (groq_verdict and groq_verdict.get("runtime_percentile") is not None) else 0
                q_mem_pct = groq_verdict.get("memory_percentile", 0) if (groq_verdict and groq_verdict.get("memory_percentile") is not None) else 0

                report = ""
                if gemini_accepted and groq_accepted:
                    # Compare
                    winner = "Gemini" if g_runtime_pct >= q_runtime_pct else "Groq"
                    report = f"""
[bold green]Both Solvers Succeeded! 🎉[/bold green]

[bold yellow]🤖 Gemini Results:[/bold yellow]
- Runtime: {g_runtime} (Beats {round(g_runtime_pct, 1)}%)
- Memory: {g_mem} (Beats {round(g_mem_pct, 1)}%)

[bold yellow]⚡ Groq Results:[/bold yellow]
- Runtime: {q_runtime} (Beats {round(q_runtime_pct, 1)}%)
- Memory: {q_mem} (Beats {round(q_mem_pct, 1)}%)

[bold cyan]🏆 Winner: {winner}![/bold cyan]
[bold cyan]🔥 Daily Streak Successfully Maintained![/bold cyan]
"""
                elif gemini_accepted:
                    report = f"""
[bold green]Gemini Succeeded! 🎉[/bold green] (Groq did not get accepted)

[bold yellow]🤖 Gemini Results:[/bold yellow]
- Runtime: {g_runtime} (Beats {round(g_runtime_pct, 1) if isinstance(g_runtime_pct, (int, float)) else g_runtime_pct}%)
- Memory: {g_mem} (Beats {round(g_mem_pct, 1) if isinstance(g_mem_pct, (int, float)) else g_mem_pct}%)

[bold cyan]🔥 Daily Streak Successfully Maintained![/bold cyan]
"""
                else:
                    report = f"""
[bold green]Groq Succeeded! 🎉[/bold green] (Gemini did not get accepted)

[bold yellow]⚡ Groq Results:[/bold yellow]
- Runtime: {q_runtime} (Beats {round(q_runtime_pct, 1) if isinstance(q_runtime_pct, (int, float)) else q_runtime_pct}%)
- Memory: {q_mem} (Beats {round(q_mem_pct, 1) if isinstance(q_mem_pct, (int, float)) else q_mem_pct}%)

[bold cyan]🔥 Daily Streak Successfully Maintained![/bold cyan]
"""
                winner_name = None
                if gemini_accepted and groq_accepted:
                    winner_name = "Gemini" if g_runtime_pct >= q_runtime_pct else "Groq"

                if not args.dry_run:
                    send_email_report(
                        problem_details=daily,
                        gemini_code=gemini_code,
                        groq_code=groq_code,
                        gemini_verdict=gemini_verdict,
                        groq_verdict=groq_verdict,
                        winner=winner_name
                    )

                if HAS_RICH:
                    console.print(Panel(report.strip(), title="🏆 Submission & Comparison Result", border_style="green"))
                else:
                    console.print(f"\n--- Submission & Comparison Result ---\n{report.strip()}\n--------------------------------------\n")
                break
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
            send_email_report(
                problem_details=daily,
                gemini_code=gemini_code,
                groq_code=groq_code,
                gemini_verdict=gemini_prev_err,
                groq_verdict=groq_prev_err,
                error_message=err_msg
            )
            log_error(err_msg)
            sys.exit(1)

    except Exception as e:
        err_msg = f"Execution failed: {str(e)}"
        log_error(err_msg)
        try:
            if 'daily' in locals():
                send_email_report(
                    problem_details=daily,
                    error_message=err_msg
                )
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
