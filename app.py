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
        rdw_verbruik_liter = 6.0 
        
        if req_brandstof:
            for b in req_brandstof:
                omschrijving = b.get("brandstof_omschrijving", "").lower()
                if omschrijving in ["benzine", "diesel", "lpg"]:
                    verbruik = b.get("brandstofverbruik_gecombineerd")
                    if verbruik: rdw_verbruik_liter = float(verbruik)
        
        eerste_toelating = data.get("datum_eerste_toelating_dt", "2020-01-01")[:10]
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": eerste_toelating,
            "bouwjaar": int(eerste_toelating[:4]),
            "brandstoffen": brandstoffen,
            "rdw_verbruik_liter": rdw_verbruik_liter
        }
    except:
        return None

# VERFIJNDE WEGENBELASTING FORMULE (Kalibratie op Kia Rio 1.000kg = €122/kw)
def schat_mrb(gewicht, brandstoffen, provincie):
    # Basis voor 1000kg is ongeveer 460 per jaar. We gebruiken een factor per kg boven de 500kg.
    basis_jaar = max(160, (gewicht - 500) * 0.65 + 140)
    
    # Provincie correctie (Utrecht is vaak 'basis', Gelderland/Zuid-Holland duurder)
    prov_factors = {"Noord-Holland": 0.96, "Zuid-Holland": 1.08, "Gelderland": 1.05, "Utrecht": 1.00, "Groningen": 1.06, "Friesland": 1.04, "Drenthe": 1.06}
    factor = prov_factors.get(provincie, 1.03)
    
    is_ev = any("elektriciteit" in b for b in brandstoffen)
    is_diesel = any("diesel" in b for b in brandstoffen)
    
    if is_ev: return (basis_jaar * factor) * 0.25 # 2025 korting
    if is_diesel: return (basis_jaar * factor) * 2.15 # Diesel toeslag
    return basis_jaar * factor

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

# --- 3. INPUT & VALIDATIE ---
st.subheader("1. Klant & Voertuig Gegevens")
colA, colB = st.columns(2)
with colA: klant_naam = st.text_input("Naam relatie *")
with colB: klant_nummer = st.text_input("Relatienummer (cijfers) *")

colC, colD, colE = st.columns([2, 2, 1])
with colC: kenteken_input = st.text_input("Kenteken *")
with colD: provincie = st.selectbox("Provincie", ["Gelderland", "Noord-Holland", "Zuid-Holland", "Utrecht", "Noord-Brabant", "Overijssel", "Flevoland", "Groningen", "Friesland", "Drenthe", "Zeeland", "Limburg"])
with colE: bereken_knop = st.button("Berekenen")

gevalideerd = bool(klant_naam) and klant_nummer.isdigit()

st.markdown("---")

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if not auto:
        st.error("Kenteken niet gevonden.")
    else:
        toelating_date = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        leeftijd_exact = relativedelta(datetime.datetime.now(), toelating_date)
        is_youngtimer_auto = leeftijd_exact.years >= 15
        
        berekende_mrb = schat_mrb(auto['gewicht'], auto['brandstoffen'], provincie)
        idx_bijt = bepaal_bijtelling_index(auto['bouwjaar'], any("elektriciteit" in b for b in auto['brandstoffen']), is_youngtimer_auto)
        
        st.success(f"{auto['merk']} {auto['handelsbenaming']} | {leeftijd_exact.years} jaar oud")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            aanschaf = st.number_input("Aanschafwaarde (€)", value=int(auto['catalogusprijs']))
            gekozen_bijt = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES, index=idx_bijt)
            z_km = st.number_input("Zakelijke km / jaar", value=15000)
            p_km = st.number_input("Privé km / jaar", value=5000)
            totaal_km = z_km + p_km
        with col2:
            st.markdown("**Verbruik & Brandstof**")
            verbruik = st.number_input("Verbruik (L of kWh/100km)", value=float(auto['rdw_verbruik_liter']))
            prijs = st.number_input("Prijs per eenheid (€)", value=1.95)
            brandstofkosten = (totaal_km / 100) * verbruik * prijs
        with col3:
            st.markdown("**Vaste & Variabele Kosten**")
            mrb = st.number_input("Wegenbelasting (€ / jaar)", value=int(berekende_mrb))
            onderhoud = st.number_input("Onderhoud (€ / jaar)", value=600)
            verzekering = st.number_input("Verzekering (€ / jaar)", value=800)
            overige = st.number_input("Overige kosten (€ / jaar)", value=500)
            lease = st.number_input("Lease/Rente (€ / jaar)", value=0)

        # Berekeningen
        afschr = (aanschaf * 0.80) * 0.20
        totale_k = brandstofkosten + mrb + onderhoud + verzekering + overige + afschr + lease
        
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
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 49, 92)
            pdf.set_xy(10, 45); pdf.cell(0, 10, "Autoberekening: Zakelijk of Prive?", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)

            pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
            pdf.cell(35, 6, "Naam relatie:"); pdf.cell(70, 6, clean(klant_naam))
            pdf.cell(35, 6, "Datum:"); pdf.cell(50, 6, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 6, "Relatienummer:"); pdf.cell(70, 6, clean(klant_nummer), ln=True); pdf.ln(5)

            pdf.set_fill_color(245); pdf.cell(190, 7, clean(f" {auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), fill=True, ln=True)
            pdf.cell(95, 6, f" Cataloguswaarde: EUR {fmt(auto['catalogusprijs'])}", fill=True)
            pdf.cell(95, 6, f" Aanschafwaarde: EUR {fmt(aanschaf)}", fill=True, ln=True); pdf.ln(5)

            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0); pdf.ln(2)
            
            rows = [
                ("Brandstof/Laad:", f"EUR {fmt(brandstofkosten)}", "Vergoeding:", "EUR 0,23 / km"),
                ("Wegenbelasting:", f"EUR {fmt(mrb)}", "Zakelijke km:", fmt(z_km)),
                ("Onderhoud:", f"EUR {fmt(onderhoud)}", "", ""),
                ("Verzekering:", f"EUR {fmt(verzekering)}", "", ""),
                ("Afschrijving:", f"EUR {fmt(afschr)}", "", ""),
                ("Lease/Rente:", f"EUR {fmt(lease)}", "", "")
            ]
            for l1, v1, l2, v2 in rows:
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5)
                pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)

            pdf.ln(3); pdf.set_font("Arial", 'B', 10)
            pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, f"EUR {fmt(totale_k)}", align='R', ln=True)
            pdf.cell(45, 6, "Bijtelling:"); pdf.cell(45, 6, f"EUR {fmt(bijt_bedrag)}", align='R', ln=True)
            
            pdf.ln(3); pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(aftrek_zak)} ", fill=True, align='R')
            pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(aftrek_pri)} ", fill=True, align='R', ln=True)
            
            pdf.ln(8); pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255)
            pdf.cell(190, 10, clean(f"  Advies: {advies}"), fill=True, ln=True)
            
            pdf.ln(10); pdf.set_text_color(0, 49, 92); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Aandachtspunten:", ln=True)
            pdf.set_font("Arial", '', 8); pdf.set_text_color(0)
            pdf.multi_cell(0, 4, clean("- Bedragen zijn afgerond op hele euro's.\n- Kosten zijn gebaseerd op schattingen.\n- Bijtelling geldt voor 60 maanden vanaf datum eerste toelating."))

            st.download_button("📄 Download Definitief Rapport", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_Advies_{kenteken_input}.pdf")
