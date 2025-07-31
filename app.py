# app.py

from datetime import datetime, date
from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# 🚩 MUST be first Streamlit call (before any st.write/st.title)
st.set_page_config(
    page_title="Requiva — Smart Lab Order Intelligence",
    page_icon="🧪",
    layout="wide",
)

# Import everything we use from utils
from utils import (
    USE_FIRESTORE,
    FB,
    load_orders,
    save_orders,
    gen_req_id,
    compute_total,
    validate_order,
    REQUIRED_COLUMNS,
)

# --- Status banner / quick debug ---
st.write("Backend:", "Firestore ✅" if USE_FIRESTORE else "CSV (dev) ⚠️")
st.write("Secrets keys present:", list(FB.keys()) if isinstance(FB, dict) else [])

if USE_FIRESTORE:
    st.success("Connected to Firestore")
else:
    st.warning("Using local CSV (dev mode). Add Firebase secrets to enable Firestore.")

# --- App header ---
st.title("Requiva — Smart Lab Order Intelligence")
st.caption("Powered by TOBI HealthOps AI")

tab_new, tab_table, tab_analytics, tab_export = st.tabs(
    ["➕ New Order", "📋 Orders", "📈 Analytics", "⬇️ Export"]
)

# ======================
# ➕ New Order
# ======================
with tab_new:
    st.subheader("Create a New Order")
    df = load_orders()

    col1, col2, col3 = st.columns(3)
    with col1:
        item = st.text_input("ITEM *", placeholder="e.g., Fetal Bovine Serum (FBS) 500 mL")
        vendor = st.text_input("VENDOR *", placeholder="e.g., Thermo Fisher")
        cat_no = st.text_input("CAT #", placeholder="e.g., 12345-TF")
        grant_used = st.text_input("GRANT USED", placeholder="e.g., R01CA12345 (comma separated)")
    with col2:
        qty = st.number_input("NUMBER OF ITEM *", min_value=0.0, value=0.0, step=1.0)
        unit_price = st.number_input(
            "AMOUNT PER ITEM *", min_value=0.0, value=0.0, step=1.0, format="%.2f"
        )
        po_source = st.selectbox("PO SOURCE", ["ShopBlue", "Stock Room", "External Vendor"], index=0)
        po_no = st.text_input("PO #", placeholder="e.g., PO-2025-00123")
    with col3:
        notes = st.text_area("NOTES", placeholder="Any notes (urgent, storage req., etc.)")
        ordered_by = st.text_input("ORDERED BY", placeholder="Name / ID")
        # Use date.today() to give a pure date (avoids timezone warnings)
        date_ordered = st.date_input("DATE ORDERED", value=date.today())
        received_flag = st.checkbox("Item received?")
        date_received = st.date_input("DATE RECEIVED", value=date.today()) if received_flag else None

    submitted = st.button("Add Order", type="primary")
    if submitted:
        ok, msg = validate_order(item, qty, unit_price, vendor)
        if not ok:
            st.error(msg)
        else:
            req_id = gen_req_id(df)
            total = compute_total(qty, unit_price)
            new_row = {
                "REQ#": req_id,
                "ITEM": item,
                "NUMBER OF ITEM": qty,
                "AMOUNT PER ITEM": unit_price,
                "TOTAL": total,
                "VENDOR": vendor,
                "CAT #": cat_no,
                "GRANT USED": grant_used,
                "PO SOURCE": po_source,
                "PO #": po_no,
                "NOTES": notes,
                "ORDERED BY": ordered_by,
                "DATE ORDERED": pd.to_datetime(date_ordered).date().isoformat() if date_ordered else "",
                "DATE RECEIVED": pd.to_datetime(date_received).date().isoformat() if date_received else "",
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_orders(df)
            st.success(f"Order {req_id} added.")

# ======================
# 📋 Orders
# ======================
with tab_table:
    st.subheader("Orders Table")
    df = load_orders()

    c1, c2, c3 = st.columns(3)
    with c1:
        vendor_filter = st.text_input("Filter by VENDOR")
    with c2:
        grant_filter = st.text_input("Filter by GRANT USED")
    with c3:
        po_source_filter = st.selectbox(
            "Filter by PO SOURCE", ["All", "ShopBlue", "Stock Room", "External Vendor"]
        )

    filtered = df.copy()
    if vendor_filter:
        filtered = filtered[filtered["VENDOR"].str.contains(vendor_filter, case=False, na=False)]
    if grant_filter:
        filtered = filtered[filtered["GRANT USED"].str.contains(grant_filter, case=False, na=False)]
    if po_source_filter != "All":
        filtered = filtered[filtered["PO SOURCE"] == po_source_filter]

    st.dataframe(filtered, use_container_width=True)

# ======================
# 📈 Analytics
# ======================
with tab_analytics:
    st.subheader("Top Items by Frequency")
    df = load_orders()
    if not df.empty and "ITEM" in df.columns:
        counts = df["ITEM"].value_counts().head(10)
        fig, ax = plt.subplots(figsize=(8, 4))
        counts.plot(kind="bar", ax=ax)
        ax.set_xlabel("Item")
        ax.set_ylabel("Orders (count)")
        ax.set_title("Top 10 Ordered Items")
        st.pyplot(fig)
    else:
        st.info("No data yet. Add some orders to see analytics.")

# ======================
# ⬇️ Export
# ======================
with tab_export:
    st.subheader("Download Orders")
    df = load_orders()
    df = df[REQUIRED_COLUMNS]

    # CSV download
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Excel download
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Orders", index=False)
    st.download_button(
        label="Download Excel",
        data=output.getvalue(),
        file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.markdown("---")
st.caption("Requiva MVP • Export includes all locked fields for grant and audit readiness.")
\
