import io
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Woo ⟷ SmartBill | Stock Sync Reports", layout="wide")

st.title("🧮 Woo ⟷ SmartBill — Rapoarte stoc pentru site")
st.caption("Încarcă exporturile tale cu coloanele **Name**, **Sku**, **Stock** și obține două rapoarte: • produse de adăugat pe site • produse de șters de pe site")

with st.sidebar:
    st.subheader("Instrucțiuni rapide")
    st.markdown(
        """
        1. **WooCommerce**: export CSV cu coloanele `Name, Sku, Stock`.
        2. **SmartBill**: export XLS/XLSX (sau CSV) cu `Name, Sku, Stock`.
        3. Apasă **Generează rapoarte**.

        🔧 Notă: SKU-urile sunt normalizate (trim, upper). Stocurile sunt agregate pe SKU (sumă).
        """
    )

@st.cache_data(show_spinner=False)
def _read_table(uploaded_file: io.BytesIO, filename: str) -> pd.DataFrame:
    """Read CSV/XLS/XLSX into a DataFrame without assuming separators/encodings.
    Required columns: Name, Sku, Stock (case-insensitive). Returns empty df on failure.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    name_lower = filename.lower()
    try:
        if name_lower.endswith(".csv"):
            # Try common separators
            for sep in [",", ";", "\t", "|"]:
                try:
                    df = pd.read_csv(uploaded_file, sep=sep, dtype=str, engine="python")
                    if df.shape[1] > 1:
                        break
                except Exception:
                    uploaded_file.seek(0)
                    continue
        elif name_lower.endswith((".xls", ".xlsx")):
            df = pd.read_excel(uploaded_file, dtype=str)
        else:
            # Fallback: try CSV
            df = pd.read_csv(uploaded_file, dtype=str)
    except Exception as e:
        st.error(f"Nu am putut citi fișierul `{filename}`: {e}")
        return pd.DataFrame()

    # Standardize column names
    df.columns = [str(c).strip() for c in df.columns]
    colmap = {}
    for col in df.columns:
        l = col.lower()
        if l in {"name", "product name", "denumire", "nume"} and "name" not in colmap:
            colmap[col] = "Name"
        elif l in {"sku", "cod", "product code", "cod produs", "code"} and "Sku" not in colmap:
            colmap[col] = "Sku"
        elif l in {"stock", "stoc", "qty", "cantitate", "qty on hand", "quantity"} and "Stock" not in colmap:
            colmap[col] = "Stock"

    df = df.rename(columns=colmap)

    required = {"Name", "Sku", "Stock"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Fișierul `{filename}` nu conține coloanele necesare: {', '.join(sorted(missing))} .")
        return pd.DataFrame()

    # Keep just required columns (and drop entirely empty rows)
    df = df[["Name", "Sku", "Stock"]].copy()
    df = df.dropna(how="all")

    # Normalize
    df["Sku"] = df["Sku"].astype(str).str.strip().str.upper()
    # Try to coerce stock to numeric, empty -> 0
    df["Stock"] = pd.to_numeric(df["Stock"].astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0)

    # Some exports may include negative or float stocks; keep numeric as-is
    # Aggregate by SKU (sum) and keep the first non-null Name preferring the most frequent
    agg = (df
           .groupby("Sku", as_index=False)
           .agg(
               Stock=("Stock", "sum"),
               Name=("Name", lambda s: s.dropna().astype(str).value_counts().idxmax() if len(s.dropna()) else "")
           ))

    return agg

# Uploaders
col1, col2 = st.columns(2)
with col1:
    woo_file = st.file_uploader("Încarcă **WooCommerce CSV**", type=["csv"], key="woo")
with col2:
    sb_file = st.file_uploader("Încarcă **SmartBill XLS/XLSX/CSV**", type=["xls", "xlsx", "csv"], key="sb")

if st.button("✨ Generează rapoarte", type="primary"):
    woo_df = _read_table(woo_file, woo_file.name) if woo_file else pd.DataFrame()
    sb_df = _read_table(sb_file, sb_file.name) if sb_file else pd.DataFrame()

    if woo_df.empty or sb_df.empty:
        st.warning("Încarcă ambele fișiere valide pentru a continua.")
        st.stop()

    # Merge for reporting
    merged = pd.merge(
        sb_df.rename(columns={"Stock": "SB_Stock", "Name": "SB_Name"}),
        woo_df.rename(columns={"Stock": "WOO_Stock", "Name": "WOO_Name"}),
        on="Sku",
        how="outer",
        validate="one_to_one"
    )

    # Prefer SmartBill name if available, else Woo name
    merged["Name"] = merged["SB_Name"].fillna(merged["WOO_Name"]) \
                               .fillna("").astype(str)

    # Fill missing stocks with 0 for logic
    merged["SB_Stock"] = pd.to_numeric(merged["SB_Stock"], errors="coerce").fillna(0)
    merged["WOO_Stock"] = pd.to_numeric(merged["WOO_Stock"], errors="coerce").fillna(0)

    # Reports
    add_to_site = merged[(merged["SB_Stock"] != 0) & (merged["WOO_Stock"] == 0)] \
        [["Sku", "Name", "SB_Stock", "WOO_Stock"]] \
        .sort_values(["Name", "Sku"]).reset_index(drop=True)

    remove_from_site = merged[(merged["SB_Stock"] == 0) & (merged["WOO_Stock"] != 0)] \
        [["Sku", "Name", "SB_Stock", "WOO_Stock"]] \
        .sort_values(["Name", "Sku"]).reset_index(drop=True)

    # Summary
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("SKU-uri în SmartBill", f"{len(sb_df):,}")
    with c2:
        st.metric("SKU-uri în WooCommerce", f"{len(woo_df):,}")
    with c3:
        st.metric("De adăugat pe site", f"{len(add_to_site):,}")
    with c4:
        st.metric("De șters de pe site", f"{len(remove_from_site):,}")

    st.divider()

    st.subheader("1) 📥 Produse de **adăugat** pe site")
    st.caption("Apar cu stoc diferit de 0 în SmartBill, dar cu stoc 0 în WooCommerce (sau lipsesc din Woo).")
    st.dataframe(add_to_site, use_container_width=True, hide_index=True)

    st.download_button(
        label="Descarcă CSV — Produse de adăugat",
        data=add_to_site.to_csv(index=False).encode("utf-8"),
        file_name=f"raport_adaugat_pe_site_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        type="primary",
        disabled=add_to_site.empty,
    )

    st.divider()

    st.subheader("2) 🗑️ Produse de **șters** de pe site")
    st.caption("Apar cu stoc 0 în SmartBill, dar cu stoc diferit de 0 în WooCommerce.")
    st.dataframe(remove_from_site, use_container_width=True, hide_index=True)

    st.download_button(
        label="Descarcă CSV — Produse de șters",
        data=remove_from_site.to_csv(index=False).encode("utf-8"),
        file_name=f"raport_sters_de_pe_site_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        type="secondary",
        disabled=remove_from_site.empty,
    )

else:
    st.info("Încarcă fișierele și apasă **Generează rapoarte**.")

with st.expander("ℹ️ Sfaturi și note"):
    st.markdown(
        """
        - Dacă ai mai multe rânduri pe același SKU într-un fișier (mai multe depozite/variante), aplicația **agregă stocul prin sumă**.
        - Pentru nume, păstrăm varianta cea mai frecventă din fișierul sursă.
        - Dacă vrei să ignori diferențele de literă mică/mare sau spații în SKU, deja facem **trim + upper**.
        - Poți salva rapoartele ca CSV și să le imporți în Retool/Sheets/Excel sau în scripturile tale de sincronizare.
        - Dacă ai nevoie și de un raport 3️⃣ (ex: *diferențe de stoc între Woo și SmartBill*), spune-mi și îl adaug.
        """
    )
