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
VVAA_GRIJS_LICHT = "#F8F9FB" # Achtergrond pagina
VVAA_GRIJS_CARD = "#FFFFFF"  # Achtergrond kaart
VVAA_BORDER = "#D1D5DB"      # Donkerdere border voor contrast

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = f"""
<style>
    .stApp {{ background-color: {VVAA_GRIJS_LICHT} !important; }}
    .stApp, p, label, span, div[data-testid="stMarkdownContainer"] > p, li {{ color: {VVAA_BLAUW} !important; font-family: 'Arial', sans-serif; }}
    h1, h2, h3, h4, h5, h6 {{ color: {VVAA_ORANJE} !important; font-family: 'Arial', sans-serif !important; font-weight: bold; }}
    
    /* Kaarten/Secties contrast */
    div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stVerticalBlockBorderWrapper"]) {{
        background-color: {VVAA_GRIJS_CARD} !important;
        border: 1px solid {VVAA_BORDER} !important;
        border-radius: 10px !important;
        padding: 20px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        margin-bottom: 20px !important;
    }}

    /* Input velden contrast */
    input, select, div[data-baseweb="select"] > div {{ 
        border: 1px solid #A0A0A0 !important; 
        background-color: white !important;
        color: {VVAA_BLAUW} !important;
    }}

    /* Resultaat boxen */
    div[data-testid="metric-container"] {{
        background-color: #F0F4F8 !important;
        border: 1px solid {VVAA_BLAUW} !important;
        border-left: 8px solid {VVAA_ORANJE} !important;
        padding: 20px !important;
        border-radius: 8px !important;
    }}

    /* Knoppen */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; color: white !important; 
        font-weight: bold; border-radius: 6px; width: 100%; border: none; padding: 10px;
    }}
    
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; color: white !important; border-radius: 8px !important;
        padding: 15px !important; font-weight: bold !important; width: 100% !important;
    }}

    /* Dropdown fix */
    div[data-baseweb="popover"] ul {{ background-color: white !important; }}
    div[data-baseweb="popover"] li {{ color: {VVAA_BLAUW} !important; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

def fmt(val):
    return f"{int(round(val)):,}".replace(",", ".")

# --- 2. LIVE BRANDSTOF PRIJZEN ---
@st.cache_data(ttl=86400) 
def haal_actuele_brandstofprijzen():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get("https://www.unitedconsumers.com/tanken", headers=headers, timeout=5)
        e95 = re.search(r'Euro95 \(E10\).*?€\s*(\d{1},\d{3})', res.text, re.DOTALL)
        dsl = re.search(r'Diesel.*?€\s*(\d{1},\d{3})', res.text, re.DOTALL)
        lpg = re.search(r'LPG.*?€\s*(\d{1},\d{3})', res.text, re.DOTALL)
        return {
            "benzine": float(e95.group(1).replace(',', '.')) if e95 else 2.05,
            "diesel": float(dsl.group(1).replace(',', '.')) if dsl else 1.85,
            "lpg": float(lpg.group(1).replace(',', '.')) if lpg else 0.85
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

# --- 4. HEADER ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    logo_path = "VvAA-logo-RGB.png" if os.path.exists("VvAA-logo-RGB.png") else "vvaa_logo.jpg"
    if os.path.exists(logo_path): st.image(logo_path, use_container_width=True)
with col_title:
    st.markdown(f"<h1 style='color: {VVAA_BLAUW}; margin: 0;'>Autoberekening: Zakelijk of Privé?</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='color: {VVAA_ORANJE}; margin: 0;'>In het hart van de gezondheidszorg.</h4>", unsafe_allow_html=True)
st.markdown(f"<hr style='border: 2px solid {VVAA_ORANJE}; margin-top: 10px; margin-bottom: 25px;'>", unsafe_allow_html=True)

# --- 5. RDW API ---
@st.cache_data
def get_rdw_data(kenteken):
    kenteken = kenteken.replace("-", "").upper()
    url_basis = f"https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken={kenteken}"
    url_brandstof = f"https://opendata.rdw.nl/resource/8ys7-d773.json?kenteken={kenteken}"
    try:
        rb = requests.get(url_basis).json()
        rf = requests.get(url_brandstof).json()
        if not rb: return None
        d = rb[0]
        brandstoffen = []
        verbruik = 0.0
        if rf:
            for b in rf:
                oms = b.get("brandstof_omschrijving", "").lower()
                brandstoffen.append(oms)
                if oms in ["benzine", "diesel", "lpg"]:
                    v = b.get("brandstofverbruik_gecombineerd")
                    if v: verbruik = float(v)
        return {
            "merk": d.get("merk", "Onbekend"), "handelsbenaming": d.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(d.get("catalogusprijs", 0)), "gewicht": int(d.get("massa_ledig_voertuig", 0)),
            "toelating": d.get("datum_eerste_toelating_dt", "2020-01-01")[:10], "brandstoffen": brandstoffen, "rdw_verbruik": verbruik
        }
    except: return None

def bereken_mrb_csv(gewicht, brandstoffen, provincie_naam):
    if df_mrb is None or df_prov is None: return 0
    trede = df_mrb[df_mrb['min_massa'] <= gewicht].iloc[-1]
    basis = trede['basis_3mnd']
    if trede['toeslag_per_100kg'] > 0:
        basis += math.ceil((gewicht - trede['drempel']) / 100) * trede['toeslag_per_100kg']
    opc = df_prov[df_prov['provincie'] == provincie_naam]['opcenten'].values[0]
    totaal = (basis + (basis * (opc / 100)))
    toeslag = 0
    if any("diesel" in b for b in brandstoffen): toeslag = 153.00 + (math.ceil(max(0, gewicht-900)/100) * 16.57)
    elif any("lpg" in b for b in brandstoffen): toeslag = 172.08 + (math.ceil(max(0, gewicht-900)/100) * 18.22)
    jaarbedrag = (totaal + toeslag) * 4
    if any("elektriciteit" in b for b in brandstoffen) and not any(x in ["benzine", "diesel", "lpg"] for x in brandstoffen):
        jaarbedrag *= 0.75
    return round(jaarbedrag)

BIJTELLING_OPTIES = [
    "22% over Cataloguswaarde (Standaard of Hybride)", "35% over Aanschafwaarde (Youngtimer)",
    "4% tot € 50.000 (EV 2019)", "8% tot € 45.000 (EV 2020)", "12% tot € 40.000 (EV 2021)",
    "16% tot € 35.000 (EV 2022)", "16% tot € 30.000 (EV 2023/24)", "17% tot € 30.000 (EV 2025/26)"
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
    c1, c2 = st.columns(2)
    klant_naam = c1.text_input("Naam relatie *")
    klant_nummer = c2.text_input("Relatienummer *")
    c3, c4, c5 = st.columns([2, 2, 1])
    kenteken_input = c3.text_input("Kenteken *")
    prov = c4.selectbox("Provincie", df_prov['provincie'].tolist() if df_prov is not None else ["Utrecht"])
    c5.button("Berekenen")

gevalideerd = bool(klant_naam) and klant_nummer.isdigit()

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if auto:
        toel_dt = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        leeftijd = relativedelta(datetime.datetime.now(), toel_dt)
        brandstof_t = ", ".join(auto['brandstoffen']).title()
        is_ev = any("elektriciteit" in b for b in auto['brandstoffen'])
        is_bs = any(b in ["benzine", "diesel", "lpg"] for b in auto['brandstoffen'])
        is_full_ev = is_ev and not is_bs
        
        peil_jaar = toel_dt.year
        is_vervallen_ev = False
        if is_full_ev:
            eind_60 = toel_dt + relativedelta(months=61) # 1e dag mnd na toelating + 60
            if datetime.datetime.now() >= eind_60:
                is_vervallen_ev = True
                peil_jaar = eind_60.year

        st.info(f"🚙 **{auto['merk']} {auto['handelsbenaming']}** | Brandstof: {brandstof_t} | Toelating: {toel_dt.strftime('%d-%m-%Y')} ({leeftijd.years} jaar, {leeftijd.months} mnd)")
        
        with st.container(border=True):
            st.markdown("### ⚙️ 2. Gebruik & Uitgangspunten")
            t1, t2, t3 = st.columns(3)
            z_km = t1.number_input("Zakelijke km / jaar", value=0, min_value=0)
            p_km = t1.number_input("Privé km / jaar", value=0, min_value=0)
            is_young_manual = t2.checkbox("Youngtimer regeling", value=leeftijd.years >= 15)
            is_500 = t2.checkbox("Minder dan 500 km privé?", value=False)
            is_lease = t2.checkbox("Geleased / Gefinancierd?", value=False)
            if is_500: t3.warning("Zorg voor sluitende rittenadministratie.")
            if is_vervallen_ev and not is_young_manual: t3.warning(f"60-mnd regel vervallen. Tarief {peil_jaar} toegepast.")

            st.markdown("<hr style='border: 1px solid #ddd;'>", unsafe_allow_html=True)
            f1, f2, f3 = st.columns(3)
            with f1:
                st.markdown("#### Waarde & Bijtelling")
                aanschaf = st.number_input("Dagwaarde (€)", value=int(auto['catalogusprijs']))
                idx = bepaal_bijtelling_index(peil_jaar, is_full_ev, is_young_manual)
                profiel = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES, index=idx)
                if is_500: calc_b = 0.0
                elif is_young_manual: calc_b = aanschaf * 0.35
                else:
                    perc = float(profiel.split("%")[0]) / 100
                    cap = 50000 if "2019" in profiel else (45000 if "2020" in profiel else (40000 if "2021" in profiel else (35000 if "2022" in profiel else 30000)))
                    if "EV" in profiel: calc_b = (min(auto['catalogusprijs'], cap) * perc) + (max(0, auto['catalogusprijs']-cap) * 0.22)
                    else: calc_b = auto['catalogusprijs'] * perc
                bijt_bruto = st.number_input("Bijtelling (€/jr)", value=float(calc_b))
            
            with f2:
                st.markdown("#### Brandstof & Laden")
                ap = haal_actuele_brandstofprijzen()
                bk, lk = 0.0, 0.0
                if is_bs or not is_ev:
                    v_l = st.number_input("Verbruik (L/100km)", value=float(auto['rdw_verbruik']))
                    bs_l = [b.lower() for b in auto['brandstoffen']]
                    p_l = st.number_input("Prijs per Liter (€)", value=ap["diesel"] if "diesel" in bs_l else (ap["lpg"] if "lpg" in bs_l else ap["benzine"]))
                    bk = st.number_input("Brandstofkosten p/j (€)", value=float(((z_km + p_km) / 100) * v_l * p_l))
                if is_ev:
                    v_k = st.number_input("Verbruik (kWh/100km)", value=0.0)
                    lk = st.number_input("Laadkosten p/j (€)", value=float(((z_km + p_km) / 100) * v_k * 0.40))
            
            with f3:
                st.markdown("#### Overige Kosten")
                mrb = st.number_input("Wegenbelasting (€/jr)", value=int(bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)))
                schat = st.checkbox("Bereken schatting")
                if schat:
                    with st.expander("Uitleg schatting"): st.write("- Onderhoud: € 0,04 per km\n- Overig: € 250,- per jaar")
                oh = st.number_input("Onderhoud (€/jr)", value=int((z_km+p_km)*0.04) if schat else 0)
                verz = st.number_input("Verzekering (€/jr)", value=0)
                afschr = (aanschaf * 0.8) * 0.2
                ov = st.number_input("Overige autokosten (€/jr)", value=250 if schat else 0)
                lease_k, rente_k = 0.0, 0.0
                if is_lease:
                    lease_k = st.number_input("Lease (Operational) (€/jr)", value=0)
                    rente_k = st.number_input("Rente (Lening) (€/jr)", value=0)

        tot_k = bk + lk + mrb + oh + verz + ov + afschr + lease_k + rente_k
        bijt_def = min(bijt_bruto, tot_k) if not is_500 else 0.0
        zak_aftrek, pri_aftrek = tot_k - bijt_def, z_km * 0.23
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        with st.container(border=True):
            st.markdown("### 📊 3. Resultaat & Fiscaal Advies")
            if bijt_bruto > tot_k and not is_500: st.warning(f"⚖️ Bijtelling gemaximeerd op totale kosten (€ {fmt(tot_k)}).")
            st.success(f"💡 **Conclusie:** {advies}")
            r1, r2 = st.columns(2)
            r1.metric("🏢 Auto Zakelijk (Fiscale Aftrek)", f"€ {fmt(zak_aftrek)}", help="Kosten minus bijtelling")
            r2.metric("🏠 Auto Privé (Fiscale Aftrek)", f"€ {fmt(pri_aftrek)}", help="€ 0,23 per zakelijke km")

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
            pdf.set_font(f, 'B', 16); pdf.set_text_color(0, 49, 92); pdf.set_xy(10, 45)
            pdf.cell(0, 10, clean("Autoberekening: Zakelijk of Privé?"), ln=True); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, clean("1. Relatiegegevens"), ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0)
            pdf.cell(35, 5, "Relatie:"); pdf.cell(70, 5, clean(klant_naam)); pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Lidnummer:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, clean("2. Voertuigspecificaties"), ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), fill=True, ln=True)
            pdf.cell(35, 6, " Toelating:", fill=True); pdf.cell(155, 6, f"{toel_dt.strftime('%d-%m-%Y')} ({leeftijd.years} jaar, {leeftijd.months} mnd)", fill=True, ln=True); pdf.ln(3)
            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True); pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.ln(2)
            left = []
            if is_bs or not is_ev: left.append(("Brandstofkosten:", f"EUR {fmt(bk)}"))
            if is_ev: left.append(("Laadkosten:", f"EUR {fmt(lk)}"))
            left.extend([("Wegenbelasting:", f"EUR {fmt(mrb)}"), ("Onderhoud:", f"EUR {fmt(oh)}"), ("Verzekering:", f"EUR {fmt(verz)}"), ("Overig/Afschr:", f"EUR {fmt(ov+afschr)}")])
            if is_lease: left.append(("Lease/Rente:", f"EUR {fmt(lease_k+rente_k)}"))
            right = [("Fiscale vergoeding:", f"EUR {fmt(pri_aftrek)}"), ("Zakelijke km:", fmt(z_km)), ("Privé km:", fmt(p_km)), ("Tarief p/km:", "EUR 0,23")]
            for i in range(max(len(left), len(right))):
                l1, v1 = left[i] if i < len(left) else ("", "")
                l2, v2 = right[i] if i < len(right) else ("", "")
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5); pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)
            pdf.ln(2); pdf.set_font(f, 'B', 10); pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, f"EUR {fmt(tot_k)}", align='R', ln=True)
            pdf.cell(45, 6, "Bijtelling:"); pdf.cell(45, 6, f"- EUR {fmt(bijt_def)}", align='R', ln=True); pdf.ln(2); pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(zak_aftrek)} ", fill=True, align='R'); pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(pri_aftrek)} ", fill=True, align='R', ln=True); pdf.ln(5)
            pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255); pdf.set_font(f, 'B', 11); pdf.cell(190, 10, clean(f"  Advies vanuit fiscaal oogpunt: {advies}"), fill=True, ln=True); pdf.ln(4)
            pdf.set_text_color(0, 49, 92); pdf.set_font(f, 'B', 10); pdf.cell(0, 5, "Aandachtspunten:", ln=True); pdf.set_font(f, '', 8); pdf.set_text_color(0)
            pnt = ["- De getoonde berekening is een schatting op basis van uw eigen opgave.", "- Wegenbelasting is gebaseerd op Belastingdienst tarieven 2026.", "- Percentage bijtelling geldt voor 60 maanden."]
            if is_500: pnt.insert(0, "- Voor 0% bijtelling is een sluitende rittenadministratie vereist.")
            for p in pnt: pdf.cell(0, 4, clean(p), ln=True)
            st.download_button("📄 Autoberekening Downloaden", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}.pdf")
        else: st.info("ℹ️ Vul naam en lidnummer in om rapport te downloaden.")
    else: st.error("❌ Kenteken niet gevonden.")
