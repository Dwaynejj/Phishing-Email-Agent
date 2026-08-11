import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer, HashingVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, accuracy_score,
                              f1_score, roc_auc_score, confusion_matrix)
import joblib
import os
import re
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# NLTK setup — download required corpora on first run
# --------------------------------------------------------------------------
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

def _ensure_nltk_data():
    for resource in ['stopwords', 'wordnet', 'omw-1.4']:
        try:
            nltk.data.find(f'corpora/{resource}')
        except LookupError:
            print(f"Downloading NLTK resource: {resource}")
            nltk.download(resource, quiet=True)

_ensure_nltk_data()

_lemmatizer = WordNetLemmatizer()
_stop_words  = set(stopwords.words('english'))


def preprocess_text(text: str) -> str:
    """
    Clean and normalise email text.
    Steps: lowercase → strip HTML → remove URLs → tokenise →
           remove stopwords → lemmatize → rejoin.
    """
    if not text:
        return ""

    # Strip HTML tags with BeautifulSoup (layout feature: link extraction happens
    # separately; here we just want the visible text for wording features)
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(separator=" ")

    # Lowercase
    text = text.lower()

    # Remove URLs (they are handled as layout/structural features elsewhere)
    text = re.sub(r'https?://\S+|www\.\S+', ' url ', text)

    # Remove non-alphabetic characters (keep spaces)
    text = re.sub(r'[^a-z\s]', ' ', text)

    # Tokenise, remove stopwords, lemmatize
    tokens = [
        _lemmatizer.lemmatize(tok)
        for tok in text.split()
        if tok not in _stop_words and len(tok) > 1
    ]
    return " ".join(tokens)


def extract_html_link_count(text: str) -> int:
    """
    Count hyperlinks in HTML email bodies using BeautifulSoup.
    Falls back to regex count for plain-text emails.
    (Layout / structural feature group)
    """
    if not text:
        return 0
    soup = BeautifulSoup(text, "html.parser")
    anchors = soup.find_all('a', href=True)
    if anchors:
        return len(anchors)
    # plain-text fallback
    return len(re.findall(r'https?://\S+|www\.\S+', text, re.IGNORECASE))


def extract_additional_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer the three evidence groups described in the research document:
      - Wording  (linguistic)  — text length, urgent keywords
      - Layout   (structural)  — hyperlink density, HTML tags, special chars
      - Background (metadata) — domain features
    """
    # --- Wording features ---
    df['email_length']   = df['email_text'].apply(len)
    df['subject_length'] = df['subject'].apply(len)

    # --- Layout features ---
    # Use BeautifulSoup for accurate link count in HTML emails
    df['bs4_link_count'] = df['email_text'].apply(extract_html_link_count)
    # Prefer the dataset's links_count when it differs; use bs4 as supplement
    df['links_count'] = df.apply(
        lambda r: max(r['links_count'], r['bs4_link_count']), axis=1)

    df['link_density'] = df['links_count'] / (df['email_length'] + 1)
    df['special_chars'] = df['email_text'].apply(
        lambda x: len(re.findall(r'[!$%^&*()_+|~=`{}\[\]:";\'<>?,./]', x)))
    df['html_tags'] = df['email_text'].apply(
        lambda x: len(re.findall(r'<[^>]+>', x.lower())))

    # --- Background / metadata feature ---
    # NOTE: domain_age is a placeholder (hash-based).
    # A production system should use python-whois or a WHOIS API lookup.
    df['domain_age'] = df['sender_domain'].apply(
        lambda x: hash(str(x)) % 30 if x else 0)

    # Drop the intermediate column
    df.drop(columns=['bs4_link_count'], inplace=True)

    return df


def train_and_save_model():
    print("Loading dataset …")
    df = pd.read_csv('dataset.csv')

    # Fill NaN values before feature engineering
    df['email_text']    = df['email_text'].fillna('')
    df['subject']       = df['subject'].fillna('')
    df['sender_domain'] = df['sender_domain'].fillna('')

    # Encode label
    df['label'] = df['label'].apply(lambda x: 1 if x == 'phishing' else 0)
    print(f"Dataset loaded: {len(df)} rows  |  "
          f"Phishing: {df['label'].sum()}  Legitimate: {(df['label']==0).sum()}")

    # -----------------------------------------------------------------
    # NLTK preprocessing on text columns (wording feature group)
    # -----------------------------------------------------------------
    print("Preprocessing text with NLTK …")
    df['email_text_clean'] = df['email_text'].apply(preprocess_text)
    df['subject_clean']    = df['subject'].apply(preprocess_text)

    # Additional engineered features
    df = extract_additional_features(df)

    # -----------------------------------------------------------------
    # Feature / target split
    # -----------------------------------------------------------------
    numeric_features = [
        'has_attachment', 'links_count', 'urgent_keywords',
        'email_length', 'subject_length', 'link_density',
        'domain_age', 'special_chars', 'html_tags'
    ]

    X = df[['email_text_clean', 'subject_clean', 'sender_domain'] + numeric_features]
    y = df['label']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    # -----------------------------------------------------------------
    # Preprocessing pipeline
    # -----------------------------------------------------------------
    # Wording features — TF-IDF on pre-cleaned text
    text_transformer = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True      # log-scale TF, helps with long emails
        )),
    ])

    # Background feature — domain hashing
    # Subclass so sklearn 1.6+ treats the (stateless) hasher as fitted.
    class FittedHashingVectorizer(HashingVectorizer):
        def __sklearn_is_fitted__(self):
            return True

    domain_transformer = Pipeline([
        ('hash', FittedHashingVectorizer(n_features=256, alternate_sign=False))
    ])

    numeric_transformer = StandardScaler()

    preprocessor = ColumnTransformer(
        transformers=[
            ('email_text', text_transformer, 'email_text_clean'),
            ('subject',    text_transformer, 'subject_clean'),
            ('domain',     domain_transformer, 'sender_domain'),
            ('num',        numeric_transformer, numeric_features),
        ],
        remainder='drop'
    )

    # -----------------------------------------------------------------
    # Random Forest Classifier  (per research document specification)
    # -----------------------------------------------------------------
    model = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(
            n_estimators=50,
            max_depth=None,          # let trees grow fully (good for RF)
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',     # standard RF setting
            class_weight='balanced', # handles class imbalance
            random_state=42,
            n_jobs=-1                # use all CPU cores
        ))
    ])

    # -----------------------------------------------------------------
    # Train
    # -----------------------------------------------------------------
    print("Training Random Forest model …")
    model.fit(X_train, y_train)

    # -----------------------------------------------------------------
    # Evaluate — full metrics suite as described in research doc Ch.5
    # -----------------------------------------------------------------
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    f1       = f1_score(y_test, y_pred)
    auc_roc  = roc_auc_score(y_test, y_proba)

    print(f"\n{'='*50}")
    print(f"Model Accuracy : {accuracy:.4f}")
    print(f"F1 Score       : {f1:.4f}")
    print(f"AUC-ROC        : {auc_roc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=['legitimate', 'phishing']))
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  TP={cm[1,1]}  FP={cm[0,1]}  FN={cm[1,0]}  TN={cm[0,0]}")
    print(f"{'='*50}\n")

    # -----------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/phishing_detection_model.pkl', compress=3)
    print("Model saved → models/phishing_detection_model.pkl")


if __name__ == '__main__':
    train_and_save_model()