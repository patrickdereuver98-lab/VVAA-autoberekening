import streamlit as st
import requests
import datetime
from fpdf import FPDF
from dateutil.relativedelta import relativedelta

# --- 1. STYLING (VvAA Huisstijl) ---
st.set_page_config(page_title="VvAA Autoberekening", page_icon="🚗", layout="wide")

vvaa_css = """
<style>
    h1, h2, h3, h4 { color: #EA5B0C; font-family: 'Arial', sans-serif; }
    .stButton>button { background-color: #EA5B0C; color: white; border-radius: 5px; border: none; padding: 10px 24px; font-weight: bold; }
    .stButton>button:hover { background-color: #cc4d08; color: white; }
    .stDownloadButton>button { background-color: #003366; color: white; }
</style>
"""
st.markdown(vvaa_css, unsafe_allow_html=True)

st.title("Autoberekening zakelijk of prive?")
st.write("*In het hart van de gezondheidszorg.*")

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
        eerste_toelating = data.get("datum_eerste_toelating_dt", datetime.datetime.now().strftime("%Y-%m-%d"))
        
        return {
            "merk": data.get("merk", "Onbekend"),
            "handelsbenaming": data.get("handelsbenaming", "Onbekend"),
            "catalogusprijs": float(data.get("catalogusprijs", 0)),
            "gewicht": int(data.get("massa_ledig_voertuig", 0)),
            "toelating": eerste_toelating[:10],
            "bouwjaar": int(eerste_toelating[:4]),
            "brandstoffen": brandstoffen
        }
    except:
        return None

# --- BEREKENING FUNCTIES (MRB & BIJTELLING) ---
def schat_mrb(gewicht, brandstof_is_ev, brandstof_is_diesel, provincie):
    basis_mrb = max(0, (gewicht - 500) * 1.25)
    if brandstof_is_ev:
        basis_mrb = basis_mrb * 0.60
    elif brandstof_is_diesel:
        basis_mrb = basis_mrb * 2.10
        
    provincie_factoren = {
        "Noord-Holland": 0.95, "Zuid-Holland": 1.10, "Gelderland": 1.05, 
        "Drenthe": 1.08, "Groningen": 1.06, "Friesland": 1.04,
        "Overijssel": 1.03, "Flevoland": 1.02, "Utrecht": 1.01,
        "Zeeland": 1.04, "Noord-Brabant": 1.03, "Limburg": 1.05
    }
    factor = provincie_factoren.get(provincie, 1.05)
    return basis_mrb * factor

BIJTELLING_OPTIES = [
    "22% over Cataloguswaarde (Standaard Benzine/Diesel)",
    "35% over Aanschafwaarde (Youngtimer >15 jaar)",
    "4% tot € 50.000, 22% daarboven (EV 2019)",
    "8% tot € 45.000, 22% daarboven (EV 2020)",
    "12% tot € 40.000, 22% daarboven (EV 2021)",
    "16% tot € 35.000, 22% daarboven (EV 2022)",
    "16% tot € 30.000, 22% daarboven (EV 2023/2024)",
    "17% tot € 30.000, 22% daarboven (EV 2025/2026)"
]

def bepaal_standaard_bijtelling_index(bouwjaar, is_ev, is_youngtimer):
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
colA, colB, colC = st.columns(3)
with colA:
    klant_naam = st.text_input("Naam relatie *")
with colB:
    klant_nummer = st.text_input("Relatienummer (alleen cijfers) *")
with colC:
    kenteken_input = st.text_input("Kenteken (bijv. AB-123-C) *")

provincie = st.selectbox("Provincie (voor Wegenbelasting)", ["Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen", "Limburg", "Noord-Brabant", "Noord-Holland", "Overijssel", "Utrecht", "Zeeland", "Zuid-Holland"])

is_valid_naam = bool(klant_naam) and not klant_naam.replace(" ", "").isdigit()
is_valid_nummer = bool(klant_nummer) and klant_nummer.isdigit()
gevalideerd = is_valid_naam and is_valid_nummer

