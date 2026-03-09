import streamlit as st
import requests
import datetime
from fpdf import FPDF
import base64

# --- 1. STYLING (VvAA Huisstijl) ---
# VvAA Oranje is ongeveer HEX #EA5B0C
st.set_page_config(page_title="VvAA Auto Calculator", page_icon="🚗", layout="wide")

vvaa_css = """
<style>
    /* Headers en tekst in VvAA oranje/donkerblauw tinten */
    h1, h2, h3 { color: #EA5B0C; font-family: 'Arial', sans-serif; }
    
    /* Primaire knop styling */
    .stButton>button {
        background-color: #EA5B0C;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #cc4d08;
        color: white;
    }
    
    /* Download knop specifieke styling */
    .stDownloadButton>button {
        background-color: #003366; /* Donkerblauw als secundaire kleur */
        color: white;
    }
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

# Probeer een lokaal logo te laden, anders sla over
try:
    st.image("vvaa_logo.png", width=200)
except:
    st.markdown("**(VvAA Logo ontbreekt - plaats 'vvaa_logo.png' in de map)**")

st.title("Autoberekening: Zakelijk of Privé?")
st.write("Vul het kenteken en de kilometers in om direct te zien wat fiscaal voordeliger is.")

# --- 2. RDW API FUNCTIES ---
def get_rdw_data(kenteken):
    kenteken = kenteken.replace("-", "").upper()
    url_basis = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={kenteken}"
    url_brandstof = f"https://opendata.rdw.nl/resource/8ys7-d773.json?kenteken={kenteken}"
    
    try:
        req_basis = requests.get(url_basis).json()
        req_brandstof = requests.get(url_brandstof).json()
        
        if not req_basis:
            return None
            
        data = req_basis[0]
        brandstof_data = req_brandstof[0] if req_brandstof else {}
        
        # Datums en waarden veilig ophalen
        eerste_toelating = data.get("datum_eerste_toelating_dt", datetime.datetime.now().strftime("%Y-%m-%d"))
        bouwjaar = int(eerste_toelating[:4])
        catalogusprijs = float(data.get("catalogusprijs", 0))
        gewicht = int(data.get("massa_ledig_voertuig", 0))
        brandstof = brandstof_data.get("brandstof_omschrijving", "Onbekend")
        
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "bouwjaar": bouwjaar,
            "catalogusprijs": catalogusprijs,
            "gewicht": gewicht,
            "brandstof": brandstof
        }
    except Exception as e:
        return None

# --- 3. INPUT VELDEN (Sidebar & Main) ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Voertuig & RDW Gegevens")
    kenteken_input = st.text_input("Kenteken (bijv. AB-123-C)")
    aanschafwaarde = st.number_input("Aanschafwaarde (€) (Handmatige invoer)", min_value=0.0, step=500.0)
    provincie = st.selectbox("Provincie (voor MRB)", ["Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen", "Limburg", "Noord-Brabant", "Noord-Holland", "Overijssel", "Utrecht", "Zeeland", "Zuid-Holland"])

with col2:
    st.subheader("Kilometers")
    zakelijke_km = st.number_input("Zakelijke kilometers / jaar", min_value=0, value=15000, step=1000)
    prive_km = st.number_input("Privé kilometers / jaar", min_value=0, value=5000, step=1000)
    totaal_km = zakelijke_km + prive_km
    st.info(f"Totaal kilometers: **{totaal_km} km**")

# --- 4. BEREKENING & RESULTATEN ---
if st.button("Bereken Fiscale Positie"):
    if not kenteken_input:
        st.error("Vul een kenteken in.")
    elif aanschafwaarde == 0:
        st.warning("Vergeet niet de werkelijke aanschafwaarde in te vullen voor de afschrijving.")
    else:
        with st.spinner("RDW Data ophalen en berekenen..."):
            auto = get_rdw_data(kenteken_input)
            
            if auto:
                st.success(f"Voertuig gevonden: {auto['merk']} {auto['handelsbenaming']} ({auto['brandstof']}) - Bouwjaar: {auto['bouwjaar']}")
                
                # Berekeningen
                leeftijd = datetime.datetime.now().year - auto['bouwjaar']
                
                # 1. Afschrijving: 20% van (Aanschafwaarde minus 20% restwaarde)
                afschrijving = (aanschafwaarde * 0.80) * 0.20
                
                # 2. Onderhoud: Formule basis €300 + €50 per jaar + €0.02 per km
                onderhoud = 300 + (leeftijd * 50) + (totaal_km * 0.02)
                
                # 3. Verzekering schatting
                verzekering = 600 + (auto['catalogusprijs'] * 0.01)
                
                # 4. Brandstof / Stroom schatting
                if "Elektriciteit" in auto['brandstof']:
                    brandstofkosten = totaal_km * 0.18 * 0.35 # 18 kWh/100km * €0.35
                else:
                    brandstofkosten = totaal_km * 0.06 * 1.95 # 6L/100km * €1.95
                
                # 5. MRB (Gesimplificeerde schatting o.b.v. gewicht, elektrisch is €0)
                mrb = 0 if "Elektriciteit" in auto['brandstof'] else (auto['gewicht'] * 0.8)
                
                # 6. Bijtelling (Basis logica: 22% of 16% voor oudere EV's)
                bijtellingspercentage = 0.16 if ("Elektriciteit" in auto['brandstof'] and leeftijd > 2) else 0.22
                bijtelling = auto['catalogusprijs'] * bijtellingspercentage
                
                # Totalen
                totale_autokosten = afschrijving + onderhoud + verzekering + brandstofkosten + mrb
                aftrekpost_zakelijk = totale_autokosten - bijtelling
                aftrekpost_prive = zakelijke_km * 0.23

                # --- 5. RESULTATEN WEERGAVE ---
                st.markdown("---")
                st.header("Resultaat: Wat is voordeliger?")
                
                res1, res2 = st.columns(2)
                with res1:
                    st.subheader("🏢 Auto Zakelijk")
                    st.write(f"Totale kosten: € {totale_autokosten:,.2f}")
                    st.write(f"Minus bijtelling: € {bijtelling:,.2f}")
                    st.metric("Fiscale Aftrekpost (Zakelijk)", f"€ {aftrekpost_zakelijk:,.2f}")
                
                with res2:
                    st.subheader("🏠 Auto Privé")
                    st.write(f"Vaste vergoeding per km: € 0.23")
                    st.write(f"Zakelijke kilometers: {zakelijke_km}")
                    st.metric("Fiscale Aftrekpost (Privé)", f"€ {aftrekpost_prive:,.2f}")
                
                if aftrekpost_zakelijk > aftrekpost_prive:
                    st.success("💡 **Advies:** De auto ZAKELIJK rijden levert de hoogste aftrekpost op.")
                else:
                    st.info("💡 **Advies:** De auto in PRIVÉ houden (en €0,23 / km declareren) is fiscaal voordeliger.")

                # --- 6. PDF GENERATIE ---
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.set_text_color(234, 91, 12) # VvAA Oranje
                pdf.cell(200, 10, txt="VvAA Autoberekening: Zakelijk of Prive", ln=True, align='L')
                
                pdf.set_font("Arial", size=12)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(200, 10, txt=f"Voertuig: {auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})", ln=True)
                pdf.cell(200, 10, txt=f"Advies: {'ZAKELIJK' if aftrekpost_zakelijk > aftrekpost_prive else 'PRIVE'} is voordeliger.", ln=True)
                pdf.line(10, 40, 200, 40)
                
                pdf.cell(200, 10, txt=f"Totale werkelijke kosten: EUR {totale_autokosten:,.2f}", ln=True)
                pdf.cell(200, 10, txt=f"Fiscale bijtelling: EUR {bijtelling:,.2f}", ln=True)
                pdf.cell(200, 10, txt=f"Netto Aftrekpost Zakelijk: EUR {aftrekpost_zakelijk:,.2f}", ln=True)
                pdf.cell(200, 10, txt=f"Netto Aftrekpost Prive: EUR {aftrekpost_prive:,.2f}", ln=True)
                
                # Output PDF voor download
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                
                st.markdown("---")
                st.download_button(
                    label="📄 Download Rapport als PDF",
                    data=pdf_bytes,
                    file_name=f"VvAA_Autoberekening_{kenteken_input}.pdf",
                    mime="application/pdf"
                )
                
            else:
                st.error("Kenteken niet gevonden in de RDW database. Controleer de invoer.")
