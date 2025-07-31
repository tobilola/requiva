# debug_app.py
import json, os
import streamlit as st

st.set_page_config(page_title="Requiva Debug", page_icon="🧪")

st.title("Requiva • Debug")

# 1) Show secrets keys
fb = st.secrets.get("firebase", {})
st.write("Secrets present:", list(fb.keys()))

# 2) Try to parse service_account_json
raw = fb.get("service_account_json")
if not raw:
    st.warning("No service_account_json in [firebase] secrets. (If using Option A, add it.)")
else:
    st.write("Length of service_account_json:", len(raw))
    try:
        sa = json.loads(raw)
        st.success("JSON parsed OK.")
        st.write("project_id:", sa.get("project_id"))
        st.write("client_email:", sa.get("client_email"))
    except Exception as e:
        st.error(f"JSON parse failed: {e}")

# 3) Try Firestore init
try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if raw:
        sa = json.loads(raw)
        cred = credentials.Certificate(sa)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.success("Firestore client initialized ✅")
    else:
        st.info("Skipping Firestore init (no JSON provided).")
except Exception as e:
    st.error(f"Firestore init failed: {e}")

st.caption("If something fails above, copy the full error text and share it (without secrets).")
