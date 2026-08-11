# 🛡️ PhishShield – Advanced Phishing Detection System

PhishShield is a powerful AI-driven phishing detection agent that analyzes emails and web content to identify potential phishing threats in real-time. Using an intelligently trained **Random Forest** classifier on a dataset of **200k+ emails**, PhishShield leverages linguistic patterns, link analysis, and structural metadata to predict whether a message is phishing or legitimate with over **96% of  accuracy**.    

# 📌 Overview

PhishShield consists of

- **🧠 Backend (Flask API):** ML-powered REST API for real-time predictions.
- **🎨 Frontend (HTML/CSS/JS):** Interactive UI for email inspection and manual inputs.
- **📊 ML Model:** Pre-trained model using advanced feature engineering.
- **📁 Dataset:** 200,000 labeled email samples with 7 rich features for training and research..


### Model Working

PhishShield extracts wording, layout, and sender-domain features, then classifies with a Random Forest model.

# 🌟 Key Features

### 🚀 Real-time Detection

- REST API via Flask backend
- JSON-based predictions with confidence scores
- Auto model training fallback (`train.py`)

### 🧪 Smart Feature Engineering

- 25+ extracted features including:
  - Domain reputation
  - Link patterns
  - Urgent language indicators
  - HTML tag frequency
  - Attachment behavior

### 🧠 ML Model Highlights

- **Random Forest Classifier**
- Over **96% accuracy**
- Trained on 200k labeled samples
- Explainable predictions

### 💡 User-Friendly Interface

- Drag-and-drop email file analysis (`.eml`, `.txt`; `.msg` with optional `extract-msg`)
- Server-side email parsing (headers, body, attachments, links)
- Manual content entry support
- Visual risk indicator (safe/suspicious)
- Historical detection log with one-click reanalysis
- Chrome extension for Gmail (local API)

### 🔌 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Model status |
| `POST` | `/predict` | JSON prediction (`email_text`, `subject`, …) |
| `POST` | `/detect` | Alias of `/predict` (extension) |
| `POST` | `/parse` | Upload email file → parsed fields |
| `POST` | `/analyze` | Upload email file → parse + predict |

---
# PhishShield Demo Walkthrough

### Home — Upload
<img src="screenshots/01-home-upload.png" width="800" alt="Home upload view">

### Manual Input
<img src="screenshots/02-manual-input.png" width="800" alt="Manual input view">

### About
<img src="screenshots/03-about.png" width="800" alt="About modal">

### Settings
<img src="screenshots/04-settings.png" width="800" alt="Settings modal">

### File Ready to Check
<img src="screenshots/05-file-ready-to-check.png" width="800" alt="Uploaded file awaiting Check email">

### Phishing Result
<img src="screenshots/06-result-phishing.png" width="800" alt="Phishing result flagged in red">

### Legitimate Result
<img src="screenshots/07-result-legitimate.png" width="800" alt="Legitimate result flagged in green">

### History
<img src="screenshots/08-history.png" width="800" alt="Analysis history">

### Dashboard Overview
<img src="screenshots/09-dashboard-overview.png" width="800" alt="Full dashboard overview">

### Chrome Extension Popup
<img src="screenshots/10-extension-popup.png" width="360" alt="Chrome extension popup">

---

# 📊 Dataset

PhishShield includes a **robust and reusable dataset** of **200,000+ labeled emails** for training, evaluation, and experimentation.

### 📑 Labels (Features):
| Feature            | Description |
|--------------------|-------------|
| `email_text`       | Body content of the email |
| `subject`          | Email subject line |
| `has_attachment`   | Binary flag (1 = yes, 0 = no) |
| `links_count`      | Number of hyperlinks detected |
| `sender_domain`    | Domain of sender’s email address |
| `urgent_keywords`  | Binary flag (1 = urgent words found) |
| `label`            | Target class: `phishing` or `legitimate` |

> 🧠 Ideal for building and enhancing phishing classifiers or integrating into broader cybersecurity AI pipelines.

---

## 🛠️ Installation & Setup

### 📋 Prerequisites
- Python 3.8+
- Git
- Node.js (for frontend development, optional)

### 🔧 Backend Setup
```bash
# Clone the repository
git clone https://github.com/Dwaynejj/Phishing-Email-Agent.git
cd Phishing-Email-Agent

# Create virtual environment
python -m venv venv

# Activate environment
# For Windows:
venv\Scripts\activate
# For macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Flask server (default: http://127.0.0.1:5001)
# Port 5001 avoids macOS AirPlay Receiver, which often binds 5000
python app.py

# Optional: custom port
PORT=8080 python app.py
```

Open the UI at [http://127.0.0.1:5001](http://127.0.0.1:5001).

### 🧩 Chrome Extension (Gmail)
1. Start the Flask server on port **5001**.
2. Open `chrome://extensions` → enable **Developer mode**.
3. Click **Load unpacked** and select the `Extension/` folder.
4. Open a Gmail message → click the PhishShield icon → **Check Email**.

### 📎 Outlook `.msg` files (optional)
`.eml` and `.txt` work out of the box. For `.msg` support:
```bash
pip install extract-msg
```

### 🔁 Retrain the model
```bash
python train.py
```

## 📬 Contact
<ul>
  <li><strong>GitHub</strong>: <a href="https://github.com/Dwaynejj/" target="_blank">https://github.com/Dwaynejj/</a></li>
</ul>


## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE.txt) file for details.
