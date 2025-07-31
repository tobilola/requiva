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

if FB and FB.get("service_account_json"):
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        sa_info = json.loads(FB["service_account_json"])  # full JSON blob from secrets
        cred = credentials.Certificate(sa_info)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIRESTORE = True
    except Exception as e:
        st.warning(f"⚠️ Firestore init failed, using CSV. Details: {e}")
        USE_FIRESTORE = False

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
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True
        )
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
