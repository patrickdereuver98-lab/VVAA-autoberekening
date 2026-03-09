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
VVAA_LICHTORANJE = "#F9E8DF" 
VVAA_GRIJS = "#F4F6F8" 
VVAA_MELDING_ORANJE = "#FDCEA8"

st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = f"""
<style>
    /* --- 1. ALGEMENE SCALING --- */
    html, body {{
        font-size: 0.92rem !important;
    }}
    
    /* --- 2. MODERNE HEADERS & UITLIJNING --- */
    h3 {{ border-bottom: 2px solid {VVAA_ORANJE} !important; padding-bottom: 8px !important; margin-bottom: 20px !important; font-size: 1.3rem !important; }}
    
    [data-testid="column"] h4 {{
        margin-top: 0 !important;
        margin-bottom: 12px !important;
        padding-top: 0 !important;
        font-size: 1.05rem !important;
        color: {VVAA_ORANJE} !important;
    }}

    /* --- 3. MODERNE CARDS (Witte vlakken voor de layout) --- */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 15px rgba(0, 49, 92, 0.05) !important;
        padding: 15px !important;
    }}

    /* --- 4. SPECIFIEKE TWEAKS --- */
    /* Forceer hoofdletters specifiek in het kenteken veld */
    input[aria-label="Kenteken *"] {{
        text-transform: uppercase !important;
    }}

    /* --- 5. KNOPPEN (BUTTONS) --- */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; color: white !important; 
        border-radius: 6px; border: none; padding: 10px 24px; font-weight: bold; width: 100%; margin-top: 28px;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{ background-color: #C7400A !important; transform: translateY(-1px); box-shadow: 0 4px 8px rgba(232, 78, 15, 0.3) !important; }}
    
    div.stDownloadButton > button {{ 
        background-color: {VVAA_BLAUW} !important; color: white !important; border-radius: 8px !important;
        padding: 15px 32px !important; font-size: 18px !important; font-weight: bold !important; width: 100% !important;
        box-shadow: 0 4px 6px rgba(0, 49, 92, 0.15) !important; border: none !important; transition: all 0.3s ease;
        display: block !important;
    }}
    div.stDownloadButton > button:hover {{ background-color: #001F3F !important; transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0, 49, 92, 0.25) !important; }}
    
    /* --- 6. MELDINGEN & ALERTS --- */
    div[data-testid="stAlert"] {{ 
        background-color: transparent !important;
        background: transparent !important;
        border: none !important; 
        padding: 0 !important; 
    }}
    div[data-testid="stAlert"] > div[role="alert"] {{
        background-color: {VVAA_MELDING_ORANJE} !important; 
        color: {VVAA_BLAUW} !important; 
        border-radius: 8px !important;
        padding: 16px !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
        border: 1px solid #F0D5C9 !important;
    }}
    div[data-testid="stAlert"] * {{ color: {VVAA_BLAUW} !important; }}
    div[data-testid="stAlert"] svg {{ fill: {VVAA_BLAUW} !important; }}
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

@st.cache_data
def load_mrb_data():
    try:
        return pd.read_csv("mrb_tarieven_2026.csv"), pd.read_csv("mrb_provincies_2026.csv")
    except:
        return None, None

df_mrb, df_prov = load_mrb_data()

# --- 4. MODERNE HEADER LAYOUT ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    logo_path = "VvAA_logo.png" 
    if os.path.exists(logo_path):
        st.image(logo_path, width=130) 
with col_title:
    st.markdown(f"<h2 style='color: {VVAA_BLAUW}; margin: 0; padding-top: 15px;'>Autoberekening: Zakelijk of Privé?</h2>", unsafe_allow_html=True)
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

            st.markdown("---")
            st.markdown("### 💶 Financiële Specificaties")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("#### Waarde & Bijtelling")
                
                with st.expander("ℹ️ Uitleg Waarde & Bijtelling"):
                    st.write("Selecteer het juiste bijtellingsprofiel. De berekende bijtelling wordt automatisch gemaximeerd (afgetopt) als deze onverhoopt hoger uitvalt dan de totale werkelijke autokosten.")
                
                # Kleur toegevoegd aan de div zodat deze altijd netjes blauw blijft en niet grijs wordt
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
                
            with col2:
                st.markdown("#### Verbruik & Brandstof")
                
                with st.expander("ℹ️ Uitleg Brandstof & Bron"):
                    st.write("De voorgestelde literprijs is gebaseerd op de actuele gemiddelde landelijke adviesprijs (bron: UnitedConsumers). De kosten worden berekend via de formule: *(Totale km / 100) × Verbruik × Literprijs*.")
                
                brandstof_kosten = 0.0
                laad_kosten = 0.0
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
                    st.markdown(f"<div style='height: 35px; display: flex; align-items: center; color: {VVAA_BLAUW};'>Stroomprijs berekend op € 0,40 / kWh.</div>", unsafe_allow_html=True)
                    verbruik_kwh = st.number_input("Verbruik Stroom (kWh/100km)", value=0.0)
                    price_kwh = 0.40
                    calc_laad = ((z_km + p_km) / 100) * verbruik_kwh * price_kwh
                    laad_kosten = float(round(calc_laad))
                    laad_kosten = st.number_input("Laadkosten per jaar (€)", value=laad_kosten)
                
            with col3:
                st.markdown("#### Vaste Kosten")
                
                with st.expander("ℹ️ Uitleg Kosten Schatting"):
                    st.write("- **Wegenbelasting:** Automatisch berekend o.b.v. RDW data en provincie.\n- **Onderhoud (schatting):** Berekent € 0,04 per gereden km.\n- **Overig (schatting):** Vaste aanname € 250,- per jaar.")
                
                gebruik_schatting = st.checkbox("🧮 Vaste kosten schatting toepassen?", value=False)
                
                mrb_jaar = bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)
                mrb = st.number_input("Wegenbelasting per jaar (€)", value=int(mrb_jaar))
                
                calc_onderhoud = round(totaal_km * 0.04) if gebruik_schatting else 0
                onderhoud = st.number_input("Onderhoud per jaar (€)", value=float(calc_onderhoud))
                verzekering = st.number_input("Verzekering per jaar (€)", value=0.0)
                overige = st.number_input("Overige kosten per jaar (€)", value=250.0 if gebruik_schatting else 0.0)
                
                lease_kosten = 0.0
                rente_kosten = 0.0
                if is_geleased:
                    st.markdown("#### Financiering")
                    st.caption("ℹ️ *Bij Operational Lease zijn Wegenbelasting, Onderhoud en Verzekering vaak al inbegrepen. Zet deze hierboven dan op € 0.*")
                    lease_kosten = st.number_input("Leasekosten per jaar (€)", value=0.0)
                    rente_kosten = st.number_input("Rentekosten lening per jaar (€)", value=0.0)

        afschr = round((aanschaf * 0.8) * 0.2)
        tot_k = round(brandstof_kosten + laad_kosten + mrb + onderhoud + verzekering + overige + afschr + lease_kosten + rente_kosten)
        
        is_gemaximeerd = bijt_bruto > tot_k and not is_minder_dan_500
        bijt_definitief = round(min(bijt_bruto, tot_k) if not is_minder_dan_500 else 0.0)

        zak_aftrek = round(tot_k - bijt_definitief)
        pri_aftrek = round(z_km * 0.23)
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        with st.container(border=True):
            st.markdown("### 📊 3. Resultaat & Fiscaal Advies")
            
            if is_gemaximeerd:
                st.warning(f"**Let op: Bijtelling gemaximeerd.** Uw berekende bijtelling (€ {fmt(bijt_bruto)}) is hoger dan de totale werkelijke autokosten (€ {fmt(tot_k)}). U hoeft niet meer bij te tellen dan uw autokosten. Uw bijtelling is afgetopt op € {fmt(bijt_definitief)}.")
                
            st.success(f"**Conclusie:** Vanuit fiscaal oogpunt is de optie **{advies}**.")
            
            html_result = f"""<div style='display: flex; gap: 20px; margin-top: 20px; margin-bottom: 20px; flex-wrap: wrap;'>
