# utils.py
import os, json
import pandas as pd
from datetime import datetime
from typing import Tuple
import streamlit as st

REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #",
    "NOTES", "ORDERED BY", "DATE ORDERED", "DATE RECEIVED"
]

DATA_PATH = os.getenv("REQUIVA_DATA_PATH", "data/orders.csv")

USE_FIRESTORE = False
db = None
FB = st.secrets.get("firebase", {})

def _init_firestore_from_secrets():
    """Try Option A (full JSON), then Option B (3 fields). Return client or None."""
    if not FB:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        cred = None
        # OPTION A: full JSON blob
        if FB.get("service_account_json"):
            sa_info = json.loads(FB["service_account_json"])
            cred = credentials.Certificate(sa_info)

        # OPTION B: 3 separate fields
        elif FB.get("project_id") and FB.get("client_email") and FB.get("private_key"):
            sa_info = {
                "type": "service_account",
                "project_id": FB["project_id"],
                "private_key_id": "dummy",
                "private_key": FB["private_key"],
                "client_email": FB["client_email"],
                "client_id": "dummy",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(sa_info)

        if cred:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            return firestore.client()

    except Exception as e:
        st.warning(f"⚠️ Firestore init failed; falling back to CSV. Details: {e}")
        return None

    return None

db = _init_firestore_from_secrets()
USE_FIRESTORE = db is not None
COLLECTION = FB.get("collection", "requiva_orders")

def ensure_data_file():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        pd.DataFrame(columns=REQUIRED_COLUMNS).to_csv(DATA_PATH, index=False)

def load_orders() -> pd.DataFrame:
    if USE_FIRESTORE and db is not None:
        docs = db.collection(COLLECTION).stream()
        rows = [d.to_dict() for d in docs]
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df[REQUIRED_COLUMNS]
    else:
        ensure_data_file()
        df = pd.read_csv(DATA_PATH)
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df[REQUIRED_COLUMNS]

def save_orders(df: pd.DataFrame):
    df = df[REQUIRED_COLUMNS].copy()
    if USE_FIRESTORE and db is not None:
        from google.cloud import firestore as _fs  # ensure dependency present
        batch = db.batch()
        col_ref = db.collection(COLLECTION)
        for _, row in df.iterrows():
            req_id = str(row["REQ#"])
            if not req_id or req_id == "nan":
                continue
            doc = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            batch.set(col_ref.document(req_id), doc, merge=True)
        batch.commit()
    else:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        df.to_csv(DATA_PATH, index=False)

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
