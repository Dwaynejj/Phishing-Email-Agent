from flask import Flask, request, jsonify, render_template
import joblib
from flask_cors import CORS
import pandas as pd
import os
import re
import tldextract
from bs4 import BeautifulSoup

from email_utils import parse_email_file, URGENT_PHRASES

# Use bundled Public Suffix List only (no network / cache writes at runtime)
_tld_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

# --------------------------------------------------------------------------
# NLTK setup
# --------------------------------------------------------------------------
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

def _ensure_nltk_data():
    for resource in ['stopwords', 'wordnet', 'omw-1.4']:
        try:
            nltk.data.find(f'corpora/{resource}')
        except LookupError:
            nltk.download(resource, quiet=True)

_ensure_nltk_data()

_lemmatizer = WordNetLemmatizer()
_stop_words = set(stopwords.words('english'))


def preprocess_text(text: str) -> str:
    """NLTK cleaning pipeline (used when model was trained with cleaned text)."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ")
    text = text.lower()
    text = re.sub(r'https?://\S+|www\.\S+', ' url ', text)
    text = re.sub(r'[^a-z\s]', ' ', text)
    tokens = [
        _lemmatizer.lemmatize(tok)
        for tok in text.split()
        if tok not in _stop_words and len(tok) > 1
    ]
    return " ".join(tokens)


def extract_html_link_count(text: str) -> int:
    """Count hyperlinks using BeautifulSoup (layout/structural feature)."""
    if not text:
        return 0
    soup = BeautifulSoup(text, "html.parser")
    anchors = soup.find_all('a', href=True)
    if anchors:
        return len(anchors)
    return len(re.findall(r'https?://\S+|www\.\S+', text, re.IGNORECASE))


def to_flag(value):
    """Normalize client booleans/strings to 0/1, or None if absent."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        return int(value.strip().lower() in ("1", "true", "yes", "on"))
    return int(bool(value))


def normalize_domain(domain: str) -> str:
    if not domain:
        return ""
    domain = domain.strip().lower()
    # Accept full emails or URLs
    if "@" in domain:
        domain = domain.split("@", 1)[1]
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    extracted = _tld_extract(domain)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return domain


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# --------------------------------------------------------------------------
# Model loading
# --------------------------------------------------------------------------
model = None
MODEL_USES_CLEANED_TEXT = False


def detect_model_column_names(m):
    """Return True if the model was trained with 'email_text_clean' columns."""
    try:
        for name, _, cols in m.named_steps['preprocessor'].transformers_:
            if name == 'email_text' and cols == 'email_text_clean':
                return True
    except Exception:
        pass
    return False


def load_model():
    global model, MODEL_USES_CLEANED_TEXT
    if not os.path.exists('models/phishing_detection_model.pkl'):
        print("Model not found. Training a new one…")
        from train import train_and_save_model
        train_and_save_model()
    model = joblib.load('models/phishing_detection_model.pkl')
    _patch_hashing_vectorizer_fitted(model)
    MODEL_USES_CLEANED_TEXT = detect_model_column_names(model)
    classifier_name = type(model.named_steps['classifier']).__name__
    print(f"Model loaded: {classifier_name} | clean-text pipeline: {MODEL_USES_CLEANED_TEXT}")


def _patch_hashing_vectorizer_fitted(m):
    """
    HashingVectorizer is intentionally stateless; sklearn 1.6+ still treats it as
    'unfitted' and will hard-fail in 1.8. Mark domain hashers as fitted.
    """
    import types
    try:
        pre = m.named_steps.get('preprocessor')
        if pre is None:
            return
        for name, trans, _cols in pre.transformers_:
            if name != 'domain':
                continue
            targets = []
            if hasattr(trans, 'named_steps'):
                targets.extend(trans.named_steps.values())
            targets.append(trans)
            for est in targets:
                est.__sklearn_is_fitted__ = types.MethodType(lambda self: True, est)
    except Exception as exc:
        print(f"Warning: could not patch domain hasher fitted state: {exc}")


load_model()


# --------------------------------------------------------------------------
# Feature extraction — adapts to whichever model is loaded
# --------------------------------------------------------------------------
def extract_features_from_email(email_text, subject="", has_attachment=None,
                                links_count=None, sender_domain=None,
                                urgent_keywords=None):
    raw_text = email_text if email_text else ""
    raw_subject = subject if subject else ""

    if links_count is not None:
        n_links = int(links_count)
    else:
        bs4_links = extract_html_link_count(raw_text)
        re_links = len(re.findall(r'https?://\S+|www\.\S+', raw_text, re.IGNORECASE))
        n_links = max(bs4_links, re_links)

    if sender_domain is None or sender_domain == "":
        match = re.search(
            r'[\w.+-]+@([\w.-]+\.\w{2,})|https?://([\w.-]+\.\w{2,})',
            raw_text.lower())
        sender_domain = (match.group(1) or match.group(2)) if match else ""
    sender_domain = normalize_domain(str(sender_domain))

    if urgent_keywords is not None:
        n_urgent = to_flag(urgent_keywords)
        if n_urgent is None:
            n_urgent = 0
    else:
        combined = f"{raw_subject}\n{raw_text}".lower()
        n_urgent = int(any(phrase in combined for phrase in URGENT_PHRASES))

    email_length = len(raw_text)
    subject_length = len(raw_subject)
    link_density = n_links / (email_length + 1)
    special_chars = len(re.findall(r'[!$%^&*()_+|~=`{}\[\]:";\'<>?,./]', raw_text))
    html_tags = len(re.findall(r'<[^>]+>', raw_text.lower()))
    # Hash-based proxy kept consistent with training pipeline (see train.py)
    domain_age = hash(str(sender_domain)) % 30 if sender_domain else 0
    has_att = to_flag(has_attachment)
    if has_att is None:
        has_att = 0

    numeric_fields = {
        'has_attachment': has_att,
        'links_count': n_links,
        'urgent_keywords': n_urgent,
        'email_length': email_length,
        'subject_length': subject_length,
        'link_density': link_density,
        'domain_age': domain_age,
        'special_chars': special_chars,
        'html_tags': html_tags,
    }

    if MODEL_USES_CLEANED_TEXT:
        features = {
            'email_text_clean': preprocess_text(raw_text),
            'subject_clean': preprocess_text(raw_subject),
            'sender_domain': str(sender_domain),
            **numeric_fields
        }
    else:
        features = {
            'email_text': raw_text,
            'subject': raw_subject,
            'sender_domain': str(sender_domain),
            **numeric_fields
        }

    return features, numeric_fields