if not gevalideerd and (klant_naam or klant_nummer):
    st.warning("⚠️ Let op: Naam relatie is verplicht (mag geen nummer zijn) en Relatienummer mag uitsluitend uit cijfers bestaan.")

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
        voorspelde_bijtelling_index = bepaal_standaard_bijtelling_index(auto['bouwjaar'], is_ev, is_youngtimer_auto)
        
        st.success(f"**Voertuig:** {auto['merk']} {auto['handelsbenaming']} | **Brandstof:** {brandstof_tekst}")
        st.info(f"📅 **Leeftijd auto:** {leeftijd_exact.years} jaar en {leeftijd_exact.months} maanden (Eerste toelating: {auto['toelating']})")
        
        st.subheader("2. Financiële Details & Verbruik")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Waarde & Bijtelling**")
            st.write(f"Cataloguswaarde (RDW): **€ {auto['catalogusprijs']:,.2f}**")
            aanschafwaarde = st.number_input("Aanschafwaarde (€) (Handmatige invoer)", min_value=0.0, step=500.0, value=auto['catalogusprijs'])
            
            gekozen_bijtelling = st.selectbox(
                "Fiscaal Bijtellingsprofiel (Automatisch geselecteerd, pas aan indien nodig):", 
                BIJTELLING_OPTIES, 
                index=voorspelde_bijtelling_index
            )
            
            st.markdown("**Kilometers**")
            zakelijke_km = st.number_input("Zakelijke kilometers / jaar", min_value=0, value=25000, step=1000)
            prive_km = st.number_input("Privé-kilometers / jaar", min_value=0, value=25000, step=1000)
            totaal_km = zakelijke_km + prive_km

        with col2:
            st.markdown("**Verbruik & Kosten**")
            brandstofkosten = 0.0
            laadkosten = 0.0
            
            if is_brandstof:
                verbruik_liter = st.number_input("Verbruik (liters per 100 km)", value=6.0)
                prijs_liter = st.number_input("Brandstofprijs per liter (€)", value=1.95)
                calc_brandstof = (totaal_km / 100) * verbruik_liter * prijs_liter
                brandstofkosten = st.number_input("Brandstofkosten (€)", value=float(calc_brandstof))
                
            if is_ev:
                verbruik_kwh = st.number_input("Verbruik (KWH per 100 km)", value=18.0)
                prijs_kwh = st.number_input("Kosten per KWH (€)", value=0.50)
                calc_laad = (totaal_km / 100) * verbruik_kwh * prijs_kwh
                laadkosten = st.number_input("Laadkosten (€)", value=float(calc_laad))

        with col3:
            st.markdown("**Overige Autokosten**")
            mrb = st.number_input("Motorrijtuigenbelasting (€) (Geschat op basis van provincie/gewicht)", value=float(berekende_mrb))
            onderhoud = st.number_input("Onderhoud & Reparatie (€)", value=600.0)
            verzekering = st.number_input("Verzekering (€)", value=800.0)
            overige = st.number_input("Overige autokosten (€)", value=500.0)
            leasebedrag = st.number_input("Leasebedrag all-in / Rente (€)", value=0.0)

        voldoet_aan_10_procent = True
        if totaal_km > 0:
            percentage_zakelijk = (zakelijke_km / totaal_km) * 100
            if percentage_zakelijk < 10.0:
                voldoet_aan_10_procent = False
                st.error(f"🚨 **Fiscale Eis:** Auto wordt voor {percentage_zakelijk:.1f}% zakelijk gebruikt. Minimum is 10%.")

        bijtelling_bedrag = 0.0
        is_huidige_youngtimer = "Youngtimer" in gekozen_bijtelling
        
        if is_huidige_youngtimer:
            bijtelling_bedrag = aanschafwaarde * 0.35
        elif "Standaard" in gekozen_bijtelling:
            bijtelling_bedrag = auto['catalogusprijs'] * 0.22
        else:
            parts = gekozen_bijtelling.split("%")
            base_perc = float(parts[0]) / 100
            cap_str = gekozen_bijtelling.split("€ ")[1].split(",")[0].replace(".", "")
            cap = float(cap_str)
            
            if auto['catalogusprijs'] <= cap:
                bijtelling_bedrag = auto['catalogusprijs'] * base_perc
            else:
                bijtelling_laag = cap * base_perc
                bijtelling_hoog = (auto['catalogusprijs'] - cap) * 0.22
                bijtelling_bedrag = bijtelling_laag + bijtelling_hoog

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
            st.write(f"Bijtelling ({gekozen_bijtelling.split('(')[0]}): € {bijtelling_bedrag:,.2f}")
            st.success(f"**Fiscale aftrekpost: € {aftrek_zakelijk:,.2f}**")

        with res2:
            st.markdown("#### Auto prive")
            st.write(f"Totale autokosten (gebaseerd op {totaal_km} km): € {totale_kosten:,.2f}")
            st.write(f"Vergoeding: € 0,23 per km")
            st.write(f"Zakelijke kilometers: {zakelijke_km}")
            for _ in range(7 if (is_ev and is_brandstof) else 6): st.write("")
            st.success(f"**Fiscale aftrekpost: € {aftrek_prive:,.2f}**")

        st.markdown("---")
        advies = "Zakelijk voordeliger" if aftrek_zakelijk > aftrek_prive else "Prive voordeliger"
        st.subheader(f"Advies vanuit fiscaal oogpunt: {advies}")

        # --- PDF GENERATIE ---
        if gevalideerd:
            if st.button("Genereer PDF Rapport"):
                # Hulpfunctie om vreemde tekens (zoals € of emojis) om te zetten voordat het in de PDF gaat
                def clean_text(text):
                    return str(text).replace('€', 'EUR').encode('latin-1', 'replace').decode('latin-1')

                pdf = FPDF()
                pdf.add_page()
                
                oranje = (234, 91, 12)
                zwart = (0, 0, 0)
                grijs = (100, 100, 100)
                rood = (220, 53, 69)
                
                pdf.set_font("Arial", 'B', 20)
                pdf.set_text_color(*oranje)
                pdf.cell(200, 10, txt="VvAA", ln=True)
                pdf.set_font("Arial", 'I', 12)
                pdf.set_text_color(*grijs)
                pdf.cell(200, 8, txt="In het hart van de gezondheidszorg.", ln=True)
                pdf.ln(5)
                
                pdf.set_font("Arial", 'B', 16)
                pdf.set_text_color(*zwart)
                pdf.cell(200, 10, txt="Autoberekening zakelijk of prive?", ln=True)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(5)
                
                pdf.set_font("Arial", '', 10)
                pdf.cell(50, 6, txt="Naam relatie:", ln=False)
                pdf.cell(100, 6, txt=clean_text(klant_naam), ln=True)
                pdf.cell(50, 6, txt="Relatienummer:", ln=False)
                pdf.cell(100, 6, txt=clean_text(klant_nummer), ln=True)
                pdf.ln(5)
                
                pdf.cell(50, 6, txt="Merk auto:", ln=False)
                pdf.cell(100, 6, txt=clean_text(auto['merk']), ln=True)
                pdf.cell(50, 6, txt="Type:", ln=False)
                pdf.cell(100, 6, txt=clean_text(auto['handelsbenaming']), ln=True)
                pdf.cell(50, 6, txt="Kenteken:", ln=False)
                pdf.cell(100, 6, txt=clean_text(kenteken_input.upper()), ln=True)
                pdf.cell(50, 6, txt="Eerste toelating:", ln=False)
                pdf.cell(100, 6, txt=f"{auto['toelating']} ({leeftijd_exact.years} jaar, {leeftijd_exact.months} mnd)", ln=True)
                pdf.cell(50, 6, txt="Cataloguswaarde:", ln=False)
                pdf.cell(100, 6, txt=f"EUR {auto['catalogusprijs']:,.0f}", ln=True)
                pdf.cell(50, 6, txt="Aanschafwaarde:", ln=False)
                pdf.cell(100, 6, txt=f"EUR {aanschafwaarde:,.0f}", ln=True)
                
                pdf.cell(50, 6, txt="Bijtellingsprofiel:", ln=False)
                pdf.set_font("Arial", 'I', 9)
                pdf.cell(100, 6, txt=clean_text(gekozen_bijtelling), ln=True)
                pdf.set_font("Arial", '', 10)
                pdf.ln(5)
                
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(100, 8, txt="Auto zakelijk", ln=False)
                pdf.cell(100, 8, txt="Auto prive", ln=True)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(2)
                
                pdf.set_font("Arial", '', 10)
                def row(label1, val1, label2="", val2=""):
                    pdf.cell(60, 6, txt=label1, ln=False)
                    pdf.cell(40, 6, txt=val1, ln=False)
                    pdf.cell(60, 6, txt=label2, ln=False)
                    pdf.cell(40, 6, txt=val2, ln=True)

                if is_ev: row("Laadkosten:", f"EUR {laadkosten:,.2f}", f"Totale kosten ({totaal_km}km):", f"EUR {totale_kosten:,.2f}")
                if is_brandstof: 
                    lbl2 = f"Totale kosten ({totaal_km}km):" if not is_ev else "Vergoeding:"
                    val2 = f"EUR {totale_kosten:,.2f}" if not is_ev else "EUR 0,23 / km"
                    row("Brandstofkosten:", f"EUR {brandstofkosten:,.2f}", lbl2, val2)
                
                row("Motorrijtuigenbelasting:", f"EUR {mrb:,.2f}", "Vergoeding:" if not (is_ev and is_brandstof) else "Zakelijke km:", "EUR 0,23 / km" if not (is_ev and is_brandstof) else str(zakelijke_km))
                row("Onderhoud:", f"EUR {onderhoud:,.2f}", "Zakelijke km:" if not (is_ev and is_brandstof) else "", str(zakelijke_km) if not (is_ev and is_brandstof) else "")
                row("Verzekering:", f"EUR {verzekering:,.2f}")
                row("Overige autokosten:", f"EUR {overige:,.2f}")
                row("Afschrijving:", f"EUR {afschrijving:,.2f}")
                row("Leasebedrag all-in:", f"EUR {leasebedrag:,.2f}")
                
                pdf.ln(2)
                pdf.set_font("Arial", 'B', 10)
                row("Totale autokosten:", f"EUR {totale_kosten:,.2f}")
                pdf.set_font("Arial", '', 10)
                row("Bijtelling:", f"EUR {bijtelling_bedrag:,.2f}")
                
                pdf.ln(2)
                pdf.set_font("Arial", 'B', 10)
                row("Fiscale aftrekpost:", f"EUR {aftrek_zakelijk:,.0f}", "Fiscale aftrekpost:", f"EUR {aftrek_prive:,.0f}")
                pdf.ln(8)
                
                pdf.set_font("Arial", 'B', 12)
                pdf.set_text_color(*oranje)
                pdf.cell(200, 8, txt=clean_text(f"Advies vanuit fiscaal oogpunt: {advies}"), ln=True)
                pdf.ln(5)
                
                pdf.set_text_color(*zwart)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(200, 6, txt="Aandachtspunten bij zakelijk rijden:", ln=True)
                pdf.set_font("Arial", '', 9)
                
                if not voldoet_aan_10_procent:
                    pdf.set_text_color(*rood)
                    pdf.cell(200, 5, txt="- LET OP: Auto wordt voor minder dan 10% zakelijk gebruikt en kwalificeert fiscaal mogelijk niet als zakelijk vermogen.", ln=True)
                    pdf.set_text_color(*zwart)
                    
                pdf.cell(200, 5, txt="- verschillende kostenposten zijn gebaseerd op een schatting", ln=True)
                pdf.cell(200, 5, txt="- rekening houden met vervallen van rente op de lening", ln=True)
                pdf.cell(200, 5, txt="- na 5 jaar vervallen de afschrijvingskosten", ln=True)
                pdf.cell(200, 5, txt="- bij inruil kan een boekwinst ontstaan, welke belast kan zijn in de onderneming", ln=True)
                pdf.cell(200, 5, txt="- percentage bijtelling geldt voor 60 maanden vanaf datum eerste toelating (n.v.t. bij een youngtimer)", ln=True)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                
                st.download_button(
                    label="📄 Klik hier om de gemaakte PDF te Downloaden",
                    data=pdf_bytes,
                    file_name=clean_text(f"VvAA_Autoberekening_{kenteken_input}.pdf"),
                    mime="application/pdf"
                )
