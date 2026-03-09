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
VVAA_GRIJS = "#F4F6F8" 

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = f"""
<style>
    /* Algemene scaling: alles iets kleiner voor overzicht */
    html, body, [class*="st-"] {{
        font-size: 0.92rem !important;
    }}

    .stApp {{ background-color: {VVAA_GRIJS} !important; }}
    .stApp, p, label, span, div[data-testid="stMarkdownContainer"] > p, li {{ color: {VVAA_BLAUW} !important; font-family: 'Arial', sans-serif; }}
    h1, h2, h3, h4, h5, h6 {{ color: {VVAA_ORANJE} !important; font-family: 'Arial', sans-serif !important; font-weight: bold; }}
    
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; color: white !important; 
        border-radius: 6px; border: none; padding: 10px 24px; font-weight: bold; width: 100%; margin-top: 28px;
        transition: 0.3s;
    }}
    .stButton>button:hover {{ background-color: #c7400a !important; box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
    
    /* DOWNLOADKNOP STYLING */
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; color: white !important; border-radius: 8px !important;
        padding: 15px 32px !important; font-size: 18px !important; font-weight: bold !important; width: 100% !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 2px solid {VVAA_BLAUW} !important; transition: 0.3s;
    }}
    div.stDownloadButton > button:hover {{ background-color: #001f3f !important; }}
    div.stDownloadButton > button p, div.stDownloadButton > button span {{ color: white !important; }}
    
    div[data-testid="stAlert"] {{ background-color: white !important; border-left: 5px solid {VVAA_ORANJE} !important; padding: 15px; border-radius: 6px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
    
    div[data-testid="stExpander"] {{ background-color: white !important; border-left: 4px solid {VVAA_ORANJE} !important; border-radius: 6px; }}
    .streamlit-expanderHeader {{ color: {VVAA_BLAUW} !important; font-weight: bold; }}
    
    /* DROPDOWN FIX: Altijd lichte achtergrond met blauwe tekst */
    input, select, div[data-baseweb="select"] > div {{ background-color: white !important; color: {VVAA_BLAUW} !important; border-radius: 6px !important; border: 1px solid #ddd !important; }}
    div[data-baseweb="popover"] > div, ul[role="listbox"] {{ background-color: white !important; }}
    ul[role="listbox"] li {{ color: {VVAA_BLAUW} !important; background-color: white !important; }}
    ul[role="listbox"] li:hover {{ background-color: #f0f2f6 !important; }}

    div[data-testid="metric-container"] {{
        background-color: white; border-left: 5px solid {VVAA_ORANJE}; padding: 15px 20px; border-radius: 8px; box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
    }}
    div[data-testid="metric-container"] label {{ font-size: 16px !important; font-weight: bold; color: {VVAA_BLAUW} !important; }}
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{ color: {VVAA_ORANJE} !important; font-weight: bold; }}
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

# --- 3. DATA LADEN UIT CSV ---
@st.cache_data
def load_mrb_data():
    try:
        return pd.read_csv("mrb_tarieven_2026.csv"), pd.read_csv("mrb_provincies_2026.csv")
    except:
        return None, None

df_mrb, df_prov = load_mrb_data()

# --- 4. HEADER LAYOUT ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    logo_path = "VvAA-logo-RGB.png" if os.path.exists("VvAA-logo-RGB.png") else "vvaa_logo.jpg"
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
with col_title:
    st.markdown(f"<h1 style='color: {VVAA_BLAUW}; margin-bottom: 0px; padding-bottom: 0px;'>Autoberekening: Zakelijk of Privé?</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='color: {VVAA_ORANJE}; margin-top: 5px; font-weight: normal;'>In het hart van de gezondheidszorg.</h4>", unsafe_allow_html=True)
st.markdown(f"<hr style='border: 2px solid {VVAA_ORANJE}; border-radius: 5px; margin-top: 10px; margin-bottom: 30px;'>", unsafe_allow_html=True)

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
        rdw_v = 0.0  
        if req_brandstof:
            for b in req_brandstof:
                oms = b.get("brandstof_omschrijving", "").lower()
                brandstoffen.append(oms)
                if oms in ["benzine", "diesel", "lpg"]:
                    verb = b.get("brandstofverbruik_gecombineerd")
                    if verb: rdw_v = float(verb)
        return {
            "merk": data.get("merk", "Onbekend"), "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)), "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": data.get("datum_eerste_toelating_dt", "2020-01-01")[:10], "brandstoffen": brandstoffen, "rdw_verbruik": rdw_v
        }
    except: return None

def bereken_mrb_csv(gewicht, brandstoffen, provincie_naam):
    if df_mrb is None or df_prov is None: return 0
    trede = df_mrb[df_mrb['min_massa'] <= gewicht].iloc[-1]
    basis = trede['basis_3mnd']
    if trede['toeslag_per_100kg'] > 0:
        basis += math.ceil((gewicht - trede['drempel']) / 100) * trede['toeslag_per_100kg']
    opc = df_prov[df_prov['provincie'] == provincie_naam]['opcenten'].values[0]
    mrb_3mnd = basis + (basis * (opc / 100))
    toeslag = 0
    if any("diesel" in b for b in brandstoffen): toeslag = 153.00 + (math.ceil(max(0, gewicht-900)/100) * 16.57)
    elif any("lpg" in b for b in brandstoffen): toeslag = 172.08 + (math.ceil(max(0, gewicht-900)/100) * 18.22)
    jaarbedrag = (mrb_3mnd + toeslag) * 4
    if any("elektriciteit" in b for b in brandstoffen) and not any(x in ["benzine", "diesel", "lpg"] for x in brandstoffen):
        jaarbedrag *= 0.75
    return round(jaarbedrag)

BIJTELLING_OPTIES = [
    "22% over Cataloguswaarde (Standaard of Hybride)", "35% over Aanschafwaarde (Youngtimer)",
    "4% tot € 50.000 (EV 2019)", "8% tot € 45.000 (EV 2020)", "12% tot € 40.000 (EV 2021)",
    "16% tot € 35.000 (EV 2022)", "16% tot € 30.000 (EV 2023/2024)", "17% tot € 30.000 (EV 2025/2026)"
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

# --- 6. INTERFACE ---
with st.container(border=True):
    st.markdown("### 👤 1. Relatiegegevens")
    colA, colB = st.columns(2)
    with colA: klant_naam = st.text_input("Naam relatie *")
    with colB: klant_nummer = st.text_input("Relatienummer (alleen cijfers) *")
    colC, colD, colE = st.columns([2, 2, 1])
    with colC: 
        # FIX: Kenteken automatisch UPPERCASE
        kenteken_input = st.text_input("Kenteken *").upper()
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
        leeftijd = relativedelta(datetime.datetime.now(), toel_dt)
        is_young_auto = leeftijd.years >= 15
        is_ev = any("elektriciteit" in b for b in auto['brandstoffen'])
        is_bs = any(b in ["benzine", "diesel", "lpg"] for b in auto['brandstoffen'])
        is_full_ev = is_ev and not is_bs
        brandstof_t = ", ".join(auto['brandstoffen']).title()
        
        peil_jaar = toel_dt.year
        if is_full_ev:
            eind_60 = toel_dt + relativedelta(months=61)
            if datetime.datetime.now() >= eind_60: peil_jaar = eind_60.year

        st.success(f"🚙 **{auto['merk']} ({kenteken_input}) - {auto['handelsbenaming']}** | Toelating: {toelating_nl}")
        
        with st.container(border=True):
            st.markdown("### ⚙️ 2. Gebruik & Uitgangspunten")
            top1, top2, top3 = st.columns(3)
            with top1:
                st.markdown("#### Kilometers per jaar")
                # FIX: Step 1000
                z_km = st.number_input("Zakelijke km / jaar", value=0, min_value=0, step=1000)
                p_km = st.number_input("Privé km / jaar", value=0, min_value=0, step=1000)
                totaal_km = z_km + p_km
            with top2:
                st.markdown("#### Fiscale Keuzes")
                is_young_manual = st.checkbox("Youngtimer regeling toepassen?", value=is_young_auto)
                is_minder_dan_500 = st.checkbox("Minder dan 500 km privé per jaar?", value=False)
                is_geleased = st.checkbox("Wordt de auto geleased of gefinancierd?", value=False)
            with top3:
                if is_minder_dan_500: st.info("ℹ️ Zorg voor een sluitende rittenadministratie.")
                if peil_jaar > toel_dt.year: st.info(f"⚡ 60-maandenregel EV toegepast ({peil_jaar}).")

            st.markdown("---")
            st.markdown("### 💶 Financiële Specificaties")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("#### Waarde & Bijtelling")
                aanschaf = st.number_input("Aanschafwaarde / Dagwaarde (€)", value=int(auto['catalogusprijs']))
                idx_bijt = bepaal_bijtelling_index(peil_jaar, is_full_ev, is_young_manual)
                gekozen_bijt = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES, index=idx_bijt)
                if is_minder_dan_500: calc_bijt = 0.0
                elif is_young_manual: calc_bijt = aanschaf * 0.35
                else:
                    perc = float(gekozen_bijt.split("%")[0]) / 100
                    cap = 50000 if "2019" in gekozen_bijt else (45000 if "2020" in gekozen_bijt else (40000 if "2021" in gekozen_bijt else (35000 if "2022" in gekozen_bijt else 30000)))
                    if "EV" in gekozen_bijt: calc_bijt = (min(auto['catalogusprijs'], cap) * perc) + (max(0, auto['catalogusprijs'] - cap) * 0.22)
                    else: calc_bijt = auto['catalogusprijs'] * perc
                bijt_bruto = st.number_input("Bijtelling (€/jaar)", value=float(round(calc_bijt)))
            
            with col2:
                st.markdown("#### Verbruik & Brandstof")
                brandstof_kosten, laad_kosten = 0.0, 0.0
                ap = haal_actuele_brandstofprijzen()
                if is_bs or not is_ev:
                    verb_l = st.number_input("Verbruik (L/100km)", value=float(auto['rdw_verbruik']))
                    bs_l = [b.lower() for b in auto['brandstoffen']]
                    p_l = st.number_input("Literprijs (€)", value=ap["diesel"] if "diesel" in bs_l else ap["benzine"])
                    brandstof_kosten = float(round(((z_km+p_km)/100)*verb_l*p_l))
                    st.number_input("Brandstofkosten p/j", value=brandstof_kosten)
                if is_ev:
                    v_k = st.number_input("Stroomverbruik (kWh/100km)", value=0.0)
                    laad_kosten = float(round(((z_km+p_km)/100)*v_k*0.40))
                    st.number_input("Laadkosten p/j", value=laad_kosten)
            
            with col3:
                st.markdown("#### Vaste Kosten")
                mrb = st.number_input("Wegenbelasting (€/j)", value=int(bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)))
                gebruik_schatting = st.checkbox("🧮 Bereken schatting")
                oh = round(totaal_km * 0.04) if gebruik_schatting else 0
                onderhoud = st.number_input("Onderhoud (€/j)", value=float(oh))
                verzekering = st.number_input("Verzekering (€/j)", value=0.0)
                overige = st.number_input("Overig (€/j)", value=250.0 if gebruik_schatting else 0.0)
                lease_k, rente_k = 0.0, 0.0
                if is_geleased:
                    lease_k = st.number_input("Leasekosten (€/j)", value=0.0)
                    rente_k = st.number_input("Rentekosten (€/j)", value=0.0)

        afschr = round((aanschaf * 0.8) * 0.2)
        tot_k = round(brandstof_kosten + laad_kosten + mrb + onderhoud + verzekering + overige + afschr + lease_k + rente_k)
        bijt_def = round(min(bijt_bruto, tot_k) if not is_minder_dan_500 else 0.0)
        zak_aftrek, pri_aftrek = round(tot_k - bijt_def), round(z_km * 0.23)
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        with st.container(border=True):
            st.markdown("### 📊 3. Resultaat & Fiscaal Advies")
            if bijt_bruto > tot_k and not is_minder_dan_500: st.warning(f"⚖️ Bijtelling gemaximeerd op werkelijke kosten (€ {fmt(tot_k)}).")
            st.success(f"💡 **Conclusie:** Vanuit fiscaal oogpunt is de optie **{advies}**.")
            res1, res2 = st.columns(2)
            with res1:
                st.write(f"Totale kosten p/j: **€ {fmt(tot_k)}** | Bijtelling: **- € {fmt(bijt_def)}**")
                st.metric("Fiscale Aftrekpost", f"€ {fmt(zak_aftrek)}")
            with res2:
                st.write(f"Aantal zakelijke km: **{fmt(z_km)}**")
                st.write("<br>", unsafe_allow_html=True)
                st.metric("Fiscale Aftrekpost", f"€ {fmt(pri_aftrek)}")

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
                    self.set_xy(10, 32); self.set_font(self.font_fam, '', 10); self.cell(0, 10, clean("In het hart van de gezondheidszorg."), ln=True)
                def footer(self):
                    self.set_y(-15); self.set_fill_color(0, 49, 92); self.rect(0, 282, 210, 15, 'F')
                    self.set_text_color(255); self.set_font(self.font_fam, '', 9); self.cell(0, 15, clean("VvAA | www.vvaa.nl | Voor zorgverleners, door zorgverleners"), align='C', ln=True)

            pdf = VVAAPDF(); pdf.set_auto_page_break(auto=False); pdf.add_page(); f = pdf.font_fam
            pdf.set_font(f, 'B', 16); pdf.set_text_color(0, 49, 92); pdf.set_xy(10, 45); pdf.cell(0, 10, clean("Autoberekening: Zakelijk of Privé?"), ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "1. Relatiegegevens", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.cell(35, 5, "Relatie:"); pdf.cell(70, 5, clean(klant_naam)); pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Lidnr:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)
            
            # --- VOERTUIGSPECIFICATIES (HERSTELD) ---
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "2. Voertuigspecificaties", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input})"), fill=True, ln=True)
            pdf.cell(35, 6, " Brandstof:", fill=True); pdf.cell(155, 6, brandstof_t, fill=True, ln=True)
            pdf.cell(35, 6, " Eerste toelating:", fill=True); pdf.cell(155, 6, f"{toelating_nl} ({leeftijd.years} jaar, {leeftijd.months} mnd)", fill=True, ln=True)
            pdf.cell(35, 6, " Youngtimer:", fill=True); pdf.cell(155, 6, "Ja" if is_young_manual else "Nee", fill=True, ln=True)
            pdf.cell(35, 6, " < 500 km prive:", fill=True); pdf.cell(155, 6, "Ja (Geen bijtelling)" if is_minder_dan_500 else "Nee", fill=True, ln=True)
            pdf.cell(35, 6, " Lease auto:", fill=True); pdf.cell(155, 6, "Ja" if is_geleased else "Nee", fill=True, ln=True); pdf.ln(3)

            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True); pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.ln(2)
            
            left = [("Brandstof/Laden:", f"EUR {fmt(brandstof_kosten+laad_kosten)}"), ("Wegenbelasting:", f"EUR {fmt(mrb)}"), ("Onderhoud:", f"EUR {int(onderhoud)}"), ("Verzekering:", f"EUR {int(verzekering)}"), ("Overig/Afschr:", f"EUR {fmt(overige+afschr)}")]
            if is_geleased: left.append(("Lease/Rente:", f"EUR {fmt(lease_k+rente_k)}"))
            # Alleen zakelijke km in PDF
            right = [("Fiscale vergoeding:", f"EUR {fmt(pri_aftrek)}"), ("Zakelijke km:", fmt(z_km)), ("Tarief p/km:", "EUR 0,23")]
            
            for i in range(max(len(left), len(right))):
                l1, v1 = left[i] if i < len(left) else ("", "")
                l2, v2 = right[i] if i < len(right) else ("", "")
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5); pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)
            
            pdf.ln(2); pdf.set_font(f, 'B', 10); pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, f"EUR {fmt(tot_k)}", align='R', ln=True)
            pdf.cell(45, 6, "Bijtelling:"); pdf.cell(45, 6, f"- EUR {fmt(bijt_def)}", align='R', ln=True); pdf.ln(2); pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(zak_aftrek)} ", fill=True, align='R'); pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(pri_aftrek)} ", fill=True, align='R', ln=True); pdf.ln(5)
            
            pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255); pdf.set_font(f, 'B', 11); pdf.cell(190, 10, clean(f"  Advies: {advies}"), fill=True, ln=True); pdf.ln(4)
            pnt = ["- Getoonde cijfers zijn afgeronde hele euro's.", "- Wegenbelasting is gebaseerd op tarieven 2026.", "- De berekening is een schatting op basis van uw opgave."]
            pdf.set_font(f, '', 8); pdf.set_text_color(0); [pdf.cell(0, 4, clean(p), ln=True) for p in pnt]
            st.download_button("📄 Autoberekening Downloaden", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}.pdf")
    else: st.error("❌ Kenteken niet gevonden.")