def _extract_request_fields(data: dict):
    """Accept both web-UI and extension payload shapes."""
    email_text = (
        data.get('email_text')
        or data.get('text')
        or data.get('body')
        or data.get('content')
        or ""
    )
    subject = data.get('subject') or data.get('email_subject') or ""
    sender_domain = data.get('sender_domain') or data.get('from_domain') or data.get('domain')
    return {
        'email_text': email_text,
        'subject': subject,
        'has_attachment': data.get('has_attachment'),
        'links_count': data.get('links_count'),
        'sender_domain': sender_domain,
        'urgent_keywords': data.get('urgent_keywords'),
    }


def run_prediction(fields: dict):
    features, numeric_fields = extract_features_from_email(**fields)
    input_df = pd.DataFrame([features])
    prediction = model.predict(input_df)
    probability = model.predict_proba(input_df)
    label = 'phishing' if int(prediction[0]) == 1 else 'legitimate'
    phishing_prob = float(probability[0][1])
    confidence = float(max(probability[0]))
    return {
        'prediction': label,
        'result': label,  # alias for older extension clients
        'probability': phishing_prob,
        'confidence': confidence,
        'features_used': numeric_fields,
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/parse', methods=['POST', 'OPTIONS'])
def parse_email():
    """Parse an uploaded .eml / .msg / .txt file into prediction-ready fields."""
    if request.method == 'OPTIONS':
        return _cors_preflight()

    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded (expected form field "file")'}), 400
        uploaded = request.files['file']
        if not uploaded.filename:
            return jsonify({'error': 'Empty filename'}), 400

        raw = uploaded.read()
        if not raw:
            return jsonify({'error': 'Empty file'}), 400

        parsed = parse_email_file(uploaded.filename, raw)
        return jsonify(parsed)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print("Parse error:", str(e))
        return jsonify({'error': f'Failed to parse email: {e}'}), 500


@app.route('/predict', methods=['POST', 'OPTIONS'])
def predict():
    try:
        if request.method == 'OPTIONS':
            return _cors_preflight()

        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'error': 'No JSON data received'}), 400
        if not isinstance(data, dict):
            return jsonify({'error': 'JSON body must be an object'}), 400

        fields = _extract_request_fields(data)
        if not str(fields['email_text']).strip() and not str(fields['subject']).strip():
            return jsonify({'error': 'Provide email_text (or text/body) and/or subject'}), 400

        result = run_prediction(fields)
        return jsonify(result)

    except Exception as e:
        print("Prediction error:", str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/detect', methods=['POST', 'OPTIONS'])
def detect():
    """Alias endpoint for the browser extension (POSTs to /detect)."""
    return predict()


@app.route('/analyze', methods=['POST', 'OPTIONS'])
def analyze_file():
    """Parse an uploaded email file and run phishing prediction in one step."""
    if request.method == 'OPTIONS':
        return _cors_preflight()

    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded (expected form field "file")'}), 400
        uploaded = request.files['file']
        if not uploaded.filename:
            return jsonify({'error': 'Empty filename'}), 400

        raw = uploaded.read()
        parsed = parse_email_file(uploaded.filename, raw)
        result = run_prediction({
            'email_text': parsed.get('email_text', ''),
            'subject': parsed.get('subject', ''),
            'has_attachment': parsed.get('has_attachment'),
            'links_count': parsed.get('links_count'),
            'sender_domain': parsed.get('sender_domain'),
            'urgent_keywords': parsed.get('urgent_keywords'),
        })
        result['parsed'] = parsed
        result['filename'] = uploaded.filename
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print("Analyze error:", str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    classifier_name = type(model.named_steps['classifier']).__name__ if model else 'not loaded'
    return jsonify({
        'status': 'ok',
        'model_loaded': model is not None,
        'classifier': classifier_name,
        'uses_cleaned_text': MODEL_USES_CLEANED_TEXT
    })


def _cors_preflight():
    resp = jsonify({'status': 'preflight'})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return resp


if __name__ == '__main__':
    # Default 5001 — macOS AirPlay Receiver often occupies 5000.
    # Override with: PORT=8080 python3 app.py
    port = int(os.environ.get('PORT', 5001))
    print(f"Starting PhishShield on http://127.0.0.1:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
