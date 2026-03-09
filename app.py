import streamlit as st
import requests
import datetime
from fpdf import FPDF
import io

# --- 1. STYLING (VvAA Huisstijl) ---
st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = """
<style>
    h1, h2, h3, h4 { color: #EA5B0C; font-family: 'Arial', sans-serif; }
    .stButton>button { background-color: #EA5B0C; color: white; border-radius: 5px; border: none; padding: 10px 24px; font-weight: bold; }
    .stButton>button:hover { background-color: #cc4d08; color: white; }
    .stDownloadButton>button { background-color: #003366; color: white; }
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

st.title("Autoberekening zakelijk of prive?")
st.write("*In het hart van de gezondheidszorg.*")

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
        st.success(f"Voertuig: {auto['merk']} {auto['handelsbenaming']} | Datum toelating: {auto['toelating']} | Cataloguswaarde: € {auto['catalogusprijs']:,.2f}")
        
        leeftijd = datetime.datetime.now().year - auto['bouwjaar']
        is_ev = "Elektriciteit" in auto['brandstof']
        est_mrb = 0 if is_ev else (auto['gewicht'] * 0.8)
        
        st.subheader("2. Financiële Details & Verbruik")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            aanschafwaarde = st.number_input("Aanschafwaarde (€)", min_value=0.0, step=500.0, value=auto['catalogusprijs'])
            bijtelling_perc = st.number_input("Percentage voor de bijtelling (%)", min_value=0.0, max_value=100.0, value=16.0 if is_ev and leeftijd > 2 else 22.0)
            
            st.markdown("**Kilometers**")
            zakelijke_km = st.number_input("Zakelijke kilometers op jaarbasis", min_value=0, value=25000, step=1000)
            prive_km = st.number_input("Privé-kilometers op jaarbasis", min_value=0, value=25000, step=1000)
            totaal_km = zakelijke_km + prive_km
            st.info(f"Totaal kilometers: **{totaal_km}**")

        with col2:
            st.markdown("**Verbruik & Kosten (Brandstof/Stroom)**")
            verbruik_liter = st.number_input("Verbruik (liters per 100 km)", value=1.0)
            prijs_liter = st.number_input("Brandstofprijs per liter (€)", value=1.95)
            
            verbruik_kwh = st.number_input("Verbruik (KWH per 100 km)", value=28.3)
            prijs_kwh = st.number_input("Kosten per KWH (€)", value=0.50)
            
            st.caption("Let op: Handmatige invoer hieronder overschrijft de automatische berekening.")
            calc_brandstof = (totaal_km / 100) * verbruik_liter * prijs_liter if verbruik_liter > 0 else 0
            calc_laad = (totaal_km / 100) * verbruik_kwh * prijs_kwh if verbruik_kwh > 0 else 0
            
            brandstofkosten = st.number_input("Brandstofkosten (€)", value=float(calc_brandstof))
            laadkosten = st.number_input("Laadkosten (€)", value=float(calc_laad))

        with col3:
            st.markdown("**Overige Autokosten**")
            mrb = st.number_input("Motorrijtuigenbelasting (€)", value=float(est_mrb))
            onderhoud = st.number_input("Onderhoud (€)", value=0.0)
            verzekering = st.number_input("Verzekering (€)", value=0.0)
            overige = st.number_input("Overige autokosten (€)", value=500.0)
            leasebedrag = st.number_input("Leasebedrag all-in / Rente (€)", value=0.0)

        # --- BEREKENINGEN ---
        afschrijving = (aanschafwaarde * 0.80) * 0.20
        totale_kosten = laadkosten + brandstofkosten + mrb + onderhoud + verzekering + overige + afschrijving + leasebedrag
        bijtelling_bedrag = auto['catalogusprijs'] * (bijtelling_perc / 100)
        
        aftrek_zakelijk = totale_kosten - bijtelling_bedrag
        aftrek_prive = zakelijke_km * 0.23

        # --- WEERGAVE ---
        st.markdown("---")
        st.subheader("3. Resultaat")
        
        res1, res2 = st.columns(2)
        
        with res1:
            st.markdown("#### Auto zakelijk")
            st.write(f"Laadkosten: € {laadkosten:,.2f}")
            st.write(f"Brandstofkosten: € {brandstofkosten:,.2f}")
            st.write(f"Motorrijtuigenbelasting: € {mrb:,.2f}")
            st.write(f"Onderhoud: € {onderhoud:,.2f}")
            st.write(f"Verzekering: € {verzekering:,.2f}")
            st.write(f"Overige autokosten: € {overige:,.2f}")
            st.write(f"Afschrijving: € {afschrijving:,.2f}")
            st.write(f"Leasebedrag all-in: € {leasebedrag:,.2f}")
            st.markdown(f"**Totale autokosten: € {totale_kosten:,.2f}**")
            st.write(f"Bijtelling: € {bijtelling_bedrag:,.2f}")
            st.success(f"**Fiscale aftrekpost: € {aftrek_zakelijk:,.2f}**")

        with res2:
            st.markdown("#### Auto prive")
            st.write(f"Vergoeding: € 0,23 per km")
            st.write(f"Zakelijke kilometers: {zakelijke_km}")
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.write("")
            st.success(f"**Fiscale aftrekpost: € {aftrek_prive:,.2f}**")

        st.markdown("---")
        if aftrek_zakelijk > aftrek_prive:
            advies = "Zakelijk voordeliger"
        else:
            advies = "Prive voordeliger"
            
        st.subheader(f"Advies vanuit fiscaal oogpunt: {advies}")

        # --- PDF GENERATIE ---
        if st.button("Genereer PDF Rapport"):
            pdf = FPDF()
            pdf.add_page()
            
            # Kleuren
            oranje = (234, 91, 12)
            zwart = (0, 0, 0)
            grijs = (100, 100, 100)
            
            # Header
            pdf.set_font("Arial", 'B', 20)
            pdf.set_text_color(*oranje)
            pdf.cell(200, 10, txt="VvAA", ln=True, align='L')
            pdf.set_font("Arial", 'I', 12)
            pdf.set_text_color(*grijs)
            pdf.cell(200, 8, txt="In het hart van de gezondheidszorg.", ln=True, align='L')
            pdf.ln(5)
            
            pdf.set_font("Arial", 'B', 16)
            pdf.set_text_color(*zwart)
            pdf.cell(200, 10, txt="Autoberekening zakelijk of prive?", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            # Klant Info
            pdf.set_font("Arial", '', 10)
            pdf.cell(50, 6, txt="Naam relatie:", ln=False)
            pdf.cell(100, 6, txt=str(klant_naam), ln=True)
            pdf.cell(50, 6, txt="Relatienummer:", ln=False)
            pdf.cell(100, 6, txt=str(klant_nummer), ln=True)
            pdf.ln(5)
            
            # Auto Info
            pdf.cell(50, 6, txt="Merk auto:", ln=False)
            pdf.cell(100, 6, txt=str(auto['merk']), ln=True)
            pdf.cell(50, 6, txt="Type:", ln=False)
            pdf.cell(100, 6, txt=str(auto['handelsbenaming']), ln=True)
            pdf.cell(50, 6, txt="Kenteken:", ln=False)
            pdf.cell(100, 6, txt=str(kenteken_input.upper()), ln=True)
            pdf.cell(50, 6, txt="Eerste toelating:", ln=False)
            pdf.cell(100, 6, txt=str(auto['toelating']), ln=True)
            pdf.cell(50, 6, txt="Aanschafwaarde:", ln=False)
            pdf.cell(100, 6, txt=f"EUR {aanschafwaarde:,.0f}", ln=True)
            pdf.cell(50, 6, txt="Cataloguswaarde:", ln=False)
            pdf.cell(100, 6, txt=f"EUR {auto['catalogusprijs']:,.0f}", ln=True)
            pdf.cell(50, 6, txt="Percentage voor de bijtelling:", ln=False)
            pdf.cell(100, 6, txt=f"{bijtelling_perc}%", ln=True)
            pdf.ln(5)
            
            # Kilometers & Verbruik
            pdf.cell(60, 6, txt="Zakelijke kilometers op jaarbasis:", ln=False)
            pdf.cell(40, 6, txt=str(zakelijke_km), ln=True)
            pdf.cell(60, 6, txt="Prive-kilometers op jaarbasis:", ln=False)
            pdf.cell(40, 6, txt=str(prive_km), ln=True)
            pdf.cell(60, 6, txt="Totaal kilometers op jaarbasis:", ln=False)
            pdf.cell(40, 6, txt=str(totaal_km), ln=True)
            pdf.ln(2)
            pdf.cell(60, 6, txt="Verbruik (liters per 100 kilometer):", ln=False)
            pdf.cell(40, 6, txt=str(verbruik_liter), ln=True)
            pdf.cell(60, 6, txt="Brandstofprijs per liter:", ln=False)
            pdf.cell(40, 6, txt=f"EUR {prijs_liter:,.2f}", ln=True)
            pdf.cell(60, 6, txt="KWH per 100 km:", ln=False)
            pdf.cell(40, 6, txt=str(verbruik_kwh), ln=True)
            pdf.cell(60, 6, txt="Kosten per KWH:", ln=False)
            pdf.cell(40, 6, txt=f"EUR {prijs_kwh:,.2f}", ln=True)
            pdf.ln(10)
            
            # Financiële Tabel
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(100, 8, txt="Auto zakelijk", ln=False)
            pdf.cell(100, 8, txt="Auto prive", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)
            
            pdf.set_font("Arial", '', 10)
            
            def row(label1, val1, label2="", val2=""):
                pdf.cell(60, 6, txt=label1, ln=False)
                pdf.cell(40, 6, txt=val1, ln=False)
                pdf.cell(60, 6, txt=label2, ln=False)
                pdf.cell(40, 6, txt=val2, ln=True)

            row("Laadkosten:", f"EUR {laadkosten:,.2f}", "Vergoeding:", "EUR 0,23")
            row("Brandstofkosten:", f"EUR {brandstofkosten:,.2f}", "Zakelijke km:", str(zakelijke_km))
            row("Motorrijtuigenbelasting:", f"EUR {mrb:,.2f}")
            row("Onderhoud:", f"EUR {onderhoud:,.2f}")
            row("Verzekering:", f"EUR {verzekering:,.2f}")
            row("Overige autokosten:", f"EUR {overige:,.2f}")
            row("Afschrijving:", f"EUR {afschrijving:,.2f}")
            row("Leasebedrag all-in:", f"EUR {leasebedrag:,.2f}")
            
            pdf.ln(2)
            pdf.set_font("Arial", 'B', 10)
            row("Totale autokosten:", f"EUR {totale_kosten:,.2f}")
            pdf.set_font("Arial", '', 10)
            row("Bijtelling:", f"EUR {bijtelling_bedrag:,.2f}")
            
            pdf.ln(2)
            pdf.set_font("Arial", 'B', 10)
            row("Fiscale aftrekpost:", f"EUR {aftrek_zakelijk:,.0f}", "Fiscale aftrekpost:", f"EUR {aftrek_prive:,.0f}")
            pdf.ln(8)
            
            # Advies
            pdf.set_font("Arial", 'B', 12)
            pdf.set_text_color(*oranje)
            pdf.cell(200, 8, txt=f"Advies vanuit fiscaal oogpunt: {advies}", ln=True)
            pdf.ln(5)
            
            # Aandachtspunten
            pdf.set_text_color(*zwart)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(200, 6, txt="Aandachtspunten bij zakelijk rijden:", ln=True)
            pdf.set_font("Arial", '', 9)
            pdf.cell(200, 5, txt="- verschillende kostenposten zijn gebaseerd op een schatting", ln=True)
            pdf.cell(200, 5, txt="- rekening houden met vervallen van rente op de lening", ln=True)
            pdf.cell(200, 5, txt="- na 5 jaar vervallen de afschrijvingskosten", ln=True)
            pdf.cell(200, 5, txt="- bij inruil kan een boekwinst ontstaan, welke belast kan zijn in de onderneming", ln=True)
            pdf.cell(200, 5, txt="- percentage bijtelling geldt voor 60 maanden vanaf datum eerste toelating (n.v.t. bij een youngtimer)", ln=True)
            
            # Output PDF
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            
            st.download_button(
                label="📄 Download Rapport als PDF",
                data=pdf_bytes,
                file_name=f"VvAA_Autoberekening_{kenteken_input}.pdf",
                mime="application/pdf"
            )
