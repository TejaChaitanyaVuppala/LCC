# 🔥 Autonomous LeetCode Daily Streak Bot

An autonomous bot that fetches the official LeetCode Daily Challenge every day, solves it using **Gemini AI**, submits the solution directly to your LeetCode account, and maintains your streak 24/7 via **GitHub Actions** (or locally).

---

## ✨ Features

- **Automated Daily Challenge Fetcher**: Pulls the daily problem details, constraints, tags, and function templates using LeetCode's GraphQL API.
- **Smart AI Solver (Gemini 2.5 Flash)**: Generates optimal, bug-free solutions matching the exact LeetCode class & method signature.
- **Self-Healing Error Correction**: If LeetCode rejects a solution (Wrong Answer, Runtime Error, TLE), the error and failed test case are fed back into Gemini to fix the code automatically (up to 3 retries).
- **Zero-Maintenance Cloud Automation**: Configured with a GitHub Actions cron schedule to run every day at `01:30 AM UTC` for free without leaving your PC turned on.
- **Dry-Run Mode**: Test solving problems without submitting.

---

## 🛠️ Step 1: Getting Your Credentials

### 1. LeetCode Cookies (`LEETCODE_SESSION` & `LEETCODE_CSRF_TOKEN`)
1. Open [leetcode.com](https://leetcode.com) in your browser and log into your account.
2. Press `F12` (or Right-Click -> **Inspect**) to open Browser Developer Tools.
3. Go to the **Application** tab (in Chrome/Edge/Brave) or **Storage** tab (in Firefox).
4. In the left sidebar, expand **Cookies** and click on `https://leetcode.com`.
5. Locate and copy the values for:
   - `LEETCODE_SESSION` (long token string)
   - `csrftoken` (value for `LEETCODE_CSRF_TOKEN`)

> [!NOTE]
> LeetCode session cookies typically stay valid for several months unless you explicitly click "Log Out".

### 2. Gemini API Key (`GEMINI_API_KEY`)
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Get API Key** and create a free key.

---

## 🚀 Step 2: Running Locally

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your environment variables**:
   Create a `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
   Fill in your `.env` values:
   ```env
   LEETCODE_SESSION=your_leetcode_session_cookie
   LEETCODE_CSRF_TOKEN=your_csrftoken_cookie
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   PROGRAMMING_LANGUAGE=python3
   ```

3. **Run the bot**:
   ```bash
   # Test in dry-run mode (solves without submitting to LeetCode)
   python main.py --dry-run

   # Run for real (solves and submits to LeetCode)
   python main.py
   ```

---

## ☁️ Step 3: 24/7 Cloud Automation with GitHub Actions (Recommended)

You can run this completely in the cloud every day for free so your streak never breaks:

1. **Create a new Private GitHub Repository**:
   - Go to [GitHub -> New Repository](https://github.com/new).
   - Set the repository visibility to **Private** (to protect your code & actions).

2. **Push this project to your repository**:
   ```bash
   git init
   git add .
   git commit -m "feat: setup leetcode daily streak bot"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

3. **Add your Secrets to GitHub**:
   - In your GitHub repo, go to **Settings** -> **Secrets and variables** -> **Actions**.
   - Click **New repository secret** and add the following:
     - `LEETCODE_SESSION`: Your session cookie
     - `LEETCODE_CSRF_TOKEN`: Your `csrftoken` cookie
     - `GEMINI_API_KEY`: Your Gemini API key

4. **Done!**
   - The workflow located at [`.github/workflows/daily_streak.yml`](.github/workflows/daily_streak.yml) will trigger automatically every day at `01:30 AM UTC`.
   - You can also test it immediately by going to **Actions** -> **LeetCode Daily Streak Bot** -> **Run workflow**.

---

## ⚙️ Configuration Options

| Option | Environment Variable | CLI Argument | Default | Description |
|---|---|---|---|---|
| Language | `PROGRAMMING_LANGUAGE` | `--lang` | `python3` | Language to solve (`python3`, `cpp`, `java`, `golang`) |
| Model | `GEMINI_MODEL` | - | `gemini-2.5-flash` | Gemini model to use |
| Max Retries | - | `--max-retries` | `3` | Number of auto-retry attempts if not Accepted |
| Dry Run | - | `--dry-run` | `False` | Run solver without submitting to LeetCode |
