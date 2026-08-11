# PhishShield

PhishShield is a phishing email detection system built with a **Flask** API, a **Random Forest** classifier trained on **200,000** labeled emails, a cream/grey web UI, and an optional **Chrome extension** for Gmail.

It classifies a message as **phishing** (red) or **legitimate** (green) using wording, layout, and sender-domain features.

<p align="center">
  <img src="screenshots/09-dashboard-overview.png" width="860" alt="PhishShield dashboard">
</p>

---

## What’s included

| Component | Path | Role |
|-----------|------|------|
| Flask API + UI server | `app.py` | Serves the web app and prediction endpoints |
| Email parsing | `email_utils.py` | Parses `.eml` / `.txt` (optional `.msg`) |
| Model training | `train.py` | Builds and saves the Random Forest pipeline |
| Saved model | `models/phishing_detection_model.pkl` | Loaded at startup (auto-trains if missing) |
| Dataset | `dataset.csv` | 200k labeled emails |
| Web UI | `templates/index.html` | Upload / manual analysis, results, history |
| Chrome extension | `Extension/` | Checks the open Gmail message via the local API |
| Screenshots | `screenshots/` | Current UI captures |

---

## Features

### Detection
- Random Forest classifier with TF-IDF text features, domain hashing, and numeric signals
- Confidence score and phishing probability in every response
- Feature breakdown shown in the UI (links, urgent language, lengths, HTML tags, etc.)
- Auto-train fallback if the model file is missing (`python train.py` / startup)

### Web UI
- Cream & grey theme; **phishing = red**, **legitimate = green**
- **Upload file** → review the selected file → click **Check email**
- **Manual input** for pasted body, subject, sender domain, and options
- About / Settings modals, scan stats, and localStorage history with reanalyze
- Default server port **5001** (avoids macOS AirPlay on port 5000)

### Chrome extension
- Reads the open Gmail message (subject, sender, body)
- Posts to `/detect` on your local PhishShield server
- Configurable API URL (default `http://127.0.0.1:5001`)

### API
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Model status |
| `POST` | `/predict` | JSON prediction |
| `POST` | `/detect` | Same as `/predict` (extension) |
| `POST` | `/parse` | Upload email file → parsed fields |
| `POST` | `/analyze` | Upload email file → parse + predict |

**Example `/predict` body:**
```json
{
  "email_text": "Dear customer, verify your account now: https://evil.example/login",
  "subject": "Urgent: Action required",
  "sender_domain": "evil.example",
  "has_attachment": 0,
  "urgent_keywords": 1,
  "links_count": 1
}
```

Aliases accepted for the body field: `email_text`, `text`, `body`, or `content`.

**Example response:**
```json
{
  "prediction": "phishing",
  "result": "phishing",
  "probability": 0.9,
  "confidence": 0.9,
  "features_used": {
    "links_count": 1,
    "urgent_keywords": 1,
    "email_length": 181
  }
}
```

---

## Screenshots

### Home — upload
<img src="screenshots/01-home-upload.png" width="800" alt="Home upload view">

### Manual input
<img src="screenshots/02-manual-input.png" width="800" alt="Manual input">

### About
<img src="screenshots/03-about.png" width="800" alt="About modal">

### Settings
<img src="screenshots/04-settings.png" width="800" alt="Settings modal">

### File ready — Check email
<img src="screenshots/05-file-ready-to-check.png" width="800" alt="File staged with Check email button">

### Phishing result
<img src="screenshots/06-result-phishing.png" width="800" alt="Phishing result in red">

### Legitimate result
<img src="screenshots/07-result-legitimate.png" width="800" alt="Legitimate result in green">

### History
<img src="screenshots/08-history.png" width="800" alt="Analysis history">

### Chrome extension
<img src="screenshots/10-extension-popup.png" width="360" alt="Chrome extension popup">

---

## Dataset

`dataset.csv` contains **200,000** labeled rows (`phishing` / `legitimate`).

| Column | Description |
|--------|-------------|
| `email_text` | Email body |
| `subject` | Subject line |
| `has_attachment` | `1` / `0` |
| `links_count` | Hyperlink count |
| `sender_domain` | Sender domain |
| `urgent_keywords` | `1` if urgent phrases present |
| `label` | `phishing` or `legitimate` |

At prediction time the app also derives lengths, link density, HTML tag count, special-character count, and a hash-based `domain_age` proxy (kept consistent with training; not a live WHOIS lookup).

---

## Setup

### Prerequisites
- Python 3.8+
- Git
- Chrome (only if you use the extension)

