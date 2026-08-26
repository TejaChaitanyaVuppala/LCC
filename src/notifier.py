import os
import requests
from typing import Dict, Any, Optional
from src.logger import log_info, log_error, log_success

def send_email_report(
    problem_details: Dict[str, Any],
    gemini_code: Optional[str] = None,
    groq_code: Optional[str] = None,
    gemini_verdict: Optional[Dict[str, Any]] = None,
    groq_verdict: Optional[Dict[str, Any]] = None,
    gemini_run_verdict: Optional[Dict[str, Any]] = None,
    groq_run_verdict: Optional[Dict[str, Any]] = None,
    submitted_model: Optional[str] = None,
    winner: Optional[str] = None,
    error_message: Optional[str] = None
) -> bool:
    """Sends a detailed execution report via Resend email API."""
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("TO_EMAIL")
    from_email = os.getenv("FROM_EMAIL", "LeetCode Bot <onboarding@resend.dev>")

    if not api_key:
        log_warning("RESEND_API_KEY not configured. Skipping email report.")
        return False
    if not to_email:
        log_warning("TO_EMAIL not configured. Skipping email report.")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Build HTML Content
    title = problem_details.get("title", "Daily Problem")
    difficulty = problem_details.get("difficulty", "N/A")
    link = problem_details.get("link", "#")
    frontend_id = problem_details.get("frontend_id", "")

    status_header = ""
    if error_message:
        status_header = f"<h2 style='color: #ef4444;'>❌ Execution Failed</h2><p><b>Error Details:</b> {error_message}</p>"
    else:
        status_header = "<h2 style='color: #22c55e;'>🎉 LeetCode Daily Challenge Solved Successfully!</h2>"

    details_table = f"""
    <table style='border-collapse: collapse; width: 100%; max-width: 600px; margin-bottom: 20px;'>
        <tr style='background-color: #f3f4f6;'>
            <th style='border: 1px solid #d1d5db; padding: 8px; text-align: left;'>Property</th>
            <th style='border: 1px solid #d1d5db; padding: 8px; text-align: left;'>Value</th>
        </tr>
        <tr>
            <td style='border: 1px solid #d1d5db; padding: 8px;'><b>Problem</b></td>
            <td style='border: 1px solid #d1d5db; padding: 8px;'>#{frontend_id} - {title}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #d1d5db; padding: 8px;'><b>Difficulty</b></td>
            <td style='border: 1px solid #d1d5db; padding: 8px;'>{difficulty}</td>
        </tr>
        <tr>
            <td style='border: 1px solid #d1d5db; padding: 8px;'><b>URL</b></td>
            <td style='border: 1px solid #d1d5db; padding: 8px;'><a href='{link}'>{link}</a></td>
        </tr>
        {"<tr><td style='border: 1px solid #d1d5db; padding: 8px;'><b>Chosen Best Model</b></td><td style='border: 1px solid #d1d5db; padding: 8px; color: #0f766e; font-weight: bold;'>" + submitted_model + "</td></tr>" if submitted_model else ""}
        {"<tr><td style='border: 1px solid #d1d5db; padding: 8px;'><b>🏆 Winner</b></td><td style='border: 1px solid #d1d5db; padding: 8px; color: #06b6d4; font-weight: bold;'>" + winner + "</td></tr>" if winner else ""}
    </table>
    """

    results_section = "<h3>Solver Performance Details</h3>"

    # Gemini Block
    g_run_info = "Did not run"
    if gemini_run_verdict:
        g_passed = gemini_run_verdict.get("total_correct", 0)
        g_total = gemini_run_verdict.get("total_testcases", 0)
        g_status = gemini_run_verdict.get("status_msg", "N/A")
        g_run_info = f"<b>{g_passed}/{g_total} passed</b> ({g_status})"
        
    g_sub_info = "Not submitted (Best Code Submission rule)"
    if gemini_verdict:
        g_accepted = gemini_verdict.get("status_msg") == "Accepted"
        g_runtime = gemini_verdict.get("status_runtime", "N/A")
        g_mem = gemini_verdict.get("status_memory", "N/A")
        g_runtime_pct = gemini_verdict.get("runtime_percentile") or 0
        g_mem_pct = gemini_verdict.get("memory_percentile") or 0
        g_sub_info = f"<b>{gemini_verdict.get('status_msg', 'Failed')}</b>"
        if g_accepted:
            g_sub_info += f" | Runtime: {g_runtime} (Beats {round(g_runtime_pct, 1)}%) | Memory: {g_mem} (Beats {round(g_mem_pct, 1)}%)"

    results_section += f"""
    <div style='background-color: #f9fafb; padding: 15px; border-left: 5px solid #22c55e; margin-bottom: 15px;'>
        <h4 style='margin-top: 0; color: #15803d;'>🤖 Gemini (gemini-2.5-flash)</h4>
        <p style='margin: 5px 0;'><b>Test Run:</b> {g_run_info}</p>
        <p style='margin: 5px 0;'><b>Submission:</b> {g_sub_info}</p>
    </div>
    """

    # Groq Block
    q_run_info = "Did not run"
    if groq_run_verdict:
        q_passed = groq_run_verdict.get("total_correct", 0)
        q_total = groq_run_verdict.get("total_testcases", 0)
        q_status = groq_run_verdict.get("status_msg", "N/A")
        q_run_info = f"<b>{q_passed}/{q_total} passed</b> ({q_status})"
        
    q_sub_info = "Not submitted (Best Code Submission rule)"
    if groq_verdict:
        q_accepted = groq_verdict.get("status_msg") == "Accepted"
        q_runtime = groq_verdict.get("status_runtime", "N/A")
        q_mem = groq_verdict.get("status_memory", "N/A")
        q_runtime_pct = groq_verdict.get("runtime_percentile") or 0
        q_mem_pct = groq_verdict.get("memory_percentile") or 0
        q_sub_info = f"<b>{groq_verdict.get('status_msg', 'Failed')}</b>"
        if q_accepted:
            q_sub_info += f" | Runtime: {q_runtime} (Beats {round(q_runtime_pct, 1)}%) | Memory: {q_mem} (Beats {round(q_mem_pct, 1)}%)"

    results_section += f"""
    <div style='background-color: #f9fafb; padding: 15px; border-left: 5px solid #06b6d4; margin-bottom: 15px;'>
        <h4 style='margin-top: 0; color: #0369a1;'>⚡ Groq (qwen/qwen3.6-27b)</h4>
        <p style='margin: 5px 0;'><b>Test Run:</b> {q_run_info}</p>
        <p style='margin: 5px 0;'><b>Submission:</b> {q_sub_info}</p>
    </div>
    """

    code_section = ""
    if gemini_code or groq_code:
        code_section += "<h3>Generated Solutions</h3>"
        if gemini_code:
            g_code_esc = gemini_code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            code_section += f"""
            <h4>🤖 Gemini Code:</h4>
            <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: monospace;'>{g_code_esc}</pre>
            """
        if groq_code:
            q_code_esc = groq_code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            code_section += f"""
            <h4>⚡ Groq Code:</h4>
            <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: monospace;'>{q_code_esc}</pre>
            """

    html_content = f"""
    <html>
    <body style='font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937; padding: 20px;'>
        {status_header}
        {details_table}
        {results_section}
        {code_section}
        <hr style='border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;'>
        <p style='font-size: 12px; color: #6b7280;'>Sent autonomously by LeetCode Daily Streak Bot</p>
    </body>
    </html>
    """

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": f"🔥 LeetCode Solver: #{frontend_id} {title} - {'SUCCESS' if not error_message else 'FAILED'}",
        "html": html_content
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code == 200 or response.status_code == 201:
            log_success("Email report sent successfully via Resend API.")
            return True
        else:
            log_error(f"Failed to send email via Resend (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        log_error(f"Resend email dispatch error: {str(e)}")
        return False

def log_warning(message: str):
    from src.logger import log_warning as lw
    lw(message)