<div style='flex: 1; min-width: 300px; background: #FFFFFF; padding: 25px; border-radius: 12px; border-top: 6px solid {VVAA_BLAUW}; box-shadow: 0 4px 12px rgba(0, 49, 92, 0.08); border: 1px solid #E0E6ED;'>
<h4 style='color: {VVAA_BLAUW}; margin-top: 0; margin-bottom: 20px; font-size: 1.2rem; border: none; padding-top: 0;'><span style='font-size:1.2em;'>🏢</span> Auto Zakelijk</h4>
<div style='display: flex; justify-content: space-between; border-bottom: 1px solid #F0F4F8; padding-bottom: 10px; margin-bottom: 10px;'>
<span style='color: #4A5568;'>Totale kosten per jaar</span>
<strong style='color: {VVAA_BLAUW};'>€ {fmt(tot_k)}</strong>
</div>
<div style='display: flex; justify-content: space-between; border-bottom: 1px solid #F0F4F8; padding-bottom: 10px; margin-bottom: 20px;'>
<span style='color: #4A5568;'>Bijtelling {"(afgetopt)" if is_gemaximeerd else ("(< 500km)" if is_minder_dan_500 else "")}</span>
<strong style='color: {VVAA_BLAUW};'>- € {fmt(bijt_definitief)}</strong>
</div>
<div style='text-align: center; background: {VVAA_LICHTORANJE}; padding: 20px; border-radius: 8px; border: 1px solid #F0D5C9;'>
<span style='color: {VVAA_BLAUW}; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;'>Fiscale Aftrekpost</span>
<h2 style='color: {VVAA_ORANJE}; margin: 8px 0 0 0; font-size: 2.2rem;'>€ {fmt(zak_aftrek)}</h2>
</div>
</div>