### Install & run
```bash
git clone https://github.com/Dwaynejj/Phishing-Email-Agent.git
cd Phishing-Email-Agent

python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows
# venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5001**

Custom port / local debug:
```bash
PORT=8080 FLASK_DEBUG=1 python app.py
```

### Chrome extension (Gmail)
1. Start PhishShield (local or hosted).
2. Go to `chrome://extensions` → enable **Developer mode**.
3. **Load unpacked** → select the `Extension/` folder.
4. Open a Gmail message → PhishShield icon → **Check Email**.
5. If hosted in the cloud, set **API URL** in the popup to your Render URL (e.g. `https://phishshield.onrender.com`).

### Outlook `.msg` (optional)
`.eml` and `.txt` work by default. For `.msg`:
```bash
pip install extract-msg
```

### Retrain the model
```bash
python train.py
```
This overwrites `models/phishing_detection_model.pkl`.

### Refresh UI screenshots (optional)
With the server running:
```bash
pip install playwright
python -m playwright install chromium
python scripts/capture_screenshots.py
```

---

## Host on Render (Option B)

PhishShield is set up for [Render](https://render.com) with `Procfile`, `runtime.txt`, and `render.yaml`.

### 1. Push the latest code to GitHub
```bash
git add -A
git commit -m "Add Render/gunicorn production hosting config"
git push
```
Use your `Dwaynejj/Phishing-Email-Agent` remote.

### 2. Create a Render account
1. Go to [https://render.com](https://render.com) and sign up.
2. Connect your **GitHub** account.
3. Authorize access to **Dwaynejj/Phishing-Email-Agent** (only that repo is enough).

### 3. Create a Web Service
**Either use Blueprint (easiest):**
1. Dashboard → **New** → **Blueprint**
2. Select `Dwaynejj/Phishing-Email-Agent`
3. Render reads `render.yaml` and proposes service **phishshield**
4. Click **Apply**

**Or create manually:**
1. Dashboard → **New** → **Web Service**
2. Connect `Dwaynejj/Phishing-Email-Agent`
3. Settings:
   - **Runtime:** Python 3
   - **Build command:**  
     `pip install -r requirements.txt && python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('omw-1.4')"`
   - **Start command:**  
     `gunicorn -b 0.0.0.0:$PORT -w 2 --timeout 120 app:app`
   - **Instance type:** Free
4. Env vars:
   - `FLASK_DEBUG` = `0`
   - `PYTHON_VERSION` = `3.11.9` (optional if `runtime.txt` is present)
5. Click **Create Web Service**

### 4. Wait for the deploy
- First build installs packages + NLTK data (a few minutes).
- When status is **Live**, open the URL Render gives you, e.g.  
  `https://phishshield-xxxx.onrender.com`

### 5. Smoke-test
```bash
curl https://YOUR-SERVICE.onrender.com/health
```
You should see `"status":"ok"` and `"model_loaded": true`.

Then open the URL in a browser and run a manual analysis.

### 6. Point the Chrome extension at Render
1. In the extension popup, set API URL to `https://YOUR-SERVICE.onrender.com` (no trailing slash).
2. Click **Save API**.
3. Reload the extension on `chrome://extensions` if needed.

`Extension/manifest.json` already allows `https://*.onrender.com/*`.

### Free-tier notes
- The free service **spins down** after ~15 minutes idle; the first request after that can take 30–60s.
- Keep `models/phishing_detection_model.pkl` in the repo so Render does **not** retrain on boot (training 200k rows would exceed free limits).
- Do not rely on `debug` mode in production (`FLASK_DEBUG=0`).

---

## Project layout

```
Phishing-Email-Agent/
├── app.py                 # Flask app, features, API routes
├── email_utils.py         # .eml / .txt / .msg parsing
├── train.py               # Training pipeline
├── dataset.csv            # Training data
├── models/                # Saved sklearn pipeline
├── templates/index.html   # Web UI
├── Extension/             # Chrome MV3 extension
├── screenshots/           # UI screenshots
├── scripts/               # Helper scripts (e.g. screenshot capture)
├── Procfile               # Gunicorn start command (PaaS)
├── render.yaml            # Render Blueprint config
├── runtime.txt            # Python version for Render
└── requirements.txt
```

---

## License

MIT — see [LICENSE.txt](LICENSE.txt).

**GitHub:** [https://github.com/Dwaynejj/Phishing-Email-Agent](https://github.com/Dwaynejj/Phishing-Email-Agent)
