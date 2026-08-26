import os
import requests
from typing import Dict, Any, Optional
from src.logger import log_info, log_error, log_warning, log_success

def send_email_report(
    problem_details: Dict[str, Any],
    submitted_code: Optional[str] = None,
    submitted_verdict: Optional[Dict[str, Any]] = None,
    submitted_model: Optional[str] = None,
    winner: Optional[str] = None,
    error_message: Optional[str] = None,
    mode: str = "potd",
    extra_index: Optional[int] = None,
    today_stats: Optional[Dict[str, int]] = None,
    # Backward-compatibility parameters (if caller passes individual model verdicts)
    gemini_code: Optional[str] = None,
    groq_code: Optional[str] = None,
    gemini_verdict: Optional[Dict[str, Any]] = None,
    groq_verdict: Optional[Dict[str, Any]] = None,
    gemini_run_verdict: Optional[Dict[str, Any]] = None,
    groq_run_verdict: Optional[Dict[str, Any]] = None
) -> bool:
    """Sends a clean, detailed execution report via Resend email API."""
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("TO_EMAIL")
    from_email = os.getenv("FROM_EMAIL", "LeetCode Bot <onboarding@resend.dev>")
    
    if not api_key:
        log_warning("RESEND_API_KEY not configured. Skipping email report.")
        return False
    if not to_email:
        log_warning("TO_EMAIL not configured. Skipping email report.")
        return False

    # Determine submitted code and verdict from fallbacks if not explicitly passed
    active_code = submitted_code
    if not active_code:
        if submitted_model == "Gemini" and gemini_code:
            active_code = gemini_code
        elif submitted_model == "Groq" and groq_code:
            active_code = groq_code
        else:
            active_code = gemini_code or groq_code

    active_verdict = submitted_verdict
    if not active_verdict:
        if submitted_model == "Gemini" and gemini_verdict:
            active_verdict = gemini_verdict
        elif submitted_model == "Groq" and groq_verdict:
            active_verdict = groq_verdict
        else:
            active_verdict = gemini_verdict or groq_verdict

    title = problem_details.get("title", "Daily Problem")
    difficulty = problem_details.get("difficulty", "N/A")
    link = problem_details.get("link", "#")
    frontend_id = problem_details.get("frontend_id", "")
    content = problem_details.get("content", "")

    mode_label = "Problem of the Day" if mode == "potd" else (f"Extra Problem #{extra_index}" if extra_index else "Extra Daily Problem")
    tag_prefix = "[POTD]" if mode == "potd" else (f"[EXTRA #{extra_index}]" if extra_index else "[EXTRA]")

    # Format Testcases Passed & Metrics from Submission
    testcases_info = "N/A"
    runtime_info = "N/A"
    memory_info = "N/A"
    verdict_status = "N/A"

    if active_verdict:
        total_correct = active_verdict.get("total_correct")
        total_testcases = active_verdict.get("total_testcases")
        verdict_status = active_verdict.get("status_msg", "N/A")

        if total_correct is not None and total_testcases is not None:
            pct = round((total_correct / total_testcases) * 100, 1) if total_testcases > 0 else 0
            testcases_info = f"<span style='color: #15803d; font-weight: bold;'>{total_correct} / {total_testcases} passed ({pct}%)</span>"
        elif total_correct is not None:
            testcases_info = f"{total_correct} passed"

        runtime_val = active_verdict.get("status_runtime", "N/A")
        runtime_pct = active_verdict.get("runtime_percentile")
        if runtime_pct is not None:
            runtime_info = f"{runtime_val} (Beats {round(runtime_pct, 1)}%)"
        else:
            runtime_info = str(runtime_val)

        memory_val = active_verdict.get("status_memory", "N/A")
        memory_pct = active_verdict.get("memory_percentile")
        if memory_pct is not None:
            memory_info = f"{memory_val} (Beats {round(memory_pct, 1)}%)"
        else:
            memory_info = str(memory_val)

    # Status Header
    is_success = not error_message and verdict_status == "Accepted"
    if error_message:
        status_header = f"""
        <div style='background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin-bottom: 20px;'>
            <h2 style='color: #dc2626; margin: 0 0 8px 0;'>❌ {mode_label} Failed</h2>
            <p style='color: #991b1b; margin: 0;'><b>Error:</b> {error_message}</p>
        </div>
        """
    elif is_success:
        status_header = f"""
        <div style='background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; margin-bottom: 20px;'>
            <h2 style='color: #16a34a; margin: 0 0 6px 0;'>🎉 LeetCode {mode_label} Accepted!</h2>
            <p style='color: #166534; margin: 0; font-size: 14px;'>Successfully submitted to your LeetCode account.</p>
        </div>
        """
    else:
        status_header = f"""
        <div style='background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 16px; margin-bottom: 20px;'>
            <h2 style='color: #d97706; margin: 0 0 6px 0;'>⚠️ {mode_label}: {verdict_status}</h2>
        </div>
        """

    # Progress row
    stats_row = ""
    if today_stats:
        stats_row = f"""
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Today's Progress</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px;'>POTD: <b>{today_stats.get('potd', 0)}</b> | Extra: <b>{today_stats.get('extra', 0)}/5</b> | Total Solved Today: <b style='color: #4f46e5;'>{today_stats.get('total', 0)}</b></td>
        </tr>
        """

    diff_color = "#16a34a" if difficulty == "Easy" else ("#d97706" if difficulty == "Medium" else "#dc2626")

    # Summary Details Table
    details_table = f"""
    <table style='border-collapse: collapse; width: 100%; max-width: 650px; margin-bottom: 25px; font-size: 14px;'>
        <tr style='background-color: #f8fafc;'>
            <th style='border: 1px solid #e5e7eb; padding: 10px; text-align: left; width: 35%;'>Attribute</th>
            <th style='border: 1px solid #e5e7eb; padding: 10px; text-align: left;'>Value</th>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Category</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold; color: #4f46e5;'>{mode_label}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Problem</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px;'>#{frontend_id} - <a href='{link}' style='color: #2563eb; text-decoration: none; font-weight: bold;'>{title}</a></td>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Difficulty</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold; color: {diff_color};'>{difficulty}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>LeetCode Verdict</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold; color: #16a34a;'>{verdict_status}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Testcases Passed</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px;'>{testcases_info}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Runtime</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px;'>{runtime_info}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Memory</td>
            <td style='border: 1px solid #e5e7eb; padding: 10px;'>{memory_info}</td>
        </tr>
        {"<tr><td style='border: 1px solid #e5e7eb; padding: 10px; font-weight: bold;'>Selected Model</td><td style='border: 1px solid #e5e7eb; padding: 10px; color: #0f766e; font-weight: bold;'>" + str(submitted_model or winner or 'AI Solver') + "</td></tr>"}
        {stats_row}
    </table>
    """

    # Section 1: Question Description
    question_section = ""
    if content:
        question_section = f"""
        <div style='margin-bottom: 25px;'>
            <h3 style='color: #1f2937; margin-bottom: 10px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px;'>📝 Question Description</h3>
            <div style='background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; font-size: 14px; line-height: 1.6; color: #374151; max-height: 500px; overflow-y: auto;'>
                {content}
            </div>
        </div>
        """

    # Section 2: Selected & Submitted Code ONLY
    code_section = ""
    if active_code:
        code_esc = active_code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        author_tag = f" (Generated by {submitted_model})" if submitted_model else ""
        code_section = f"""
        <div style='margin-bottom: 25px;'>
            <h3 style='color: #1f2937; margin-bottom: 10px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px;'>💻 Selected & Submitted Solution{author_tag}</h3>
            <pre style='background-color: #1e1e1e; color: #e2e8f0; padding: 18px; border-radius: 8px; overflow-x: auto; font-family: Consolas, Monaco, "Courier New", monospace; font-size: 13px; line-height: 1.5; margin: 0;'>{code_esc}</pre>
        </div>
        """

    html_content = f"""
    <html>
    <body style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1f2937; background-color: #f9fafb; padding: 25px;'>
        <div style='max-width: 700px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);'>
            {status_header}
            {details_table}
            {question_section}
            {code_section}
            <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;'>
            <p style='font-size: 12px; color: #9ca3af; text-align: center; margin: 0;'>Sent autonomously by LeetCode Daily Streak Bot</p>
        </div>
    </body>
    </html>
    """

    status_str = "SUCCESS" if is_success else ("FAILED" if error_message else verdict_status)
    subject = f"{tag_prefix} #{frontend_id} {title} - {status_str}"

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code in [200, 201]:
            log_success("Email report sent successfully via Resend API.")
            return True
        else:
            log_error(f"Failed to send email via Resend (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        log_error(f"Resend email dispatch error: {str(e)}")
        return False
