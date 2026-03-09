import streamlit as st
import requests
import datetime
import os
from fpdf import FPDF
from dateutil.relativedelta import relativedelta

# --- 1. VvAA HUISSTIJL & CONFIGURATIE ---
VVAA_ORANJE = "#E84E0F"
VVAA_BLAUW = "#00315C"
VVAA_GRIJS = "#F4F4F4"

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = f"""
<style>
    .stApp {{ background-color: #ffffff !important; }}
    .stApp, p, label, div[data-testid="stMarkdownContainer"] > p {{ color: {VVAA_BLAUW} !important; }}

    h1, h2, h3, h4, h5, h6, 
    div[data-testid="stMarkdownContainer"] > h1, 
    div[data-testid="stMarkdownContainer"] > h2, 
    div[data-testid="stMarkdownContainer"] > h3 {{ 
        color: {VVAA_ORANJE} !important; 
        font-family: 'Arial', sans-serif !important; 
    }}
    
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; 
        color: white !important; 
        border-radius: 4px; border: none; padding: 10px 24px; font-weight: bold; width: 100%; margin-top: 28px; 
    }}
    .stButton>button:hover {{ background-color: #c73e07 !important; }}
    
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; color: white !important; border-radius: 6px !important;
        border: 2px solid {VVAA_BLAUW} !important; padding: 15px 32px !important; font-size: 18px !important; font-weight: bold !important;
        width: 100% !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: 0.3s;
    }}
    div.stDownloadButton > button * {{ color: white !important; font-size: 18px !important; }}
    div.stDownloadButton > button:hover {{ background-color: white !important; color: {VVAA_BLAUW} !important; border: 2px solid {VVAA_ORANJE} !important; }}
    div.stDownloadButton > button:hover * {{ color: {VVAA_BLAUW} !important; }}
    
    div[data-testid="stAlert"] {{ background-color: {VVAA_GRIJS} !important; border-left: 5px solid {VVAA_ORANJE} !important; padding: 10px; }}
    div[data-testid="stAlert"] * {{ color: {VVAA_BLAUW} !important; }}
    input, select, div[data-baseweb="select"] > div {{ background-color: #ffffff !important; color: {VVAA_BLAUW} !important; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

# Helper functie voor Nederlandse bedragen zonder decimalen (bijv: 1.250)
def fmt(val):
    return f"{int(round(val)):,}".replace(",", ".")

if os.path.exists("vvaa_logo.jpg"):
    st.image("vvaa_logo.jpg", width=200)

st.title("Autoberekening zakelijk of privé?")
st.write(f"***In het hart van de gezondheidszorg.***")
st.markdown("---")

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
        brandstoffen = []
        rdw_verbruik_liter = 6.0 
        
        if req_brandstof:
            for b in req_brandstof:
                omschrijving = b.get("brandstof_omschrijving", "").lower()
                brandstoffen.append(omschrijving)
                if omschrijving in ["benzine", "diesel", "lpg"]:
                    verbruik = b.get("brandstofverbruik_gecombineerd")
                    if verbruik: rdw_verbruik_liter = float(verbruik)
        
        eerste_toelating = data.get("datum_eerste_toelating_dt", datetime.datetime.now().strftime("%Y-%m-%d"))
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": eerste_toelating[:10],
            "bouwjaar": int(eerste_toelating[:4]),
            "brandstoffen": brandstoffen,
            "rdw_verbruik_liter": rdw_verbruik_liter
        }
    except:
        return None

# VERBETERDE MRB SCHATTING
def schat_mrb(gewicht, brandstof_is_ev, brandstof_is_diesel, provincie):
    # Belastingdienst werkt grofweg in schijven van 100kg boven de 500kg
    gewichtsklasse = max(0, (gewicht - 500) // 100)
    basis_jaar = 150 + (gewichtsklasse * 135) # Realistischere benzine-curve
    
    if brandstof_is_ev: 
        basis_jaar = basis_jaar * 0.25 # EV korting simulatie
    elif brandstof_is_diesel: 
        basis_jaar = basis_jaar * 2.20 # Zware diesel/fijnstof toeslag
        
    provincie_factoren = {"Noord-Holland": 0.95, "Zuid-Holland": 1.12, "Gelderland": 1.05, "Drenthe": 1.08, "Groningen": 1.06, "Friesland": 1.04, "Overijssel": 1.03, "Flevoland": 1.02, "Utrecht": 1.00, "Zeeland": 1.04, "Noord-Brabant": 1.03, "Limburg": 1.05}
    return basis_jaar * provincie_factoren.get(provincie, 1.05)

BIJTELLING_OPTIES = [
    "22% over Cataloguswaarde (Standaard)", "35% over Aanschafwaarde (Youngtimer >15 jaar)",
    "4% tot € 50.000, 22% daarboven (EV 2019)", "8% tot € 45.000, 22% daarboven (EV 2020)",
    "12% tot € 40.000, 22% daarboven (EV 2021)", "16% tot € 35.000, 22% daarboven (EV 2022)",
    "16% tot € 30.000, 22% daarboven (EV 2023/2024)", "17% tot € 30.000, 22% daarboven (EV 2025/2026)"
]

def bepaal_bijtelling_index(bouwjaar, is_ev, is_youngtimer):
    if is_youngtimer: return 1
    if not is_ev: return 0
    if bouwjaar <= 2019: return 2
    elif bouwjaar == 2020: return 3
    elif bouwjaar == 2021: return 4
    elif bouwjaar == 2022: return 5
    elif bouwjaar in [2023, 2024]: return 6
    else: return 7

# --- 3. KLANTGEGEVENS & VALIDATIE ---
st.subheader("1. Klant & Voertuig Gegevens")

colA, colB = st.columns(2)
with colA: klant_naam = st.text_input("Naam relatie *")
with colB: klant_nummer = st.text_input("Relatienummer (alleen cijfers) *")

colC, colD, colE = st.columns([2, 2, 1])
with colC: kenteken_input = st.text_input("Kenteken (bijv. AB-123-C) *")
with colD: provincie = st.selectbox("Provincie (voor Wegenbelasting)", ["Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen", "Limburg", "Noord-Brabant", "Noord-Holland", "Overijssel", "Utrecht", "Zeeland", "Zuid-Holland"])
with colE: bereken_knop = st.button("Laden / Berekenen")

is_valid_naam = bool(klant_naam) and not klant_naam.replace(" ", "").isdigit()
is_valid_nummer = bool(klant_nummer) and klant_nummer.isdigit()
gevalideerd = is_valid_naam and is_valid_nummer

if not gevalideerd and (klant_naam or klant_nummer):
    st.warning("⚠️ Naam relatie is verplicht en Relatienummer mag uitsluitend uit cijfers bestaan.")

st.markdown("---")

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if not auto:
        st.error("Kenteken niet gevonden. Controleer de invoer.")
    else:
        toelating_date = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        vandaag = datetime.datetime.now()
        leeftijd_exact = relativedelta(vandaag, toelating_date)
        is_youngtimer_auto = leeftijd_exact.years >= 15
        
        is_ev = any("elektriciteit" in b for b in auto['brandstoffen'])
        is_diesel = any("diesel" in b for b in auto['brandstoffen'])
        is_brandstof = any(b in ["benzine", "diesel", "lpg", "alcohol"] for b in auto['brandstoffen'])
        if not is_ev and not is_brandstof: is_brandstof = True
        
        brandstof_tekst = ", ".join(auto['brandstoffen']).title()
        berekende_mrb = schat_mrb(auto['gewicht'], is_ev, is_diesel, provincie)
        voorspelde_bijtelling_index = bepaal_bijtelling_index(auto['bouwjaar'], is_ev, is_youngtimer_auto)
        
        st.success(f"**Voertuig:** {auto['merk']} {auto['handelsbenaming']} | **Brandstof:** {brandstof_tekst} | **RDW Verbruik:** {auto['rdw_verbruik_liter']} L/100km")
        
        st.subheader("2. Financiële Details & Verbruik")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**Waarde & Bijtelling**")
            st.write(f"Cataloguswaarde (RDW): **€ {fmt(auto['catalogusprijs'])}**")
            aanschafwaarde = st.number_input("Aanschafwaarde (€)", min_value=0, step=500, value=int(auto['catalogusprijs']))
            gekozen_bijtelling = st.selectbox("Fiscaal Bijtellingsprofiel:", BIJTELLING_OPTIES, index=voorspelde_bijtelling_index)
            st.markdown(f"**Kilometers per jaar**")
            zakelijke_km = st.number_input("Zakelijke km", min_value=0, value=25000, step=1000)
            prive_km = st.number_input("Privé km", min_value=0, value=25000, step=1000)
            totaal_km = zakelijke_km + prive_km

        with col2:
            st.markdown(f"**Verbruik & Kosten**")
            brandstofkosten = 0.0
            laadkosten = 0.0
            if is_brandstof:
                verbruik_liter = st.number_input("Verbruik (liters per 100 km)", value=float(auto['rdw_verbruik_liter']))
                prijs_liter = st.number_input("Brandstofprijs per liter (€)", value=1.95)
                brandstofkosten = st.number_input("Brandstofkosten (€)", value=int((totaal_km / 100) * verbruik_liter * prijs_liter))
            if is_ev:
                verbruik_kwh = st.number_input("Verbruik (KWH per 100 km)", value=18.0)
                prijs_kwh = st.number_input("Kosten per KWH (€)", value=0.50)
                laadkosten = st.number_input("Laadkosten (€)", value=int((totaal_km / 100) * verbruik_kwh * prijs_kwh))

        with col3:
            st.markdown(f"**Overige Autokosten**")
            mrb = st.number_input("Motorrijtuigenbelasting (€)", value=int(berekende_mrb))
