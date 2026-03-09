import streamlit as st
import requests
import datetime
import os
import pandas as pd
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
    
    /* Bereken knop */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; color: white !important; 
        border-radius: 4px; border: none; padding: 10px 24px; font-weight: bold; width: 100%; margin-top: 28px; 
    }}
    
    /* Grote Download PDF Knop met witte tekst */
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
    }}
    div.stDownloadButton > button p, div.stDownloadButton > button span {{
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

# --- DATA LADEN UIT CSV (PUNT 4: TABELLEN) ---
@st.cache_data
def load_mrb_data():
    try:
        tarieven = pd.read_csv("mrb_tarieven_2026.csv")
        provincies = pd.read_csv("mrb_provincies_2026.csv")
        return tarieven, provincies
    except Exception as e:
        return None, None

df_mrb, df_prov = load_mrb_data()

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
        brandstoffen = [b.get("brandstof_omschrijving", "").lower() for b in req_brandstof]
        v = req_brandstof[0].get("brandstofverbruik_gecombineerd", 6.0) if req_brandstof else 6.0
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": data.get("datum_eerste_toelating_dt", "2020-01-01")[:10],
            "brandstoffen": brandstoffen,
            "rdw_verbruik": float(v)
        }
    except: return None

# --- 3. MRB REKENMETHODE VIA CSV TABELLEN ---
def bereken_mrb_csv(gewicht, brandstoffen, provincie_naam):
    if df_mrb is None or df_prov is None: return 0
    
    # Zoek gewichtstrede
    trede = df_mrb[df_mrb['min_massa'] <= gewicht].iloc[-1]
    basis_kwartaal = trede['basis_3mnd']
    extra = 0
    if trede['toeslag_per_100kg'] > 0:
        eenheden = math.ceil((gewicht - trede['drempel']) / 100)
        extra = eenheden * trede['toeslag_per_100kg']
    
    basis_totaal = basis_kwartaal + extra
    
    # Provincie factor
    opcenten = df_prov[df_prov['provincie'] == provincie_naam]['opcenten'].values[0]
    mrb_3mnd = basis_totaal + (basis_totaal * (opcenten / 100))
    
    # Brandstoftoeslagen
    toeslag = 0
    if any("diesel" in b for b in brandstoffen): 
        toeslag = 86.16 + (max(0, gewicht-500)/100 * 18.34)
    elif any("lpg" in b for b in brandstoffen): 
        toeslag = 50.00 + (max(0, gewicht-500)/100 * 15.22)
    
    jaarbedrag = (mrb_3mnd + toeslag) * 4
    
    # EV-korting 2026 (75% korting in 2025, 25% korting in 2026 = 75% betalen)
    if any("elektriciteit" in b for b in brandstoffen) and not any(x in ["benzine", "diesel"] for x in brandstoffen):
        jaarbedrag *= 0.75
        
    return round(jaarbedrag)

BIJTELLING_OPTIES = [
    "22% over Cataloguswaarde (Standaard)", "35% over Aanschafwaarde (Youngtimer >15 jaar)",
    "4% tot € 50.000, 22% daarboven (EV 2019)", "8% tot € 45.000, 22% daarboven (EV 2020)",
    "12% tot € 40.000, 22% daarboven (EV 2021)", "16% tot € 35.000, 22% daarboven (EV 2022)",
    "16% tot € 30.000, 22% daarboven (EV 2023/2024)", "17% tot € 30.000, 22% daarboven (EV 2025/2026)"
]

# --- 4. INTERFACE ---
st.subheader("1. Klant & Voertuig Gegevens")
colA, colB = st.columns(2)
with colA: klant_naam = st.text_input("Naam relatie *")
with colB: klant_nummer = st.text_input("Relatienummer *")

colC, colD, colE = st.columns([2, 2, 1])
with colC: kenteken_input = st.text_input("Kenteken *")
with colD: 
    prov_lijst = df_prov['provincie'].tolist() if df_prov is not None else ["Gelderland"]
    prov = st.selectbox("Provincie", prov_lijst)
with colE: st.button("Berekenen")

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if auto:
        toel_dt = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        leeftijd_exact = relativedelta(datetime.datetime.now(), toel_dt)
        st.success(f"**{auto['merk']} {auto['handelsbenaming']}** | {leeftijd_exact.years} jaar oud")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            st.write(f"Cataloguswaarde (RDW): **€ {fmt(auto['catalogusprijs'])}**")
            aanschaf = st.number_input("Aanschafwaarde (€)", value=int(auto['catalogusprijs']))
            gekozen_bijt = st.selectbox("Bijtellingsprofiel", BIJTELLING_OPTIES)
            z_km = st.number_input("Zakelijke km / jaar", value=25000)
            p_km = st.number_input("Privé km / jaar", value=5000)
            totaal_km = z_km + p_km
        with col2:
            st.markdown("**Verbruik & Brandstof**")
            verbruik = st.number_input("Verbruik (L of kWh/100km)", value=auto['rdw_verbruik'])
            prijs_brand = st.number_input("Prijs p/l of kWh", value=1.95)
            brandstof_totaal = ((z_km + p_km) / 100) * verbruik * prijs_brand
        with col3:
            st.markdown("**Vaste & Variabele Kosten**")
            mrb_jaar = st.number_input("Wegenbelasting p.j.", value=int(bereken_mrb_csv(auto['gewicht'], auto['brandstoffen'], prov)))
            ond = st.number_input("Onderhoud p.j.", value=600)
            verz = st.number_input("Verzekering p.j.", value=800)
            overige = st.number_input("Overige kosten p.j.", value=500)
            lease = st.number_input("Lease/Rente p.j.", value=0)

        afschr = (aanschaf * 0.8) * 0.2
        tot_k = brandstof_totaal + mrb_jaar + ond + verz + overige + afschr + lease
        
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
        res1.metric("Zakelijke Aftrekpost", f"€ {fmt(aftrek_zak)}")
        res2.metric("Privé Aftrekpost", f"€ {fmt(pri_aftrek)}")

        if klant_naam and klant_nummer and st.button("Genereer Definitief Rapport"):
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
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 49, 92); pdf.set_xy(10, 45); pdf.cell(0, 10, "Autoberekening: Zakelijk of Prive?", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(3)

            # Sectie 1
            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "1. Relatiegegevens", ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
            pdf.cell(35, 5, "Naam relatie:"); pdf.cell(70, 5, clean(klant_naam)); pdf.cell(35, 5, "Datum:"); pdf.cell(50, 5, datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            pdf.cell(35, 5, "Nummer:"); pdf.cell(70, 5, clean(klant_nummer), ln=True); pdf.ln(3)

            # Sectie 2
            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(200, 6, "2. Voertuigspecificaties", ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0); pdf.set_fill_color(245)
            pdf.cell(35, 6, " Merk & Type:", fill=True); pdf.cell(155, 6, clean(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), fill=True, ln=True)
            pdf.cell(35, 6, " Eerste toelating:", fill=True); pdf.cell(155, 6, f"{auto['toelating']} ({leeftijd_exact.years} jaar, {leeftijd_exact.months} mnd)", fill=True, ln=True)
            pdf.cell(35, 6, " Verbruik:", fill=True); pdf.cell(155, 6, f"{auto['rdw_verbruik']} L/100km (RDW)", fill=True, ln=True); pdf.ln(2)
            
            pdf.cell(45, 5, "Cataloguswaarde:"); pdf.cell(45, 5, f"EUR {fmt(auto['catalogusprijs'])}", align='R')
            pdf.cell(10, 5); pdf.cell(45, 5, "Aanschafwaarde:"); pdf.cell(45, 5, f"EUR {fmt(aanschaf)}", align='R', ln=True)
            pdf.cell(45, 5, "Bijtellingsprofiel:"); pdf.set_font("Arial", 'I', 9); pdf.cell(145, 5, clean(gekozen_bijt), ln=True); pdf.ln(3)

            # Sectie 3
            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0); pdf.ln(2)
            
            rows = [
                ("Brandstof/Laad:", fmt(brandstof_totaal), "Vergoeding:", f"EUR {fmt(pri_aftrek)}"),
                ("Wegenbelasting:", fmt(mrb_jaar), "Zakelijke km:", fmt(z_km)),
                ("Onderhoud:", fmt(ond), "Vergoeding p/km:", "EUR 0,23"),
                ("Verzekering:", fmt(verz), "", ""),
                ("Afschrijving:", fmt(afschr), "", ""),
                ("Lease/Rente:", fmt(lease), "", "")
            ]
            for l1, v1, l2, v2 in rows:
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5)
                pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R' if v2 else 'L', ln=True)

            pdf.ln(2); pdf.set_font("Arial", 'B', 10)
            pdf.cell(45, 6, "Totale kosten:"); pdf.cell(45, 6, f"EUR {fmt(tot_k)}", align='R', ln=True)
            pdf.cell(45, 6, "Bijtelling:"); pdf.cell(45, 6, f"EUR {fmt(bijt_bedrag)}", align='R', ln=True); pdf.ln(2)
            
            pdf.set_fill_color(245)
            pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(zak_aftrek)} ", fill=True, align='R')
            pdf.cell(10, 8); pdf.cell(45, 8, " Fiscale aftrek:", fill=True); pdf.cell(45, 8, f"EUR {fmt(pri_aftrek)} ", fill=True, align='R', ln=True); pdf.ln(4)
            
            # Advies & Punten
            pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 11)
            pdf.cell(190, 10, clean(f"  Advies vanuit fiscaal oogpunt: {advies}"), fill=True, ln=True); pdf.ln(4)
            
            pdf.set_text_color(0, 49, 92); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Aandachtspunten bij zakelijk rijden:", ln=True)
            pdf.set_font("Arial", '', 8); pdf.set_text_color(0)
            punten = ["- Kosten zijn schattingen. MRB gebaseerd op Belastingdienst 2026 tabellen.", "- Houd rekening met het eventuele vervallen van rente op de lening.", "- Na 5 jaar vervallen de afschrijvingskosten.", "- Bij inruil kan een boekwinst ontstaan.", "- Bijtelling geldt voor 60 maanden vanaf datum eerste toelating."]
            for p in punten: pdf.cell(0, 4, clean(p), ln=True)

            st.download_button("📄 Download Definitief Rapport (VvAA PDF)", data=pdf.output(dest='S').encode('latin-1'), file_name=f"VvAA_Advies_{kenteken_input}.pdf")
