# utils.py

import os
import json
from datetime import datetime
from typing import Tuple

import pandas as pd
import streamlit as st

REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #",
    "NOTES", "ORDERED BY", "DATE ORDERED", "DATE RECEIVED",
]

DATA_PATH = os.getenv("REQUIVA_DATA_PATH", "data/orders.csv")

# ----------------------
# 🔐 Firebase Setup
# ----------------------
FB = st.secrets.get("firebase", {})
COLLECTION = FB.get("collection", "requiva_orders")

def _init_firestore_from_secrets():
    if not FB:
        st.info("⚠️ No [firebase] secrets found. Using local CSV.")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        cred = None

        # ✅ OPTION A: Full JSON (recommended)
        if "service_account_json" in FB:
            sa_json = FB["service_account_json"]
            sa_info = json.loads(sa_json)
            cred = credentials.Certificate(sa_info)

        # ✅ OPTION B: Separate fields fallback
        elif all(k in FB for k in ["project_id", "client_email", "private_key"]):
            key = FB["private_key"].replace("\\n", "\n")
            sa_info = {
                "type": "service_account",
                "project_id": FB["project_id"],
                "private_key_id": FB.get("private_key_id", "dummy"),
                "private_key": key,
                "client_email": FB["client_email"],
                "client_id": FB.get("client_id", "dummy"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": FB.get("client_x509_cert_url", ""),
                "universe_domain": "googleapis.com"
            }
            cred = credentials.Certificate(sa_info)

        if cred is None:
            st.warning("⚠️ Firebase secrets found but incomplete. Cannot initialize Firestore.")
            return None

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        return firestore.client()

    except Exception as e:
        st.warning(f"⚠️ Firestore init failed. Using CSV. \n\nDetails: {e}")
        return None

# 🔄 Initialize Firestore client
db = _init_firestore_from_secrets()
USE_FIRESTORE = db is not None

# ----------------------
# 📦 Data Functions
# ----------------------

def ensure_data_file():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        pd.DataFrame(columns=REQUIRED_COLUMNS).to_csv(DATA_PATH, index=False)

def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[REQUIRED_COLUMNS]

def load_orders() -> pd.DataFrame:
    if USE_FIRESTORE and db:
        docs = db.collection(COLLECTION).stream()
        rows = [d.to_dict() for d in docs]
        df = pd.DataFrame(rows)
        return _ensure_columns(df) if not df.empty else pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        ensure_data_file()
        df = pd.read_csv(DATA_PATH)
        return _ensure_columns(df)

def save_orders(df: pd.DataFrame):
    df = _ensure_columns(df.copy())

    if USE_FIRESTORE and db:
        from google.cloud import firestore as _fs
        batch = db.batch()
        col_ref = db.collection(COLLECTION)
        for _, row in df.iterrows():
            req_id = str(row["REQ#"])
            if not req_id or req_id.lower() == "nan":
                continue
            doc = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            batch.set(col_ref.document(req_id), doc, merge=True)
        batch.commit()
    else:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        df.to_csv(DATA_PATH, index=False)

# ----------------------
# 🛠 Utility Functions
# ----------------------

def gen_req_id(df: pd.DataFrame) -> str:
    year = datetime.now().strftime("%Y")
    prefix = f"REQ-{year}-"
    existing = df["REQ#"].dropna().astype(str).tolist()
    nums = [int(x.split("-")[-1]) for x in existing if x.startswith(prefix) and x.split("-")[-1].isdigit()]
    next_num = (max(nums) + 1) if nums else 1
    return f"{prefix}{next_num:04d}"

def compute_total(qty: float, unit_price: float) -> float:
    try:
        return round(float(qty) * float(unit_price), 2)
    except Exception:
        return 0.0

def validate_order(item: str, qty, price, vendor: str) -> Tuple[bool, str]:
    if not item or str(item).strip() == "":
        return False, "ITEM is required."
    try:
        q = float(qty)
        if q < 0:
            return False, "NUMBER OF ITEM must be >= 0."
    except Exception:
        return False, "NUMBER OF ITEM must be a number."
    try:
        p = float(price)
        if p < 0:
            return False, "AMOUNT PER ITEM must be >= 0."
    except Exception:
        return False, "AMOUNT PER ITEM must be a number."
    if not vendor or str(vendor).strip() == "":
        return False, "VENDOR is required."
    return True, ""

