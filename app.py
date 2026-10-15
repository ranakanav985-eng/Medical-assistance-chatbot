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

# Styling for the prescription card.
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
.rx-warn{background:#fff4f4;border-left:4px solid #d32f2f;
  padding:6px 10px;margin-top:10px;font-size:13px;}
.rx-foot{font-size:11px;color:#777;margin-top:10px;}
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------
# API CONFIGURATION
# --------------------------------------------------

def get_api_key():
    try:
        key = st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        key = ""

    return key or os.getenv("OPENROUTER_API_KEY", "")


api_key = get_api_key()

with st.sidebar:
    st.subheader("⚙️ Settings")

    if not api_key:
        api_key = st.text_input(
            "OpenRouter API key",
            type="password",
            help="Optional. Leave blank to use the basic local "
                 "symptom guidance engine.",
        )

    language = st.radio("Language / भाषा", ["English", "हिन्दी"], horizontal=True)
    voice_on = st.toggle("🔊 Speak responses", value=True)

    with st.expander("Patient information", expanded=True):
        patient_name = st.text_input("Name (optional)")
        patient_age = st.number_input(
            "Age (years)", min_value=0, max_value=120, value=18
        )
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
        st.rerun()

SPEECH_LANG = "hi-IN" if language == "हिन्दी" else "en-IN"


# --------------------------------------------------
# CLINICAL SAFETY RULES
# --------------------------------------------------

SYSTEM_PROMPT = """
You are MedAssist AI, an educational clinical triage assistant.
Reply with ONE JSON object only. No markdown, no text outside the JSON.

Schema:
{
 "type": "advice" or "question",
 "diagnosis": "Possible cause(s), max 12 words, never a confirmed diagnosis",
 "advice": ["max 3 short supportive-care tips"],
 "medicines": [{"name": "over-the-counter medicine or product, or a
     non-drug measure like ORS", "purpose": "max 6 words",
     "note": "one short precaution, max 12 words"}],
 "tests": ["tests a doctor may advise, max 3, can be empty"],
 "red_flags": ["max 3 emergency warning signs"],
 "see_doctor": "one short sentence on when to see a doctor",
 "question": "ONE short follow-up question if key information is missing
     (age, duration, severity), else empty string",
 "speech": "2-3 short sentences summarising the guidance for reading aloud"
}

Rules:
- If the patient has not given enough information, use type "question",
  put one short question in "question" and leave other lists empty.
- Check for emergency warning signs first.
- Suggest over-the-counter medicines or non-drug care only. NEVER suggest
  antibiotics or prescription medicines.
- NEVER write doses, frequencies or treatment durations. The app adds
  "as per label / pharmacist" itself.
- Do not assume a medicine is safe because no allergies were reported.
  Respect the allergies, current medicines and conditions provided.
- For children, never apply adult guidance; say a doctor/pharmacist must
  choose the medicine.
- Keep every field brief. Be fast and concise.
- Write all text values in the requested language.
"""


# --------------------------------------------------
# EMERGENCY WARNING-SIGN SCREENING (simple keyword screen)
# --------------------------------------------------

EMERGENCY_GROUPS = [
    (["can't breathe", "cannot breathe", "cannot breath",
      "difficulty breathing", "severe shortness of breath",
      "blue lips", "gasping for air", "सांस नहीं", "साँस नहीं"],
     "Possible severe breathing emergency"),
    (["chest pain", "chest pressure", "crushing chest",
      "chest tightness with sweating", "सीने में दर्द"],
     "Possible serious chest emergency"),
    (["face drooping", "sudden weakness on one side",
      "sudden trouble speaking", "sudden loss of vision"],
     "Possible stroke warning signs"),
    (["unconscious", "not waking up", "seizure", "vomiting blood",
      "heavy bleeding", "बेहोश"],
     "Possible medical emergency"),
    (["swollen tongue", "throat closing", "anaphylaxis"],
     "Possible severe allergic reaction"),
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


def emergency_check(message):
    text = message.lower()
    for phrases, category in EMERGENCY_GROUPS:
        if any(phrase in text for phrase in phrases):
            return category
    return None


# --------------------------------------------------
# LOCAL FALLBACK KNOWLEDGE BASE (used without API key / on failure)
# --------------------------------------------------

FALLBACK_DB = {
    "fever": {
        "title": "Fever (possible viral infection)",
        "care": ["Rest", "Drink fluids regularly", "Monitor temperature"],
        "meds": [("Paracetamol (OTC fever reducer)", "Lowers fever, eases aches",
                  "Check label; avoid if liver problems or allergy.")],
        "tests": ["CBC"],
        "red_flags": ["Confusion or stiff neck", "Difficulty breathing",
                      "Seizure"],
        "see": "See a doctor if fever lasts over 3 days; babies under "
               "3 months need urgent care.",
        "keywords": ["fever", "temperature", "febrile", "बुखार"],
    },
    "headache": {
        "title": "Headache (tension / migraine possible)",
        "care": ["Rest in a quiet room", "Drink water", "Check sleep and meals"],
        "meds": [("Paracetamol (OTC pain reliever)", "Eases mild headache",
                  "Ask a pharmacist if on other medicines.")],
        "tests": [],
        "red_flags": ["Sudden severe headache", "Weakness or confusion",
                      "Headache after head injury"],
        "see": "See a doctor if headaches are frequent or worsening.",
        "keywords": ["headache", "head pain", "migraine", "सिरदर्द"],
    },
    "cold": {
        "title": "Common cold (possible)",
        "care": ["Rest", "Warm fluids", "Steam inhalation with care"],
        "meds": [("Saline nasal spray/drops", "Relieves blocked nose",
                  "Avoid duplicate ingredients in combination products.")],
        "tests": [],
        "red_flags": ["Breathing difficulty", "Blue lips", "Chest pain"],
        "see": "See a doctor if symptoms last over 7-10 days.",
        "keywords": ["cold", "runny nose", "blocked nose", "sneezing", "जुकाम"],
    },
    "cough": {
        "title": "Cough (irritation / infection possible)",
        "care": ["Warm fluids", "Avoid smoke and dust",
                 "Honey if older than 1 year"],
        "meds": [("Throat lozenges / honey-based syrup", "Soothes cough",
                  "Check age limits on the label.")],
        "tests": [],
        "red_flags": ["Coughing blood", "Breathing difficulty", "Chest pain"],
        "see": "See a doctor if cough lasts over 2 weeks.",
        "keywords": ["cough", "coughing", "खांसी"],
    },
    "sore throat": {
        "title": "Sore throat (possible viral)",
        "care": ["Warm fluids", "Warm salt-water gargle", "Rest your voice"],
        "meds": [("Throat lozenges", "Temporary throat relief",
                  "Follow age limits on the label.")],
        "tests": [],
        "red_flags": ["Cannot swallow saliva", "Breathing difficulty",
                      "Rapid neck swelling"],
        "see": "See a doctor if pain lasts over 3-5 days.",
        "keywords": ["sore throat", "throat pain", "throat irritation", "गले में दर्द"],
    },
    "stomach": {
        "title": "Stomach discomfort (indigestion possible)",
        "care": ["Small sips of fluids", "Light food", "Note pain location"],
        "meds": [("None advised without a clear cause", "Avoid self-treating",
                  "Ask a pharmacist before any antacid or painkiller.")],
        "tests": ["CBC", "Stool test if persistent"],
        "red_flags": ["Severe or worsening pain", "Blood in vomit or stool",
                      "Fainting"],
        "see": "See a doctor if pain is severe or lasts over 2 days.",
        "keywords": ["stomach pain", "stomach ache", "abdominal pain",
                     "indigestion", "stomach discomfort", "पेट दर्द"],
    },
    "diarrhea": {
        "title": "Diarrhea (possible gastroenteritis)",
        "care": ["Drink fluids often", "Eat light food", "Wash hands well"],
        "meds": [("ORS (oral rehydration solution)", "Replaces lost fluids",
                  "Prepare exactly as per packet.")],
        "tests": ["Stool test if persistent"],
        "red_flags": ["Blood in stool", "Very little urine", "Fainting"],
        "see": "See a doctor if it lasts over 2 days or with fever.",
        "keywords": ["diarrhea", "diarrhoea", "loose motions", "दस्त"],
    },
    "vomiting": {
        "title": "Vomiting / nausea (possible stomach infection)",
        "care": ["Frequent small sips of fluids", "Light food when tolerated"],
        "meds": [("ORS (oral rehydration solution)", "Prevents dehydration",
                  "Take small sips; follow packet instructions.")],
        "tests": [],
        "red_flags": ["Blood in vomit", "Severe abdominal pain", "Confusion"],
        "see": "See a doctor if you cannot keep fluids down.",
        "keywords": ["vomit", "vomiting", "nausea", "throwing up", "उल्टी"],
    },
    "rash": {
        "title": "Skin rash / itching (allergy or irritation possible)",
        "care": ["Avoid suspected irritants", "Cool compress", "Do not scratch"],
        "meds": [("Pharmacist-advised anti-itch product", "Eases itching",
                  "Cause must be assessed first.")],
        "tests": [],
        "red_flags": ["Breathing trouble", "Tongue or throat swelling",
                      "Rash spreading fast with fever"],
        "see": "See a doctor if the rash persists over 3 days.",
        "keywords": ["rash", "itchy skin", "itching", "hives", "खुजली"],
    },
    "allergy": {
        "title": "Possible allergy",
        "care": ["Move away from the trigger", "Monitor symptoms"],
        "meds": [("Antihistamine (pharmacist-advised)", "Eases mild allergy",
                  "May cause drowsiness; age limits apply.")],
        "tests": [],
        "red_flags": ["Tongue or throat swelling", "Breathing difficulty",
                      "Collapse"],
        "see": "See a doctor if allergies keep recurring.",
        "keywords": ["allergy", "allergic"],
    },
    "back pain": {
        "title": "Back pain (muscle strain possible)",
        "care": ["Gentle movement", "Avoid long bed rest",
                 "Warm or cold pack with a cloth"],
        "meds": [("Pharmacist-advised pain reliever", "Eases muscle pain",
                  "Unsuitable with kidney or stomach problems.")],
        "tests": [],
        "red_flags": ["Loss of bladder/bowel control", "Groin numbness",
                      "Progressive leg weakness"],
        "see": "See a doctor if pain lasts over 1 week.",
        "keywords": ["back pain", "backache", "lower back pain", "कमर दर्द"],
    },
    "constipation": {
        "title": "Constipation",
        "care": ["Drink fluids", "Add fibre gradually", "Stay active"],
        "meds": [("Fibre supplement (pharmacist-advised)", "Softens stool",
                  "Follow the product label.")],
        "tests": [],
        "red_flags": ["Severe abdominal pain", "Vomiting",
                      "Cannot pass stool or gas"],
        "see": "See a doctor if it lasts over 1 week.",
        "keywords": ["constipation", "hard stool", "कब्ज"],
    },
}


def fallback_reply(user_text):
    text = user_text.lower()
    entries = sorted(
        FALLBACK_DB.values(),
        key=lambda item: max(map(len, item["keywords"])),
        reverse=True,
    )
    for entry in entries:
        if any(k in text for k in entry["keywords"]):
            return {
                "type": "advice",
                "diagnosis": entry["title"],
                "advice": entry["care"],
                "medicines": [
                    {"name": n, "purpose": p, "note": note}
                    for n, p, note in entry["meds"]
                ],
                "tests": entry["tests"],
                "red_flags": entry["red_flags"],
                "see_doctor": entry["see"],
                "question": "",
                "speech": (
                    f"Possible cause: {entry['title']}. "
                    f"{entry['care'][0]}. {entry['see']}"
                ),
            }

    q = ("Please describe your main symptom, when it started and how "
         "severe it is.")
    return {"type": "question", "question": q, "speech": q,
            "diagnosis": "", "advice": [], "medicines": [], "tests": [],
            "red_flags": [], "see_doctor": ""}


# --------------------------------------------------
# OPENROUTER REQUEST (short prompt + token cap = faster answers)
# --------------------------------------------------

def parse_json_reply(raw):
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def history_text(item):
    """Compact text version of a stored message for LLM context."""
    if item.get("rx"):
        rx = item["rx"]
        return (f"{rx.get('diagnosis', '')} "
                f"{rx.get('question', '')}").strip() or item["content"]
    return item["content"]


def ask_openrouter(user_text, patient_context, conversation):
    clean_key = str(api_key).strip().strip('"').strip("'")
    if not clean_key:
        return None

    messages = [{
        "role": "system",
        "content": SYSTEM_PROMPT + f"\nLanguage: {language}",
    }]

    # Only the last few turns keeps responses fast.
    for item in conversation[-4:]:
        if item["role"] in ("user", "assistant"):
            messages.append({"role": item["role"],
                             "content": history_text(item)})

    messages.append({
        "role": "user",
        "content": (f"Patient context:\n{patient_context}\n\n"
                    f"Latest patient message:\n{user_text}"),
    })

    payload = json.dumps({
        "model": "openrouter/free",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,
    }).encode("utf-8")

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
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
        choices = result.get("choices", [])
        if not choices:
            return None
        answer = choices[0].get("message", {}).get("content", "")
        return parse_json_reply(answer)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            ValueError, KeyError, TypeError, OSError):
        return None


# --------------------------------------------------
# PRESCRIPTION-STYLE RENDERING
# Doses/frequency/duration are NEVER generated by the AI. The app fills
# them with safe, fixed text so the bot cannot invent a dose.
# --------------------------------------------------

def clean_list(value, limit=4):
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def normalise(data):
    """Make sure every field exists and has the right type."""
    meds = []
    for m in (data.get("medicines") or [])[:3]:
        if isinstance(m, dict) and str(m.get("name", "")).strip():
            meds.append({
                "name": str(m.get("name", "")).strip(),
                "purpose": str(m.get("purpose", "")).strip(),
                "note": str(m.get("note", "")).strip(),
            })
    return {
        "type": data.get("type", "advice"),
        "diagnosis": str(data.get("diagnosis", "")).strip(),
        "advice": clean_list(data.get("advice"), 3),
        "medicines": meds,
        "tests": clean_list(data.get("tests"), 3),
        "red_flags": clean_list(data.get("red_flags"), 3),
        "see_doctor": str(data.get("see_doctor", "")).strip(),
        "question": str(data.get("question", "")).strip(),
        "speech": str(data.get("speech", "")).strip(),
    }


def dose_text(age):
    if age < 12:
        return "Doctor / pharmacist to decide (child)"
    return "As per product label / pharmacist"


def build_rx_html(rx, patient):
    e = html.escape
    hindi = patient["language"] == "हिन्दी"
    L = {
        "diag": "निदान (संभावित)" if hindi else "Diagnosis (possible)",
        "med": "दवा" if hindi else "Medicine",
        "dose": "मात्रा" if hindi else "Dosage",
        "timing": "समय - अवधि" if hindi else "Timing - Freq. - Duration",
        "tests": "सुझाई गई जांच" if hindi else "Tests advised",
        "care": "देखभाल" if hindi else "Supportive care",
        "doc": "डॉक्टर को कब दिखाएं" if hindi else "See a doctor",
        "warn": "आपातकालीन संकेत" if hindi else "Emergency warning signs",
        "label": "लेबल के अनुसार" if hindi else "As per label",
        "foot": ("शैक्षिक डेमो। निदान या नुस्खा नहीं। दवा लेने से पहले "
                 "डॉक्टर/फार्मासिस्ट से पूछें।") if hindi else
                ("Educational demo. Not a diagnosis or prescription. "
                 "Confirm any medicine with a doctor/pharmacist."),
    }
 
    name = e(patient["name"] or "—")
    info = f"{name} | Age: {patient['age']}"
    if patient["weight"] > 0:
        info += f" | {patient['weight']:g} kg"
    if patient["allergies"]:
        info += f" | Allergies: {e(patient['allergies'])}"
 
    rows = ""
    for i, m in enumerate(rx["medicines"], 1):
        rows += (
            f"<tr><td>{i}) <b>{e(m['name'])}</b>"
            f"<br><span class='rx-sub'>{e(m['purpose'])}</span></td>"
            f"<td>{e(dose_text(patient['age']))}</td>"
            f"<td>{L['label']}</td></tr>"
        )
        if m["note"]:
            rows += (f"<tr><td colspan='3' class='rx-note'>"
                     f"Notes: {e(m['note'])}</td></tr>")
 
    table = ""
    if rows:
        table = (
            "<div class='rx-symbol'>℞</div>"
            "<table class='rx-table'><tr>"
            f"<th>{L['med']}</th><th>{L['dose']}</th>"
            f"<th>{L['timing']}</th></tr>{rows}</table>"
        )
 
    care = ""
    if rx["advice"]:
        items = "".join(f"<li>{e(a)}</li>" for a in rx["advice"])
        care = (f"<div class='rx-section'><b>{L['care']}:</b>"
                f"<ul style='margin:2px 0'>{items}</ul></div>")
 
    tests = ""
    if rx["tests"]:
        tests = (f"<div class='rx-section'><b>{L['tests']}:</b> "
                 f"{e(', '.join(rx['tests']))}</div>")
 
    doc = ""
    if rx["see_doctor"]:
        doc = (f"<div class='rx-section'><b>{L['doc']}:</b> "
               f"{e(rx['see_doctor'])}</div>")
 
    warn = ""
    if rx["red_flags"]:
        warn = (f"<div class='rx-warn'>🚨 <b>{L['warn']}:</b> "
                f"{e('; '.join(rx['red_flags']))}</div>")
 
    return (
        "<div class='rx-card'>"
        "<div class='rx-head'><span class='rx-clinic'>🩺 MedAssist AI</span>"
        f"<span class='rx-date'>{date.today().strftime('%d %b %Y')}</span></div>"
        f"<div class='rx-patient'>{info}</div>"
        f"<div class='rx-diag'><b>{L['diag']}:</b> {e(rx['diagnosis'])}</div>"
        f"{table}{care}{tests}{doc}{warn}"
        f"<div class='rx-foot'>{L['foot']}</div></div>"
    )
 
 
def emergency_rx(category):
    msg = EMERGENCY_REPLY_HI if language == "हिन्दी" else EMERGENCY_REPLY_EN
    return {
        "type": "emergency",
        "diagnosis": category,
        "advice": [], "medicines": [], "tests": [],
        "red_flags": [], "see_doctor": "", "question": "",
        "speech": msg,
        "emergency_text": msg,
    }
 
 
def render_reply(rx, patient, key):
    """Show one assistant reply (card, question or emergency)."""
    if rx["type"] == "emergency":
        st.error("🚨 " + rx["emergency_text"])
        return
 
    if rx["type"] == "question" or not (rx["diagnosis"] or rx["medicines"]):
        st.markdown(rx["question"] or rx["speech"])
        return
 
    card = build_rx_html(rx, patient)
    st.markdown(card, unsafe_allow_html=True)
 
    page = ("<html><head><meta charset='utf-8'><style>body{font-family:"
            "Arial;max-width:700px;margin:20px auto}"
            ".rx-card{border:1px solid #999;padding:16px}"
            ".rx-table{width:100%;border-collapse:collapse}"
            ".rx-table td,.rx-table th{text-align:left;padding:6px;"
            "border-bottom:1px solid #ddd}.rx-sub,.rx-foot{color:#777;"
            "font-size:12px}</style></head><body>"
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
 
def play_audio(script_text, lang_code):
    if not script_text:
        return
 
    safe_text = json.dumps(script_text).replace("</", "<\\/")
    safe_lang = json.dumps(lang_code)
 
    page = f"""
    <div style="font-family:Arial">
      <button id="speak-button" style="background:#0E76A8;color:white;
        border:0;padding:8px 14px;border-radius:7px;cursor:pointer;
        font-size:14px;">🔊 Listen again</button>
      <button id="stop-button" style="background:#555;color:white;border:0;
        padding:8px 14px;border-radius:7px;cursor:pointer;font-size:14px;
        margin-left:6px;">⏹ Stop</button>
    </div>
    <script>
      const speechText = {safe_text};
      const speechLang = {safe_lang};
 
      function speak() {{
        if (!("speechSynthesis" in window)) return;
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(speechText);
        u.lang = speechLang;
        u.rate = 1.0;
        window.speechSynthesis.speak(u);
      }}
 
      document.getElementById("speak-button").onclick = speak;
      document.getElementById("stop-button").onclick = () => {{
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      }};
 
      // Try to speak automatically (some browsers need a click first).
      setTimeout(speak, 300);
    </script>
    """
    components.html(page, height=55)
 
 
# --------------------------------------------------
# SESSION STATE AND INITIAL GREETING
# --------------------------------------------------
 
GREETING_EN = (
    "Hello! 👋 I'm **MedAssist AI**.\n\n"
    "Tell me your symptoms and I'll give a short prescription-style "
    "guidance sheet: possible cause, supportive care, medicine safety "
    "information and tests a doctor may advise.\n\n"
    "What symptoms are you experiencing?"
)
 
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": GREETING_EN, "rx": None}
    ]
 
patient = {
    "name": patient_name.strip(),
    "age": int(patient_age),
    "weight": float(patient_weight),
    "allergies": allergies.strip(),
    "language": language,
}
 
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message.get("rx"):
            render_reply(message["rx"], message.get("patient", patient), idx)
        else:
            st.markdown(message["content"])
 
 
# --------------------------------------------------
# CHAT INPUT AND RESPONSE
# --------------------------------------------------
 
user_input = st.chat_input("Describe your symptoms...")
 
if user_input and user_input.strip():
    user_input = user_input.strip()
 
    st.session_state.messages.append(
        {"role": "user", "content": user_input, "rx": None}
    )
 
    with st.chat_message("user"):
        st.markdown(user_input)
 
    with st.chat_message("assistant"):
        with st.spinner("Preparing your guidance sheet..."):
            emergency = emergency_check(user_input)
 
            if emergency:
                reply = emergency_rx(emergency)
            else:
                patient_context = (
                    f"Age: {patient_age}\n"
                    f"Weight in kg: "
                    f"{patient_weight if patient_weight > 0 else 'Unknown'}\n"
                    f"Medicine allergies: {allergies or 'Unknown'}\n"
                    f"Current medicines: {current_medicines or 'Unknown'}\n"
                    f"Relevant medical history: {medical_history or 'Unknown'}"
                )
                previous = st.session_state.messages[:-1]
                data = ask_openrouter(user_input, patient_context, previous)
 
                if data:
                    reply = normalise(data)
                else:
                    reply = fallback_reply(user_input)
                    reply["lang"] = "en-IN"  # local fallback is English
 
                if not reply["speech"]:
                    reply["speech"] = (reply["question"] or reply["diagnosis"])
 
        key = len(st.session_state.messages)
        render_reply(reply, patient, key)
 
        if voice_on:
            play_audio(reply["speech"], reply.get("lang", SPEECH_LANG))
 
    st.session_state.messages.append({
        "role": "assistant",
        "content": reply["speech"] or reply["diagnosis"],
        "rx": reply,
        "patient": patient,
    })
 
