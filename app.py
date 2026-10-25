import html
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date

import streamlit as st
import streamlit.components.v1 as components


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="MedAssist AI - Clinical Assistant",
    page_icon="🩺",
    layout="centered",
)

st.title("🩺 MedAssist AI")
st.caption(
    "Educational clinical triage assistant | "
    "Not a substitute for professional medical care."
)

st.markdown(
    """
<style>
.rx-card{background:#fff;color:#1b1b1b;border:1px solid #cfd8dc;
  border-radius:12px;padding:16px 18px;margin:4px 0 8px 0;
  font-family:Arial,Helvetica,sans-serif;}
.rx-head{display:flex;justify-content:space-between;align-items:center;
  border-bottom:2px solid #0E76A8;padding-bottom:6px;margin-bottom:8px;}
.rx-clinic{font-weight:700;color:#0E76A8;font-size:16px;}
.rx-date{font-size:12px;color:#555;}
.rx-patient{font-size:12px;color:#444;margin-bottom:8px;}
.rx-diag{font-size:15px;margin:6px 0;}
.rx-symbol{font-size:26px;font-weight:700;color:#0E76A8;margin:4px 0;}
.rx-table{width:100%;border-collapse:collapse;font-size:14px;}
.rx-table th{text-align:left;border-bottom:1px solid #90a4ae;
  padding:6px 4px;color:#37474f;}
.rx-table td{padding:6px 4px;border-bottom:1px solid #eceff1;
  vertical-align:top;}
.rx-sub{color:#607d8b;font-size:12px;}
.rx-note{font-size:13px;color:#37474f;padding:2px 4px 8px 18px;}
.rx-section{font-size:14px;margin-top:8px;}
.rx-section ul{margin:2px 0 0 0;padding-left:20px;}
.rx-warn{background:#fff4f4;border-left:4px solid #d32f2f;
  padding:6px 10px;margin-top:10px;font-size:13px;}
.rx-urg{display:inline-block;font-size:13px;font-weight:600;
  padding:4px 10px;border-radius:14px;margin:4px 0 6px 0;}
.rx-urg-routine{background:#e8f5e9;color:#1b5e20;}
.rx-urg-soon{background:#fff3e0;color:#e65100;}
.rx-urg-urgent{background:#ffebee;color:#b71c1c;}
.rx-info{background:#e3f2fd;border-left:4px solid #1976d2;color:#0d47a1;
  padding:6px 10px;margin-top:10px;font-size:13px;}
.rx-foot{font-size:11px;color:#777;margin-top:10px;}
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------
# API CONFIGURATION
# --------------------------------------------------

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, default)


api_key = get_secret("OPENROUTER_API_KEY")
MODEL_NAME = get_secret("OPENROUTER_MODEL", "openrouter/free")

with st.sidebar:
    st.subheader("⚙️ Settings")

    if not api_key:
        api_key = st.text_input(
            "OpenRouter API key",
            type="password",
            help="Optional. Leave blank to use the built-in offline "
                 "medical knowledge engine.",
        )

    voice_on = st.toggle("🔊 Speak responses", value=True)

    with st.expander("More patient details (optional)"):
        patient_weight = st.number_input(
            "Weight (kg, if known)", min_value=0.0, max_value=300.0, value=0.0
        )
        allergies = st.text_input(
            "Medicine allergies", placeholder="Unknown or none known"
        )
        current_medicines = st.text_area(
            "Current medicines", placeholder="List medicines, or unknown"
        )
        medical_history = st.text_area(
            "Relevant medical conditions", placeholder="Enter conditions, or unknown"
        )

    if st.button("🗑️ Reset conversation", use_container_width=True):
        st.session_state.pop("messages", None)
        st.session_state.pop("profile", None)  # new patient
        st.session_state.pop("greeted", None)
        st.rerun()

# The bot answers in the language the patient wrote or spoke.
HINGLISH_WORDS = {
    "mujhe", "mera", "meri", "mere", "hai", "hain", "nahi", "nahin", "kya",
    "bahut", "thoda", "hua", "hui", "raha", "rahi", "rahe", "dard",
    "bukhar", "khansi", "zukam", "ulti", "dast", "kamar", "gala", "aankh",
    "dawai", "dawa", "mein", "aur", "ke", "ki", "ka", "ko", "se", "ho",
}


def detect_language(text):
    """Return 'hi' for Hindi (Devanagari or Roman Hindi), else 'en'."""
    dev = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    if dev == 0 and latin == 0:
        return "en"
    if dev >= 3 and dev >= 0.3 * (dev + latin):
        return "hi"
    words = re.findall(r"[a-z]+", text.lower())
    hits = sum(1 for w in words if w in HINGLISH_WORDS and w != "ho")
    if words and hits >= 2 and hits / len(words) >= 0.3:
        return "hi"
    return "en"


# --------------------------------------------------
# AI SYSTEM PROMPT
# --------------------------------------------------

SYSTEM_PROMPT = """
You are MedAssist AI, an educational clinical triage assistant.
Reply with ONE JSON object only. No markdown, no text outside the JSON.

Schema:
{
 "possible_causes": ["2-4 most likely conditions, most likely first"],
 "urgency": "routine" or "soon" or "urgent",
 "home_care": ["3-4 short practical at-home care steps"],
 "medicines": [{"name": "over-the-counter medicine or product, or a
     non-drug item like ORS", "purpose": "max 6 words",
     "note": "one short precaution, max 12 words"}],
 "tests": ["tests a doctor may advise, max 4, can be empty"],
 "red_flags": ["max 3 emergency warning signs"],
 "see_doctor": "one short sentence on when/how soon to see a doctor",
 "summary": "4-5 short plain sentences read aloud: likely causes, how
     urgent it is, home care, which medicine(s). No dose numbers."
}

Rules:
- Analyse ALL complaints in the message together and think about the full
  list of possible causes before answering.
- ALWAYS give the complete answer in your FIRST reply. NEVER ask questions.
- urgency "urgent": blood in urine or stool, jaundice, severe pain,
  high fever with stiff neck or rash, pregnancy complications, anything
  that needs a doctor within 24 hours. "soon": needs a doctor in 1-2 days.
  "routine": self-care is reasonable.
- Suggest only common over-the-counter medicines or non-drug care.
  NEVER suggest antibiotics, steroids, opioids, sedatives or other
  prescription medicines. NEVER suggest oral anti-inflammatory painkillers
  (ibuprofen, diclofenac tablets, aspirin, naproxen, nimesulide).
- If no medicine is safe before a doctor examines the patient, leave
  "medicines" empty or list only a safe supportive item.
- NEVER write doses, frequencies or durations. The app adds them.
- Respect the patient's age, gender, pregnancy, allergies, current
  medicines and conditions. Be extra careful for children, older adults
  and pregnant or breastfeeding patients.
- Earlier messages in this conversation are about the SAME patient. Combine
  ALL earlier symptoms, test results and reports with the latest message.
  Never forget them until the conversation is reset.
- If tests are needed, still list the safe over-the-counter medicines the
  patient can use to relieve symptoms until the report comes.
- If the patient reports a test result or a doctor's diagnosis, accept it
  as the working diagnosis and update the causes (put it first). Do NOT
  suggest antibiotics: only a doctor can prescribe them after seeing the
  report. The app adds a note about this itself.
- Keep every field brief. Be fast and concise.
- Write all text values in the requested language. JSON keys, and the
  "urgency" value (routine / soon / urgent), always stay in English.
  Medicine names are always written in English letters (e.g. Paracetamol).
"""


# --------------------------------------------------
# EMERGENCY AND CRISIS SCREENING (simple keyword screen)
# --------------------------------------------------

EMERGENCY_GROUPS = [
    (["can't breathe", "cant breathe", "cannot breathe", "cannot breath",
      "can not breathe", "difficulty breathing", "difficulty in breathing",
      "severe shortness of breath", "blue lips", "gasping for air",
      "सांस नहीं", "साँस नहीं", "सांस लेने में तकलीफ"],
     "Possible severe breathing emergency"),
    (["chest pain", "chest pressure", "crushing chest",
      "chest tightness", "सीने में दर्द", "छाती में दर्द"],
     "Possible serious chest emergency"),
    (["face drooping", "sudden weakness on one side",
      "sudden trouble speaking", "sudden loss of vision", "slurred speech"],
     "Possible stroke warning signs"),
    (["unconscious", "not waking up", "seizure", "fits", "vomiting blood",
      "vomited blood", "coughing blood", "heavy bleeding",
      "bleeding heavily", "बेहोश"],
     "Possible medical emergency"),
    (["swollen tongue", "throat closing", "anaphylaxis",
      "lips are swelling", "face swelling"],
     "Possible severe allergic reaction"),
    (["poison", "overdose", "snake bite", "snakebite", "drank phenyl",
      "swallowed acid"],
     "Possible poisoning or overdose"),
]

CRISIS_PHRASES = [
    "suicide", "suicidal", "kill myself", "end my life", "want to die",
    "self harm", "self-harm", "hurt myself", "ending my life",
    "आत्महत्या", "मरना चाहता", "मरना चाहती",
]

EMERGENCY_REPLY_EN = (
    "Your message includes a possible emergency warning sign. "
    "Call your local emergency number (112 in India) or go to the nearest "
    "emergency department now. Do not wait for this chatbot."
)
EMERGENCY_REPLY_HI = (
    "आपके संदेश में आपातकालीन चेतावनी के संकेत हो सकते हैं। "
    "तुरंत 112 पर कॉल करें या नज़दीकी अस्पताल के आपातकालीन विभाग जाएं। "
    "इस चैटबॉट के जवाब का इंतज़ार न करें।"
)
CRISIS_REPLY_EN = (
    "I'm really sorry you are going through this. You are not alone, and "
    "help is available right now. Please call Tele-MANAS at 14416 (free, "
    "24x7), or 112 if you are in immediate danger, and ask someone you "
    "trust to stay with you."
)
CRISIS_REPLY_HI = (
    "मुझे बहुत खेद है कि आप इस दौर से गुज़र रहे हैं। आप अकेले नहीं हैं और "
    "मदद अभी उपलब्ध है। कृपया Tele-MANAS को 14416 (निःशुल्क, 24x7) पर कॉल "
    "करें, या तुरंत खतरे में हों तो 112 पर कॉल करें, और किसी भरोसेमंद "
    "व्यक्ति को अपने साथ रहने के लिए कहें।"
)


def emergency_check(message):
    """Return (category, is_crisis) or (None, False)."""
    text = message.lower()
    if any(p in text for p in CRISIS_PHRASES):
        return "Support needed", True
    for phrases, category in EMERGENCY_GROUPS:
        if any(phrase in text for phrase in phrases):
            return category, False
    return None, False


# --------------------------------------------------
# SAFETY FILTERS FOR MEDICINES
# --------------------------------------------------

BLOCKED_DRUGS = [
    # antibiotics and other prescription-only medicines
    "amoxicillin", "amoxycillin", "augmentin", "clavulan", "azithromycin",
    "azithral", "ciprofloxacin", "cipro", "levofloxacin", "ofloxacin",
    "norfloxacin", "nitrofurantoin", "metronidazole", "doxycycline",
    "cefixime", "cefuroxime", "cephalexin", "ceftriaxone", "clindamycin",
    "penicillin", "erythromycin", "antibiotic", "cotrimoxazole",
    "prednisolone", "prednisone", "dexamethasone", "betamethasone",
    "steroid", "tramadol", "codeine", "morphine", "diazepam", "alprazolam",
    "clonazepam", "zolpidem", "sildenafil", "insulin", "ivermectin",
    # oral anti-inflammatory painkillers (need doctor/pharmacist review)
    "ibuprofen", "naproxen", "nimesulide", "aspirin", "ketorolac",
    "mefenamic", "etoricoxib", "aceclofenac", "combiflam", "brufen",
]


def is_blocked(name_lower):
    if "diclofenac" in name_lower and any(
        w in name_lower for w in ("gel", "cream", "topical", "ointment")
    ):
        return False
    if "diclofenac" in name_lower:
        return True
    return any(drug in name_lower for drug in BLOCKED_DRUGS)


def sanitize_medicines(meds, patient):
    """Drop prescription-only, anti-inflammatory or allergy-conflicting items."""
    allergy_text = patient.get("allergies", "").lower()
    clean, seen = [], set()
    for m in meds:
        low = m["name"].lower()
        if is_blocked(low):
            continue
        tokens = re.findall(r"[a-z]{5,}", low)
        if allergy_text and any(t in allergy_text for t in tokens):
            continue
        first = re.split(r"[\s(]", low.strip())[0]
        if first in seen:
            continue
        seen.add(first)
        clean.append(m)
    return clean[:3]


# --------------------------------------------------
# DOSAGE TABLE - fixed, reviewed text. The AI never writes doses.
# Standard adult over-the-counter label guidance.
# --------------------------------------------------

def _dose(keywords, dose, time, dose_hi=None, time_hi=None,
          min_age=18, elderly_ok=False):
    return (keywords, {
        "dose": dose, "time": time,
        "dose_hi": dose_hi or dose, "time_hi": time_hi or time,
        "min_age": min_age, "elderly_ok": elderly_ok,
    })


DOSE_TABLE = [
    _dose(["paracetamol", "acetaminophen", "crocin", "dolo"],
          "500 mg tablet - 1 tablet",
          "Every 6 hours if needed, after food. Max 4 tablets in 24 hours. "
          "Up to 3 days.",
          "500 mg की 1 गोली",
          "ज़रूरत होने पर हर 6 घंटे, खाने के बाद। 24 घंटे में अधिकतम 4 गोली। "
          "अधिकतम 3 दिन।",
          elderly_ok=True),
    _dose(["ors", "oral rehydration"],
          "1 glass (200 ml), mixed as per packet",
          "After each loose stool or vomit, in small sips, until better.",
          "1 गिलास (200 ml), पैकेट के अनुसार घोलें",
          "हर बार दस्त या उल्टी के बाद, छोटे घूंट में, ठीक होने तक।",
          elderly_ok=True),
    _dose(["saline"],
          "2 drops or sprays in each nostril",
          "2-3 times a day, up to 5 days.",
          "हर नथुने में 2 बूंद या स्प्रे",
          "दिन में 2-3 बार, अधिकतम 5 दिन।",
          min_age=12, elderly_ok=True),
    _dose(["lozenge"],
          "1 lozenge, let it dissolve slowly",
          "Every 3-4 hours, up to 3 days (max as per label).",
          "1 लोज़ेंज, धीरे-धीरे चूसें",
          "हर 3-4 घंटे में, अधिकतम 3 दिन (लेबल के अनुसार)।",
          elderly_ok=True),
    _dose(["cetirizine", "antihistamine"],
          "10 mg tablet - 1 tablet",
          "Once a day at night, up to 5 days.",
          "10 mg की 1 गोली",
          "दिन में एक बार रात को, अधिकतम 5 दिन।"),
    _dose(["antacid", "aluminium", "magnesium hydroxide", "gelusil", "digene"],
          "10-20 ml liquid or 1-2 chewable tablets",
          "After meals and at bedtime, up to 3 times a day, up to 5 days.",
          "10-20 ml लिक्विड या 1-2 चबाने वाली गोलियां",
          "खाने के बाद और सोते समय, दिन में अधिकतम 3 बार, अधिकतम 5 दिन।"),
    _dose(["fibre", "fiber", "isabgol", "psyllium"],
          "1 teaspoon husk in a full glass of water",
          "Once a day at night with plenty of water, up to 7 days.",
          "1 चम्मच भूसी, पूरे गिलास पानी में",
          "रात को दिन में एक बार, खूब पानी के साथ, अधिकतम 7 दिन।",
          elderly_ok=True),
    _dose(["calamine"],
          "Thin layer on itchy skin",
          "2-3 times a day, up to 5 days. Not on broken skin.",
          min_age=12, elderly_ok=True),
    _dose(["clotrimazole"],
          "Thin layer on the affected skin and a little around it",
          "Twice a day for up to 2 weeks.",
          min_age=12, elderly_ok=True),
    _dose(["povidone", "betadine", "antiseptic"],
          "Thin layer after cleaning the wound",
          "1-2 times a day, up to 5 days.",
          min_age=12, elderly_ok=True),
    _dose(["lubricant eye", "artificial tear", "eye drop"],
          "1-2 drops in each eye",
          "3-4 times a day, up to 5 days.",
          min_age=12, elderly_ok=True),
    _dose(["ketoconazole", "anti-dandruff", "antidandruff", "zinc pyrithione"],
          "Apply on wet scalp, leave 3-5 minutes, then rinse",
          "Twice a week for 4 weeks.",
          min_age=12, elderly_ok=True),
    _dose(["diclofenac", "pain-relief gel", "pain relief gel"],
          "Thin layer on the painful area, rub gently",
          "3 times a day, up to 7 days. Not on broken skin.",
          elderly_ok=True),
    _dose(["mouth ulcer", "choline salicylate", "benzocaine"],
          "Small amount on the ulcer with a clean finger",
          "3-4 times a day, up to 7 days.",
          min_age=12, elderly_ok=True),
    _dose(["benzoyl"],
          "Thin layer on pimples",
          "Once a day at night; start every second night if skin is dry.",
          min_age=12, elderly_ok=True),
]


def dose_for(med_name, patient):
    """Return (dose, timing, is_specific) from age, pregnancy and a fixed table."""
    age = patient["age"]
    hindi = patient["language"] == "हिन्दी"

    def doctor(reason_en, reason_hi):
        if hindi:
            return (f"डॉक्टर/फार्मासिस्ट तय करेंगे ({reason_hi})",
                    "डॉक्टर की सलाह के अनुसार", False)
        return (f"Doctor / pharmacist to decide ({reason_en})",
                "As advised by doctor", False)

    if patient.get("pregnant"):
        return doctor("pregnancy / breastfeeding", "गर्भावस्था/स्तनपान")

    low = med_name.lower()
    entry = None
    for keywords, d in DOSE_TABLE:
        if any(re.search(r"\b" + re.escape(k), low) for k in keywords):
            entry = d
            break

    if entry is None:
        if age < 18 or age >= 65:
            return doctor("due to age", "उम्र के कारण")
        if hindi:
            return "लेबल / फार्मासिस्ट के अनुसार", "लेबल के अनुसार", False
        return "As per product label / pharmacist", "As per label", False

    if age < entry["min_age"] or (age >= 65 and not entry["elderly_ok"]):
        return doctor("due to age", "उम्र के कारण")

    suffix = "_hi" if hindi else ""
    return entry["dose" + suffix], entry["time" + suffix], True


# --------------------------------------------------
# OFFLINE MEDICAL KNOWLEDGE BASE
# Used when no API key is set or the AI call fails. It reads ALL the
# complaints in a message and merges them into one guidance sheet.
# --------------------------------------------------

URGENCY_RANK = {"routine": 0, "soon": 1, "urgent": 2}

PARACETAMOL = ("Paracetamol (OTC pain / fever reliever)",
               "Eases pain, fever and body ache",
               "Avoid if liver disease or allergy.")
ORS = ("ORS (oral rehydration solution)", "Replaces lost fluids",
       "Prepare exactly as per packet.")
ANTACID = ("Antacid liquid or chewable tablet", "Eases acidity and burning",
           "Use only for burning/acid pain; not for severe pain.")
CETIRIZINE = ("Antihistamine (cetirizine)", "Eases sneezing, itching, allergy",
              "May cause drowsiness; avoid driving.")
LOZENGE = ("Throat lozenges", "Temporary throat relief",
           "Follow the age limits on the label.")
CALAMINE = ("Calamine lotion", "Soothes itching and skin irritation",
            "Do not apply on broken skin.")
FIBRE = ("Fibre supplement (isabgol / psyllium husk)", "Softens stool",
         "Take with plenty of water.")


def E(title, causes, home, meds, tests, red, see, kw,
      urgency="routine", female_only=False):
    return {"title": title, "causes": causes, "home": home, "meds": meds,
            "tests": tests, "red": red, "see": see, "kw": kw,
            "urgency": urgency, "female_only": female_only}


KB = [
    E("Fever",
      ["Viral fever or flu", "Throat or chest infection",
       "Dengue, malaria or typhoid if it lasts"],
      ["Rest and sleep well", "Drink water, ORS and soups regularly",
       "Wear light clothes; sponge with room-temperature water",
       "Check temperature every 6 hours"],
      [PARACETAMOL], ["CBC"],
      ["Confusion or stiff neck", "Difficulty breathing",
       "Seizure or rash with fever"],
      "See a doctor if fever lasts over 3 days or goes above 103°F (39.4°C).",
      ["fever", "temperature", "febrile", "bukhar", "बुखार"]),
    E("Headache",
      ["Tension headache", "Migraine",
       "Eye strain, dehydration or lack of sleep"],
      ["Rest in a quiet, dark room", "Drink water and do not skip meals",
       "Cold or warm compress on the forehead",
       "Limit screen time and sleep well"],
      [PARACETAMOL], [],
      ["Sudden, worst-ever headache", "Weakness, confusion or trouble speaking",
       "Headache after a head injury"],
      "See a doctor if headaches are frequent or last over 3 days.",
      ["headache", "head pain", "migraine", "sir dard", "sar dard",
       "सिरदर्द", "सिर दर्द"]),
    E("Cold and runny nose",
      ["Common cold (viral)", "Allergic rhinitis (dust / pollen)"],
      ["Steam inhalation 2-3 times a day", "Warm fluids, soup and rest",
       "Warm salt-water gargle", "Avoid cold drinks, dust and smoke"],
      [("Saline nasal spray or drops", "Clears a blocked nose",
        "Use a clean nozzle."), CETIRIZINE],
      [], ["Breathing difficulty", "Blue lips", "Chest pain"],
      "See a doctor if symptoms last over 7-10 days or fever develops.",
      ["cold", "runny nose", "blocked nose", "stuffy nose", "sneezing",
       "sneeze", "zukam", "jukam", "जुकाम", "सर्दी"]),
    E("Cough",
      ["Viral cough", "Throat irritation or post-nasal drip",
       "Bronchitis or asthma if it persists"],
      ["Warm water with honey (not under 1 year)", "Steam inhalation",
       "Avoid smoke, dust and cold drinks", "Sleep with the head raised"],
      [LOZENGE], [],
      ["Coughing blood", "Breathing difficulty", "Chest pain"],
      "See a doctor if cough lasts over 2 weeks or has wheezing.",
      ["cough", "coughing", "khansi", "खांसी", "खाँसी"]),
    E("Sore throat",
      ["Viral throat infection", "Tonsillitis (bacterial possible)",
       "Acid reflux or irritation"],
      ["Warm salt-water gargle 3-4 times a day",
       "Warm fluids and soups", "Rest your voice",
       "Avoid cold and fried food"],
      [LOZENGE, PARACETAMOL], ["Throat swab only if the doctor advises"],
      ["Cannot swallow saliva", "Breathing difficulty",
       "Rapid neck swelling"],
      "See a doctor if pain lasts over 3-5 days or with high fever.",
      ["sore throat", "throat pain", "throat irritation", "tonsil",
       "gale me dard", "gale mein dard", "गले में दर्द", "गले में खराश"]),
    E("Stomach pain",
      ["Indigestion or gastritis", "Gas or food intolerance",
       "Stomach infection"],
      ["Take small sips of fluids and light food (khichdi, banana, curd)",
       "Avoid spicy, oily food, tea and coffee",
       "Warm compress on the belly",
       "Note where the pain is and how severe"],
      [ANTACID], ["CBC", "Stool routine", "Ultrasound abdomen if it persists"],
      ["Severe or worsening pain", "Blood in vomit or stool",
       "Rigid abdomen or fainting"],
      "See a doctor if pain is severe or lasts over 2 days.",
      ["stomach pain", "stomach ache", "stomach", "abdominal pain",
       "abdomen", "belly pain", "pet dard", "पेट दर्द", "पेट में दर्द"]),
    E("Acidity",
      ["Acid reflux or gastritis", "Indigestion"],
      ["Eat small, frequent meals", "Avoid spicy, oily food, tea and coffee",
       "Wait 2-3 hours after food before lying down",
       "Keep the head of the bed raised"],
      [ANTACID], [],
      ["Black stools or vomiting blood", "Difficulty swallowing", "Chest pain"],
      "See a doctor if it happens most days or lasts over 2 weeks.",
      ["acidity", "heartburn", "acid reflux", "gas", "bloating", "burping",
       "खट्टी डकार", "एसिडिटी"]),
    E("Diarrhea",
      ["Stomach infection (gastroenteritis)", "Food poisoning",
       "Food intolerance"],
      ["Drink ORS and fluids after every loose stool",
       "Eat light food: khichdi, banana, rice, curd",
       "Avoid milk, oily and street food", "Wash hands well"],
      [ORS], ["Stool routine", "CBC"],
      ["Blood in stool", "Very little urine or dizziness",
       "Fever above 102°F"],
      "See a doctor if it lasts over 2 days or comes with blood or fever.",
      ["diarrhea", "diarrhoea", "loose motion", "loose motions",
       "loose stool", "watery stool", "dast", "दस्त"]),
    E("Vomiting",
      ["Stomach infection", "Food poisoning",
       "Indigestion or motion sickness"],
      ["Sip ORS or water slowly every few minutes",
       "Avoid solid food for 1-2 hours, then eat light food",
       "Rest and avoid strong smells", "Wash hands often"],
      [ORS], [],
      ["Blood in vomit", "Severe stomach pain",
       "Signs of dehydration or confusion"],
      "See a doctor if vomiting lasts over 1 day or fluids cannot stay down.",
      ["vomit", "vomiting", "nausea", "throwing up", "ulti", "उल्टी", "मतली"]),
    E("Constipation",
      ["Low fibre or low water intake", "Irregular routine"],
      ["Drink 8-10 glasses of water", "Eat fruits, vegetables and salad",
       "Walk daily and fix a toilet time", "Warm water in the morning"],
      [FIBRE], [],
      ["Severe belly pain with vomiting", "Blood in stool",
       "Cannot pass stool or gas"],
      "See a doctor if it lasts over 1 week.",
      ["constipation", "hard stool", "kabz", "कब्ज"]),
    E("Skin rash or itching",
      ["Skin allergy or contact dermatitis", "Fungal infection",
       "Insect bite or heat rash"],
      ["Avoid scratching and suspected triggers",
       "Cool compress; wear loose cotton clothes",
       "Use mild soap and keep skin dry"],
      [CALAMINE, CETIRIZINE], [],
      ["Breathing trouble or throat swelling",
       "Rash spreading fast with fever", "Blisters or peeling skin"],
      "See a doctor if the rash lasts over 3 days or keeps returning.",
      ["rash", "itchy skin", "itching", "itchy", "hives", "khujli",
       "खुजली", "allergy", "allergic"]),
    E("Back pain",
      ["Muscle strain", "Poor posture or disc problem",
       "Kidney or urine problem if with fever"],
      ["Avoid long bed rest; move gently", "Warm compress for 15 minutes",
       "Sit and sleep with good back support",
       "Avoid heavy lifting and sudden twisting"],
      [PARACETAMOL, ("Diclofenac pain-relief gel", "Local pain relief",
                     "Not on broken skin; wash hands after.")],
      ["Vitamin D, calcium if it persists"],
      ["Loss of bladder or bowel control", "Numbness around the groin",
       "Progressive leg weakness"],
      "See a doctor if pain lasts over 1 week or spreads down the leg.",
      ["back pain", "backache", "lower back pain", "kamar dard",
       "कमर दर्द", "पीठ दर्द"]),
    E("Joint or muscle pain",
      ["Muscle strain or overuse", "Viral body ache",
       "Arthritis or vitamin D deficiency if persistent"],
      ["Rest the area; avoid heavy lifting",
       "Warm compress for stiffness; cold pack for a fresh sprain",
       "Gentle stretching", "Keep a good posture"],
      [PARACETAMOL, ("Diclofenac pain-relief gel", "Local pain relief",
                     "Not on broken skin; wash hands after.")],
      ["Vitamin D, calcium if it persists"],
      ["Joint swelling with fever", "Cannot move or bear weight",
       "Numbness or weakness"],
      "See a doctor if pain lasts over 1 week or follows an injury.",
      ["joint pain", "knee pain", "body ache", "body pain", "muscle pain",
       "sprain", "shoulder pain", "neck pain", "badan dard",
       "जोड़ों", "घुटने", "बदन दर्द"]),
    E("Burning or painful urination",
      ["Urinary tract infection (cystitis)", "Dehydration",
       "Bladder stone or irritation"],
      ["Drink 2-3 litres of water a day",
       "Do not hold urine; empty the bladder often",
       "Keep the genital area clean; wear cotton underwear",
       "Avoid caffeine, alcohol and spicy food"],
      [("Paracetamol (OTC pain reliever)", "Eases pain or fever only",
        "Antibiotics only if a doctor prescribes after a urine test.")],
      ["Urine routine and culture"],
      ["Fever with chills or back pain", "Blood in urine",
       "Unable to pass urine"],
      "See a doctor within 1-2 days; antibiotics need a prescription.",
      ["burning urination", "burning urine", "burning while urinat",
       "burning in urine", "painful urination", "pain while urinat",
       "urinary", "urine infection", "uti", "bladder",
       "frequent urination", "peshab me jalan", "पेशाब में जलन"],
      urgency="soon"),
    E("Blood in urine",
      ["Urinary tract infection", "Kidney or bladder stone",
       "Kidney or bladder inflammation"],
      ["Drink plenty of water (2-3 litres a day) unless a doctor "
       "has restricted fluids",
       "Empty the bladder regularly; do not hold urine",
       "Avoid alcohol, caffeine and spicy food",
       "Note urine colour, pain and any fever"],
      [("Paracetamol (OTC pain reliever)", "Eases pain only",
        "No antibiotics or painkiller tablets before a doctor checks.")],
      ["Urine routine and culture", "Ultrasound KUB",
       "CBC and kidney function test"],
      ["Unable to pass urine", "Fever with back or flank pain",
       "Heavy bleeding or clots", "Dizziness or fainting"],
      "See a doctor within 24 hours for urine tests and an ultrasound; "
      "do not self-treat with antibiotics.",
      ["blood in urine", "blood in urin", "bloody urine", "hematuria",
       "haematuria", "red urine", "urine me khoon", "पेशाब में खून",
       "पेशाब में खून"],
      urgency="urgent"),
    E("Blood in stool",
      ["Piles (haemorrhoids)", "Anal fissure",
       "Intestinal infection or inflammation"],
      ["Eat high-fibre food and drink plenty of water",
       "Warm sitz bath for 10 minutes", "Avoid straining and spicy food"],
      [FIBRE], ["CBC", "Stool routine", "Doctor's examination"],
      ["Heavy bleeding", "Dizziness or fainting", "Black tarry stools"],
      "See a doctor within 24 hours.",
      ["blood in stool", "blood in motion", "blood while passing stool",
       "bleeding piles", "black stool", "tarry stool", "मल में खून"],
      urgency="urgent"),
    E("Toothache",
      ["Tooth decay (cavity)", "Gum infection", "Tooth sensitivity"],
      ["Rinse with warm salt water", "Cold compress on the cheek",
       "Avoid very hot, cold or sweet food", "Brush gently and floss"],
      [PARACETAMOL], ["Dental X-ray (by the dentist)"],
      ["Facial swelling", "Fever with tooth pain",
       "Difficulty swallowing or breathing"],
      "See a dentist within 1-2 days; infection needs proper treatment.",
      ["toothache", "tooth pain", "tooth ache", "gum pain", "dant dard",
       "दांत दर्द", "दाँत दर्द"],
      urgency="soon"),
    E("Red or irritated eyes",
      ["Conjunctivitis (pink eye)", "Dust or allergy irritation",
       "Eye strain"],
      ["Wash hands often; do not rub the eyes",
       "Clean with cooled boiled water", "Cold compress",
       "Avoid contact lenses and sharing towels"],
      [("Lubricant eye drops", "Soothes dry or irritated eyes",
        "No steroid or antibiotic drops without a doctor.")],
      [], ["Loss of vision", "Severe eye pain",
           "Injury or chemical in the eye"],
      "See an eye doctor if redness lasts over 2 days or has discharge.",
      ["red eye", "eye pain", "eye redness", "itchy eyes", "watery eyes",
       "conjunctivitis", "pink eye", "eye infection", "आंख लाल", "आँख लाल"],
      urgency="soon"),
    E("Ear pain",
      ["Ear infection", "Blocked ear wax", "Water in the ear"],
      ["Keep the ear dry", "Warm compress outside the ear",
       "Do not put oil, drops or sticks in the ear"],
      [PARACETAMOL], [],
      ["Discharge with fever", "Hearing loss", "Swelling behind the ear"],
      "See a doctor within 1-2 days.",
      ["ear pain", "earache", "ear ache", "ear discharge", "kaan dard",
       "कान दर्द"],
      urgency="soon"),
    E("Period cramps",
      ["Primary dysmenorrhoea (period cramps)", "Hormonal changes"],
      ["Hot water bag on the lower belly", "Light exercise or yoga",
       "Warm drinks; avoid caffeine", "Rest well"],
      [PARACETAMOL], [],
      ["Very heavy bleeding", "Severe pain not relieved", "Fever or fainting"],
      "See a gynaecologist if cramps are severe or cycles are irregular.",
      ["period pain", "menstrual cramp", "period cramps", "periods pain",
       "menstrual pain", "dysmenorrhea", "पीरियड"],
      female_only=True),
    E("Dizziness or weakness",
      ["Dehydration or low blood sugar", "Anaemia or low blood pressure",
       "Vitamin deficiency or lack of sleep"],
      ["Sit or lie down; get up slowly", "Drink water or ORS",
       "Eat regular, balanced meals", "Sleep 7-8 hours"],
      [ORS], ["CBC", "Blood sugar", "Vitamin B12 and D", "Thyroid profile"],
      ["Fainting", "Chest pain or palpitations", "Weakness on one side"],
      "See a doctor if dizziness is frequent or tiredness lasts over 1 week.",
      ["dizzy", "dizziness", "weakness", "fatigue", "tired", "giddiness",
       "chakkar", "thakan", "कमजोरी", "चक्कर", "थकान"]),
    E("Sleeplessness",
      ["Stress or irregular routine", "Too much caffeine or screen time"],
      ["Keep fixed sleep and wake times",
       "No screens or caffeine 2 hours before bed",
       "Light dinner; a glass of warm milk", "Slow deep breathing"],
      [], [], ["Low mood lasting weeks", "Breathing pauses during sleep"],
      "See a doctor if sleeplessness lasts over 2 weeks.",
      ["insomnia", "cannot sleep", "can't sleep", "cant sleep",
       "not able to sleep", "sleeplessness", "neend nahi", "नींद नहीं"]),
    E("Stress or anxiety",
      ["Stress or anxiety", "Lack of sleep or overwork"],
      ["Slow deep breathing for 5 minutes", "Daily walk or light exercise",
       "Talk to someone you trust", "Limit caffeine and keep a routine"],
      [], ["Thyroid profile if symptoms persist"],
      ["Thoughts of self-harm", "Panic attack with chest pain",
       "Unable to do daily tasks"],
      "Talk to a doctor or counsellor if it affects daily life; "
      "Tele-MANAS 14416 offers free support.",
      ["anxiety", "stress", "panic", "worried", "depressed", "low mood",
       "घबराहट", "तनाव"]),
    E("Minor cut, wound or burn",
      ["Minor cut or scrape", "Minor burn"],
      ["Wash with clean running water for 5-10 minutes",
       "For a burn: cool under running water for 10-20 minutes; no ice, "
       "toothpaste or butter",
       "Cover with a clean dressing", "Keep it clean and dry"],
      [("Povidone-iodine antiseptic", "Prevents infection in cuts",
        "Not for deep wounds or large burns.")], [],
      ["Bleeding that will not stop after 10 minutes",
       "Deep wound or large burn", "Pus, spreading redness or fever"],
      "See a doctor for deep cuts, large burns or if a tetanus shot is due.",
      ["cut", "wound", "burn", "burnt", "scrape", "injury", "chot",
       "जल गया", "कट गया"],
      urgency="soon"),
    E("Acne",
      ["Acne vulgaris", "Oily skin or hormonal changes"],
      ["Wash the face twice a day with a mild cleanser",
       "Do not pick or squeeze pimples",
       "Avoid oily cosmetics; change pillow covers often",
       "Eat a balanced diet and drink water"],
      [("Benzoyl peroxide 2.5% gel", "Reduces pimples",
        "May dry the skin; test a small patch first.")], [],
      ["Painful deep cysts", "Scarring"],
      "See a dermatologist if acne is severe or leaves marks.",
      ["acne", "pimple", "pimples", "muhase", "मुंहासे", "मुहांसे"]),
    E("Hair fall or dandruff",
      ["Seborrheic dermatitis (dandruff)",
       "Telogen effluvium (stress or illness hair shedding)",
       "Iron, B12, vitamin D deficiency or thyroid problem"],
      ["Wash hair with a mild shampoo 2-3 times a week",
       "Avoid tight hairstyles, harsh styling and heat",
       "Eat protein, iron and vitamin-rich food",
       "Manage stress and sleep well"],
      [("Anti-dandruff shampoo (ketoconazole 2% / zinc pyrithione)",
        "Treats scalp dandruff",
        "Leave on for 3-5 minutes, then rinse.")],
      ["CBC", "Vitamin B12", "Thyroid profile", "Vitamin D"],
      ["Patchy bald spots", "Painful, red, scaly scalp",
       "Sudden heavy hair loss"],
      "See a dermatologist if hair loss lasts over 2-3 months.",
      ["hair fall", "hairfall", "hair loss", "dandruff", "dandruf",
       "itchy scalp", "baal jhad", "बाल झड़", "रूसी"]),
    E("Fungal skin infection",
      ["Ringworm / tinea (fungal infection)"],
      ["Keep the skin clean and dry",
       "Wear loose cotton clothes; change daily", "Do not share towels",
       "Do not use steroid creams without a doctor"],
      [("Clotrimazole 1% cream", "Treats fungal infection",
        "Do not use on open wounds.")], [],
      ["Spreading fast", "Pus or severe pain", "No improvement in 2 weeks"],
      "See a doctor if there is no improvement in 2 weeks.",
      ["ringworm", "fungal", "fungus", "groin itching", "jock itch",
       "athlete's foot", "दाद"]),
    E("Mouth ulcer",
      ["Aphthous ulcer (vitamin deficiency, stress or injury)"],
      ["Rinse with warm salt water",
       "Avoid spicy, sour and very hot food",
       "Use a soft toothbrush and drink water",
       "Eat curd, banana and soft fruit"],
      [("Mouth ulcer gel (choline salicylate / benzocaine)",
        "Numbs and protects the ulcer", "Not for young children.")],
      ["CBC; vitamin B12 if recurrent"],
      ["Ulcer lasting over 2-3 weeks", "Difficulty swallowing", "Fever"],
      "See a doctor if the ulcer lasts over 2 weeks.",
      ["mouth ulcer", "ulcer in mouth", "mouth sore", "chhale",
       "मुंह में छाले", "छाले"]),
    E("Insect bite or sting",
      ["Insect bite or sting reaction"],
      ["Wash with soap and water", "Cold compress for 10 minutes",
       "Do not scratch", "Remove the sting if visible"],
      [CALAMINE, CETIRIZINE], [],
      ["Swelling of face or throat", "Breathing trouble",
       "Spreading redness"],
      "See a doctor if swelling spreads or lasts over 2 days.",
      ["insect bite", "mosquito bite", "bee sting", "sting", "bug bite",
       "काटा"]),
    E("Nosebleed",
      ["Dry air or nose picking", "Allergy or cold",
       "High blood pressure"],
      ["Sit upright and lean forward",
       "Pinch the soft part of the nose for 10 minutes",
       "Cold compress on the nose", "Do not tilt the head back"],
      [], [],
      ["Bleeding for over 20 minutes", "After a head injury",
       "Heavy bleeding"],
      "See a doctor if nosebleeds keep repeating.",
      ["nosebleed", "nose bleed", "bleeding from nose", "नाक से खून"],
      urgency="soon"),
    E("Wheezing or asthma",
      ["Asthma or allergic wheeze", "Bronchitis"],
      ["Sit upright, stay calm, breathe slowly",
       "Avoid dust, smoke and cold air",
       "Use your own prescribed inhaler if you have one",
       "Warm fluids"],
      [], ["Chest X-ray", "Spirometry (by the doctor)"],
      ["Severe breathlessness", "Blue lips",
       "Unable to speak full sentences"],
      "See a doctor within 1-2 days for proper treatment.",
      ["wheezing", "wheeze", "asthma", "whistling sound", "दमा", "अस्थमा"],
      urgency="soon"),
    E("Jaundice",
      ["Hepatitis (liver inflammation)", "Gallstones", "Blood disorder"],
      ["Rest and drink clean boiled water",
       "Eat light, low-fat food; avoid alcohol",
       "Avoid self-medication, including paracetamol"],
      [], ["Liver function test (LFT)", "Bilirubin",
           "Hepatitis A/B/E tests"],
      ["Confusion or sleepiness", "Vomiting blood", "Severe belly pain"],
      "See a doctor within 24 hours.",
      ["jaundice", "yellow eyes", "yellow skin", "yellow urine",
       "पीलिया", "peelia"],
      urgency="urgent"),
    E("Fever with chills",
      ["Dengue", "Malaria", "Typhoid"],
      ["Rest and drink plenty of fluids, ORS and coconut water",
       "Use mosquito nets or repellent", "Check temperature regularly",
       "Do not take aspirin or ibuprofen"],
      [PARACETAMOL, ORS],
      ["CBC with platelet count", "Dengue NS1 / IgM", "Malaria test",
       "Typhoid test"],
      ["Bleeding gums or nose", "Severe stomach pain or repeated vomiting",
       "Drowsiness or breathlessness"],
      "See a doctor within 24-48 hours for blood tests.",
      ["dengue", "malaria", "typhoid", "chills", "rigors", "platelet",
       "ठंड लगना", "कंपकंपी"],
      urgency="soon"),
]


def _match(entry, text):
    """Return the earliest position a keyword is found, or -1."""
    best = -1
    for k in entry["kw"]:
        if k.isascii():
            pattern = (r"\b" + re.escape(k) + r"\b" if len(k) <= 4
                       else r"\b" + re.escape(k))
            m = re.search(pattern, text)
            pos = m.start() if m else -1
        else:
            pos = text.find(k)
        if pos >= 0 and (best < 0 or pos < best):
            best = pos
    return best


def bump_urgency(text, urgency):
    """Long-lasting symptoms deserve a doctor visit sooner."""
    if urgency == "routine" and re.search(
        r"\b(\d+)\s*(weeks?|months?)\b|\b([3-9]|[1-9]\d)\s*(days?|din)\b|"
        r"\bsince\s+(last\s+)?(week|month)\b", text
    ):
        return "soon"
    return urgency


def _strip_allergy(t):
    t = t.lower()
    t = re.sub(r"\b(no|not|without)\s+(known\s+)?allerg\w*", " ", t)
    t = re.sub(r"\ballerg\w*\s+(to|with|from)\s+\w+", " ", t)
    return t


def fallback_reply(user_text, patient, latest=""):
    """user_text is the whole conversation so far (all patient messages);
    latest is the newest message, whose conditions are listed first."""
    latest_text = _strip_allergy(latest) if latest else ""
    text = user_text.lower()

    # Ignore allergy statements such as "allergic to penicillin" or
    # "no allergies" so they are not mistaken for symptoms.
    text = re.sub(r"\b(no|not|without)\s+(known\s+)?allerg\w*", " ", text)
    text = re.sub(r"\ballerg\w*\s+(to|with|from)\s+\w+", " ", text)

    found = []
    for entry in KB:
        if entry["female_only"] and patient["gender"] == "Male":
            continue
        pos = _match(entry, text)
        if pos >= 0:
            in_latest = 0 if (latest_text and _match(entry, latest_text) >= 0) else 1
            found.append((in_latest, -URGENCY_RANK[entry["urgency"]],
                          pos, entry))
    found.sort(key=lambda t: (t[0], t[1], t[2]))
    entries = [t[3] for t in found][:4]

    if not entries:
        return {
            "causes": ["Cause unclear - needs a clinical examination"],
            "urgency": "soon",
            "home_care": ["Rest and drink enough fluids",
                          "Note when the symptoms started and how severe "
                          "they are",
                          "Avoid taking medicines on your own"],
            "medicines": [],
            "tests": ["Basic tests as advised by the doctor"],
            "red_flags": ["Difficulty breathing", "Chest pain",
                          "Severe or rapidly worsening symptoms"],
            "see_doctor": "Please consult a doctor for a proper assessment.",
            "summary": ("Your symptoms need a proper examination to find "
                        "the cause. Rest, drink enough fluids and note when "
                        "the symptoms started. Avoid taking medicines on "
                        "your own until a doctor or pharmacist advises "
                        "you."),
            "_offline": True,
        }

    def merge(key, limit):
        out, seen = [], set()
        for entry in entries:
            for item in entry[key]:
                # Treat near-duplicates (same first two words) as one.
                base = re.sub(r"\(.*?\)", "", item.lower())
                sig = " ".join(base.split()[:2]) if key == "causes" else base
                if sig not in seen:
                    seen.add(sig)
                    out.append(item)
        return out[:limit]

    causes = merge("causes", 4)
    urgency = max((e["urgency"] for e in entries),
                  key=lambda u: URGENCY_RANK[u])
    urgency = bump_urgency(text, urgency)

    meds = [{"name": n, "purpose": p, "note": note}
            for e in entries for (n, p, note) in e["meds"]]

    # The most urgent condition's advice comes first.
    see = max(entries, key=lambda e: URGENCY_RANK[e["urgency"]])["see"]

    return {
        "causes": causes,
        "urgency": urgency,
        "home_care": merge("home", 5),
        "medicines": meds,
        "tests": merge("tests", 4),
        "red_flags": merge("red", 4),
        "see_doctor": see,
        "summary": "",
        "_offline": True,
    }


# --------------------------------------------------
# NORMALISING AND FINALISING A REPLY (same path for AI and offline)
# --------------------------------------------------

def clean_list(value, limit=4):
    if isinstance(value, str):
        value = [v.strip(" -•*\t") for v in re.split(r"[\n;]", value)]
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        if isinstance(v, dict):
            v = v.get("name") or v.get("text") or ""
        v = str(v).strip()
        if v:
            out.append(v)
    return out[:limit]


def normalise(data, user_text, patient):
    """Validate AI output so the card always renders correctly."""
    meds = []
    raw_meds = data.get("medicines") or data.get("medicine") or []
    if isinstance(raw_meds, (str, dict)):
        raw_meds = [raw_meds]
    for m in raw_meds[:5]:
        if isinstance(m, str) and m.strip():
            m = {"name": m.strip()}
        if isinstance(m, dict) and str(m.get("name", "")).strip():
            meds.append({
                "name": str(m.get("name", "")).strip(),
                "purpose": str(m.get("purpose", "")).strip(),
                "note": str(m.get("note", "")).strip(),
            })

    raw_causes = data.get("possible_causes") or data.get("causes")
    if isinstance(raw_causes, str):
        raw_causes = re.split(r"[,;\n]", raw_causes)
    causes = clean_list(raw_causes, 4)
    if not causes and data.get("diagnosis"):
        causes = [str(data["diagnosis"]).strip()]

    urgency = str(data.get("urgency", "routine")).strip().lower()
    if urgency not in URGENCY_RANK:
        urgency = "routine"

    return {
        "causes": causes,
        "urgency": urgency,
        "home_care": clean_list(data.get("home_care") or data.get("advice"), 5),
        "medicines": meds,
        "tests": clean_list(data.get("tests"), 4),
        "red_flags": clean_list(data.get("red_flags"), 4),
        "see_doctor": str(data.get("see_doctor", "")).strip(),
        "summary": str(data.get("summary", "")).strip(),
    }


SPEECH_WORDS = {
    "en": {
        "causes": "Possible causes",
        "urg": {
            "routine": "Self-care is reasonable for now.",
            "soon": "Please see a doctor soon, within one to two days.",
            "urgent": "This is urgent. Please see a doctor within 24 hours.",
        },
        "home": "Home care",
        "med": "Medicine",
        "nomed": "No medicine is needed right now. Follow the home care steps.",
        "tests": "Tests your doctor may advise",
        "warn": "Get emergency help if you have",
    },
    "hi": {
        "causes": "संभावित कारण",
        "urg": {
            "routine": "अभी घरेलू देखभाल पर्याप्त हो सकती है।",
            "soon": "कृपया जल्द, एक से दो दिन में डॉक्टर को दिखाएं।",
            "urgent": "यह ज़रूरी है। कृपया 24 घंटे के भीतर डॉक्टर को दिखाएं।",
        },
        "home": "घरेलू देखभाल",
        "med": "दवा",
        "nomed": "अभी किसी दवा की ज़रूरत नहीं है। घरेलू देखभाल का पालन करें।",
        "tests": "डॉक्टर ये जांच सुझा सकते हैं",
        "warn": "इन लक्षणों पर तुरंत आपातकालीन मदद लें",
    },
}


def short_name(name):
    return name.split("(")[0].strip()


def build_summary(rx, patient):
    """4-5 line paragraph: causes, urgency, home care, medicine."""
    W = SPEECH_WORDS["hi" if patient["language"] == "हिन्दी" else "en"]
    parts = []
    if rx["causes"]:
        parts.append(f"{W['causes']}: {', '.join(rx['causes'][:3])}.")
    parts.append(W["urg"][rx["urgency"]])
    if rx["home_care"]:
        parts.append(f"{W['home']}: {'; '.join(rx['home_care'][:3])}.")
    if rx["medicines"]:
        names = ", ".join(short_name(m["name"]) for m in rx["medicines"])
        parts.append(f"{W['med']}: {names}.")
    else:
        parts.append(W["nomed"])
    return " ".join(parts)


def build_speech(rx, patient):
    """Everything on the sheet, in a form that is pleasant to listen to."""
    W = SPEECH_WORDS["hi" if patient["language"] == "हिन्दी" else "en"]
    parts = [rx["summary"]]
    for m in rx["medicines"][:3]:
        dose, timing, _ = dose_for(m["name"], patient)
        parts.append(f"{short_name(m['name'])}: {dose}. {timing}")
    if rx.get("interim"):
        parts.append(rx["interim"])
    if rx["tests"]:
        parts.append(f"{W['tests']}: {', '.join(rx['tests'])}.")
    if rx["see_doctor"]:
        parts.append(rx["see_doctor"])
    if rx["red_flags"]:
        parts.append(f"{W['warn']}: {'; '.join(rx['red_flags'])}.")
    return " ".join(p.strip() for p in parts if p and p.strip())


REPORT_RE = re.compile(
    r"\b(report|reports|test|tests|culture|ultrasound|scan|x-?ray|lab|blood)\b"
    r".{0,60}\b(done|came|shows?|showed|positive|confirmed|says?|revealed|"
    r"is|are|was)\b|\bdiagnosed\b|\bdoctor\s+(said|told|confirmed)\b|"
    r"\bconfirmed\b|\btested\s+positive\b",
    re.IGNORECASE | re.DOTALL,
)
FUTURE_RE = re.compile(
    r"\b(need|have to|has to|should|will|going to|want to|how to|to get|"
    r"to do|to take|before)\b.{0,20}\b(test|tests|report|scan)\b",
    re.IGNORECASE | re.DOTALL,
)


def report_mentioned(text):
    """True if the patient says a test or doctor already confirmed something."""
    return bool(REPORT_RE.search(text)) and not FUTURE_RE.search(text)


INTERIM_TEXT = {
    "en": {
        "tests": ("These medicines only ease your symptoms until your reports "
                  "come. Further medicine, if needed, will be decided by your "
                  "doctor on the basis of the report."),
        "report": ("Please show your report to a doctor. Antibiotics and other "
                   "prescription medicines can only be prescribed by the "
                   "doctor after seeing your report, allergies and health "
                   "history. Until then, use only the symptom relief above."),
    },
    "hi": {
        "tests": ("ये दवाएं रिपोर्ट आने तक केवल लक्षणों में राहत के लिए हैं। "
                  "आगे की दवा, यदि ज़रूरी हो, डॉक्टर रिपोर्ट के आधार पर तय "
                  "करेंगे।"),
        "report": ("कृपया अपनी रिपोर्ट डॉक्टर को दिखाएं। एंटीबायोटिक और अन्य "
                   "प्रिस्क्रिप्शन दवाएं डॉक्टर रिपोर्ट, एलर्जी और स्वास्थ्य "
                   "इतिहास देखकर ही देंगे। तब तक केवल ऊपर दी गई लक्षण-राहत "
                   "वाली दवा लें।"),
    },
}


def interim_note(rx, patient, report):
    T = INTERIM_TEXT["hi" if patient["language"] == "हिन्दी" else "en"]
    if report:
        return T["report"]
    if rx["tests"]:
        return T["tests"]
    return ""


def finalize(rx, user_text, patient, report=False):
    """Apply safety filters, smart urgency and build the spoken text."""
    rx["type"] = "advice"
    rx["medicines"] = sanitize_medicines(rx["medicines"], patient)
    rx["urgency"] = bump_urgency(user_text.lower(), rx["urgency"])
    if not rx["causes"]:
        rx["causes"] = ["Cause unclear - needs a clinical examination"]
    if not rx["see_doctor"]:
        rx["see_doctor"] = "Please consult a doctor if symptoms persist."
    rx["diagnosis"] = ", ".join(rx["causes"])

    # Offline replies (and AI replies with an empty summary) get a built one.
    if not rx.get("summary"):
        rx["summary"] = build_summary(rx, patient)
    rx["interim"] = interim_note(rx, patient, report)
    rx["speech"] = build_speech(rx, patient)
    return rx


def emergency_rx(category, is_crisis, hindi=False):
    if is_crisis:
        msg = CRISIS_REPLY_HI if hindi else CRISIS_REPLY_EN
    else:
        msg = EMERGENCY_REPLY_HI if hindi else EMERGENCY_REPLY_EN
    return {
        "type": "emergency",
        "diagnosis": category,
        "causes": [], "home_care": [], "medicines": [], "tests": [],
        "red_flags": [], "see_doctor": "", "summary": "", "urgency": "urgent",
        "speech": msg, "emergency_text": msg, "crisis": is_crisis,
        "lang": "hi-IN" if hindi else "en-IN",
    }


# --------------------------------------------------
# OPENROUTER REQUEST (short prompt + token cap = faster answers)
# --------------------------------------------------

def parse_json_reply(raw):
    """Pull a JSON object out of a model reply, even if it is wrapped in
    markdown fences, has <think> text before it, or was cut off."""
    if not raw:
        return None
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    text = text.replace("```json", "```").replace("```", "")
    start = text.find("{")
    if start < 0:
        return None
    text = text[start:]

    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass

    # Repair a reply that was cut off before the closing brackets.
    closers = ['"]}', '"}', ']}', '}', '"]}}', '"}]}']
    for base in (text, text.rsplit(",", 1)[0]):
        for suffix in closers:
            try:
                obj = json.loads(base + suffix)
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                continue
    return None


def extract_text(result):
    choices = result.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return (content or "").strip()


def shorten_text(raw, max_chars=650):
    """Turn a plain-text AI answer into a short paragraph."""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    text = re.sub(r"[#*`>_|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    out = ""
    for s in sentences[:6]:
        if len(out) + len(s) > max_chars:
            break
        out = (out + " " + s).strip()
    return out or text[:max_chars]


def history_text(item):
    """Compact text version of a stored message for LLM context."""
    rx = item.get("rx")
    if rx and rx.get("type") == "advice":
        meds = ", ".join(m["name"] for m in rx.get("medicines", []))
        return ("[Previous sheet] possible causes: "
                f"{rx.get('diagnosis', '')}; urgency: {rx.get('urgency', '')}; "
                f"medicines: {meds or 'none'}; "
                f"tests: {', '.join(rx.get('tests', [])) or 'none'}")
    return item["content"]


def ask_openrouter(user_text, patient_context, conversation, lang_name="English"):
    """Return (data, raw_text, error). data is None if no usable JSON."""
    clean_key = str(api_key).strip().strip('"').strip("'")
    if not clean_key:
        return None, "", "No API key set"

    messages = [{
        "role": "system",
        "content": SYSTEM_PROMPT + f"\nLanguage: {lang_name}",
    }]
    for item in conversation[-10:]:
        if item["role"] in ("user", "assistant"):
            messages.append({"role": item["role"],
                             "content": history_text(item)})
    messages.append({
        "role": "user",
        "content": (f"Patient context:\n{patient_context}\n\n"
                    f"Latest patient message:\n{user_text}"),
    })

    payload = json.dumps({
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1800,  # room for models that "think" before answering
    }).encode("utf-8")

    last_error = "Unknown error"
    for _ in range(2):  # one retry for a busy free model
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {clean_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://streamlit.io",
                "X-Title": "MedAssist AI",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            if isinstance(result.get("error"), dict):
                last_error = ("OpenRouter: " +
                              str(result["error"].get("message", "error")))[:150]
                continue
            answer = extract_text(result)
            if not answer:
                last_error = "Model returned an empty reply"
                continue
            data = parse_json_reply(answer)
            if data:
                return data, answer, ""
            # Plain-text answer: still useful, the app will structure it.
            return None, answer, "AI answered in plain text"
        except urllib.error.HTTPError as ex:
            last_error = f"HTTP {ex.code} from OpenRouter"
            if ex.code in (401, 402, 403):
                break  # key or credit problem - retrying will not help
        except (urllib.error.URLError, TimeoutError, ValueError,
                KeyError, TypeError, OSError) as ex:
            last_error = f"{type(ex).__name__}: {ex}"[:120]
    return None, "", last_error


# --------------------------------------------------
# PRESCRIPTION-STYLE RENDERING
# --------------------------------------------------

LABELS = {
    "en": {
        "diag": "Diagnosis (possible)",
        "med": "Medicine", "dose": "Dosage",
        "timing": "Timing - Freq. - Duration",
        "home": "Home care", "tests": "Tests advised",
        "doc": "See a doctor", "warn": "Emergency warning signs",
        "note": "Doctor's note",
        "nomed": "No medicine is needed right now. Follow the home care steps.",
        "urg": {
            "routine": "🟢 Self-care is reasonable",
            "soon": "🟠 See a doctor soon (within 1-2 days)",
            "urgent": "🔴 Urgent: see a doctor within 24 hours",
        },
        "foot": ("Educational demo. Not a diagnosis or prescription. "
                 "No antibiotics or prescription medicines are suggested. "
                 "Confirm any medicine with a doctor or pharmacist."),
        "pregnant": ("Pregnant or breastfeeding: a doctor must decide every "
                     "medicine."),
        "maybe_preg": ("If you are pregnant or breastfeeding, ask a doctor "
                       "before taking any medicine."),
    },
    "hi": {
        "diag": "निदान (संभावित)",
        "med": "दवा", "dose": "मात्रा",
        "timing": "समय - अवधि",
        "home": "घरेलू देखभाल", "tests": "सुझाई गई जांच",
        "doc": "डॉक्टर को कब दिखाएं", "warn": "आपातकालीन संकेत",
        "note": "डॉक्टर का नोट",
        "nomed": "अभी किसी दवा की ज़रूरत नहीं है। घरेलू देखभाल का पालन करें।",
        "urg": {
            "routine": "🟢 घरेलू देखभाल पर्याप्त हो सकती है",
            "soon": "🟠 जल्द डॉक्टर को दिखाएं (1-2 दिन में)",
            "urgent": "🔴 ज़रूरी: 24 घंटे में डॉक्टर को दिखाएं",
        },
        "foot": ("शैक्षिक डेमो। निदान या नुस्खा नहीं। कोई एंटीबायोटिक या "
                 "प्रिस्क्रिप्शन दवा नहीं सुझाई जाती। दवा लेने से पहले "
                 "डॉक्टर/फार्मासिस्ट से पूछें।"),
        "pregnant": ("गर्भावस्था/स्तनपान में हर दवा डॉक्टर तय करें।"),
        "maybe_preg": ("यदि आप गर्भवती हैं या स्तनपान कराती हैं, तो कोई भी "
                       "दवा लेने से पहले डॉक्टर से पूछें।"),
    },
}


def build_rx_html(rx, patient):
    e = html.escape
    L = LABELS["hi" if patient["language"] == "हिन्दी" else "en"]

    info = (f"{e(patient['name'] or '—')} | Age: {patient['age']} | "
            f"{e(patient['gender'])}")
    if patient["weight"] > 0:
        info += f" | {patient['weight']:g} kg"
    if patient["allergies"]:
        info += f" | Allergies: {e(patient['allergies'])}"

    urgency = rx.get("urgency", "routine")
    badge = (f"<div class='rx-urg rx-urg-{urgency}'>"
             f"{e(L['urg'][urgency])}</div>")

    rows = ""
    for i, m in enumerate(rx["medicines"], 1):
        dose, timing, _ = dose_for(m["name"], patient)
        rows += (
            f"<tr><td>{i}) <b>{e(m['name'])}</b>"
            f"<br><span class='rx-sub'>{e(m['purpose'])}</span></td>"
            f"<td>{e(dose)}</td><td>{e(timing)}</td></tr>"
        )
        if m["note"]:
            rows += (f"<tr><td colspan='3' class='rx-note'>"
                     f"Notes: {e(m['note'])}</td></tr>")
    if rows:
        table = (
            "<div class='rx-symbol'>℞</div>"
            "<table class='rx-table'><tr>"
            f"<th>{L['med']}</th><th>{L['dose']}</th>"
            f"<th>{L['timing']}</th></tr>{rows}</table>"
        )
    else:
        table = (f"<div class='rx-section'><span class='rx-symbol'>℞</span> "
                 f"{e(L['nomed'])}</div>")

    def bullets(title, items):
        if not items:
            return ""
        li = "".join(f"<li>{e(x)}</li>" for x in items)
        return f"<div class='rx-section'><b>{title}:</b><ul>{li}</ul></div>"

    home = bullets(L["home"], rx["home_care"])
    tests = ""
    if rx["tests"]:
        tests = (f"<div class='rx-section'><b>{L['tests']}:</b> "
                 f"{e(', '.join(rx['tests']))}</div>")
    note = ""
    if rx["summary"]:
        note = (f"<div class='rx-section'><b>📝 {L['note']}:</b> "
                f"{e(rx['summary'])}</div>")
    doc = ""
    if rx["see_doctor"]:
        doc = (f"<div class='rx-section'><b>{L['doc']}:</b> "
               f"{e(rx['see_doctor'])}</div>")
    warn = ""
    if rx["red_flags"]:
        warn = (f"<div class='rx-warn'>🚨 <b>{L['warn']}:</b> "
                f"{e('; '.join(rx['red_flags']))}</div>")

    preg = ""
    if patient.get("pregnant"):
        preg = f"<div class='rx-warn'>🤰 {e(L['pregnant'])}</div>"
    elif patient["gender"] == "Female" and 12 <= patient["age"] <= 50:
        preg = f"<div class='rx-warn'>🤰 {e(L['maybe_preg'])}</div>"

    notice = ""
    if rx.get("notice"):
        notice = f"<div class='rx-info'>ℹ️ {e(rx['notice'])}</div>"

    interim = ""
    if rx.get("interim"):
        interim = f"<div class='rx-info'>ℹ️ {e(rx['interim'])}</div>"

    return (
        "<div class='rx-card'>"
        "<div class='rx-head'><span class='rx-clinic'>🩺 MedAssist AI</span>"
        f"<span class='rx-date'>{date.today().strftime('%d %b %Y')}</span></div>"
        f"<div class='rx-patient'>{info}</div>"
        f"<div class='rx-diag'><b>{L['diag']}:</b> {e(rx['diagnosis'])}</div>"
        f"{badge}{notice}{table}{interim}{home}{tests}{note}{doc}{warn}{preg}"
        f"<div class='rx-foot'>{e(L['foot'])}</div></div>"
    )


def render_reply(rx, patient, key):
    """Show one assistant reply (card or emergency alert)."""
    if rx["type"] == "emergency":
        if rx.get("crisis"):
            st.warning("💙 " + rx["emergency_text"])
        else:
            st.error("🚨 " + rx["emergency_text"])
        return

    card = build_rx_html(rx, patient)
    st.markdown(card, unsafe_allow_html=True)

    page = ("<html><head><meta charset='utf-8'><style>body{font-family:"
            "Arial;max-width:700px;margin:20px auto}"
            ".rx-card{border:1px solid #999;padding:16px}"
            ".rx-table{width:100%;border-collapse:collapse}"
            ".rx-table td,.rx-table th{text-align:left;padding:6px;"
            "border-bottom:1px solid #ddd}.rx-sub,.rx-foot{color:#777;"
            "font-size:12px}.rx-warn{background:#fff4f4;padding:6px;"
            "margin-top:8px}.rx-section{margin-top:8px}.rx-info{background:#e3f2fd;padding:6px;margin-top:8px}</style></head><body>"
            f"{card}</body></html>")
    st.download_button(
        "⬇️ Download prescription sheet",
        data=page,
        file_name="medassist_prescription.html",
        mime="text/html",
        key=f"dl_{key}",
    )


# --------------------------------------------------
# TEXT-TO-SPEECH (browser speech synthesis)
# --------------------------------------------------

def chunk_text(text, lang, limit=180):
    """Split text into sentence-sized pieces; browsers cut off long speech."""
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    chunks, current = [], ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > limit:
            chunks.append([current, lang])
            current = s
        else:
            current = (current + " " + s).strip()
    if current:
        chunks.append([current, lang])
    return chunks


def play_audio(segments, autoplay=True):
    """segments: list of [text, language_code]. Adds Read / Stop buttons."""
    if not segments:
        return

    safe = json.dumps(segments).replace("</", "<\\/")
    auto = "true" if autoplay else "false"

    page = f"""
    <div style="font-family:Arial">
      <button id="speak-button" style="background:#0E76A8;color:white;
        border:0;padding:8px 14px;border-radius:7px;cursor:pointer;
        font-size:14px;">🔊 Read aloud / सुनें</button>
      <button id="stop-button" style="background:#555;color:white;border:0;
        padding:8px 14px;border-radius:7px;cursor:pointer;font-size:14px;
        margin-left:6px;">⏹ Stop</button>
    </div>
    <script>
      const segments = {safe};
      const auto = {auto};

      function synthTools() {{
        try {{
          if (window.parent && window.parent.speechSynthesis) {{
            return [window.parent.speechSynthesis,
                    window.parent.SpeechSynthesisUtterance];
          }}
        }} catch (e) {{}}
        return [window.speechSynthesis, window.SpeechSynthesisUtterance];
      }}

      function speak() {{
        const tools = synthTools();
        const synth = tools[0], Utter = tools[1];
        if (!synth || !Utter) return;
        synth.cancel();
        segments.forEach(function (s) {{
          const u = new Utter(s[0]);
          u.lang = s[1];
          u.rate = 0.98;
          synth.speak(u);
        }});
      }}

      document.getElementById("speak-button").onclick = speak;
      document.getElementById("stop-button").onclick = function () {{
        const synth = synthTools()[0];
        if (synth) synth.cancel();
      }};

      // Some browsers block automatic speech until the page was tapped once.
      if (auto) setTimeout(speak, 300);
    </script>
    """
    components.html(page, height=60)


# --------------------------------------------------
# VOICE INPUT (speech to text, Hindi or English, Chrome / Edge)
# Fills the chat box with what was said and sends it.
# --------------------------------------------------

VOICE_WIDGET = """
<div style="font-family:Arial;display:flex;gap:8px;flex-wrap:wrap;
  align-items:center">
  <button id="en" style="background:#2e7d32;color:white;border:0;
    padding:9px 14px;border-radius:8px;cursor:pointer;font-size:14px;">
    🎤 Speak in English</button>
  <button id="hi" style="background:#ef6c00;color:white;border:0;
    padding:9px 14px;border-radius:8px;cursor:pointer;font-size:14px;">
    🎤 हिन्दी में बोलें</button>
</div>
<div id="status" style="font-family:Arial;font-size:13px;color:#555;
  margin-top:6px;min-height:18px"></div>
<script>
(function () {
  var w = window.parent;
  var SR = (w && (w.SpeechRecognition || w.webkitSpeechRecognition)) ||
           window.SpeechRecognition || window.webkitSpeechRecognition;
  var status = document.getElementById("status");
  if (!SR) {
    status.textContent = "Voice input needs Chrome or Edge. / वॉइस इनपुट के लिए Chrome या Edge चाहिए।";
  }

  function sendToChat(text) {
    var d = w.document;
    var box = d.querySelector('[data-testid="stChatInputTextArea"]') ||
              d.querySelector('[data-testid="stChatInput"] textarea');
    if (!box) { status.textContent = "Could not find the chat box."; return; }
    var setter = Object.getOwnPropertyDescriptor(
      w.HTMLTextAreaElement.prototype, "value").set;
    setter.call(box, text);
    box.dispatchEvent(new w.Event("input", { bubbles: true }));
    setTimeout(function () {
      var btn = d.querySelector('[data-testid="stChatInputSubmitButton"]') ||
                d.querySelector('[data-testid="stChatInput"] button');
      if (btn) { btn.click(); }
    }, 300);
  }

  function listen(lang) {
    if (!SR) return;
    try { w.speechSynthesis.cancel(); } catch (e) {}
    var rec = new SR();
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = false;
    var finalText = "";
    var failed = false;
    rec.onstart = function () {
      status.textContent = (lang === "hi-IN")
        ? "🎙️ सुन रहा हूँ... अब बोलिए" : "🎙️ Listening... speak now";
    };
    rec.onresult = function (e) {
      var live = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        live += e.results[i][0].transcript;
        if (e.results[i].isFinal) { finalText += e.results[i][0].transcript; }
      }
      status.textContent = "“" + (finalText || live) + "”";
    };
    rec.onerror = function (e) {
      failed = true;
      status.textContent = "Voice error: " + e.error +
        (e.error === "not-allowed" ? " - please allow the microphone." : "");
    };
    rec.onend = function () {
      if (finalText.trim()) { sendToChat(finalText.trim()); }
      else if (!failed) { status.textContent = "Did not catch that. Please try again."; }
    };
    rec.start();
  }

  document.getElementById("en").onclick = function () { listen("en-IN"); };
  document.getElementById("hi").onclick = function () { listen("hi-IN"); };
})();
</script>
"""


# --------------------------------------------------
# GREETING (shown and read aloud in English and Hindi)
# --------------------------------------------------

GREETING_EN = (
    "Hello! 👋 I'm **MedAssist AI**.\n\n"
    "Tell me **all your symptoms in one message** - what you feel, "
    "for how long, how severe it is, and any allergies or medicines you "
    "take. I'll give your prescription-style guidance sheet right away.\n\n"
    "You can type, or tap 🎤 to speak in English or Hindi. "
    "What problem are you facing?"
)
GREETING_HI = (
    "नमस्ते! 👋 मैं **MedAssist AI** हूँ।\n\n"
    "अपने **सभी लक्षण एक ही संदेश में** बताइए - क्या महसूस हो रहा है, "
    "कितने समय से, कितना तेज़ है, और कोई एलर्जी या दवा। मैं तुरंत आपके "
    "लिए पर्ची जैसी मार्गदर्शन शीट तैयार कर दूँगा।\n\n"
    "आप टाइप कर सकते हैं, या 🎤 दबाकर हिंदी या अंग्रेज़ी में बोल सकते हैं। "
    "आपको क्या समस्या है?"
)
GREETING_SEGMENTS = (
    chunk_text("Hello! I am MedAssist AI. Tell me all your symptoms in one "
               "message: what you feel, for how long, how severe it is, and "
               "any allergies or medicines you take. I will give your "
               "prescription style guidance sheet right away. You can type, "
               "or tap the microphone to speak in English or Hindi. "
               "What problem are you facing?", "en-IN")
    + chunk_text("नमस्ते! मैं मेडअसिस्ट एआई हूँ। अपने सभी लक्षण एक ही संदेश "
                 "में बताइए: क्या महसूस हो रहा है, कितने समय से, कितना "
                 "तेज़ है, और कोई एलर्जी या दवा। मैं तुरंत आपके लिए पर्ची "
                 "जैसी मार्गदर्शन शीट तैयार कर दूँगा। आप टाइप कर सकते हैं, "
                 "या माइक दबाकर हिंदी या अंग्रेज़ी में बोल सकते हैं। आपको "
                 "क्या समस्या है?", "hi-IN")
)
HINDI_OFFLINE_NOTICE = (
    "ऑफ़लाइन मोड में उत्तर अंग्रेज़ी में है। हिंदी उत्तर के लिए AI कनेक्शन "
    "ज़रूरी है।"
)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

# Ask for age and gender first: dosage and timing depend on them.
if "profile" not in st.session_state:
    st.subheader("👤 Before we start / शुरू करने से पहले")
    st.write(
        "Please enter your **age** and **gender**. The dosage and timing "
        "on your prescription sheet depend on them. / कृपया अपनी **उम्र** "
        "और **लिंग** भरें।"
    )
    with st.form("intake"):
        in_name = st.text_input("Name / नाम (optional)")
        col1, col2 = st.columns(2)
        in_age = col1.number_input(
            "Age / उम्र (years)", min_value=0, max_value=120, value=None,
            placeholder="Enter age",
        )
        in_gender = col2.selectbox("Gender / लिंग",
                                   ["Select", "Male", "Female", "Other"])
        in_pregnant = st.checkbox(
            "Pregnant or breastfeeding / गर्भवती या स्तनपान (if applicable)"
        )
        started = st.form_submit_button("Start consultation / शुरू करें")

    if started:
        if in_age is None or in_gender == "Select":
            st.error("Please enter both age and gender to continue.")
        else:
            st.session_state.profile = {
                "name": in_name.strip(),
                "age": int(in_age),
                "gender": in_gender,
                "pregnant": bool(in_pregnant) and in_gender != "Male",
            }
            st.rerun()
    st.stop()

profile = st.session_state.profile
st.sidebar.markdown(
    f"**Patient:** {profile['name'] or '—'}  \n"
    f"{profile['age']} yrs, {profile['gender']}"
)
status_box = st.sidebar.empty()


def show_status():
    mode = st.session_state.get("mode")
    if mode == "AI":
        status_box.success("🟢 AI mode connected")
    elif mode == "Offline":
        err = st.session_state.get("last_error", "")
        status_box.warning(
            "🟡 Offline medical engine" + (f"\n\nReason: {err}" if err else "")
        )


show_status()

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": GREETING_EN + "\n\n---\n\n" + GREETING_HI,
        "rx": None,
        "greeting": True,
    }]

patient = {
    "name": profile["name"],
    "age": profile["age"],
    "gender": profile["gender"],
    "pregnant": profile.get("pregnant", False),
    "weight": float(patient_weight),
    "allergies": allergies.strip(),
    "language": "English",
}

# Read the chat box first so we know if a new message is arriving.
user_input = st.chat_input("Type or speak your symptoms / लक्षण लिखें या बोलें...")
new_message = bool(user_input and user_input.strip())

last_idx = len(st.session_state.messages) - 1
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message.get("rx"):
            render_reply(message["rx"], message.get("patient", patient), idx)
            # Keep Read/Stop buttons on the latest answer after any rerun.
            if idx == last_idx and not new_message and message["rx"].get("speech"):
                play_audio(chunk_text(message["rx"]["speech"],
                                      message["rx"].get("lang", "en-IN")),
                           autoplay=False)
        else:
            st.markdown(message["content"])
            if message.get("greeting"):
                play_audio(GREETING_SEGMENTS,
                           autoplay=not st.session_state.get("greeted"))
                st.session_state.greeted = True


# --------------------------------------------------
# CHAT RESPONSE
# --------------------------------------------------

if new_message:
    user_input = user_input.strip()

    # Answer in the language the patient used.
    reply_hindi = detect_language(user_input) == "hi"
    speech_lang = "hi-IN" if reply_hindi else "en-IN"
    lang_name = "Hindi (Devanagari script)" if reply_hindi else "English"
    patient_r = dict(patient, language="हिन्दी" if reply_hindi else "English")

    st.session_state.messages.append(
        {"role": "user", "content": user_input, "rx": None}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analysing your symptoms... / जांच हो रही है..."):
            category, is_crisis = emergency_check(user_input)

            if category:
                reply = emergency_rx(category, is_crisis, reply_hindi)
            else:
                patient_context = (
                    f"Age: {patient['age']}\n"
                    f"Gender: {patient['gender']}\n"
                    f"Pregnant or breastfeeding: "
                    f"{'Yes' if patient['pregnant'] else 'No / not stated'}\n"
                    f"Weight in kg: "
                    f"{patient_weight if patient_weight > 0 else 'Unknown'}\n"
                    f"Medicine allergies: {allergies or 'Unknown'}\n"
                    f"Current medicines: {current_medicines or 'Unknown'}\n"
                    f"Relevant medical history: {medical_history or 'Unknown'}"
                )
                previous = st.session_state.messages[:-1]

                # The bot remembers every patient message until Reset.
                user_msgs = [m["content"] for m in st.session_state.messages
                             if m["role"] == "user"]
                context_text = " . ".join(user_msgs)
                report = any(report_mentioned(t) for t in user_msgs)

                data, raw_text, error = ask_openrouter(
                    user_input, patient_context, previous, lang_name
                )
                offline = fallback_reply(context_text, patient_r,
                                         latest=user_input)

                if data:
                    # AI gave structured data: use it, fill gaps from the
                    # offline medical knowledge.
                    reply = normalise(data, user_input, patient_r)
                    for field in ("causes", "home_care", "tests",
                                  "red_flags", "see_doctor"):
                        if not reply[field] and offline.get(field):
                            reply[field] = offline[field]
                    if not reply["medicines"] and reply["urgency"] != "urgent":
                        reply["medicines"] = offline["medicines"]
                    reply["lang"] = speech_lang
                    st.session_state.mode = "AI"
                    st.session_state.last_error = ""
                elif raw_text and len(raw_text) > 40:
                    # Plain-text AI answer becomes the doctor's note on top of
                    # the structured offline sheet.
                    reply = offline
                    reply["summary"] = shorten_text(raw_text)
                    reply["_ai_text"] = True
                    reply["lang"] = speech_lang
                    st.session_state.mode = "AI"
                    st.session_state.last_error = ""
                else:
                    reply = offline
                    reply["lang"] = "en-IN"  # offline engine is English
                    st.session_state.mode = "Offline"
                    st.session_state.last_error = error

                # The offline engine only knows English: keep the sheet
                # consistent and tell Hindi users why.
                if reply.get("_offline") and reply_hindi:
                    patient_r = dict(patient, language="English")
                    if not reply.get("_ai_text"):
                        reply["notice"] = HINDI_OFFLINE_NOTICE

                reply = finalize(reply, context_text, patient_r, report)

        key = len(st.session_state.messages)
        render_reply(reply, patient_r, key)

        if voice_on:
            play_audio(chunk_text(reply["speech"], reply.get("lang", speech_lang)))

    show_status()
    st.session_state.messages.append({
        "role": "assistant",
        "content": reply["speech"] or reply["diagnosis"],
        "rx": reply,
        "patient": patient_r,
    })


# --------------------------------------------------
# VOICE INPUT BUTTONS (always just above the chat box)
# --------------------------------------------------

st.caption("🎤 Speak your symptoms / बोलकर लक्षण बताएं")
components.html(VOICE_WIDGET, height=90)
