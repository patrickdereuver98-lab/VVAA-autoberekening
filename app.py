import streamlit as st
import requests
import datetime
import os
import math
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
    h1, h2, h3, h4, h5, h6 {{ color: {VVAA_ORANJE} !important; font-family: 'Arial', sans-serif !important; }}
    
    /* Primaire knop */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; color: white !important; 
        border-radius: 4px; border: none; padding: 10px 24px; font-weight: bold; width: 100%; margin-top: 28px; 
    }}
    .stButton>button:hover {{ background-color: #c73e07 !important; }}
    
    /* Grote opvallende Download PDF Knop */
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; 
        color: white !important; 
        border-radius: 6px !important;
        border: 2px solid {VVAA_BLAUW} !important;
        padding: 15px 32px !important; 
        font-size: 18px !important;
        font-weight: bold !important;
        width: 100% !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        display: flex;
        justify-content: center;
        align-items: center;
    }}
    /* Forceer witte tekstkleur voor de download knop tekst */
    div.stDownloadButton > button p, div.stDownloadButton > button span, div.stDownloadButton > button div {{
        color: white !important;
    }}
    
    div[data-testid="stAlert"] {{ background-color: {VVAA_GRIJS} !important; border-left: 5px solid {VVAA_ORANJE} !important; padding: 10px; }}
    div[data-testid="stAlert"] * {{ color: {VVAA_BLAUW} !important; }}
    input, select, div[data-baseweb="select"] > div {{ background-color: #ffffff !important; color: {VVAA_BLAUW} !important; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

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
        brandstoffen = [b.get("brandstof_omschrijving", "").lower() for b in req_brandstof] if req_brandstof else []
        rdw_verbruik = 6.0
        if req_brandstof:
            for b in req_brandstof:
                v = b.get("brandstofverbruik_gecombineerd")
                if v: rdw_verbruik = float(v)
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": data.get("datum_eerste_toelating_dt", "2020-01-01")[:10],
            "brandstoffen": brandstoffen,
            "rdw_verbruik": rdw_verbruik
        }
    except: return None

# --- 3. REKENLOGICA BELASTINGDIENST 2026 ---
def bereken_mrb_2026(gewicht, brandstoffen, provincie):
    # Basistarief Artikel 23 (per kwartaal)
    if gewicht <= 500: basis = 21.46
    elif gewicht <= 600: basis = 29.12
    elif gewicht <= 700: basis = 37.00
    elif gewicht <= 800: basis = 48.30
    else: # 900 kg en meer
        basis = 64.24 + (math.ceil(max(0, gewicht - 900) / 100) * 17.27)

    # Provinciale Opcenten 2026
    opcenten = {
        "Groningen": 95.7, "Friesland": 92.1, "Drenthe": 92.0, "Overijssel": 82.2,
        "Flevoland": 84.7, "Gelderland": 98.3, "Utrecht": 86.4, "Noord-Holland": 82.1,
        "Zuid-Holland": 104.4, "Zeeland": 84.4, "Noord-Brabant": 87.0, "Limburg": 88.5
    }
    perc = opcenten.get(provincie, 85.0)
    mrb_kwartaal = basis + (basis * (perc / 100))

    # Brandstoftoeslagen Artikel 23, tweede lid
    is_diesel = any("diesel" in b for b in brandstoffen)
    is_lpg = any("lpg" in b for b in brandstoffen)
    is_ev = any("elektriciteit" in b for b in brandstoffen)
    
    toeslag = 0
    if is_diesel:
        if gewicht <= 500: toeslag = 84.14
        elif gewicht <= 600: toeslag = 99.59
        elif gewicht <= 700: toeslag = 115.03
        elif gewicht <= 800: toeslag = 130.76
        else: toeslag = 153.00 + (math.ceil(max(0, gewicht - 900) / 100) * 16.57)
    elif is_lpg:
        if gewicht <= 500: toeslag = 98.71
        elif gewicht <= 600: toeslag = 118.32
        elif gewicht <= 700: toeslag = 137.95
        elif gewicht <= 800: toeslag = 157.54
        else: toeslag = 172.08 + (math.ceil(max(0, gewicht - 900) / 100) * 18.22)

    totaal_kwartaal = mrb_kwartaal + toeslag
    
    # EV Korting (75% korting in 2025, 25% korting in 2026)
    if is_ev: totaal_kwartaal *= 0.75 

    return totaal_kwartaal * 4

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

# --- 4. INPUT & LOGICA ---
st.subheader("1. Klant & Voertuig Gegevens")
colA, colB = st.columns(2)
with colA: klant_naam = st.text_input("Naam relatie *")
with colB: klant_nummer = st.text_input("Relatienummer (cijfers) *")

colC, colD, colE = st.columns([2, 2, 1])
with colC: kenteken_input = st.text_input("Kenteken *")
with colD: prov = st.selectbox("Provincie", ["Gelderland", "Noord-Holland", "Zuid-Holland", "Utrecht", "Noord-Brabant", "Overijssel", "Flevoland", "Groningen", "Friesland", "Drenthe", "Zeeland", "Limburg"])
with colE: st.button("Berekenen")

gevalideerd = bool(klant_naam) and klant_nummer.isdigit()

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if auto:
        toel_dt = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        leeftijd_exact = relativedelta(datetime.datetime.now(), toel_dt)
        is_young = leeftijd_exact.years >= 15
        
        mrb_jaar = bereken_mrb_2026(auto['gewicht'], auto['brandstoffen'], prov)
        idx_bijt = bepaal_bijtelling_index(int(auto['toelating'][:4]), any("elektriciteit" in b for b in auto['brandstoffen']), is_young)
        
        st.success(f"**{auto['merk']} {auto['handelsbenaming']}** | {leeftijd_exact.years} jaar oud")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            aanschaf = st.number_input("Aanschafwaarde (€)", value=int(auto['catalogusprijs']))
            gekozen_bijt = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES, index=idx_bijt)
            z_km = st.number_input("Zakelijke km / jaar", value=25000)
            p_km = st.number_input("Privé km / jaar", value=5000)
            totaal_km = z_km + p_km
        with col2:
            st.markdown("**Verbruik & Brandstof**")
            verbruik = st.number_input("Verbruik (L of kWh/100km)", value=float(auto['rdw_verbruik']))
            prijs = st.number_input("Prijs per eenheid (€)", value=1.95)
            brandstofkosten = (totaal_km / 100) * verbruik * prijs
        with col3:
            st.markdown("**Vaste & Variabele Kosten**")
            mrb = st.number_input("Wegenbelasting (€ / jaar)", value=int(mrb_jaar))
            onderhoud = st.number_input("Onderhoud (€ / jaar)", value=600)
            verzekering = st.number_input("Verzekering (€ / jaar)", value=800)
            overige = st.number_input("Overige kosten (€ / jaar)", value=500)
            lease = st.number_input("Lease/Rente (€ / jaar)", value=0)

        afschr = (aanschaf * 0.80) * 0.20
        totale_k = brandstofkosten + mrb + onderhoud + verzekering + overige + afschr + lease
        
        # Bijtelling berekening
        bijt_perc = float(gekozen_bijt.split("%")[0]) / 100
        if "Youngtimer" in gekozen_bijt: bijt_bedrag = aanschaf * 0.35
        elif "€" in gekozen_bijt:
            cap = float(gekozen_bijt.split("€ ")[1].split(",")[0].replace(".", ""))
            bijt_bedrag = (min(auto['catalogusprijs'], cap) * bijt_perc) + (max(0, auto['catalogusprijs'] - cap) * 0.22)
        else: bijt_bedrag = auto['catalogusprijs'] * bijt_perc

        aftrek_zak = totale_k - bijt_bedrag
        aftrek_pri = z_km * 0.23
        advies = "Zakelijk voordeliger" if aftrek_zak > aftrek_pri else "Privé voordeliger"

        st.markdown("---")
        res1, res2 = st.columns(2)
        with res1:
            st.markdown("#### 🏢 Auto Zakelijk")
            st.info(f"Fiscale aftrekpost: **€ {fmt(aftrek_zak)}**")
        with res2:
            st.markdown("#### 🏠 Auto Privé")
            st.info(f"Fiscale aftrekpost: **€ {fmt(aftrek_pri)}**")

        if gevalideerd:
            def clean(t): return str(t).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')
            
            class VVAAPDF(FPDF):
                def header(self):
                    self.set_fill_color(232, 78, 15); self.rect(0, 0, 210, 15, 'F')
                    if os.path.exists("vvaa_logo.jpg"): self.image("vvaa_logo.jpg", 10, 20, 35)
                    self.set_xy(10, 32); self.set_font("Arial", 'I', 10); self.cell(0, 10, "In het hart van de gezondheidszorg.", ln=True)
                def footer(self):
                    self.set_y(-15); self.set_fill_color(0, 49, 92); self.rect(0, 282, 210, 15, 'F')
                    self.set_text_color(255); self.set_font("Arial", '', 9); self.cell(0, 15, "VvAA | www.vvaa.nl | Voor zorgverleners, door zorgverleners", align='C', ln=True)

            pdf = VVAAPDF(); pdf.set_auto_page_break(auto=False); pdf.add_page()
            
            # Titel
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 49, 92)
            pdf.set_xy(10, 45); pdf.cell(0, 10, "Autoberekening: Zakelijk of Prive?", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(3)

            # Sectie 1: Relatiegegevens
            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(200, 6, "1. Relatiegegevens", ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
            pdf.cell(35, 5, "Naam relatie:"); pdf.cell(70, 5, clean(klant_naam))
            pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Relatienummer:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)

            # Sectie 2: Voertuigspecificaties
            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(200, 6, "2. Voertuigspecificaties", ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), fill=True, ln=True)
            pdf.cell(35, 6, " Eerste toelating:", fill=True); pdf.cell(155, 6, f"{auto['toelating']} ({leeftijd_exact.years} jaar, {leeftijd_exact.months} mnd)", fill=True, ln=True)
            pdf.cell(35, 6, " Verbruik:", fill=True); pdf.cell(155, 6, f"{auto['rdw_verbruik']} L/100km (RDW)", fill=True, ln=True); pdf.ln(2)
            
            pdf.cell(45, 5, "Cataloguswaarde:"); pdf.cell(45, 5, f"EUR {fmt(auto['catalogusprijs'])}", align='R')
            pdf.cell(10, 5); pdf.cell(45, 5, "Aanschafwaarde:"); pdf.cell(45, 5, f"EUR {fmt(aanschaf)}", align='R', ln=True)
            pdf.cell(45, 5, "Bijtellingsprofiel:"); pdf.set_font("Arial", 'I', 9); pdf.cell(145, 5, clean(gekozen_bijt), ln=True); pdf.ln(3)

            # Sectie 3: Financiële vergelijking
            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0); pdf.ln(2)
            
            row_data = [
                ("Brandstof/Laad:", fmt(brandstofkosten), "Vergoeding:", f"EUR {fmt(aftrek_pri)}"),
                ("Wegenbelasting:", fmt(mrb), "Zakelijke km:", fmt(z_km)),
                ("Onderhoud:", fmt(onderhoud), "Vergoeding p/km:", "EUR 0,23"),
                ("Verzekering:", fmt(verzekering), "", ""),
                ("Afschrijving:", fmt(afschr), "", ""),
                ("Lease/Rente:", fmt(lease), "", "")
            ]
            for l1, v1, l2, v2 in row_data:
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5)
                pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)

            pdf.ln(2); pdf.set_font("Arial", 'B', 10)
            pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, f"EUR {fmt(totale_k)}", align='R', ln=True)
            pdf.cell(45, 6, "Bijtelling:"); pdf.cell(45, 6, f"EUR {fmt(bijt_bedrag)}", align='R', ln=True); pdf.ln(2)
            
            pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(aftrek_zak)} ", fill=True, align='R')
            pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(aftrek_pri)} ", fill=True, align='R', ln=True); pdf.ln(5)
            
            # Sectie 4: Advies & Aandachtspunten
            pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 11)
            pdf.cell(190, 10, clean(f"  Advies vanuit fiscaal oogpunt: {advies}"), fill=True, ln=True); pdf.ln(4)
            
            pdf.set_text_color(0, 49, 92); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Aandachtspunten bij zakelijk rijden:", ln=True)
            pdf.set_font("Arial", '', 8); pdf.set_text_color(0)
            punten = [
                "- Verschillende kostenposten zijn gebaseerd op een schatting. MRB tarieven per 1 jan 2026.",
                "- Houd rekening met het eventuele vervallen van rente op de lening.",
                "- Na 5 jaar vervallen de afschrijvingskosten.",
                "- Bij inruil kan een boekwinst ontstaan, welke belast kan zijn in de onderneming.",
                "- Percentage bijtelling geldt voor 60 maanden vanaf datum eerste toelating."
            ]
            for p in punten: pdf.cell(0, 4, clean(p), ln=True)

            st.download_button("📄 Download Definitief Rapport (VvAA PDF)", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_Advies_{kenteken_input}.pdf")
