# 🔥 Autonomous LeetCode Daily Streak & Multi-Problem Bot

An autonomous bot that fetches the official LeetCode Daily Challenge plus **5 additional problems per day distributed at different times of the day**, solves them using dual AI solvers (**Gemini 2.5 Flash** and **Groq LLaMA 3.3 70B**), submits the best solution directly to your LeetCode account, sends email reports via Resend, and tracks your daily progress 24/7 via **GitHub Actions** (or locally).

---

## ✨ Features

- **Problem of the Day (POTD) + 5 Extra Problems/Day**:
  - Automatically solves the official LeetCode Daily Challenge.
  - Automatically selects 5 unsolved problems spread across different times of the day.
- **Dual AI Solver Competition**:
  - Runs **Gemini** and **Groq** simultaneously on each problem.
  - Compares testcase pass rates and runtime/memory percentiles.
  - Automatically submits the best performing code with auto-fallback.
- **Distributed Scheduling (6 Runs / Day)**:
  - **07:00 AM IST** (01:30 UTC) -> **Problem of the Day (POTD)**
  - **10:30 AM IST** (05:00 UTC) -> **Extra Problem #1**
  - **02:30 PM IST** (09:00 UTC) -> **Extra Problem #2**
  - **06:30 PM IST** (13:00 UTC) -> **Extra Problem #3**
  - **10:00 PM IST** (16:30 UTC) -> **Extra Problem #4**
  - **01:30 AM IST** (20:00 UTC) -> **Extra Problem #5**
- **Smart Duplicate Prevention**:
  - Tracks solved problem history in `solved_history.json` to ensure problems are never repeated.
- **Self-Healing Auto-Retry**:
  - If a submission fails (Wrong Answer, TLE, etc.), feedback is fed back to the AI for automatic correction (up to 3 retries).
- **Email Reports via Resend**:
  - Receives rich HTML email notifications showing problem details, runtime/memory percentiles, AI winner, code, and daily count.

---

## 🛠️ Step 1: Getting Your Credentials

### 1. LeetCode Cookies (`LEETCODE_SESSION` & `LEETCODE_CSRF_TOKEN`)
1. Open [leetcode.com](https://leetcode.com) in your browser and log into your account.
2. Press `F12` (or Right-Click -> **Inspect**) to open Developer Tools.
3. Go to **Application** -> **Cookies** -> `https://leetcode.com`.
4. Copy `LEETCODE_SESSION` and `csrftoken` (value for `LEETCODE_CSRF_TOKEN`).

### 2. Gemini API Key (`GEMINI_API_KEY`)
- Get a free key from [Google AI Studio](https://aistudio.google.com/).

### 3. Groq API Key (`GROQ_API_KEY`)
- Get a free key from [Groq Console](https://console.groq.com/).

### 4. Resend API Key (`RESEND_API_KEY`) (Optional for Email)
- Get an API key from [Resend](https://resend.com/).

---

## 🚀 Step 2: Running Locally

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up `.env`**:
   ```bash
   cp .env.example .env
   ```
   Fill in your `.env` variables with your cookies and API keys.

3. **CLI Usage Options**:
   ```bash
   # 1. Solve today's Problem of the Day (POTD)
   python main.py --mode potd

   # 2. Solve a single extra unsolved problem (e.g. Medium difficulty)
   python main.py --mode extra --difficulty MEDIUM

   # 3. Solve 5 problems at once in batch mode
   python main.py --mode batch --count 5 --difficulty RANDOM

   # 4. Filter by specific topic tag
   python main.py --mode extra --tag dynamic-programming

   # 5. Solve a specific problem slug
   python main.py --slug two-sum

   # 6. Test with dry-run (does not submit to LeetCode)
   python main.py --dry-run
   ```

---

## ☁️ Step 3: 24/7 Cloud Automation with GitHub Actions

The repository includes [`.github/workflows/daily_streak.yml`](.github/workflows/daily_streak.yml) configured with 6 distributed daily cron triggers.

1. **Push your code to a private GitHub repository**:
   ```bash
   git init
   git add .
   git commit -m "feat: setup leetcode streak and multi-problem bot"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. **Add GitHub Secrets**:
   Go to **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**:
   - `LEETCODE_SESSION`
   - `LEETCODE_CSRF_TOKEN`
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY`
   - `RESEND_API_KEY` (Optional)
   - `TO_EMAIL` (Optional)

3. **Trigger Manually Anytime**:
   - Go to **Actions** -> **LeetCode Daily Streak & Multi-Problem Bot** -> **Run workflow**.
   - Select mode (`potd`, `extra`, `batch`) and difficulty.

---

## ⚙️ Configuration Reference

| Option | Environment Variable | CLI Argument | Default | Description |
|---|---|---|---|---|
| Mode | `SOLVER_MODE` | `--mode` | `potd` | `potd` (Daily Challenge), `extra` (Single Extra), `batch` (Multiple) |
| Problem Count | `PROBLEM_COUNT` | `--count` | `1` | Number of problems for batch/extra runs |
| Difficulty | `EXTRA_PROBLEM_DIFFICULTY` | `--difficulty` | `RANDOM` | `EASY`, `MEDIUM`, `HARD`, or `RANDOM` |
| Tag | `PROBLEM_TAG` | `--tag` | None | Filter extra problems by topic (e.g. `tree`, `dp`) |
| Language | `PROGRAMMING_LANGUAGE` | `--lang` | `python3` | Language to solve (`python3`, `cpp`, `java`, etc.) |
| Max Retries | - | `--max-retries` | `3` | Number of auto-retry attempts if not Accepted |
| Dry Run | - | `--dry-run` | `False` | Run solver without submitting to LeetCode |
