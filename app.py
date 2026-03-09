import streamlit as st
import requests
import datetime
import os
import pandas as pd
import math
import re
from fpdf import FPDF
from dateutil.relativedelta import relativedelta

# --- 1. VvAA HUISSTIJL & CONFIGURATIE ---
VVAA_ORANJE = "#E84E0F"
VVAA_BLAUW = "#00315C"
VVAA_GRIJS_BG = "#F0F2F5"  # Iets grijzere achtergrond voor meer contrast met witte kaarten
VVAA_BORDER = "#CBD5E1"

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = f"""
<style>
    /* Algemene App Styling */
    .stApp {{ background-color: {VVAA_GRIJS_BG} !important; }}
    .stApp, p, label, span, div, li {{ color: {VVAA_BLAUW} !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important; }}
    
    /* Compacte Headers */
    h1 {{ font-size: 1.8rem !important; color: {VVAA_BLAUW} !important; font-weight: 800 !important; margin-bottom: 0.2rem !important; }}
    h3 {{ font-size: 1.1rem !important; color: {VVAA_ORANJE} !important; font-weight: 700 !important; margin-bottom: 0.5rem !important; margin-top: 0.5rem !important; }}
    h4 {{ font-size: 0.9rem !important; color: {VVAA_BLAUW} !important; font-weight: 700 !important; margin-bottom: 0.3rem !important; text-transform: uppercase; letter-spacing: 0.5px; }}

    /* Modern Card Design (Compact) */
    div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stVerticalBlockBorderWrapper"]) {{
        background-color: #FFFFFF !important;
        border: 1px solid {VVAA_BORDER} !important;
        border-radius: 8px !important;
        padding: 1.2rem !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04) !important;
        margin-bottom: 1rem !important;
    }}

    /* Compacte Inputs */
    .stNumberInput, .stTextInput, .stSelectbox {{ margin-bottom: -10px !important; }}
    input, select, div[data-baseweb="select"] > div {{ 
        border: 1px solid #A0AEC0 !important; 
        border-radius: 6px !important;
        height: 38px !important;
    }}

    /* Resultaat Metrics */
    div[data-testid="metric-container"] {{
        background-color: #F8FAFC !important;
        border: 1px solid {VVAA_BLAUW} !important;
        border-left: 5px solid {VVAA_ORANJE} !important;
        border-radius: 6px !important;
        padding: 10px 15px !important;
    }}
    div[data-testid="stMetricValue"] {{ font-size: 1.6rem !important; font-weight: 800 !important; color: {VVAA_BLAUW} !important; }}

    /* Knoppen (Strakker) */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; color: white !important; 
        font-weight: bold !important; border-radius: 6px !important; border: none !important;
        padding: 0.5rem 1rem !important; transition: 0.2s;
    }}
    .stButton>button:hover {{ background-color: {VVAA_BLAUW} !important; transform: translateY(-1px); }}
    
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; color: white !important;
        border-radius: 6px !important; padding: 1rem !important; font-weight: bold !important;
    }}

    /* Info meldingen compacter */
    div[data-testid="stAlert"] {{ padding: 0.5rem 1rem !important; border-radius: 6px !important; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

def fmt(val):
    return f"{int(round(val)):,}".replace(",", ".")

# --- 2. LIVE BRANDSTOF PRIJZEN SCRAPER ---
@st.cache_data(ttl=86400) 
def haal_actuele_brandstofprijzen():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get("https://www.unitedconsumers.com/tanken", headers=headers, timeout=5)
        e95_match = re.search(r'Euro95 \(E10\).*?€\s*(\d{1},\d{3})', res.text, re.DOTALL)
        diesel_match = re.search(r'Diesel.*?€\s*(\d{1},\d{3})', res.text, re.DOTALL)
        lpg_match = re.search(r'LPG.*?€\s*(\d{1},\d{3})', res.text, re.DOTALL)
        return {
            "benzine": float(e95_match.group(1).replace(',', '.')) if e95_match else 2.05,
            "diesel": float(diesel_match.group(1).replace(',', '.')) if diesel_match else 1.85,
            "lpg": float(lpg_match.group(1).replace(',', '.')) if lpg_match else 0.85
        }
    except:
        return {"benzine": 2.05, "diesel": 1.85, "lpg": 0.85}

# --- 3. DATA LADEN ---
@st.cache_data
def load_mrb_data():
    try:
        return pd.read_csv("mrb_tarieven_2026.csv"), pd.read_csv("mrb_provincies_2026.csv")
    except:
        return None, None

df_mrb, df_prov = load_mrb_data()

# --- 4. COMPACTE HEADER ---
head_left, head_right = st.columns([1, 5])
with head_left:
    logo_path = "VvAA-logo-RGB.png" if os.path.exists("VvAA-logo-RGB.png") else "vvaa_logo.jpg"
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)
with head_right:
    st.markdown(f"<h1>Autoberekening: Zakelijk of Privé?</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='margin:0; font-size: 0.9rem; color: {VVAA_ORANJE}; font-weight: 600;'>In het hart van de gezondheidszorg.</p>", unsafe_allow_html=True)
st.markdown(f"<div style='height: 3px; background: {VVAA_ORANJE}; border-radius: 2px; margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# --- 5. RDW API FUNCTIE ---
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
        rdw_verbruik_liter = 0.0  
        if req_brandstof:
            for b in req_brandstof:
                omschrijving = b.get("brandstof_omschrijving", "").lower()
                brandstoffen.append(omschrijving)
                if omschrijving in ["benzine", "diesel", "lpg"]:
                    verbruik = b.get("brandstofverbruik_gecombineerd")
                    if verbruik: rdw_verbruik_liter = float(verbruik)
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": data.get("datum_eerste_toelating_dt", "2020-01-01")[:10],
            "brandstoffen": brandstoffen,
            "rdw_verbruik": rdw_verbruik_liter
        }
    except: return None

def bereken_mrb_csv(gewicht, brandstoffen, provincie_naam):
    if df_mrb is None or df_prov is None: return 0
    trede = df_mrb[df_mrb['min_massa'] <= gewicht].iloc[-1]
    basis_kwartaal = trede['basis_3mnd']
    extra = 0
    if trede['toeslag_per_100kg'] > 0:
        eenheden = math.ceil((gewicht - trede['drempel']) / 100)
        extra = eenheden * trede['toeslag_per_100kg']
    basis_totaal = basis_kwartaal + extra
    opcenten = df_prov[df_prov['provincie'] == provincie_naam]['opcenten'].values[0]
    mrb_3mnd = basis_totaal + (basis_totaal * (opcenten / 100))
    toeslag = 0
    if any("diesel" in b for b in brandstoffen): toeslag = 153.00 + (math.ceil(max(0, gewicht-900)/100) * 16.57)
    elif any("lpg" in b for b in brandstoffen): toeslag = 172.08 + (math.ceil(max(0, gewicht-900)/100) * 18.22)
    jaarbedrag = (mrb_3mnd + toeslag) * 4
    if any("elektriciteit" in b for b in brandstoffen) and not any(x in ["benzine", "diesel", "lpg"] for x in brandstoffen):
        jaarbedrag *= 0.75
    return round(jaarbedrag)

BIJTELLING_OPTIES = [
    "22% over Cataloguswaarde (Standaard of Hybride)", "35% over Aanschafwaarde (Youngtimer)",
    "4% tot € 50.000, 22% daarboven (EV 2019)", "8% tot € 45.000, 22% daarboven (EV 2020)",
    "12% tot € 40.000, 22% daarboven (EV 2021)", "16% tot € 35.000, 22% daarboven (EV 2022)",
    "16% tot € 30.000, 22% daarboven (EV 2023/2024)", "17% tot € 30.000, 22% daarboven (EV 2025/2026)"
]

def bepaal_bijtelling_index(peil_jaar, is_full_ev, is_youngtimer):
    if is_youngtimer: return 1
    if not is_full_ev: return 0
    if peil_jaar <= 2019: return 2
    elif peil_jaar == 2020: return 3
    elif peil_jaar == 2021: return 4
    elif peil_jaar == 2022: return 5
    elif peil_jaar in [2023, 2024]: return 6
    else: return 7

# --- 6. INTERFACE SECTIES ---

# 1. Relatie & Kenteken (Compacte Row)
with st.container(border=True):
    st.markdown("### 👤 1. Relatie & Voertuig")
    r1, r2, r3, r4, r5 = st.columns([2, 1.5, 1.5, 2, 1])
    with r1: klant_naam = st.text_input("Naam relatie *")
    with r2: klant_nummer = st.text_input("Relatienummer *")
    with r3: kenteken_input = st.text_input("Kenteken *")
    with r4: 
        prov_lijst = df_prov['provincie'].tolist() if df_prov is not None else ["Gelderland"]
        prov = st.selectbox("Provincie", prov_lijst)
    with r5: bereken_knop = st.button("Laden", use_container_width=True)

is_valid_nummer = klant_nummer.isdigit()
gevalideerd = bool(klant_naam) and is_valid_nummer

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if auto:
        toel_dt = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        toelating_nl = toel_dt.strftime("%d-%m-%Y")
        vandaag = datetime.datetime.now()
        leeftijd = relativedelta(vandaag, toel_dt)
        is_young_auto = leeftijd.years >= 15
        is_ev = any("elektriciteit" in b for b in auto['brandstoffen'])
        is_brandstof = any(b in ["benzine", "diesel", "lpg", "alcohol"] for b in auto['brandstoffen'])
        is_full_ev = is_ev and not is_brandstof
        brandstof_t = ", ".join(auto['brandstoffen']).title()
        
        if is_full_ev:
            start_mnd = toel_dt.month + 1
            start_jr = toel_dt.year
            if start_mnd > 12: start_mnd = 1; start_jr += 1
            start_60mnd_dt = datetime.datetime(start_jr, start_mnd, 1)
            eind_60mnd_dt = start_60mnd_dt + relativedelta(months=60)
            is_vervallen_ev = vandaag >= eind_60mnd_dt
            peil_jaar = eind_60mnd_dt.year if is_vervallen_ev else toel_dt.year
        else:
            is_vervallen_ev = False; peil_jaar = toel_dt.year
        
        st.success(f"🚙 **{auto['merk']} {auto['handelsbenaming']}** ({kenteken_input.upper()}) | Toelating: {toelating_nl} ({leeftijd.years}j, {leeftijd.months}m)")
        
        # 2. Gebruik & Parameters (Grid Layout)
        with st.container(border=True):
            st.markdown("### ⚙️ 2. Gebruik & Parameters")
            g1, g2, g3 = st.columns(3)
            
            with g1:
                st.markdown("#### Kilometers")
                z_km = st.number_input("Zakelijke km / jaar", value=0, min_value=0)
                p_km = st.number_input("Privé km / jaar", value=0, min_value=0)
                totaal_km = z_km + p_km
                
            with g2:
                st.markdown("#### Fiscale Keuzes")
                is_young_manual = st.checkbox("Youngtimer regeling", value=is_young_auto)
                is_minder_dan_500 = st.checkbox("Minder dan 500 km privé?", value=False)
                is_geleased = st.checkbox("Geleased of gefinancierd?", value=False)
                
            with g3:
                st.markdown("#### Meldingen")
                if is_minder_dan_500: st.info("ℹ️ Rittenadministratie vereist.")
                if is_young_manual and not is_young_auto: st.warning("⚠️ Voertuig < 15 jaar.")
                if is_vervallen_ev and not is_young_manual: st.info(f"⚡ 60-mnd regel: Tarief {peil_jaar}.")

            st.markdown("<div style='height: 1px; background: #eee; margin: 15px 0;'></div>", unsafe_allow_html=True)
            
            # 3. Financiën (Grid Layout)
            st.markdown("### 💶 3. Financiële Specificaties")
            f1, f2, f3 = st.columns(3)
            
            with f1:
                st.markdown("#### Waarde & Bijtelling")
                st.caption(f"Catalogus: € {fmt(auto['catalogusprijs'])}")
                aanschaf = st.number_input("Aanschafwaarde / Dagwaarde (€)", value=int(auto['catalogusprijs']))
                idx_bijt = bepaal_bijtelling_index(peil_jaar, is_full_ev, is_young_manual)
                gekozen_bijt = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES, index=idx_bijt)
                
                if is_minder_dan_500: calc_bijt = 0.0
                elif is_young_manual: calc_bijt = aanschaf * 0.35
                else:
                    bijt_perc = float(gekozen_bijt.split("%")[0]) / 100
                    if "€" in gekozen_bijt:
                        cap = float(gekozen_bijt.split("€ ")[1].split(",")[0].replace(".", ""))
                        calc_bijt = (min(auto['catalogusprijs'], cap) * bijt_perc) + (max(0, auto['catalogusprijs'] - cap) * 0.22)
                    else: calc_bijt = auto['catalogusprijs'] * bijt_perc
                bijt_bruto = st.number_input("Bijtelling (€/jaar)", value=float(calc_bijt))
                
            with f2:
                st.markdown("#### Verbruik")
                brandstof_kosten, laad_kosten = 0.0, 0.0
                actuele_prijzen = haal_actuele_brandstofprijzen()
                
                if is_brandstof or (not is_brandstof and not is_ev):
                    verbruik_l = st.number_input("L/100km", value=float(auto['rdw_verbruik']))
                    bs_lower = [b.lower() for b in auto['brandstoffen']]
                    def_prijs = actuele_prijzen["diesel"] if any("diesel" in b for b in bs_lower) else (actuele_prijzen["lpg"] if any("lpg" in b for b in bs_lower) else actuele_prijzen["benzine"])
                    prijs_l = st.number_input("Prijs per Liter (€)", value=def_prijs)
                    brandstof_kosten = st.number_input("Totaal Brandstof (€)", value=float(((z_km + p_km) / 100) * verbruik_l * prijs_l))
                
                if is_ev:
                    verbruik_kwh = st.number_input("kWh/100km", value=0.0)
                    laad_kosten = st.number_input("Totaal Laden (€)", value=float(((z_km + p_km) / 100) * verbruik_kwh * 0.40))
            
            with f3:
                st.markdown("#### Vaste Kosten")
                mrb_jaar = bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)
                mrb = st.number_input("Wegenbelasting (€/jr)", value=int(mrb_jaar))
                gebruik_schatting = st.checkbox("🧮 Bereken schatting", value=False)
                onderhoud = st.number_input("Onderhoud (€/jr)", value=int(totaal_km * 0.04) if gebruik_schatting else 0)
                verzekering = st.number_input("Verzekering (€/jr)", value=0)
                overige = st.number_input("Overige (€/jr)", value=250 if gebruik_schatting else 0)
                lease_k, rente_k = 0.0, 0.0
                if is_geleased:
                    lease_k = st.number_input("Lease (Operational) (€/jr)", value=0)
                    rente_k = st.number_input("Rente (Financial) (€/jr)", value=0)

        afschr = (aanschaf * 0.8) * 0.2
        tot_k = brandstof_kosten + laad_kosten + mrb + onderhoud + verzekering + overige + afschr + lease_k + rente_k
        bijt_definitief = min(bijt_bruto, tot_k) if not is_minder_dan_500 else 0.0
        zak_aftrek, pri_aftrek = tot_k - bijt_definitief, z_km * 0.23
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        # 4. Resultaten (Metric Cards)
        with st.container(border=True):
            st.markdown("### 📊 4. Fiscale Vergelijking")
            if bijt_bruto > tot_k and not is_minder_dan_500: st.warning(f"⚖️ Bijtelling gemaximeerd op totale kosten (€ {fmt(tot_k)}).")
            st.success(f"💡 **Advies:** {advies}")
            res1, res2 = st.columns(2)
            with res1: st.metric("🏢 Zakelijke Aftrek", f"€ {fmt(zak_aftrek)}", help="Totale kosten minus bijtelling")
            with res2: st.metric("🏠 Privé Aftrek", f"€ {fmt(pri_aftrek)}", help="€ 0,23 per zakelijke km")

        if gevalideerd:
            def clean(t): return str(t).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')
            class VVAAPDF(FPDF):
                def __init__(self):
                    super().__init__()
                    if os.path.exists("vvaa_font.ttf"):
                        self.add_font("VvAA_Font", "", "vvaa_font.ttf", uni=True)
                        if os.path.exists("vvaa_font_bold.ttf"): self.add_font("VvAA_Font", "B", "vvaa_font_bold.ttf", uni=True)
                        self.font_fam = "VvAA_Font"
                    else: self.font_fam = "Arial"
                def header(self):
                    self.set_fill_color(232, 78, 15); self.rect(0, 0, 210, 15, 'F')
                    logo = "VvAA-logo-RGB.png" if os.path.exists("VvAA-logo-RGB.png") else "vvaa_logo.jpg"
                    if os.path.exists(logo): self.image(logo, 10, 20, 35)
                    self.set_xy(10, 32); self.set_font(self.font_fam, '', 10); self.cell(0, 10, "In het hart van de gezondheidszorg.", ln=True)
                def footer(self):
                    self.set_y(-15); self.set_fill_color(0, 49, 92); self.rect(0, 282, 210, 15, 'F')
                    self.set_text_color(255); self.set_font(self.font_fam, '', 9); self.cell(0, 15, "VvAA | www.vvaa.nl | Voor zorgverleners, door zorgverleners", align='C', ln=True)

            pdf = VVAAPDF(); pdf.set_auto_page_break(auto=False); pdf.add_page(); f = pdf.font_fam
            pdf.set_font(f, 'B', 16); pdf.set_text_color(0, 49, 92); pdf.set_xy(10, 45)
            pdf.cell(0, 10, clean("Autoberekening: Zakelijk of Privé?"), ln=True); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "1. Relatiegegevens", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0)
            pdf.cell(35, 5, "Naam relatie:"); pdf.cell(70, 5, clean(klant_naam)); pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Lidnummer:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "2. Voertuigspecificaties", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), fill=True, ln=True)
            pdf.cell(35, 6, " Brandstof:", fill=True); pdf.cell(155, 6, brandstof_t, fill=True, ln=True)
            pdf.cell(35, 6, " Eerste toelating:", fill=True); pdf.cell(155, 6, f"{toelating_nl} ({leeftijd.years} jaar, {leeftijd.months} mnd)", fill=True, ln=True); pdf.ln(3)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True); pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.ln(2)
            left = []
            if is_brandstof or not is_ev: left.append(("Brandstofkosten:", f"EUR {fmt(brandstof_kosten)}"))
            if is_ev: left.append(("Laadkosten:", f"EUR {fmt(laad_kosten)}"))
            left.extend([("Wegenbelasting:", f"EUR {fmt(mrb)}"), ("Onderhoud:", f"EUR {fmt(onderhoud)}"), ("Verzekering:", f"EUR {fmt(verzekering)}"), ("Overig/Afschr:", f"EUR {fmt(overige+afschr)}")])
            if is_geleased: left.extend([("Lease/Rente:", f"EUR {fmt(lease_k+rente_k)}")])
            right = [("Fiscale vergoeding:", f"EUR {fmt(pri_aftrek)}"), ("Zakelijke km:", fmt(z_km)), ("Privé km:", fmt(p_km)), ("Tarief p/km:", "EUR 0,23")]
            for i in range(max(len(left), len(right))):
                l1, v1 = left[i] if i < len(left) else ("", "")
                l2, v2 = right[i] if i < len(right) else ("", "")
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5); pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)
            pdf.ln(2); pdf.set_font(f, 'B', 10); pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, f"EUR {fmt(tot_k)}", align='R', ln=True)
            pdf.cell(45, 6, "Bijtelling:"); pdf.cell(45, 6, f"- EUR {fmt(bijt_definitief)}", align='R', ln=True); pdf.ln(2); pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(zak_aftrek)} ", fill=True, align='R'); pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(pri_aftrek)} ", fill=True, align='R', ln=True); pdf.ln(5)
            pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255); pdf.set_font(f, 'B', 11); pdf.cell(190, 10, clean(f"  Advies vanuit fiscaal oogpunt: {advies}"), fill=True, ln=True); pdf.ln(4)
            pdf.set_text_color(0, 49, 92); pdf.set_font(f, 'B', 10); pdf.cell(0, 5, "Aandachtspunten:", ln=True); pdf.set_font(f, '', 8); pdf.set_text_color(0)
            pnt = ["- De getoonde berekening is een schatting op basis van uw eigen opgave.", "- Wegenbelasting is gebaseerd op Belastingdienst tarieven 2026.", "- Bij inruil kan een boekwinst ontstaan."]
            if is_minder_dan_500: pnt.insert(0, "- Voor 0% bijtelling is een sluitende rittenadministratie vereist.")
            for p in pnt: pdf.cell(0, 4, clean(p), ln=True)
            st.download_button("📄 Autoberekening Downloaden", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}.pdf")
        else: st.info("ℹ️ Vul de Naam en een numeriek Lidnummer in om het rapport te kunnen genereren.")
    else: st.error("❌ Kenteken niet gevonden.")