<div style='flex: 1; min-width: 300px; background: #FFFFFF; padding: 25px; border-radius: 12px; border-top: 6px solid {VVAA_BLAUW}; box-shadow: 0 4px 12px rgba(0, 49, 92, 0.08); border: 1px solid #E0E6ED;'>
<h4 style='color: {VVAA_BLAUW}; margin-top: 0; margin-bottom: 20px; font-size: 1.2rem; border: none; padding-top: 0;'><span style='font-size:1.2em;'>🏠</span> Auto Privé</h4>
<div style='display: flex; justify-content: space-between; border-bottom: 1px solid #F0F4F8; padding-bottom: 10px; margin-bottom: 10px;'>
<span style='color: #4A5568;'>Vergoeding per km</span>
<strong style='color: {VVAA_BLAUW};'>€ 0,23</strong>
</div>
<div style='display: flex; justify-content: space-between; border-bottom: 1px solid #F0F4F8; padding-bottom: 10px; margin-bottom: 20px;'>
<span style='color: #4A5568;'>Aantal zakelijke km</span>
<strong style='color: {VVAA_BLAUW};'>{fmt(z_km)}</strong>
</div>
<div style='text-align: center; background: {VVAA_LICHTORANJE}; padding: 20px; border-radius: 8px; border: 1px solid #F0D5C9;'>
<span style='color: {VVAA_BLAUW}; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;'>Fiscale Aftrekpost</span>
<h2 style='color: {VVAA_ORANJE}; margin: 8px 0 0 0; font-size: 2.2rem;'>€ {fmt(pri_aftrek)}</h2>
</div>
</div>
</div>"""
            st.markdown(html_result, unsafe_allow_html=True)

        if gevalideerd:
            def clean(t): return str(t).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')
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
                    self.set_fill_color(232, 78, 15); self.rect(0, 0, 210, 15, 'F')
                    logo = "VvAA_logo.png" 
                    if os.path.exists(logo): self.image(logo, 10, 20, 35)
                    
                def footer(self):
                    self.set_y(-15); self.set_fill_color(0, 49, 92); self.rect(0, 282, 210, 15, 'F')
                    self.set_text_color(255); self.set_font(self.font_fam, '', 9); 
                    self.cell(0, 15, clean("VvAA | www.vvaa.nl | Voor zorgverleners, door zorgverleners"), align='C', ln=True)

            pdf = VVAAPDF(); pdf.set_auto_page_break(auto=False); pdf.add_page()
            f = pdf.font_fam
            
            pdf.set_font(f, 'B', 16); pdf.set_text_color(0, 49, 92); pdf.set_xy(10, 45)
            pdf.cell(0, 10, clean(f"Autoberekening: Zakelijk of Privé?"), ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)

            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "1. Relatiegegevens", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0)
            pdf.cell(35, 5, "Relatie:"); pdf.cell(70, 5, clean(klant_naam)); pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Lidnummer:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)

            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "2. Voertuigspecificaties", ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input})"), fill=True, ln=True)
            pdf.cell(35, 6, " Brandstof:", fill=True); pdf.cell(155, 6, brandstof_t, fill=True, ln=True)
            pdf.cell(35, 6, " Eerste toelating:", fill=True); pdf.cell(155, 6, clean(f"{toelating_nl} ({leeftijd.years} jaar, {leeftijd.months} mnd)"), fill=True, ln=True)
            pdf.cell(35, 6, " Youngtimer:", fill=True); pdf.cell(155, 6, "Ja" if is_young_manual else "Nee", fill=True, ln=True)
            pdf.cell(35, 6, " < 500 km prive:", fill=True); pdf.cell(155, 6, "Ja (Geen bijtelling)" if is_minder_dan_500 else "Nee", fill=True, ln=True)
            pdf.cell(35, 6, " Lease auto:", fill=True); pdf.cell(155, 6, "Ja" if is_geleased else "Nee", fill=True, ln=True); pdf.ln(2)
            
            pdf.cell(45, 5, "Cataloguswaarde:"); pdf.cell(45, 5, clean(f"EUR {fmt(auto['catalogusprijs'])}"), align='R')
            pdf.cell(10, 5); pdf.cell(45, 5, "Aanschaf/Taxatie:"); pdf.cell(45, 5, clean(f"EUR {fmt(aanschaf)}"), align='R', ln=True)
            pdf.cell(45, 5, "Bijtellingsprofiel:"); pdf.set_font(f, '', 9); pdf.cell(145, 5, clean(gekozen_bijt), ln=True); pdf.ln(3)

            pdf.set_font(f, 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True)
            pdf.set_font(f, '', 10); pdf.set_text_color(0); pdf.ln(2)
            
            left_col = []
            left_col.append(("Brandstofkosten:", clean(f"EUR {fmt(brandstof_kosten+laad_kosten)}")))
            left_col.append(("Wegenbelasting:", clean(f"EUR {fmt(mrb)}")))
            left_col.append(("Onderhoud:", clean(f"EUR {int(round(onderhoud))}")))
            left_col.append(("Verzekering:", clean(f"EUR {int(round(verzekering))}")))
            left_col.append(("Overige autokosten:", clean(f"EUR {fmt(overige)}")))
            left_col.append(("Afschrijving:", clean(f"EUR {fmt(afschr)}")))
            
            if is_geleased:
                left_col.append(("Leasekosten:", clean(f"EUR {fmt(lease_kosten)}")))
                left_col.append(("Rentekosten:", clean(f"EUR {fmt(rente_kosten)}")))
            
            right_col = [("Vergoeding:", clean(f"EUR {fmt(pri_aftrek)}")), ("Zakelijke km:", fmt(z_km)), ("Tarief p/km:", "EUR 0,23")]
            
            max_rows = max(len(left_col), len(right_col))
            for i in range(max_rows):
                l1, v1 = left_col[i] if i < len(left_col) else ("", "")
                l2, v2 = right_col[i] if i < len(right_col) else ("", "")
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5)
                pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)

            pdf.ln(2); pdf.set_font(f, 'B', 10)
            pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, clean(f"EUR {fmt(tot_k)}"), align='R', ln=True)
            
            lbl_bijt = "Bijtelling (gemaximeerd):" if is_gemaximeerd else ("Bijtelling (< 500km):" if is_minder_dan_500 else "Bijtelling:")
            pdf.cell(45, 6, lbl_bijt); pdf.cell(45, 6, clean(f"- EUR {fmt(bijt_definitief)}"), align='R', ln=True); pdf.ln(2)
            
            pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, clean(f"EUR {fmt(zak_aftrek)} "), fill=True, align='R')
            pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, clean(f"EUR {fmt(pri_aftrek)} "), fill=True, align='R', ln=True); pdf.ln(5)
            
            pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255, 255, 255); pdf.set_font(f, 'B', 11)
            pdf.cell(190, 10, clean(f"  Advies vanuit fiscaal oogpunt: {advies}"), fill=True, ln=True); pdf.ln(4)
            
            pdf.set_text_color(0, 49, 92); pdf.set_font(f, 'B', 10); pdf.cell(0, 5, "Aandachtspunten bij zakelijk rijden:", ln=True)
            pdf.set_font(f, '', 8); pdf.set_text_color(0, 0, 0)
            
            punten = [
                "- De getoonde berekening is een schatting op basis van uw eigen opgave. De werkelijke cijfers kunnen hiervan afwijken.",
                "- Wegenbelasting is gebaseerd op Belastingdienst tarieven 2026.", 
                "- Na 5 jaar vervallen de afschrijvingskosten.", 
                "- Bij inruil kan een boekwinst ontstaan, welke belast kan zijn in de onderneming."
            ]
            if is_minder_dan_500:
                punten.insert(0, "- LET OP: Voor 0% bijtelling is een sluitende rittenadministratie of verklaring vereist.")
            if is_gemaximeerd:
                punten.insert(0, "- LET OP: De berekende bijtelling was hoger dan de totale kosten, en is daarom gemaximeerd.")
                
            for p in punten: pdf.cell(0, 4, clean(p), ln=True)

            fname = f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}_{klant_nummer}.pdf"
            st.download_button("📄 Autoberekening Downloaden", data=pdf.output(dest='S').encode('latin-1'), file_name=fname)
        else:
            st.info("ℹ️ Vul de Naam en een numeriek Lidnummer in om het rapport te kunnen genereren.")
    else:
        st.error(f"❌ Geen voertuig gevonden in de RDW-database voor kenteken '{kenteken_input}'. Controleer het kenteken en probeer het opnieuw.")
