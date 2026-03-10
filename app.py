import streamlit as st
import requests
import datetime
import os
import pandas as pd
import math
import re
import urllib.parse
from fpdf import FPDF
from dateutil.relativedelta import relativedelta

# --- 1. VvAA HUISSTIJL & CONFIGURATIE ---
VVAA_ORANJE = "#E84E0F"
VVAA_BLAUW = "#00315C"
VVAA_LICHTORANJE = "#F9E8DF" 
VVAA_GRIJS = "#F4F6F8" 
VVAA_MELDING_ORANJE = "#FDCEA8"

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

# --- 2. CSS STYLING ---
vvaa_css = f"""
<style>
    /* --- ACHTERGRONDKLEUR HERSTEL --- */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background-color: {VVAA_LICHTORANJE} !important; }}

    /* --- ALGEMENE SCALING --- */
    html, body {{ font-size: 0.92rem !important; }}
    
    /* --- MODERNE HEADERS & UITLIJNING --- */
    h3 {{ border-bottom: 2px solid {VVAA_ORANJE} !important; padding-bottom: 8px !important; margin-bottom: 20px !important; font-size: 1.3rem !important; }}
    [data-testid="column"] h4 {{ margin-top: 0 !important; margin-bottom: 12px !important; padding-top: 0 !important; font-size: 1.05rem !important; color: {VVAA_ORANJE} !important; }}

    /* --- MODERNE CARDS --- */
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background-color: #FFFFFF !important; border: none !important; border-radius: 10px !important; box-shadow: 0 4px 15px rgba(0, 49, 92, 0.05) !important; padding: 15px !important; }}

    /* --- SPECIFIEKE TWEAKS --- */
    input[aria-label="Kenteken *"] {{ text-transform: uppercase !important; }}

    /* --- KNOPPEN (BUTTONS) --- */
    .stButton>button {{ background-color: {VVAA_ORANJE} !important; color: white !important; border-radius: 6px; border: none; padding: 10px 24px; font-weight: bold; width: 100%; margin-top: 28px; transition: all 0.3s ease; }}
    .stButton>button:hover {{ background-color: #C7400A !important; transform: translateY(-1px); box-shadow: 0 4px 8px rgba(232, 78, 15, 0.3) !important; }}
    
    div.stDownloadButton > button {{ background-color: {VVAA_BLAUW} !important; color: white !important; border-radius: 8px !important; padding: 15px 32px !important; font-size: 18px !important; font-weight: bold !important; width: 100% !important; box-shadow: 0 4px 6px rgba(0, 49, 92, 0.15) !important; border: none !important; transition: all 0.3s ease; display: block !important; }}
    div.stDownloadButton > button:hover {{ background-color: #001F3F !important; transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0, 49, 92, 0.25) !important; }}
    
    /* --- MELDINGEN & ALERTS --- */
    div[data-testid="stAlert"] {{ background-color: transparent !important; background: transparent !important; border: none !important; padding: 0 !important; }}
    div[data-testid="stAlert"] > div[role="alert"] {{ background-color: {VVAA_MELDING_ORANJE} !important; color: {VVAA_BLAUW} !important; border-radius: 8px !important; padding: 16px !important; box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important; border: 1px solid #F0D5C9 !important; }}
    div[data-testid="stAlert"] * {{ color: {VVAA_BLAUW} !important; }}
    div[data-testid="stAlert"] svg {{ fill: {VVAA_BLAUW} !important; }}

    /* --- EMAIL CODE BLOCK FIX --- */
    [data-testid="stCodeBlock"] {{ background-color: transparent !important; }}
    [data-testid="stCodeBlock"] pre, [data-testid="stCodeBlock"] code {{ font-family: 'Arial', sans-serif !important; font-size: 10pt !important; white-space: pre-wrap !important; color: #00315C !important; background-color: #FFFFFF !important; border: 1px solid #E0E6ED; border-radius: 6px; padding: 15px; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

# --- 3. ALGEMENE FUNCTIES & CLASSES ---
def fmt(val):
    return f"{int(round(val)):,}".replace(",", ".")

def clean_text(t): 
    return str(t).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')

class VVAAPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists("vvaa_font.ttf"):
            self.add_font("VvAA_Font", "", "vvaa_font.ttf", uni=True)
            if os.path.exists("vvaa_font_bold.ttf"):
                self.add_font("VvAA_Font", "B", "vvaa_font_bold.ttf", uni=True)
            self.font_fam = "VvAA_Font"
        else:
            self.font_fam = "Arial"

    def header(self):
        self.set_fill_color(244, 246, 248) 
        self.rect(0, 0, 210, 297, 'F')
        
        self.set_fill_color(232, 78, 15)
        self.rect(0, 0, 210, 4, 'F')
        
        logo = "VvAA_logo.png" 
        if os.path.exists(logo): 
            self.image(logo, 10, 10, 35)
        
        self.set_font(self.font_fam, 'B', 22)
        self.set_text_color(0, 49, 92)
        self.set_xy(10, 12)
        self.cell(190, 10, clean_text("Fiscaal Auto-advies"), align='R')
        
        self.set_font(self.font_fam, '', 12)
        self.set_text_color(232, 78, 15)
        self.set_xy(10, 22)
        self.cell(190, 6, clean_text("Zakelijk of privé rijden?"), align='R')
        
    def footer(self):
        self.set_y(-20)
        self.set_draw_color(232, 78, 15)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(0, 49, 92)
        self.set_font(self.font_fam, '', 8)
        self.cell(0, 4, clean_text("VvAA | www.vvaa.nl | Voor zorgverleners, door zorgverleners"), align='C', ln=True)
        self.cell(0, 4, clean_text(f"Advies gegenereerd op: {datetime.datetime.now().strftime('%d-%m-%Y om %H:%M')}"), align='C', ln=True)

# --- 4. DATA OPSLAG & APIS ---

# --- FAIL-SAFE FISCALE REGELS INLADEN ---
# Let op: de @st.cache_data tag is hier verwijderd zodat hij ALTIJD kijkt naar wijzigingen in CSV.
def load_fiscale_regels():
    regels = {
        "km_vergoeding": 0.23,
        "btw_forfait_normaal": 0.027,
        "btw_forfait_marge": 0.015
    }
    try:
        if os.path.exists("fiscale_regels.csv"):
            df_regels = pd.read_csv("fiscale_regels.csv", sep=";")
            for index, row in df_regels.iterrows():
                # Lege regels in the CSV negeren:
                if pd.isna(row['Regel']) or pd.isna(row['Waarde']):
                    continue
                key = str(row['Regel']).strip()
                val = float(str(row['Waarde']).replace(',', '.'))
                if key in regels:
                    regels[key] = val
    except Exception:
        pass 
    return regels

fiscale_regels = load_fiscale_regels()

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

@st.cache_data
def load_mrb_data():
    try:
        return pd.read_csv("mrb_tarieven_2026.csv"), pd.read_csv("mrb_provincies_2026.csv")
    except:
        return None, None

df_mrb, df_prov = load_mrb_data()

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

# --- 5. MODERNE HEADER LAYOUT ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    logo_path = "VvAA_logo.png" 
    if os.path.exists(logo_path):
        st.image(logo_path, width=130) 
with col_title:
    st.markdown(f"<h2 style='color: {VVAA_BLAUW}; margin: 0; padding-top: 15px;'>Autoberekening: Zakelijk of Privé?</h2>", unsafe_allow_html=True)
st.markdown(f"<hr style='border: 2px solid {VVAA_ORANJE}; border-radius: 5px; margin-top: 10px; margin-bottom: 30px;'>", unsafe_allow_html=True)

# --- 6. INTERFACE / CARDS ---
with st.container(border=True):
    st.markdown("### 👤 1. Relatiegegevens")
    colA, colB = st.columns(2)
    with colA: klant_naam = st.text_input("Naam relatie *")
    with colB: klant_nummer = st.text_input("Relatienummer (alleen cijfers) *")

    colC, colD, colE = st.columns([2, 2, 1])
    with colC: 
        kenteken_input = st.text_input("Kenteken *", key="kenteken_input").upper()
    with colD: 
        prov_lijst = df_prov['provincie'].tolist() if df_prov is not None else ["Gelderland"]
        prov = st.selectbox("Provincie", prov_lijst)
    with colE: bereken_knop = st.button("Laden / Berekenen")

is_valid_nummer = klant_nummer.isdigit()
gevalideerd = bool(klant_naam) and is_valid_nummer

if not is_valid_nummer and klant_nummer:
    st.warning("⚠️ Relatienummer mag uitsluitend uit cijfers bestaan.")

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
        
        is_vervallen_ev = False
        peil_jaar = toel_dt.year
        
        if is_full_ev:
            start_mnd = toel_dt.month + 1; start_jr = toel_dt.year
            if start_mnd > 12: start_mnd = 1; start_jr += 1
            start_60mnd_dt = datetime.datetime(start_jr, start_mnd, 1)
            eind_60mnd_dt = start_60mnd_dt + relativedelta(months=60)
            is_vervallen_ev = vandaag >= eind_60mnd_dt
            peil_jaar = eind_60mnd_dt.year if is_vervallen_ev else toel_dt.year
        
        st.success(f"🚙 **{auto['merk']} ({kenteken_input}) - {auto['handelsbenaming']}** \n\n"
                   f"Brandstof: {brandstof_t} | Toelating: {toelating_nl} ({leeftijd.years} jaar en {leeftijd.months} maanden oud)")
        
        with st.container(border=True):
            st.markdown("### ⚙️ 2. Gebruik & Uitgangspunten")
            
            top1, top2, top3 = st.columns(3)
            with top1:
                st.markdown("#### Kilometers per jaar")
                z_km = st.number_input("Zakelijke km / jaar", value=0, min_value=0, step=1000)
                p_km = st.number_input("Privé km / jaar", value=0, min_value=0, step=1000)
                totaal_km = z_km + p_km
                
            with top2:
                st.markdown("#### Fiscale Keuzes")
                is_young_manual = st.checkbox("Youngtimer regeling toepassen?", value=is_young_auto)
                is_minder_dan_500 = st.checkbox("Wordt er minder dan 500 km per jaar privé gereden?", value=False)
                is_geleased = st.checkbox("Wordt de auto geleased of gefinancierd?", value=False)
                
                is_btw_klant = st.checkbox("Ondernemer voor de btw?", value=False)
                if is_btw_klant:
                    # Toon het specifieke BTW forfait o.b.v. de config
                    forfait_tekst = f"{fiscale_regels['btw_forfait_marge']*100:.1f}%".replace('.', ',')
                    btw_marge = st.checkbox(f"↳ Marge-auto of >4 jaar in gebruik? ({forfait_tekst} btw-forfait)", value=False)
                else:
                    btw_marge = False
                
            with top3:
                st.markdown("#### Meldingen")
                if is_minder_dan_500:
                    st.info("ℹ️ Er is aangegeven dat er minder dan 500 km privé wordt gereden. Hiervoor dient een sluitende rittenadministratie aanwezig te zijn of er is een verklaring 'geen privégebruik auto' nodig.")
                if totaal_km > 0 and (z_km / totaal_km) < 0.10:
                    st.warning(f"⚠️ De auto wordt voor slechts {(z_km / totaal_km)*100:.1f}% zakelijk gebruikt. Minimaal 10% zakelijk gebruik is vereist om de auto op de zaak te mogen zetten.")
                if is_young_manual and not is_young_auto:
                    st.warning(f"⚠️ Let op: Het voertuig is pas {leeftijd.years} jaar oud. Voor de youngtimer-regeling moet de auto minstens 15 jaar geleden toegelaten zijn.")
                elif is_young_auto and not is_young_manual:
                    st.info(f"💡 Tip: Dit voertuig is ouder dan 15 jaar. De youngtimer-regeling is waarschijnlijk voordeliger.")
                if is_vervallen_ev and not is_young_manual:
                    st.info(f"⚡ Let op: De 60-maandenregel voor deze EV is verlopen. De regels van peiljaar {peil_jaar} zijn toegepast.")
                if is_btw_klant:
                    st.info("ℹ️ **Btw-ondernemer:** Vul de verwachte autokosten hieronder **exclusief btw** in. De btw-correctie voor privégebruik wordt in de linkerkolom automatisch berekend o.b.v. de cataloguswaarde.")

            st.markdown("---")
            st.markdown("### 💶 Financiële Specificaties")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("#### Waarde & Bijtelling")
                
                with st.expander("ℹ️ Uitleg Waarde & Bijtelling"):
                    st.write("Selecteer het juiste bijtellingsprofiel. De berekende bijtelling wordt automatisch gemaximeerd (afgetopt) als deze onverhoopt hoger uitvalt dan de totale werkelijke autokosten.")
                
                st.markdown(f"<div style='height: 35px; display: flex; align-items: center; color: {VVAA_BLAUW};'><strong>Cataloguswaarde (RDW):</strong>&nbsp;€ {fmt(auto['catalogusprijs'])}</div>", unsafe_allow_html=True)
                
                aanschaf = st.number_input("Aanschafprijs / Taxatiewaarde (€)", value=int(auto['catalogusprijs']))
                
                idx_bijt = bepaal_bijtelling_index(peil_jaar, is_full_ev, is_young_manual)
                gekozen_bijt = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES, index=idx_bijt)
                
                if is_minder_dan_500: calc_bijt = 0.0
                elif is_young_manual: calc_bijt = aanschaf * 0.35
                else:
                    bijt_perc = float(gekozen_bijt.split("%")[0]) / 100
                    if "€" in gekozen_bijt:
                        cap = float(gekozen_bijt.split("€ ")[1].split(",")[0].replace(".", ""))
                        calc_bijt = (min(auto['catalogusprijs'], cap) * bijt_perc) + (max(0, auto['catalogusprijs'] - cap) * 0.22)
                    else: 
                        calc_bijt = auto['catalogusprijs'] * bijt_perc
                
                bijt_bruto = st.number_input("Bijtelling per jaar (€)", value=float(round(calc_bijt)))

                if is_btw_klant:
                    calc_btw_corr = 0.0
                    if not is_minder_dan_500:
                        # Berekening via het externe / fail-safe configuratiebestand
                        calc_btw_corr = auto['catalogusprijs'] * (fiscale_regels["btw_forfait_marge"] if btw_marge else fiscale_regels["btw_forfait_normaal"])
                    btw_correctie = st.number_input("Btw-correctie privégebruik (€)", value=float(round(calc_btw_corr)))
                else:
                    btw_correctie = 0.0
                
            with col2:
                st.markdown("#### Verbruik & Brandstof")
                
                if is_full_ev:
                    with st.expander("ℹ️ Uitleg Stroomprijs & Bron"):
                        st.write("De stroomprijs is standaard ingesteld op een schatting van € 0,40 per kWh, maar je kunt deze zelf aanpassen. De kosten worden berekend via de formule: *(Totale km / 100) × Verbruik × Prijs per kWh*.")
                else:
                    with st.expander("ℹ️ Uitleg Brandstof & Bron"):
                        st.write("De voorgestelde literprijs is gebaseerd op de actuele gemiddelde landelijke adviesprijs (bron: UnitedConsumers). De kosten worden berekend via de formule: *(Totale km / 100) × Verbruik × Literprijs*.")
                
                brandstof_kosten = 0.0
                laad_kosten = 0.0
                verbruik_l = 0.0
                prijs_l = 0.0
                verbruik_kwh = 0.0
                price_kwh = 0.0
                
                actuele_prijzen = haal_actuele_brandstofprijzen()
                
                if is_brandstof or (not is_brandstof and not is_ev):
                    if auto['rdw_verbruik'] == 0.0:
                        st.info("ℹ️ RDW verbruik onbekend. Vul zelf in.")
                    
                    st.markdown(f"<div style='height: 35px; display: flex; align-items: center; color: {VVAA_BLAUW};'>Actuele brandstofprijzen ingeladen.</div>", unsafe_allow_html=True)
                    verbruik_l = st.number_input("Verbruik (L/100km)", value=float(auto['rdw_verbruik']))
                    
                    bs_lower = [b.lower() for b in auto['brandstoffen']]
                    if any("diesel" in b for b in bs_lower): def_prijs = actuele_prijzen["diesel"]
                    elif any("lpg" in b for b in bs_lower): def_prijs = actuele_prijzen["lpg"]
                    else: def_prijs = actuele_prijzen["benzine"]
                    
                    prijs_l = st.number_input("Prijs per Liter (€)", value=def_prijs)
                    calc_br = ((z_km + p_km) / 100) * verbruik_l * prijs_l
                    brandstof_kosten = float(round(calc_br))
                    brandstof_kosten = st.number_input("Brandstofkosten per jaar (€)", value=brandstof_kosten)
                
                if is_ev:
                    if not is_brandstof: st.info("ℹ️ Stroomverbruik onbekend. Vul zelf in (bijv. 18.0).")
                    
                    st.markdown("<div style='height: 35px;'></div>", unsafe_allow_html=True)
                    
                    verbruik_kwh = st.number_input("Verbruik Stroom (kWh/100km)", value=0.0)
                    price_kwh = st.number_input("Prijs per kWh (€)", value=0.40)
                    calc_laad = ((z_km + p_km) / 100) * verbruik_kwh * price_kwh
                    laad_kosten = float(round(calc_laad))
                    laad_kosten = st.number_input("Laadkosten per jaar (€)", value=laad_kosten)
                
            with col3:
                st.markdown("#### Vaste Kosten")
                
                with st.expander("ℹ️ Uitleg Kosten Schatting"):
                    st.write("- **Wegenbelasting:** Automatisch berekend o.b.v. RDW data en provincie.\n- **Onderhoud (schatting):** Berekent € 0,04 per gereden km.\n- **Overig (schatting):** Vaste aanname € 250,- per jaar.\n- **Afschrijving:** Standaard berekend als afschrijving in 5 jaar met een restwaarde van 20% van de aanschafwaarde (handmatig aan te passen).")
                
                gebruik_schatting = st.checkbox("🧮 Vaste kosten schatting toepassen?", value=False)
                
                mrb_jaar = bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)
                mrb = st.number_input("Wegenbelasting per jaar (€)", value=int(mrb_jaar))
                
                calc_onderhoud = round(totaal_km * 0.04) if gebruik_schatting else 0
                onderhoud = st.number_input("Onderhoud per jaar (€)", value=float(calc_onderhoud))
                verzekering = st.number_input("Verzekering per jaar (€)", value=0.0)
                overige = st.number_input("Overige kosten per jaar (€)", value=250.0 if gebruik_schatting else 0.0)
                
                calc_afschr = round((aanschaf * 0.8) * 0.2)
                afschr = st.number_input("Afschrijving per jaar (€)", value=float(calc_afschr))
                
                lease_kosten = 0.0
                rente_kosten = 0.0
                if is_geleased:
                    st.markdown("#### Financiering")
                    st.caption("ℹ️ *Bij Operational Lease zijn Wegenbelasting, Onderhoud en Verzekering vaak al inbegrepen. Zet deze hierboven dan op € 0.*")
                    lease_kosten = st.number_input("Leasekosten per jaar (€)", value=0.0)
                    rente_kosten = st.number_input("Rentekosten lening per jaar (€)", value=0.0)

        tot_k = round(brandstof_kosten + laad_kosten + mrb + onderhoud + verzekering + overige + afschr + lease_kosten + rente_kosten + btw_correctie)
        
        is_gemaximeerd = bijt_bruto > tot_k and not is_minder_dan_500
        bijt_definitief = round(min(bijt_bruto, tot_k) if not is_minder_dan_500 else 0.0)

        zak_aftrek = round(tot_k - bijt_definitief)
        
        # --- BEREKENING MET DE GEKOPPELDE VARIABELE ---
        pri_aftrek = round(z_km * fiscale_regels["km_vergoeding"])
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        var_cost_per_km = 0.0
        if is_brandstof or (not is_brandstof and not is_ev):
            var_cost_per_km += (verbruik_l / 100.0) * prijs_l
        if is_ev:
            var_cost_per_km += (verbruik_kwh / 100.0) * price_kwh
        if gebruik_schatting:
            var_cost_per_km += 0.04
            
        vaste_kosten = mrb + (0.0 if gebruik_schatting else onderhoud) + verzekering + overige + afschr + lease_kosten + rente_kosten + btw_correctie
        vaste_prive_km_kosten = var_cost_per_km * p_km
        
        omslagpunt = None
        richting = ""
        
        def sim_verschil(z):
            sim_k = vaste_kosten + vaste_prive_km_kosten + (var_cost_per_km * z)
            sim_b = 0.0 if is_minder_dan_500 else min(bijt_bruto, sim_k)
            # Simuleer de vergoeding met de ingestelde variabele
            return (sim_k - sim_b) - (z * fiscale_regels["km_vergoeding"])
            
        if advies == "Privé voordeliger":
            sign_0 = sim_verschil(0) > 0 
            for test_z in range(100, 150001, 100): 
                if (sim_verschil(test_z) > 0) != sign_0:
                    omslagpunt = test_z
                    break
            
            if omslagpunt:
                if z_km > omslagpunt:
                    richting = "minder"
                else:
                    richting = "meer"

        with st.container(border=True):
            st.markdown("### 📊 3. Resultaat & Fiscaal Advies")
            
            st.markdown(f"""
            <div style="background-color: {VVAA_ORANJE}; color: white; padding: 16px; border-radius: 8px; text-align: center; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(232, 78, 15, 0.2);">
                <span style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 500;">Conclusie Fiscaal Advies</span><br>
                <div style="color: white !important; margin: 4px 0 0 0; font-size: 1.4rem; font-weight: bold;">{advies.upper()}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if is_gemaximeerd:
                st.warning(f"**Let op: Bijtelling gemaximeerd.** Uw berekende bijtelling (€ {fmt(bijt_bruto)}) is hoger dan de totale werkelijke autokosten (€ {fmt(tot_k)}). U hoeft niet meer bij te tellen dan uw autokosten. Uw bijtelling is afgetopt op € {fmt(bijt_definitief)}.")
                
            if advies == "Privé voordeliger" and omslagpunt:
                st.info(f"⚖️ **Tip van de adviseur:** Zakelijk rijden wordt in deze situatie pas voordeliger bij **{richting} dan {fmt(omslagpunt)} zakelijke kilometers** per jaar.")
            
            zak_lijst = [
                ("Brandstof / Laadkosten", brandstof_kosten + laad_kosten),
                ("Wegenbelasting", mrb),
                ("Onderhoud", onderhoud),
                ("Verzekering", verzekering),
                ("Overige autokosten", overige),
                ("Afschrijving", afschr)
            ]
            if is_geleased:
                zak_lijst.append(("Leasekosten", lease_kosten))
                zak_lijst.append(("Rentekosten", rente_kosten))
            if is_btw_klant:
                zak_lijst.append(("Btw-correctie privégebruik", btw_correctie))
                
            zak_html = ""
            for lbl, val in zak_lijst:
                zak_html += f"<div style='display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed #F0F4F8;'><span>{lbl}</span><span>€ {fmt(val)}</span></div>"
            
            # Formatting the km text properly for NL rules
            km_text = f"€ {fiscale_regels['km_vergoeding']:.2f}".replace('.', ',')
            
            html_result = f"""<div style='display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap;'>
<div style='flex: 1; min-width: 300px; display: flex; flex-direction: column; background: #FFFFFF; padding: 25px; border-radius: 12px; border-top: 6px solid {VVAA_BLAUW}; box-shadow: 0 4px 12px rgba(0, 49, 92, 0.08); border: 1px solid #E0E6ED;'>
<h4 style='color: {VVAA_BLAUW}; margin-top: 0; margin-bottom: 20px; font-size: 1.2rem; border: none; padding-top: 0;'><span style='font-size:1.2em;'>🏢</span> Auto Zakelijk</h4>

<div style='font-size: 0.95em; color: #4A5568; margin-bottom: 15px;'>
{zak_html}
</div>

<div style='display: flex; justify-content: space-between; border-top: 2px solid #F0F4F8; padding-top: 10px; margin-bottom: 10px;'>
<span style='color: #4A5568; font-weight: bold;'>Totale autokosten per jaar</span>
<strong style='color: {VVAA_BLAUW};'>€ {fmt(tot_k)}</strong>
</div>
<div style='display: flex; justify-content: space-between; padding-bottom: 15px; margin-bottom: 20px;'>
<span style='color: {VVAA_ORANJE}; font-weight: bold;'>Bijtelling {"(afgetopt)" if is_gemaximeerd else ("(< 500km)" if is_minder_dan_500 else "")}</span>
<strong style='color: {VVAA_ORANJE};'>- € {fmt(bijt_definitief)}</strong>
</div>

<div style='text-align: center; background: {VVAA_LICHTORANJE}; padding: 20px; border-radius: 8px; border: 1px solid #F0D5C9; margin-top: auto;'>
<span style='color: {VVAA_BLAUW}; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;'>Fiscale Aftrekpost</span>
<h2 style='color: {VVAA_ORANJE}; margin: 8px 0 0 0; font-size: 2.2rem;'>€ {fmt(zak_aftrek)}</h2>
</div>
</div>

<div style='flex: 1; min-width: 300px; display: flex; flex-direction: column; background: #FFFFFF; padding: 25px; border-radius: 12px; border-top: 6px solid {VVAA_BLAUW}; box-shadow: 0 4px 12px rgba(0, 49, 92, 0.08); border: 1px solid #E0E6ED;'>
<h4 style='color: {VVAA_BLAUW}; margin-top: 0; margin-bottom: 20px; font-size: 1.2rem; border: none; padding-top: 0;'><span style='font-size:1.2em;'>🏠</span> Auto Privé</h4>

<div style='font-size: 0.95em; color: #4A5568; margin-bottom: 15px;'>
    <div style='display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed #F0F4F8;'><span>Vergoeding per zakelijke km</span><span>{km_text}</span></div>
    <div style='display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed #F0F4F8;'><span>Aantal zakelijke km</span><span>{fmt(z_km)}</span></div>
</div>

<div style='display: flex; justify-content: space-between; border-top: 2px solid #F0F4F8; padding-top: 10px; margin-bottom: 20px; padding-bottom: 15px;'>
<span style='color: #4A5568; font-weight: bold;'>Totale vergoeding (Aftrekpost)</span>
<strong style='color: {VVAA_BLAUW};'>€ {fmt(pri_aftrek)}</strong>
</div>

<div style='text-align: center; background: {VVAA_LICHTORANJE}; padding: 20px; border-radius: 8px; border: 1px solid #F0D5C9; margin-top: auto;'>
<span style='color: {VVAA_BLAUW}; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;'>Fiscale Aftrekpost</span>
<h2 style='color: {VVAA_ORANJE}; margin: 8px 0 0 0; font-size: 2.2rem;'>€ {fmt(pri_aftrek)}</h2>
</div>
</div>
</div>"""
            st.markdown(html_result, unsafe_allow_html=True)

        if gevalideerd:
            data_rows = [
                [("Relatie:", klant_naam), ("Merk & Type:", f"{auto['merk']} {auto['handelsbenaming']}")],
                [("Lidnummer:", klant_nummer), ("Kenteken:", kenteken_input)],
                [("", ""), ("Brandstof:", brandstof_t)],
                [("", ""), ("Eerste toelating:", f"{toelating_nl} ({leeftijd.years} jaar)")],
                [("", ""), ("Cataloguswaarde:", f"EUR {fmt(auto['catalogusprijs'])}")],
                [("", ""), ("Aanschaf/Taxatie:", f"EUR {fmt(aanschaf)}")]
            ]
            
            keuzes = [
                f"Verwachte kilometers: {fmt(z_km)} zakelijk / {fmt(p_km)} privé per jaar.",
                f"Gekozen bijtellingsprofiel: {gekozen_bijt}.",
                f"Youngtimer regeling toegepast: {'Ja' if is_young_manual else 'Nee'}.",
                f"Minder dan 500 km privé per jaar: {'Ja (Geen bijtelling berekend)' if is_minder_dan_500 else 'Nee'}.",
                f"Ondernemer voor de btw: {'Ja (Autokosten exclusief btw)' if is_btw_klant else 'Nee (Autokosten inclusief btw)'}.",
                f"Voertuig wordt geleased of gefinancierd: {'Ja' if is_geleased else 'Nee'}."
            ]

            left_items = [
                ("Brandstof / Laadkosten", f"EUR {fmt(brandstof_kosten+laad_kosten)}"),
                ("Wegenbelasting", f"EUR {fmt(mrb)}"),
                ("Onderhoud", f"EUR {int(round(onderhoud))}"),
                ("Verzekering", f"EUR {int(round(verzekering))}"),
                ("Overige autokosten", f"EUR {fmt(overige)}"),
                ("Afschrijving", f"EUR {fmt(afschr)}")
            ]
            if is_geleased:
                left_items.append(("Leasekosten", f"EUR {fmt(lease_kosten)}"))
                left_items.append(("Rentekosten", f"EUR {fmt(rente_kosten)}"))
            if is_btw_klant:
                left_items.append(("Btw-correctie privégebruik", f"EUR {fmt(btw_correctie)}"))

            # Gebruik de variabele km_text ook in de PDF
            pdf_km_text = f"EUR {fiscale_regels['km_vergoeding']:.2f}".replace('.', ',')
            
            right_items = [
                ("Vergoeding per zakelijke km", pdf_km_text),
                ("Aantal zakelijke km", f"{fmt(z_km)}"),
                ("", ""), ("", ""), ("", ""), ("", "")
            ]
            max_len = max(len(left_items), len(right_items))

            punten = [
                "- De getoonde berekening is een indicatie op basis van uw eigen opgave en algemene aannames. De werkelijke cijfers kunnen hiervan afwijken.",
                "- Wegenbelasting is berekend op basis van de actuele Belastingdienst tarieven.", 
                "- Na 5 jaar na aanschaf vervallen in de regel de afschrijvingskosten.", 
                "- Let op: Bij latere inruil of verkoop van een zakelijke auto kan een boekwinst ontstaan, welke belast is in de onderneming."
            ]
            if is_minder_dan_500:
                punten.insert(0, "- LET OP: Voor 0% bijtelling is een sluitende rittenadministratie of 'Verklaring geen privégebruik auto' vereist.")
            if is_gemaximeerd:
                punten.insert(0, "- LET OP: De berekende bijtelling was hoger dan de totale kosten. U hoeft fiscaal niet meer bij te tellen dan uw werkelijke kosten. Uw bijtelling is daarom afgetopt.")
            if is_btw_klant:
                punten.insert(0, "- LET OP: De berekende btw-correctie is gebaseerd op het forfait. Deze kan in de praktijk afwijken (bijv. als er aantoonbare privé kilometers zijn, of indien het bedrag hoger uitvalt dan de in dat jaar afgetrokken btw).")

            is_heavy = (max_len > 6) or (len(punten) > 4)
            
            gap_large = 6 if is_heavy else 10
            gap_med = 4 if is_heavy else 6
            tbl_row = 5.5 if is_heavy else 6.5
            tot_row = 6 if is_heavy else 7
            aft_row = 8 if is_heavy else 9
            ban_h = 10 if is_heavy else 12
            disclaimer_h = 3.5 if is_heavy else 4
            
            pdf = VVAAPDF()
            pdf.set_auto_page_break(auto=True, margin=15) 
            pdf.add_page()
            f = pdf.font_fam
            
            pdf.set_y(35)
            pdf.set_fill_color(249, 232, 223) 
            pdf.set_draw_color(249, 232, 223)
            pdf.rect(10, 35, 190, 42, 'DF') 
            
            pdf.set_xy(15, 38) 
            pdf.set_font(f, 'B', 12)
            pdf.set_text_color(0, 49, 92)
            pdf.cell(90, 6, clean_text("1. Relatiegegevens"), ln=False)
            pdf.cell(90, 6, clean_text("2. Voertuigspecificaties"), ln=True)
            
            pdf.set_font(f, '', 10)
            pdf.set_text_color(0, 0, 0)
            
            pdf.set_y(45) 
            for row in data_rows:
                pdf.set_x(15)
                pdf.set_font(f, 'B', 10); pdf.cell(25, 4.5, clean_text(row[0][0]))
                pdf.set_font(f, '', 10); pdf.cell(65, 4.5, clean_text(row[0][1]))
                pdf.set_font(f, 'B', 10); pdf.cell(35, 4.5, clean_text(row[1][0]))
                pdf.set_font(f, '', 10); pdf.cell(50, 4.5, clean_text(row[1][1]), ln=True)

            pdf.ln(gap_large)

            pdf.set_font(f, 'B', 12)
            pdf.set_text_color(0, 49, 92)
            pdf.cell(0, 6, clean_text("3. Uitgangspunten voor berekening"), ln=True)
            
            pdf.set_draw_color(200, 210, 220)
            pdf.set_line_width(0.3)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2 if is_heavy else 3)

            pdf.set_font(f, '', 10)
            pdf.set_text_color(0, 0, 0)
            
            for k in keuzes:
                pdf.cell(5, 4.5, "-")
                pdf.cell(0, 4.5, clean_text(k), ln=True)

            pdf.ln(gap_med)

            pdf.set_font(f, 'B', 14)
            pdf.set_text_color(0, 49, 92)
            pdf.cell(0, 8, clean_text("4. Financiële Vergelijking (Per Jaar)"), ln=True)

            pdf.set_font(f, 'B', 10)
            pdf.set_text_color(232, 78, 15)
            
            y_line = pdf.get_y() + (7 if is_heavy else 8)
            pdf.set_draw_color(232, 78, 15)
            pdf.set_line_width(0.5)
            pdf.line(10, y_line, 100, y_line) 
            pdf.line(110, y_line, 200, y_line) 
            
            pdf.cell(90, (7 if is_heavy else 8), clean_text(" AUTO ZAKELIJK"), align='L')
            pdf.cell(10, (7 if is_heavy else 8), "") 
            pdf.cell(90, (7 if is_heavy else 8), clean_text(" AUTO PRIVÉ"), align='L', ln=True)

            pdf.set_text_color(0, 49, 92)
            
            for i in range(max_len):
                l_lbl, l_val = left_items[i] if i < len(left_items) else ("", "")
                r_lbl, r_val = right_items[i] if i < len(right_items) else ("", "")

                fill = True if i % 2 == 0 else False
                pdf.set_fill_color(249, 232, 223) 

                pdf.set_font(f, '', 10)
                pdf.cell(60, tbl_row, clean_text(f" {l_lbl}"), fill=fill)
                pdf.set_font(f, 'B' if l_val else '', 10)
                pdf.cell(30, tbl_row, clean_text(l_val), align='R', fill=fill)
                
                pdf.cell(10, tbl_row, "", fill=False) 

                pdf.set_font(f, '', 10)
                pdf.cell(60, tbl_row, clean_text(f" {r_lbl}"), fill=fill)
                pdf.set_font(f, 'B' if r_val else '', 10)
                pdf.cell(30, tbl_row, clean_text(r_val), align='R', fill=fill, ln=True)

            pdf.set_draw_color(0, 49, 92)
            pdf.set_line_width(0.2)
            y_line = pdf.get_y()
            pdf.line(10, y_line, 100, y_line) 
            
            pdf.set_fill_color(249, 232, 223) 
            pdf.set_font(f, 'B', 10)
            pdf.cell(60, tot_row, clean_text(" Totale autokosten"), fill=False)
            pdf.cell(30, tot_row, clean_text(f"EUR {fmt(tot_k)}"), align='R', fill=False)
            pdf.cell(10, tot_row, "")
            pdf.cell(90, tot_row, "", fill=False, ln=True)

            lbl_bijt = " Bijtelling (gemaximeerd)" if is_gemaximeerd else (" Bijtelling (< 500km)" if is_minder_dan_500 else " Bijtelling")
            pdf.set_text_color(232, 78, 15) 
            pdf.cell(60, tot_row, clean_text(lbl_bijt), fill=False)
            pdf.cell(30, tot_row, clean_text(f"- EUR {fmt(bijt_definitief)}"), align='R', fill=False)
            pdf.cell(10, tot_row, "")
            pdf.cell(90, tot_row, "", fill=False, ln=True)

            y_line = pdf.get_y()
            pdf.set_draw_color(0, 49, 92)
            pdf.line(10, y_line, 100, y_line)
            pdf.line(110, y_line, 200, y_line)
            
            pdf.set_fill_color(249, 232, 223)
            pdf.set_text_color(0, 49, 92)
            pdf.set_font(f, 'B', 11)
            pdf.rect(10, y_line, 90, aft_row, 'F')
            pdf.rect(110, y_line, 90, aft_row, 'F')
            
            pdf.set_y(y_line)
            pdf.cell(60, aft_row, clean_text(" FISCALE AFTREKPOST"), fill=False)
            pdf.cell(30, aft_row, clean_text(f"EUR {fmt(zak_aftrek)}"), align='R', fill=False)
            pdf.cell(10, aft_row, "")
            pdf.cell(60, aft_row, clean_text(" FISCALE AFTREKPOST"), fill=False)
            pdf.cell(30, aft_row, clean_text(f"EUR {fmt(pri_aftrek)}"), align='R', fill=False, ln=True)

            pdf.ln(gap_large)

            y_conclusie = pdf.get_y()
            pdf.set_fill_color(249, 232, 223) 
            pdf.rect(10, y_conclusie, 190, ban_h, 'F')
            pdf.set_fill_color(232, 78, 15)
            pdf.rect(10, y_conclusie, 3, ban_h, 'F') 
            
            pdf.set_y(y_conclusie + (ban_h/2) - 3)
            pdf.set_font(f, 'B', 12)
            pdf.set_text_color(0, 49, 92)
            pdf.cell(4, 6, "")
            pdf.cell(180, 6, clean_text(f"Conclusie: Vanuit fiscaal oogpunt is {advies.lower()}."), ln=True, align='L')
            pdf.set_y(y_conclusie + ban_h)
            
            pdf.ln(gap_med)

            pdf.set_text_color(0, 49, 92)
            pdf.set_font(f, 'B', 10)
            pdf.cell(0, 5, clean_text("Belangrijke aandachtspunten bij dit advies:"), ln=True)
            pdf.set_text_color(80, 80, 80) 
            pdf.set_font(f, '', 8)
            
            for p in punten: 
                pdf.multi_cell(0, disclaimer_h, clean_text(p))

            fname = f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}_{klant_nummer}.pdf"
            st.download_button("📄 Fiscaal Rapport Downloaden (.PDF)", data=pdf.output(dest='S').encode('latin-1'), file_name=fname)

            # --- MAGIC EMAIL GENERATOR ---
            st.markdown("---")
            st.markdown("### ✉️ Concept E-mail naar klant")
            
            voornaam = klant_naam.split(' ')[0] if klant_naam else "klant"
            
            email_text = f"""Beste {voornaam},

Hierbij ontvang je de aangevraagde autoberekening voor de {auto['merk'].title()} {auto['handelsbenaming'].title()}. 

We hebben deze berekening gemaakt op basis van de door jou doorgegeven verwachting van {fmt(z_km)} zakelijke en {fmt(p_km)} privé kilometers per jaar.

Uit onze analyse blijkt dat het in deze situatie fiscaal het meest voordelig is om de auto {advies.split(' ')[0].lower()} te rijden.

In de bijlage vind je het uitgebreide rapport met de exacte kostenopbouw, de gemaakte aannames en de vergelijking van het uiteindelijke belastingvoordeel. 

Mocht je nog vragen hebben of de berekening willen aanpassen met andere kilometers of bedragen, laat het ons dan gerust weten!"""
            
            st.caption("Gebruik het handige **kopieer-icoontje rechtsbovenin het blok** hieronder om de hele tekst in één keer te kopiëren voor in je Outlook e-mail.")
            
            st.code(email_text, language="text")
            
            subject = f"Autoberekening voor de {auto['merk'].title()} {auto['handelsbenaming'].title()}"
            mailto_url = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(email_text)}"
            
            st.markdown(f"""
            <a href="{mailto_url}" target="_blank" style="text-decoration: none;">
                <div style="background-color: {VVAA_BLAUW}; color: white; padding: 12px 24px; border-radius: 8px; text-align: center; font-weight: bold; margin-top: 15px; box-shadow: 0 4px 6px rgba(0, 49, 92, 0.15); transition: all 0.3s ease;">
                    📧 Open direct in Outlook (Nieuw bericht)
                </div>
            </a>
            """, unsafe_allow_html=True)
            
        else:
            st.info("ℹ️ Vul de Naam en een numeriek Lidnummer in om het rapport te kunnen genereren.")
    else:
        st.error(f"❌ Geen voertuig gevonden in de RDW-database voor kenteken '{kenteken_input}'. Controleer het kenteken en probeer het opnieuw.")
