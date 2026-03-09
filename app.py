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
VVAA_GRIJS_LICHT = "#F0F2F5" # Subtiel grijze achtergrond

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = f"""
<style>
    /* Algemene scaling: alles iets kleiner voor meer overzicht */
    html, body, [class*="st-"] {{
        font-size: 0.95rem;
    }}

    /* Achtergrond en main padding */
    .stApp {{ 
        background-color: {VVAA_GRIJS_LICHT} !important; 
    }}
    .main .block-container {{
        padding-top: 2rem !important;
        max-width: 1200px;
    }}

    /* Tekst kleuren */
    p, label, span, div[data-testid="stMarkdownContainer"] > p, li {{ 
        color: {VVAA_BLAUW} !important; 
    }}
    
    h1 {{ font-size: 1.8rem !important; color: {VVAA_BLAUW} !important; margin-bottom: 0 !important; }}
    h2 {{ font-size: 1.5rem !important; color: {VVAA_BLAUW} !important; }}
    h3 {{ font-size: 1.2rem !important; color: {VVAA_ORANJE} !important; margin-top: 0 !important; }}
    h4 {{ font-size: 1rem !important; color: {VVAA_BLAUW} !important; }}

    /* Modern Card Design: compacter en strakker */
    div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stVerticalBlockBorderWrapper"]) {{
        background-color: #FFFFFF !important;
        border: 1px solid #DDE2E7 !important;
        border-radius: 8px !important;
        padding: 1.2rem !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04) !important;
        margin-bottom: 1rem !important;
    }}

    /* Input velden: strakker en minder hoog */
    .stNumberInput input, .stTextInput input, .stSelectbox div[data-baseweb="select"] {{
        border: 1px solid #B0B8C1 !important;
        border-radius: 4px !important;
        height: 2.2rem !important;
    }}

    /* Metric Cards: compacter resultaat */
    div[data-testid="metric-container"] {{
        background-color: #FFFFFF !important;
        border: 1px solid #DDE2E7 !important;
        border-left: 5px solid {VVAA_ORANJE} !important;
        padding: 10px 15px !important;
        border-radius: 6px !important;
    }}
    div[data-testid="stMetricValue"] {{ 
        font-size: 1.6rem !important; 
        color: {VVAA_BLAUW} !important;
    }}

    /* Knoppen: modern en vloeiend */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; 
        color: white !important; 
        font-weight: 600 !important; 
        border-radius: 4px !important; 
        border: none !important;
        height: 2.5rem !important;
        transition: all 0.2s ease-in-out !important;
    }}
    .stButton>button:hover {{ 
        background-color: {VVAA_BLAUW} !important; 
        transform: translateY(-1px);
    }}
    
    /* Download Knop */
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; 
        color: white !important;
        height: 3rem !important;
    }}
    div.stDownloadButton > button:hover {{ 
        background-color: #002244 !important;
    }}

    /* Expander styling */
    div[data-testid="stExpander"] {{ 
        background-color: #F8FAFC !important; 
        border: 1px solid #DDE2E7 !important; 
        border-radius: 4px !important; 
    }}

    /* Horizontale lijn */
    hr {{ margin: 1rem 0 !important; border: 0; border-top: 1px solid #DDE2E7; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

def fmt(val):
    return f"{int(round(val)):,}".replace(",", ".")

# --- 2. LIVE BRANDSTOF PRIJZEN SCRAPER (LOGICA ONGEWIJZIGD) ---
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

# --- 3. DATA LADEN (LOGICA ONGEWIJZIGD) ---
@st.cache_data
def load_mrb_data():
    try:
        return pd.read_csv("mrb_tarieven_2026.csv"), pd.read_csv("mrb_provincies_2026.csv")
    except:
        return None, None

df_mrb, df_prov = load_mrb_data()

# --- 4. HEADER (COMPACTER ONTWERP) ---
head_col1, head_col2 = st.columns([1, 5])
with head_col1:
    logo_path = "VvAA-logo-RGB.png" if os.path.exists("VvAA-logo-RGB.png") else "vvaa_logo.jpg"
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)
with head_col2:
    st.markdown("<h1>Autoberekening: Zakelijk of Privé?</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0; font-style: italic; opacity: 0.8;'>In het hart van de gezondheidszorg.</p>", unsafe_allow_html=True)
st.markdown("<hr style='border-top: 3px solid #E84E0F; margin-bottom:20px;'>", unsafe_allow_html=True)

# --- 5. RDW API FUNCTIE (LOGICA ONGEWIJZIGD) ---
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

# --- 6. INTERFACE / CARDS ---

with st.container(border=True):
    st.markdown("### 👤 1. Relatiegegevens")
    colA, colB = st.columns(2)
    with colA: klant_naam = st.text_input("Naam relatie *")
    with colB: klant_nummer = st.text_input("Relatienummer (alleen cijfers) *")

    colC, colD, colE = st.columns([2, 2, 1])
    with colC: kenteken_input = st.text_input("Kenteken *")
    with colD: 
        prov_lijst = df_prov['provincie'].tolist() if df_prov is not None else ["Gelderland"]
        prov = st.selectbox("Provincie", prov_lijst)
    with colE: bereken_knop = st.button("Laden / Berekenen")

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
            is_vervallen_ev = False
            peil_jaar = toel_dt.year
        
        st.success(f"🚙 **{auto['merk']} ({kenteken_input.upper()}) - {auto['handelsbenaming']}** | {brandstof_t} | Toelating: {toelating_nl} ({leeftijd.years}j, {leeftijd.months}m)")
        
        with st.container(border=True):
            st.markdown("### ⚙️ 2. Gebruik & Uitgangspunten")
            top1, top2, top3 = st.columns(3)
            with top1:
                st.markdown("#### Kilometers per jaar")
                z_km = st.number_input("Zakelijke km / jaar", value=0, min_value=0)
                p_km = st.number_input("Privé km / jaar", value=0, min_value=0)
                totaal_km = z_km + p_km
            with top2:
                st.markdown("#### Fiscale Keuzes")
                is_young_manual = st.checkbox("Youngtimer regeling toepassen?", value=is_young_auto)
                is_minder_dan_500 = st.checkbox("Minder dan 500 km privé per jaar?", value=False)
                is_geleased = st.checkbox("Wordt de auto geleased of gefinancierd?", value=False)
            with top3:
                st.markdown("#### Meldingen")
                if is_minder_dan_500: st.info("ℹ️ **Geen bijtelling:** Zorg voor een sluitende rittenadministratie.")
                if is_young_manual and not is_young_auto: st.warning(f"⚠️ **Pas op:** Voertuig is pas {leeftijd.years} jaar oud.")
                if is_vervallen_ev and not is_young_manual: st.info(f"⚡ **Let op:** 60-maandenregel EV vervallen. Regels {peil_jaar} toegepast.")

            st.markdown("---")
            st.markdown("### 💶 Financiële Specificaties")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("#### Waarde & Bijtelling")
                st.write(f"Cataloguswaarde: **€ {fmt(auto['catalogusprijs'])}**")
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
                bijt_bruto = st.number_input("Bijtelling (€/jaar) - overschrijfbaar", value=float(calc_bijt))
                
            with col2:
                st.markdown("#### Verbruik & Brandstof")
                brandstof_kosten, laad_kosten = 0.0, 0.0
                actuele_prijzen = haal_actuele_brandstofprijzen()
                if is_brandstof or (not is_brandstof and not is_ev):
                    verbruik_l = st.number_input("Verbruik (L/100km)", value=float(auto['rdw_verbruik']))
                    bs_lower = [b.lower() for b in auto['brandstoffen']]
                    def_prijs = actuele_prijzen["diesel"] if any("diesel" in b for b in bs_lower) else (actuele_prijzen["lpg"] if any("lpg" in b for b in bs_lower) else actuele_prijzen["benzine"])
                    prijs_l = st.number_input("Prijs per Liter (€)", value=def_prijs)
                    brandstof_kosten = st.number_input("Brandstofkosten p/j (€)", value=float(((z_km + p_km) / 100) * verbruik_l * prijs_l))
                if is_ev:
                    verbruik_kwh = st.number_input("Verbruik Stroom (kWh/100km)", value=0.0)
                    laad_kosten = st.number_input("Laadkosten p/j (€)", value=float(((z_km + p_km) / 100) * verbruik_kwh * 0.40))
                
            with col3:
                st.markdown("#### Vaste Kosten")
                mrb = st.number_input("Wegenbelasting (€ / jaar)", value=int(bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)))
                gebruik_schatting = st.checkbox("🧮 Bereken schatting")
                if gebruik_schatting:
                    with st.expander("ℹ️ Uitleg schatting"):
                        st.write("- Onderhoud: € 0,04 per km.\n- Verzekering: Zelf invullen.\n- Overig: € 250,- p/j.")
                onderhoud = st.number_input("Onderhoud (€ / jaar)", value=int(totaal_km * 0.04) if gebruik_schatting else 0)
                verzekering = st.number_input("Verzekering (€ / jaar)", value=0)
                overige = st.number_input("Overige kosten (€ / jaar)", value=250 if gebruik_schatting else 0)
                lease_kosten, rente_kosten = 0.0, 0.0
                if is_geleased:
                    st.markdown("#### Financiering")
                    lease_kosten = st.number_input("Leasekosten (€/j)", value=0)
                    rente_kosten = st.number_input("Rentekosten (€/j)", value=0)

        afschr = (aanschaf * 0.8) * 0.2
        tot_k = brandstof_kosten + laad_kosten + mrb + onderhoud + verzekering + overige + afschr + lease_kosten + rente_kosten
        bijt_definitief = min(bijt_bruto, tot_k) if not is_minder_dan_500 else 0.0
        zak_aftrek, pri_aftrek = tot_k - bijt_definitief, z_km * 0.23
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        with st.container(border=True):
            st.markdown("### 📊 3. Resultaat & Fiscaal Advies")
            if bijt_bruto > tot_k and not is_minder_dan_500: st.warning(f"⚖️ Bijtelling gemaximeerd op totale kosten (€ {fmt(tot_k)}).")
            st.success(f"💡 **Conclusie:** Vanuit fiscaal oogpunt is de optie **{advies}**.")
            r1, r2 = st.columns(2)
            with r1:
                st.write(f"Totale kosten p/j: **€ {fmt(tot_k)}** | Bijtelling: **- € {fmt(bijt_definitief)}**")
                st.metric("Fiscale Aftrekpost (Zakelijk)", f"€ {fmt(zak_aftrek)}")
            with r2:
                st.write(f"Zakelijke km: **{fmt(z_km)}** á **€ 0,23**")
                st.write("<br>", unsafe_allow_html=True)
                st.metric("Fiscale Aftrekpost (Privé)", f"€ {fmt(pri_aftrek)}")

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
            pdf.cell(35, 5, "Relatie:"); pdf.cell(70, 5, clean(klant_naam)); pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Lidnummer:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "2. Voertuigspecificaties", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), fill=True, ln=True)
            pdf.cell(35, 6, " Toelating:", fill=True); pdf.cell(155, 6, f"{toelating_nl} ({leeftijd.years} jaar, {leeftijd.months} mnd)", fill=True, ln=True); pdf.ln(3)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True); pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.ln(2)
            left = []
            if is_brandstof or not is_ev: left.append(("Brandstofkosten:", f"EUR {fmt(brandstof_kosten)}"))
            if is_ev: left.append(("Laadkosten:", f"EUR {fmt(laad_kosten)}"))
            left.extend([("Wegenbelasting:", f"EUR {fmt(mrb)}"), ("Onderhoud:", f"EUR {fmt(onderhoud)}"), ("Verzekering:", f"EUR {fmt(verzekering)}"), ("Overig/Afschr:", f"EUR {fmt(overige+afschr)}")])
            if is_geleased: left.append(("Lease/Rente:", f"EUR {fmt(lease_kosten+rente_kosten)}"))
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
            pnt = ["- De getoonde berekening is een schatting op basis van uw eigen opgave.", "- Wegenbelasting is gebaseerd op Belastingdienst tarieven 2026.", "- Percentage bijtelling geldt voor 60 maanden."]
            if is_minder_dan_500: pnt.insert(0, "- Voor 0% bijtelling is een sluitende rittenadministratie vereist.")
            for p in pnt: pdf.cell(0, 4, clean(p), ln=True)
            st.download_button("📄 Autoberekening Downloaden", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}.pdf")
        else: st.info("ℹ️ Vul de Naam en een numeriek Lidnummer in om het rapport te kunnen genereren.")
    else: st.error("❌ Kenteken niet gevonden.")
