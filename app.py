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
    .stButton>button {{ background-color: {VVAA_ORANJE} !important; color: white !important; font-weight: bold; width: 100%; margin-top: 28px; border: none; border-radius: 4px; padding: 10px; }}
    div.stDownloadButton > button {{ background-color: {VVAA_BLAUW} !important; color: white !important; font-size: 18px; font-weight: bold; width: 100% !important; border-radius: 6px; padding: 15px; border: 2px solid {VVAA_BLAUW} !important; }}
    div.stDownloadButton > button p, div.stDownloadButton > button span {{ color: white !important; }}
    div[data-testid="stAlert"] {{ background-color: {VVAA_GRIJS} !important; border-left: 5px solid {VVAA_ORANJE} !important; padding: 10px; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

# --- 2. DOMEIN BEVEILIGING ---
# Dit werkt zodra de app live staat op Streamlit Cloud. De gebruiker moet inloggen.
def check_auth():
    if not st.user.email:
        st.warning("Gelieve in te loggen met uw VvAA e-mailadres om deze tool te gebruiken.")
        st.stop()
    if not st.user.email.lower().endswith("@vvaa.nl"):
        st.error(f"Toegang geweigerd. Uw e-mailadres ({st.user.email}) is niet geautoriseerd. Gebruik een @vvaa.nl adres.")
        st.stop()

# Haal het commentaar hieronder weg als je de @vvaa.nl check wilt activeren op de live server:
# check_auth()

def fmt(val):
    return f"{int(round(val)):,}".replace(",", ".")

# --- 3. DATA & API ---
@st.cache_data
def load_mrb_data():
    try:
        tarieven = pd.read_csv("mrb_tarieven_2026.csv") # Gebaseerd op Artikel 23 
        provincies = pd.read_csv("mrb_provincies_2026.csv") # Gebaseerd op opcenten tabel [cite: 90]
        return tarieven, provincies
    except: return None, None

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

def bereken_mrb_2026(gewicht, brandstoffen, provincie_naam):
    if df_mrb is None or df_prov is None: return 0
    trede = df_mrb[df_mrb['min_massa'] <= gewicht].iloc[-1]
    basis_kwartaal = trede['basis_3mnd']
    extra = (math.ceil(max(0, gewicht - trede['drempel']) / 100) * trede['toeslag_per_100kg']) if trede['toeslag_per_100kg'] > 0 else 0
    
    opcenten = df_prov[df_prov['provincie'] == provincie_naam]['opcenten'].values[0] # [cite: 90]
    mrb_3mnd = (basis_kwartaal + extra) * (1 + opcenten / 100)

    toeslag = 0
    if any("diesel" in b for b in brandstoffen): # [cite: 30]
        toeslag = 153.00 + (math.ceil(max(0, gewicht - 900) / 100) * 16.57)
    elif any("lpg" in b for b in brandstoffen): # [cite: 37]
        toeslag = 172.08 + (math.ceil(max(0, gewicht - 900) / 100) * 18.22)
    
    jaarbedrag = (mrb_3mnd + toeslag) * 4
    if any("elektriciteit" in b for b in brandstoffen) and not any(x in ["benzine", "diesel"] for x in brandstoffen):
        jaarbedrag *= 0.75 # EV korting 2026
    return round(jaarbedrag)

# --- 4. INTERFACE ---
if os.path.exists("vvaa_logo.jpg"): st.image("vvaa_logo.jpg", width=200)
st.title("Autoberekening zakelijk of privé?")
st.write("***In het hart van de gezondheidszorg.***")
st.markdown("---")

st.subheader("1. Klant & Voertuig Gegevens")
colA, colB = st.columns(2)
with colA: klant_naam = st.text_input("Naam relatie *")
with colB: klant_nummer = st.text_input("Lidnummer (alleen cijfers) *")

colC, colD, colE = st.columns([2, 2, 1])
with colC: kenteken_input = st.text_input("Kenteken *")
with colD: 
    prov_lijst = df_prov['provincie'].tolist() if df_prov is not None else ["Gelderland"]
    prov = st.selectbox("Provincie", prov_lijst)
with colE: st.button("Laden / Berekenen")

is_valid_nummer = klant_nummer.isdigit()
gevalideerd = bool(klant_naam) and is_valid_nummer

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if auto:
        toel_dt = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        leeftijd = relativedelta(datetime.datetime.now(), toel_dt)
        is_young_auto = leeftijd.years >= 15
        brandstof_tekst = ", ".join(auto['brandstoffen']).title()
        
        st.success(f"**{auto['merk']} ({kenteken_input.upper()}) - {auto['handelsbenaming']} - {brandstof_tekst} | {leeftijd.years} jaar en {leeftijd.months} maanden oud**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            st.write(f"Cataloguswaarde (RDW): **€ {fmt(auto['catalogusprijs'])}**")
            aanschaf = st.number_input("Aanschafwaarde / Dagwaarde (€)", value=int(auto['catalogusprijs']))
            
            is_young_manual = st.checkbox("Youngtimer regeling toepassen?", value=is_young_auto)
            
            if is_young_manual and not is_young_auto:
                st.warning(f"⚠️ **Pas op:** De youngtimer-regeling wordt toegepast, maar dit voertuig is volgens de RDW-gegevens pas {leeftijd.years} jaar oud.")
            elif is_young_auto and not is_young_manual:
                st.info(f"💡 **Youngtimer-melding:** Dit voertuig is ouder dan 15 jaar. De youngtimer-regeling kan van toepassing zijn.")
            
            idx_bijt = 1 if is_young_manual else 0
            gekozen_bijt = st.selectbox("Bijtellingsprofiel", ["22% over Cataloguswaarde (Standaard)", "35% over Aanschafwaarde (Youngtimer)"], index=idx_bijt)
            z_km = st.number_input("Zakelijke km / jaar", value=25000)
            p_km = st.number_input("Privé km / jaar", value=5000)
            totaal_km = z_km + p_km
            
        with col2:
            st.markdown("**Verbruik & Brandstof**")
            verbruik = st.number_input("Verbruik (L/100km)", value=auto['rdw_verbruik'])
            prijs_brand = st.number_input("Prijs per eenheid", value=1.95)
            brandstof_kosten = ((z_km + p_km) / 100) * verbruik * prijs_brand
            
        with col3:
            st.markdown("**Vaste Kosten**")
            mrb_jaar = bereken_mrb_2026(auto['gewicht'], auto['brandstoffen'], prov)
            mrb = st.number_input("Wegenbelasting (€ / jaar)", value=int(mrb_jaar))
            onderhoud = st.number_input("Onderhoud (€ / jaar)", value=600)
            verzekering = st.number_input("Verzekering (€ / jaar)", value=800)
            overige = st.number_input("Overige kosten (€ / jaar)", value=500)

        if totaal_km > 0 and (z_km / totaal_km) < 0.10:
            st.error(f"🚨 **Fiscale Eis:** Auto wordt voor {(z_km / totaal_km)*100:.1f}% zakelijk gebruikt. Dit is minder dan de vereiste 10% zakelijkheid.")

        afschr = (aanschaf * 0.8) * 0.2
        tot_k = brandstof_kosten + mrb + onderhoud + verzekering + overige + afschr
        bijt_bedrag = (aanschaf * 0.35) if is_young_manual else (auto['catalogusprijs'] * 0.22)
        zak_aftrek = tot_k - bijt_bedrag
        pri_aftrek = z_km * 0.23
        advies = "Zakelijk voordeliger" if zak_aftrek > pri_aftrek else "Privé voordeliger"

        st.markdown("---")
        st.subheader("3. Resultaat")
        st.success(f"💡 **Fiscaal Advies: {advies}**")
        
        r1, r2 = st.columns(2)
        r1.metric("Aftrekpost Zakelijk", f"€ {fmt(zak_aftrek)}")
        r2.metric("Aftrekpost Privé", f"€ {fmt(pri_aftrek)}")

        if gevalideerd:
            def clean(t): return str(t).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')
            class VVAAPDF(FPDF):
                def header(self):
                    self.set_fill_color(232, 78, 15); self.rect(0, 0, 210, 15, 'F')
                    if os.path.exists("vvaa_logo.jpg"): self.image("vvaa_logo.jpg", 10, 20, 35)
                    self.set_xy(10, 32); self.set_font("Arial", 'I', 10); self.cell(0, 10, "In het hart van de gezondheidszorg.", ln=True)
                def footer(self):
                    self.set_y(-15); self.set_fill_color(0, 49, 92); self.rect(0, 282, 210, 15, 'F')
                    self.set_text_color(255); self.set_font("Arial", '', 9); self.cell(0, 15, "VvAA | www.vvaa.nl", align='C', ln=True)

            pdf = VVAAPDF(); pdf.set_auto_page_break(auto=False); pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 49, 92); pdf.set_xy(10, 45)
            pdf.cell(0, 10, clean(f"VvAA autoberekening: {klant_naam} ({klant_nummer})"), ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)

            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15); pdf.cell(0, 6, "1. Relatie & Voertuig", ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0)
            pdf.cell(100, 5, f"Relatie: {clean(klant_naam)} ({klant_nummer})"); pdf.cell(0, 5, f"Datum: {datetime.datetime.now().strftime('%d-%m-%Y')}", ln=True)
            pdf.cell(0, 5, f"Voertuig: {auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})", ln=True)
            pdf.cell(0, 5, f"Leeftijd: {leeftijd.years} jaar en {leeftijd.months} mnd | Youngtimer: {'Ja' if is_young_manual else 'Nee'}", ln=True); pdf.ln(5)

            pdf.set_fill_color(245); pdf.cell(95, 6, f" Cataloguswaarde: EUR {fmt(auto['catalogusprijs'])}", fill=True); pdf.cell(95, 6, f" Aanschafwaarde: EUR {fmt(aanschaf)}", fill=True, ln=True); pdf.ln(5)

            pdf.set_font("Arial", 'B', 11); pdf.set_text_color(232, 78, 15)
            pdf.cell(90, 7, "Auto zakelijk", border='B'); pdf.cell(10, 7); pdf.cell(90, 7, "Auto prive", border='B', ln=True)
            pdf.set_font("Arial", '', 10); pdf.set_text_color(0); pdf.ln(2)
            
            rows = [("Brandstof:", fmt(brandstof_kosten), "Vergoeding:", fmt(pri_aftrek)), ("Wegenbelasting:", fmt(mrb), "Zakelijke km:", fmt(z_km)), ("Onderhoud/Overig:", fmt(onderhoud+overige), "Prive km:", fmt(p_km)), ("Afschrijving:", fmt(afschr), "", "")]
            for l1, v1, l2, v2 in rows:
                pdf.cell(45, 5, l1); pdf.cell(45, 5, v1, align='R'); pdf.cell(10, 5); pdf.cell(45, 5, l2); pdf.cell(45, 5, v2, align='R', ln=True)

            pdf.ln(5); pdf.set_fill_color(232, 78, 15); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 12)
            pdf.cell(95, 10, f" Aftrek zakelijk: EUR {fmt(zak_aftrek)} ", fill=True); pdf.cell(95, 10, f" Aftrek prive: EUR {fmt(pri_aftrek)} ", fill=True, ln=True)
            
            pdf.set_y(-45); pdf.set_text_color(0); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Advies & Aandachtspunten:", ln=True)
            pdf.set_font("Arial", '', 8); pdf.multi_cell(0, 4, clean(f"- Fiscaal advies: {advies}.\n- Kosten zijn gebaseerd op Belastingdienst tarieven 2026.\n- Bijtelling geldt voor 60 maanden vanaf eerste toelating."))

            fname = f"VvAA_autoberekening_{klant_naam.replace(' ', '_')}_{klant_nummer}.pdf"
            st.download_button("📄 Download Definitief Rapport", data=pdf.output(dest='S').encode('latin-1'), file_name=fname)
        else:
            st.info("ℹ️ Vul Naam en een numeriek Lidnummer in om het rapport te kunnen genereren.")
