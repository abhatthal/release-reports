# release-reports

Generate a Markdown report summarizing GitHub releases, including assets and concise change summaries.

## ✨ Features

📦 Lists all releases (latest → oldest)

🧾 Generates structured Markdown output

🧠 AI-powered summaries of release changes

⚡ Works without AI (graceful fallback)

🔗 Includes download links and metadata for assets

🕒 Timestamps report generation (Pacific Time)

## 🐍 Requirements

Python 3.9+ (required for zoneinfo)

Recommended: Python 3.11+

## 🚀 Setup
1. Clone the repository
```
git clone <your-repo-url>
cd release-reports
```
2. Create and activate a virtual environment
```
python3 -m venv .venv
```

###  macOS / Linux
```
source .venv/bin/activate
```

### Windows (PowerShell)
```
.venv\Scripts\activate
```
3. Install dependencies
```
pip install -r requirements.txt
```

## 🔐 Environment Variables (Optional)

You can optionally set the following:

### GitHub Token (recommended)

Avoids rate limits:
```
export GITHUB_TOKEN="your_token_here"
```
### Gemini API Key (optional)

Enables AI-generated summaries:

```
export GEMINI_API_KEY="your_api_key_here"
```

If not set:

The script still works

Summaries fall back to simple heuristics

## ▶️ Usage
```
./release_report.py OWNER REPO
```
### Example
```
./release_report.py opensha opensha
./release_report.py opensha opensha --output report.md
```

## 📄 Output

If no output file is specified:

```
REPO-release-report.md
```

### Example:
```
opensha-release-report.md
```

## 🛠️ Development
### Update dependencies
```
pip freeze > requirements.txt
```
### Run locally
```
python release_report.py OWNER REPO
```
