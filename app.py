import streamlit as st
import requests
import datetime
from fpdf import FPDF
import base64

# --- 1. STYLING (VvAA Huisstijl) ---
st.set_page_config(page_title="VvAA Auto Calculator", page_icon="🚗", layout="wide")

vvaa_css = """
<style>
    h1, h2, h3, h4 { color: #EA5B0C; font-family: 'Arial', sans-serif; }
    .stButton>button { background-color: #EA5B0C; color: white; border-radius: 5px; border: none; padding: 10px 24px; font-weight: bold; }
    .stButton>button:hover { background-color: #cc4d08; color: white; }
    .stDownloadButton>button { background-color: #003366; color: white; }
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

try:
    st.image("vvaa_logo.png", width=200)
except:
    pass

st.title("Autoberekening: Zakelijk of Privé?")
st.write("Vul de ontbrekende gegevens in om de berekening kloppend te maken met het klantdossier.")

# --- 2. RDW API FUNCTIE ---
@st.cache_data
def get_rdw_data(kenteken):
    kenteken = kenteken.replace("-", "").upper()
    url_basis = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={kenteken}"
    url_brandstof = f"https://opendata.rdw.nl/resource/8ys7-d773.json?kenteken={kenteken}"
    try:
        req_basis = requests.get(url_basis).json()
        req_brandstof = requests.get(url_brandstof).json()
        if not req_basis: return None
        data = req_basis[0]
        brandstof_data = req_brandstof[0] if req_brandstof else {}
        eerste_toelating = data.get("datum_eerste_toelating_dt", datetime.datetime.now().strftime("%Y-%m-%d"))
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "bouwjaar": int(eerste_toelating[:4]),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "brandstof": brandstof_data.get("brandstof_omschrijving", "Onbekend"),
            "toelating": eerste_toelating[:10]
        }
    except:
        return None

# --- 3. INPUT VELDEN ---
with st.container():
    st.subheader("1. Klant & Voertuig Gegevens")
    colA, colB, colC = st.columns(3)
    with colA:
        klant_naam = st.text_input("Naam relatie")
    with colB:
        klant_nummer = st.text_input("Relatienummer")
    with colC:
        kenteken_input = st.text_input("Kenteken (bijv. AB-123-C)")

st.markdown("---")

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if not auto:
        st.error("Kenteken niet gevonden. Controleer de invoer.")
    else:
        st.success(f"Voertuig: {auto['merk']} {auto['handelsbenaming']} | Bouwjaar: {auto['bouwjaar']} | Brandstof: {auto['brandstof']} | Cataloguswaarde: € {auto['catalogusprijs']:,.2f}")
        
        # Bepaal EV of Brandstof
        is_ev = "Elektriciteit" in auto['brandstof']
        leeftijd = datetime.datetime.now().year - auto['bouwjaar']
        
        # Default schattingen
        est_mrb = 0 if is_ev else (auto['gewicht'] * 0.8)
        
        st.subheader("2. Financiële Details & Verbruik")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            aanschafwaarde = st.number_input("Aanschafwaarde (€)", min_value=0.0, step=500.0, value=auto['catalogusprijs'])
            bijtelling_perc = st.number_input("Percentage Bijtelling (%)", min_value=0.0, max_value=100.0, value=16.0 if is_ev and leeftijd > 2 else 22.0)
            rente = st.number_input("Rente financiering (€)", value=0.0, step=100.0)
            
        with col2:
            st.markdown("**Kilometers & Verbruik**")
            zakelijke_km = st.number_input("Zakelijke km / jaar", min_value=0, value=15000, step=1000)
            prive_km = st.number_input("Privé km / jaar", min_value=0, value=5000, step=1000)
            totaal_km = zakelijke_km + prive_km
            
            if is_ev:
                verbruik = st.number_input("Verbruik (kWh per 100 km)", value=18.0)
                prijs = st.number_input("Elektriciteitsprijs per kWh (€)", value=0.35)
            else:
                verbruik = st.number_input("Verbruik (Liters per 100 km)", value=6.0)
                prijs = st.number_input("Brandstofprijs per liter (€)", value=1.95)

        with col3:
            st.markdown("**Vaste Kosten (Jaarbasis)**")
            mrb = st.number_input("Motorrijtuigenbelasting (€)", value=float(est_mrb))
            # Schatting onderhoud en verzekering als default invulwaarde
            est_ond = 300 + (leeftijd * 50) + (totaal_km * 0.02)
            est_verz = 600 + (auto['catalogusprijs'] * 0.01)
            
            onderhoud = st.number_input("Onderhoud (€)", value=float(est_ond))
            verzekering = st.number_input("Verzekering (€)", value=float(est_verz))
            overige = st.number_input("Overige autokosten (€)", value=0.0)

        # --- BEREKENINGEN ---
        afschrijving = (aanschafwaarde * 0.80) * 0.20
        brandstofkosten = (totaal_km / 100) * verbruik * prijs
        totale_kosten = brandstofkosten + mrb + onderhoud + verzekering + overige + afschrijving + rente
        bijtelling_bedrag = auto['catalogusprijs'] * (bijtelling_perc / 100)
        
        aftrek_zakelijk = totale_kosten - bijtelling_bedrag
        aftrek_prive = zakelijke_km * 0.23

        # --- WEERGAVE ZOALS IN EXCEL ---
        st.markdown("---")
        st.subheader("3. Autoberekening zakelijk of prive?")
        
        res1, res2 = st.columns(2)
        
        with res1:
            st.markdown("#### 🏢 Auto Zakelijk")
            st.write(f"**Brandstof/Laadkosten:** € {brandstofkosten:,.2f}")
            st.write(f"**Motorrijtuigenbelasting:** € {mrb:,.2f}")
            st.write(f"**Onderhoud:** € {onderhoud:,.2f}")
            st.write(f"**Verzekering:** € {verzekering:,.2f}")
            st.write(f"**Overige autokosten:** € {overige:,.2f}")
            st.write(f"**Afschrijving:** € {afschrijving:,.2f}")
            st.write(f"**Rente financiering:** € {rente:,.2f}")
            st.markdown(f"**Totale autokosten:** **€ {totale_kosten:,.2f}**")
            st.write(f"**Minus Bijtelling:** € -{bijtelling_bedrag:,.2f}")
            st.info(f"**Fiscale aftrekpost:** € {aftrek_zakelijk:,.2f}")

        with res2:
            st.markdown("#### 🏠 Auto Privé")
            st.write(f"**Vergoeding:** € 0.23 per zakelijke kilometer")
            st.write(f"**Zakelijke kilometers:** {zakelijke_km}")
            st.write("") # witregels om uit te lijnen
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.info(f"**Fiscale aftrekpost:** € {aftrek_prive:,.2f}")

        st.markdown("---")
        if aftrek_zakelijk > aftrek_prive:
            advies = "voordeliger"
            st.success("💡 **Advies vanuit fiscaal oogpunt:** ZAKELIJK is voordeliger.")
        else:
            advies = "minder voordelig"
            st.warning("💡 **Advies vanuit fiscaal oogpunt:** PRIVÉ is voordeliger.")

        # --- AANDACHTSPUNTEN (Uit Excel) ---
        st.markdown("#### Aandachtspunten bij zakelijk rijden:")
        st.write("- Controleer of de werkelijke afschrijving afwijkt van de aannames.")
        st.write("- Btw-correctie privégebruik (meestal 2,7% van de cataloguswaarde) is afhankelijk van de exacte situatie en moet nog in de aangifte verwerkt worden.")
        st.write("- Bovenstaande is een indicatie, aan deze berekening kunnen geen rechten worden ontleend.")

        # --- PDF GENERATIE ---
        if st.button("Genereer PDF Rapport"):
            pdf = FPDF()
            pdf.add_page()
            
            # Kleuren en lettertype
            oranje = (234, 91, 12)
            zwart = (0, 0, 0)
            
            pdf.set_font("Arial", 'B', 16)
            pdf.set_text_color(*oranje)
            pdf.cell(200, 10, txt="VvAA Autoberekening: Zakelijk of Prive", ln=True, align='L')
            
            pdf.set_font("Arial", size=10)
            pdf.set_text_color(*zwart)
            pdf.cell(200, 6, txt=f"Relatienaam: {klant_naam} | Relatienummer: {klant_nummer}", ln=True)
            pdf.cell(200, 6, txt=f"Voertuig: {auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})", ln=True)
            pdf.cell(200, 6, txt=f"Cataloguswaarde: EUR {auto['catalogusprijs']:,.2f} | Bijtelling: {bijtelling_perc}%", ln=True)
            pdf.line(10, 40, 200, 40)
            pdf.ln(5)
            
            # Tabel Zakelijk
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(100, 8, txt="Auto Zakelijk", ln=False)
            pdf.cell(100, 8, txt="Auto Prive", ln=True)
            
            pdf.set_font("Arial", size=10)
            # Rij 1
            pdf.cell(100, 6, txt=f"Brandstof/Laadkosten: EUR {brandstofkosten:,.2f}", ln=False)
            pdf.cell(100, 6, txt=f"Zakelijke km: {zakelijke_km}", ln=True)
            # Rij 2
            pdf.cell(100, 6, txt=f"MRB: EUR {mrb:,.2f}", ln=False)
            pdf.cell(100, 6, txt=f"Vergoeding: EUR 0.23/km", ln=True)
            # Overige zakelijke rijen
            pdf.cell(200, 6, txt=f"Onderhoud: EUR {onderhoud:,.2f}", ln=True)
            pdf.cell(200, 6, txt=f"Verzekering: EUR {verzekering:,.2f}", ln=True)
            pdf.cell(200, 6, txt=f"Overige kosten: EUR {overige:,.2f}", ln=True)
            pdf.cell(200, 6, txt=f"Afschrijving: EUR {afschrijving:,.2f}", ln=True)
            pdf.cell(200, 6, txt=f"Rente: EUR {rente:,.2f}", ln=True)
            
            pdf.line(10, pdf.get_y(), 100, pdf.get_y())
            pdf.ln(2)
            
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(200, 6, txt=f"Totale autokosten: EUR {totale_kosten:,.2f}", ln=True)
            pdf.cell(200, 6, txt=f"Minus Bijtelling: EUR -{bijtelling_bedrag:,.2f}", ln=True)
            
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(100, 8, txt=f"Fiscale aftrekpost Zakelijk: EUR {aftrek_zakelijk:,.2f}", ln=False)
            pdf.cell(100, 8, txt=f"Fiscale aftrekpost Prive: EUR {aftrek_prive:,.2f}", ln=True)
            
            pdf.ln(10)
            pdf.set_text_color(*oranje)
            pdf.cell(200, 10, txt=f"Advies: ZAKELIJK is {advies}.", ln=True)
            
            # Output PDF
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            
            st.download_button(
                label="📄 Download Rapport als PDF",
                data=pdf_bytes,
                file_name=f"VvAA_Autoberekening_{kenteken_input}.pdf",
                mime="application/pdf"
            )
