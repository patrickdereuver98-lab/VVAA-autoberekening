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
    
    /* Primaire Bereken Knop */
    .stButton>button {{ 
        background-color: {VVAA_ORANJE} !important; 
        color: white !important; 
        border-radius: 4px; 
        border: none; 
        padding: 10px 24px; 
        font-weight: bold;
        width: 100%;
        margin-top: 28px; /* Lijnt hem mooi uit met de invulvelden */
    }}
    .stButton>button:hover {{ background-color: #c73e07 !important; }}
    
    /* Grote, opvallende Download PDF Knop */
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
        transition: 0.3s;
    }}
    div.stDownloadButton > button * {{ color: white !important; font-size: 18px !important; }}
    div.stDownloadButton > button:hover {{ 
        background-color: white !important; 
        color: {VVAA_BLAUW} !important;
        border: 2px solid {VVAA_ORANJE} !important;
    }}
    div.stDownloadButton > button:hover * {{ color: {VVAA_BLAUW} !important; }}
    
    div[data-testid="stAlert"] {{ background-color: {VVAA_GRIJS} !important; border-left: 5px solid {VVAA_ORANJE} !important; }}
    div[data-testid="stAlert"] * {{ color: {VVAA_BLAUW} !important; }}
    input, select, div[data-baseweb="select"] > div {{ background-color: #ffffff !important; color: {VVAA_BLAUW} !important; }}
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

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
        brandstoffen = []
        rdw_verbruik_liter = 6.0 
        
        if req_brandstof:
            for b in req_brandstof:
                omschrijving = b.get("brandstof_omschrijving", "").lower()
                brandstoffen.append(omschrijving)
                if omschrijving in ["benzine", "diesel", "lpg"]:
                    verbruik = b.get("brandstofverbruik_gecombineerd")
                    if verbruik: rdw_verbruik_liter = float(verbruik)
        
        eerste_toelating = data.get("datum_eerste_toelating_dt", datetime.datetime.now().strftime("%Y-%m-%d"))
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": eerste_toelating[:10],
            "bouwjaar": int(eerste_toelating[:4]),
            "brandstoffen": brandstoffen,
            "rdw_verbruik_liter": rdw_verbruik_liter
        }
    except:
        return None

def schat_mrb(gewicht, brandstof_is_ev, brandstof_is_diesel, provincie):
    basis_mrb = max(0, (gewicht - 500) * 1.25)
    if brandstof_is_ev: basis_mrb *= 0.60
    elif brandstof_is_diesel: basis_mrb *= 2.10
    provincie_factoren = {"Noord-Holland": 0.95, "Zuid-Holland": 1.10, "Gelderland": 1.05, "Drenthe": 1.08, "Groningen": 1.06, "Friesland": 1.04, "Overijssel": 1.03, "Flevoland": 1.02, "Utrecht": 1.01, "Zeeland": 1.04, "Noord-Brabant": 1.03, "Limburg": 1.05}
    return basis_mrb * provincie_factoren.get(provincie, 1.05)

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

# --- 3. KLANTGEGEVENS & VALIDATIE ---
st.subheader("1. Klant & Voertuig Gegevens")

colA, colB = st.columns(2)
with colA: klant_naam = st.text_input("Naam relatie *")
with colB: klant_nummer = st.text_input("Relatienummer (alleen cijfers) *")

colC, colD, colE = st.columns([2, 2, 1])
with colC: kenteken_input = st.text_input("Kenteken (bijv. AB-123-C) *")
with colD: provincie = st.selectbox("Provincie (voor Wegenbelasting)", ["Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen", "Limburg", "Noord-Brabant", "Noord-Holland", "Overijssel", "Utrecht", "Zeeland", "Zuid-Holland"])
with colE: bereken_knop = st.button("Laden / Berekenen")

is_valid_naam = bool(klant_naam) and not klant_naam.replace(" ", "").isdigit()
is_valid_nummer = bool(klant_nummer) and klant_nummer.isdigit()
gevalideerd = is_valid_naam and is_valid_nummer

if not gevalideerd and (klant_naam or klant_nummer):
    st.warning("⚠️ Naam relatie is verplicht en Relatienummer mag uitsluitend uit cijfers bestaan.")

st.markdown("---")

if kenteken_input:
    auto = get_rdw_data(kenteken_input)
    if not auto:
        st.error("Kenteken niet gevonden. Controleer de invoer.")
    else:
        toelating_date = datetime.datetime.strptime(auto['toelating'], "%Y-%m-%d")
        vandaag = datetime.datetime.now()
        leeftijd_exact = relativedelta(vandaag, toelating_date)
        is_youngtimer_auto = leeftijd_exact.years >= 15
        
        is_ev = any("elektriciteit" in b for b in auto['brandstoffen'])
        is_diesel = any("diesel" in b for b in auto['brandstoffen'])
        is_brandstof = any(b in ["benzine", "diesel", "lpg", "alcohol"] for b in auto['brandstoffen'])
        if not is_ev and not is_brandstof: is_brandstof = True
        
        brandstof_tekst = ", ".join(auto['brandstoffen']).title()
        berekende_mrb = schat_mrb(auto['gewicht'], is_ev, is_diesel, provincie)
        voorspelde_bijtelling_index = bepaal_bijtelling_index(auto['bouwjaar'], is_ev, is_youngtimer_auto)
        
        st.success(f"**Voertuig:** {auto['merk']} {auto['handelsbenaming']} | **Brandstof:** {brandstof_tekst} | **RDW Verbruik:** {auto['rdw_verbruik_liter']} L/100km")
        
        st.subheader("2. Financiële Details & Verbruik")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**Waarde & Bijtelling**")
            st.write(f"Cataloguswaarde (RDW): **€ {auto['catalogusprijs']:,.2f}**")
            aanschafwaarde = st.number_input("Aanschafwaarde (€)", min_value=0.0, step=500.0, value=auto['catalogusprijs'])
            gekozen_bijtelling = st.selectbox("Fiscaal Bijtellingsprofiel:", BIJTELLING_OPTIES, index=voorspelde_bijtelling_index)
            st.markdown(f"**Kilometers per jaar**")
            zakelijke_km = st.number_input("Zakelijke km", min_value=0, value=25000, step=1000)
            prive_km = st.number_input("Privé km", min_value=0, value=25000, step=1000)
            totaal_km = zakelijke_km + prive_km

        with col2:
            st.markdown(f"**Verbruik & Kosten**")
            brandstofkosten = 0.0
            laadkosten = 0.0
            if is_brandstof:
                verbruik_liter = st.number_input("Verbruik (liters per 100 km)", value=float(auto['rdw_verbruik_liter']))
                prijs_liter = st.number_input("Brandstofprijs per liter (€)", value=1.95)
                brandstofkosten = st.number_input("Brandstofkosten (€)", value=float((totaal_km / 100) * verbruik_liter * prijs_liter))
            if is_ev:
                verbruik_kwh = st.number_input("Verbruik (KWH per 100 km)", value=18.0)
                prijs_kwh = st.number_input("Kosten per KWH (€)", value=0.50)
                laadkosten = st.number_input("Laadkosten (€)", value=float((totaal_km / 100) * verbruik_kwh * prijs_kwh))

        with col3:
            st.markdown(f"**Overige Autokosten**")
            mrb = st.number_input("Motorrijtuigenbelasting (€)", value=float(berekende_mrb))
            onderhoud = st.number_input("Onderhoud & Reparatie (€)", value=600.0)
            verzekering = st.number_input("Verzekering (€)", value=800.0)
            overige = st.number_input("Overige autokosten (€)", value=500.0)
            leasebedrag = st.number_input("Leasebedrag all-in / Rente (€)", value=0.0)

        voldoet_aan_10_procent = (totaal_km == 0) or ((zakelijke_km / totaal_km) >= 0.10)
        if not voldoet_aan_10_procent:
            st.error(f"🚨 **Fiscale Eis:** Auto wordt voor {(zakelijke_km / totaal_km)*100:.1f}% zakelijk gebruikt. Minimum is 10%.")

        bijtelling_bedrag = 0.0
        if "Youngtimer" in gekozen_bijtelling:
            bijtelling_bedrag = aanschafwaarde * 0.35
        elif "Standaard" in gekozen_bijtelling:
            bijtelling_bedrag = auto['catalogusprijs'] * 0.22
        else:
            parts = gekozen_bijtelling.split("%")
            base_perc = float(parts[0]) / 100
            cap = float(gekozen_bijtelling.split("€ ")[1].split(",")[0].replace(".", ""))
            if auto['catalogusprijs'] <= cap:
                bijtelling_bedrag = auto['catalogusprijs'] * base_perc
            else:
                bijtelling_bedrag = (cap * base_perc) + ((auto['catalogusprijs'] - cap) * 0.22)

        afschrijving = (aanschafwaarde * 0.80) * 0.20
        totale_kosten = laadkosten + brandstofkosten + mrb + onderhoud + verzekering + overige + afschrijving + leasebedrag
        aftrek_zakelijk = totale_kosten - bijtelling_bedrag
        aftrek_prive = zakelijke_km * 0.23

        st.markdown("---")
        st.subheader("3. Resultaat")
        res1, res2 = st.columns(2)
        
        with res1:
            st.markdown("#### Auto zakelijk")
            if is_ev: st.write(f"Laadkosten: € {laadkosten:,.2f}")
            if is_brandstof: st.write(f"Brandstofkosten: € {brandstofkosten:,.2f}")
            st.write(f"Motorrijtuigenbelasting: € {mrb:,.2f}")
            st.write(f"Onderhoud: € {onderhoud:,.2f}")
            st.write(f"Verzekering: € {verzekering:,.2f}")
            st.write(f"Overige autokosten: € {overige:,.2f}")
            st.write(f"Afschrijving: € {afschrijving:,.2f}")
            st.write(f"Leasebedrag all-in: € {leasebedrag:,.2f}")
            st.markdown(f"**Totale autokosten: € {totale_kosten:,.2f}**")
            st.write(f"Bijtelling: € {bijtelling_bedrag:,.2f}")
            st.success(f"**Fiscale aftrekpost: € {aftrek_zakelijk:,.2f}**")

        with res2:
            st.markdown("#### Auto privé")
            st.write(f"Totale autokosten ({totaal_km} km): € {totale_kosten:,.2f}")
            st.write(f"Vergoeding: € 0,23 per km")
            st.write(f"Zakelijke kilometers: {zakelijke_km}")
            for _ in range(7 if (is_ev and is_brandstof) else 6): st.write("")
            st.success(f"**Fiscale aftrekpost: € {aftrek_prive:,.2f}**")

        advies = "Zakelijk voordeliger" if aftrek_zakelijk > aftrek_prive else "Privé voordeliger"

        # --- PDF GENERATIE (STRAKKER & RECHTS UITGELIJND) ---
        if gevalideerd:
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            def clean_text(text): return str(text).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')
            
            # Helper functie voor strakke, rechts uitgelijnde rijen
            def row_pdf(pdf, label1, val1, label2="", val2=""):
                pdf.set_font("Arial", '', 10)
                pdf.cell(45, 6, txt=label1, ln=False)
                pdf.cell(45, 6, txt=val1, ln=False, align='R')
                pdf.cell(10, 6, txt="", ln=False) # Midden-spacer
                pdf.cell(45, 6, txt=label2, ln=False)
                if label2:
                    pdf.cell(45, 6, txt=val2, ln=True, align='R')
                else:
                    pdf.cell(45, 6, txt="", ln=True)

            class VVAAPDF(FPDF):
                def header(self):
                    self.set_fill_color(232, 78, 15)
                    self.rect(0, 0, 210, 15, 'F')
                    if os.path.exists("vvaa_logo.jpg"):
                        self.image("vvaa_logo.jpg", x=10, y=20, w=35)
                    else:
                        self.set_font("Arial", 'B', 24)
                        self.set_text_color(232, 78, 15)
                        self.set_xy(10, 20)
                        self.cell(0, 10, "VvAA", ln=True)
                    self.set_font("Arial", 'I', 11)
                    self.set_text_color(100, 100, 100)
                    self.set_xy(10, 32)
                    self.cell(0, 10, "In het hart van de gezondheidszorg.", ln=True)
                    self.ln(10)

                def footer(self):
                    self.set_y(-25)
                    self.set_fill_color(0, 49, 92)
                    self.rect(0, 282, 210, 15, 'F')
                    self.set_text_color(255, 255, 255)
                    self.set_font("Arial", '', 9)
                    self.cell(0, 20, "VvAA | www.vvaa.nl | Voor zorgverleners, door zorgverleners", align='C')

            pdf = VVAAPDF()
            pdf.add_page()
            
            oranje = (232, 78, 15)
            blauw = (0, 49, 92)
            zwart = (0, 0, 0)
            licht_grijs = (245, 245, 245)
            
            # --- TITEL ---
            pdf.set_font("Arial", 'B', 18)
            pdf.set_text_color(*blauw)
            pdf.cell(200, 10, txt="Autoberekening: Zakelijk of Privé?", ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            # --- SECTIE 1: RELATIE ---
            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(*oranje)
            pdf.cell(200, 8, txt="1. Relatiegegevens", ln=True)
            
            pdf.set_text_color(*zwart)
            pdf.set_font("Arial", '', 10)
            pdf.cell(35, 6, txt="Naam relatie:", ln=False)
            pdf.cell(70, 6, txt=clean_text(klant_naam), ln=False)
            pdf.cell(35, 6, txt="Datum:", ln=False)
            pdf.cell(50, 6, txt=datetime.datetime.now().strftime("%d-%m-%Y"), ln=True)
            
            pdf.cell(35, 6, txt="Relatienummer:", ln=False)
            pdf.cell(70, 6, txt=clean_text(klant_nummer), ln=True)
            pdf.ln(5)
            
            # --- SECTIE 2: VOERTUIG ---
            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(*oranje)
            pdf.cell(200, 8, txt="2. Voertuigspecificaties", ln=True)
            
            pdf.set_text_color(*zwart)
            pdf.set_font("Arial", '', 10)
            # Voertuig Box
            pdf.set_fill_color(*licht_grijs)
            pdf.cell(35, 7, txt=" Merk & Type:", ln=False, fill=True)
            pdf.cell(155, 7, txt=clean_text(f"{auto['merk']} {auto['handelsbenaming']} ({kenteken_input.upper()})"), ln=True, fill=True)
            pdf.cell(35, 7, txt=" Eerste toelating:", ln=False, fill=True)
            pdf.cell(155, 7, txt=f"{auto['toelating']} ({leeftijd_exact.years} jaar, {leeftijd_exact.months} mnd)", ln=True, fill=True)
            pdf.cell(35, 7, txt=" Verbruik:", ln=False, fill=True)
            pdf.cell(155, 7, txt=f"{auto['rdw_verbruik_liter']} L/100km (RDW)", ln=True, fill=True)
            pdf.ln(3)
            
            # Auto Waardes strak uitgelijnd
            row_pdf(pdf, "Cataloguswaarde:", f"EUR {auto['catalogusprijs']:,.2f}", "Aanschafwaarde:", f"EUR {aanschafwaarde:,.2f}")
            pdf.cell(45, 6, txt="Bijtellingsprofiel:", ln=False)
            pdf.set_font("Arial", 'I', 9)
            pdf.cell(145, 6, txt=clean_text(gekozen_bijtelling), ln=True)
            pdf.ln(8)
            
            # --- SECTIE 3: FINANCIEEL ---
            pdf.set_font("Arial", 'B', 12)
            pdf.set_text_color(*oranje)
            pdf.cell(90, 8, txt="Auto zakelijk", ln=False, border='B')
            pdf.cell(10, 8, txt="", ln=False)
            pdf.cell(90, 8, txt="Auto privé", ln=True, border='B')
            pdf.ln(3)
            
            pdf.set_text_color(*zwart)
            if is_ev: row_pdf(pdf, "Laadkosten:", f"EUR {laadkosten:,.2f}", f"Totale kosten ({totaal_km}km):", f"EUR {totale_kosten:,.2f}")
            if is_brandstof: 
                lbl2 = f"Totale kosten ({totaal_km}km):" if not is_ev else "Vergoeding:"
                val2 = f"EUR {totale_kosten:,.2f}" if not is_ev else "EUR 0,23 / km"
                row_pdf(pdf, "Brandstofkosten:", f"EUR {brandstofkosten:,.2f}", lbl2, val2)
            
            row_pdf(pdf, "Wegenbelasting:", f"EUR {mrb:,.2f}", "Vergoeding:" if not (is_ev and is_brandstof) else "Zakelijke km:", "EUR 0,23 / km" if not (is_ev and is_brandstof) else str(zakelijke_km))
            row_pdf(pdf, "Onderhoud:", f"EUR {onderhoud:,.2f}", "Zakelijke km:" if not (is_ev and is_brandstof) else "", str(zakelijke_km) if not (is_ev and is_brandstof) else "")
            row_pdf(pdf, "Verzekering:", f"EUR {verzekering:,.2f}")
            row_pdf(pdf, "Overige autokosten:", f"EUR {overige:,.2f}")
            row_pdf(pdf, "Afschrijving:", f"EUR {afschrijving:,.2f}")
            row_pdf(pdf, "Leasebedrag all-in:", f"EUR {leasebedrag:,.2f}")
            
            pdf.ln(2)
            pdf.set_font("Arial", 'B', 10)
            row_pdf(pdf, "Totale autokosten:", f"EUR {totale_kosten:,.2f}")
            pdf.set_font("Arial", '', 10)
            row_pdf(pdf, "Bijtelling:", f"EUR {bijtelling_bedrag:,.2f}")
            
            pdf.ln(3)
            pdf.set_fill_color(*licht_grijs)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(45, 8, txt=" Fiscale aftrekpost:", ln=False, fill=True)
            pdf.cell(45, 8, txt=f"EUR {aftrek_zakelijk:,.2f} ", ln=False, align='R', fill=True)
            pdf.cell(10, 8, txt="", ln=False)
            pdf.cell(45, 8, txt=" Fiscale aftrekpost:", ln=False, fill=True)
            pdf.cell(45, 8, txt=f"EUR {aftrek_prive:,.2f} ", ln=True, align='R', fill=True)
            pdf.ln(10)
            
            # --- SECTIE 4: ADVIES ---
            pdf.set_fill_color(*oranje)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(190, 10, txt=clean_text(f"  Advies vanuit fiscaal oogpunt: {advies}"), ln=True, fill=True)
            pdf.ln(6)
            
            # --- SECTIE 5: AANDACHTSPUNTEN ---
            pdf.set_text_color(*blauw)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(200, 6, txt="Aandachtspunten bij zakelijk rijden:", ln=True)
            
            pdf.set_text_color(*zwart)
            pdf.set_font("Arial", '', 9)
            if not voldoet_aan_10_procent:
                pdf.set_text_color(220, 53, 69)
                pdf.cell(200, 5, txt="- LET OP: Auto wordt voor minder dan 10% zakelijk gebruikt (fiscale kwalificatie risico).", ln=True)
                pdf.set_text_color(*zwart)
                
            pdf.cell(200, 5, txt="- Verschillende kostenposten zijn gebaseerd op een schatting.", ln=True)
            pdf.cell(200, 5, txt="- Houd rekening met het vervallen van de rente op de lening.", ln=True)
            pdf.cell(200, 5, txt="- Na 5 jaar vervallen de afschrijvingskosten.", ln=True)
            pdf.cell(200, 5, txt="- Bij inruil kan een boekwinst ontstaan, welke belast kan zijn in de onderneming.", ln=True)
            pdf.cell(200, 5, txt="- Percentage bijtelling geldt voor 60 maanden vanaf datum eerste toelating.", ln=True)
            
            st.download_button(
                label="📄 Klik hier om het Definitieve Rapport te Downloaden",
                data=pdf.output(dest='S').encode('latin-1'),
                file_name=clean_text(f"VvAA_Autoberekening_{kenteken_input}.pdf"),
                mime="application/pdf"
            )
