# Woo ⟷ SmartBill Stock Sync Reports

Aplicație simplă în **Streamlit** pentru compararea stocurilor între **WooCommerce** și **SmartBill**.

## Cum funcționează
1. Încarci două fișiere:
   - WooCommerce CSV (`Name, Sku, Stock`)
   - SmartBill XLS/XLSX/CSV (`Name, Sku, Stock`)
2. Apeși **Generează rapoarte**
3. Obții:
   - 📥 Produse de adăugat pe site (stoc ≠ 0 în SmartBill, dar 0 în WooCommerce)
   - 🗑️ Produse de șters de pe site (stoc = 0 în SmartBill, dar ≠ 0 în WooCommerce)

## Instalare locală
```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>
pip install -r requirements.txt
streamlit run streamlit_stock_sync_reports.py
