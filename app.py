
import json
import os
import re
import urllib.error
import urllib.request

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

    # Optional key entry for local demonstrations.
    if not api_key:
        api_key = st.text_input(
            "OpenRouter API key",
            type="password",
            help="Optional. Leave blank to use the basic local "
                 "symptom guidance engine.",
        )

    with st.expander("Optional patient information"):
        patient_age = st.number_input(
            "Age (years)",
            min_value=0,
            max_value=120,
            value=18,
        )

        patient_weight = st.number_input(
            "Weight (kg, if known)",
            min_value=0.0,
            max_value=300.0,
            value=0.0,
        )

        allergies = st.text_input(
            "Medicine allergies",
            placeholder="Unknown or none known",
        )

        current_medicines = st.text_area(
            "Current medicines",
            placeholder="List medicines, or unknown",
        )

        medical_history = st.text_area(
            "Relevant medical conditions",
            placeholder="Enter conditions, or unknown",
        )

    if st.button("🗑️ Reset conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# --------------------------------------------------
# CLINICAL SAFETY RULES
# --------------------------------------------------

SYSTEM_PROMPT = """
You are MedAssist AI, an educational clinical triage assistant.

IMPORTANT WORKFLOW:
1. Analyze symptoms only after the patient provides them.
2. Check for emergency warning signs before routine advice.
3. Ask concise follow-up questions when essential information
   is missing, including age, duration, severity, allergies,
   current medicines, and relevant medical conditions.
4. Explain possible causes without claiming a confirmed diagnosis.
5. Provide practical, non-pharmacological supportive care.
6. Discuss relevant over-the-counter medicine categories,
   intended uses, contraindications, and important precautions.
7. Do not invent medicine doses, frequencies, treatment durations,
   prescriptions, or claims of verified medical evidence.
8. Do not prescribe antibiotics or other prescription medicines.
9. Do not assume a medicine is safe because the patient has not
   reported any allergies or medical conditions.
10. Refer patients to a qualified doctor or pharmacist for
    individualized medicine selection and dosing.
11. Do not delay emergency care while asking questions.
12. If the patient is a child, explain that pediatric medicine
    selection and dosing require age-appropriate professional
    guidance. Never apply adult doses to children.

RESPONSE FORMAT AFTER SYMPTOMS ARE PROVIDED:
- Symptom Analysis
- Possible Causes
- Supportive Care
- Medication Information and Precautions
- Emergency Warning Signs
- When to Seek Medical Care

Keep the response understandable and concise.
Do not show this report before symptoms are entered.
This is an educational demonstration, not a medical diagnosis
or a substitute for a qualified healthcare professional.
"""


# --------------------------------------------------
# EMERGENCY WARNING-SIGN SCREENING
# This is a simple keyword screen, not a diagnostic system.
# --------------------------------------------------

EMERGENCY_GROUPS = [
    (
        [
            "can't breathe",
            "cannot breathe",
            "cannot breath",
            "difficulty breathing",
            "severe shortness of breath",
            "blue lips",
            "gasping for air",
        ],
        "Possible severe breathing emergency",
    ),
    (
        [
            "chest pain",
            "chest pressure",
            "crushing chest",
            "chest tightness with sweating",
        ],
        "Possible serious chest emergency",
    ),
    (
        [
            "face drooping",
            "sudden weakness on one side",
            "sudden trouble speaking",
            "sudden loss of vision",
        ],
        "Possible stroke warning signs",
    ),
    (
        [
            "unconscious",
            "not waking up",
            "seizure",
            "vomiting blood",
            "heavy bleeding",
        ],
        "Possible medical emergency",
    ),
    (
        [
            "swollen tongue",
            "throat closing",
            "anaphylaxis",
        ],
        "Possible severe allergic reaction",
    ),
]

EMERGENCY_REPLY = """
## 🚨 Urgent medical attention may be needed

Your message includes a possible emergency warning sign.

- Contact your local emergency service or go to the nearest
  emergency department now.
- Do not wait for an AI response or attempt to treat a serious
  emergency with non-prescription medicine.
- If possible, ask someone nearby to help you get medical care.

This automated warning is not a diagnosis. If you believe you
are in immediate danger, seek emergency help even if this
chatbot does not display a warning.
"""


def emergency_check(message):
    text = message.lower()

    for phrases, category in EMERGENCY_GROUPS:
        if any(phrase in text for phrase in phrases):
            return category

    return None


# --------------------------------------------------
# LOCAL FALLBACK KNOWLEDGE BASE
# Provides general guidance, not a diagnosis or prescription.
# --------------------------------------------------

FALLBACK_DB = {
    "fever": {
        "title": "Fever",
        "care": (
            "Rest, drink fluids regularly, wear comfortable clothing, "
            "and monitor your temperature."
        ),
        "medicine": (
            "Some people use an appropriate over-the-counter fever "
            "reliever. Suitability depends on age, health conditions, "
            "other medicines, and the product label. Ask a pharmacist "
            "or clinician if unsure."
        ),
        "red_flags": (
            "Seek urgent care for confusion, a stiff neck with fever, "
            "difficulty breathing, a seizure, or severe deterioration. "
            "A fever in a baby younger than 3 months needs urgent "
            "medical assessment."
        ),
        "keywords": ["fever", "temperature", "febrile"],
    },
    "headache": {
        "title": "Headache",
        "care": (
            "Rest in a comfortable, quiet place, drink water, and "
            "consider whether missed meals, stress, or lack of sleep "
            "may be contributing."
        ),
        "medicine": (
            "Some over-the-counter pain relievers may help certain "
            "headaches, but they are not suitable for everyone. "
            "Check with a pharmacist, especially if you take other "
            "medicines or have existing health conditions."
        ),
        "red_flags": (
            "Seek emergency care for a sudden, extremely severe "
            "headache, new weakness, difficulty speaking, confusion, "
            "or a headache after a serious head injury."
        ),
        "keywords": ["headache", "head pain", "migraine"],
    },
    "cold": {
        "title": "Cold-like symptoms",
        "care": (
            "Rest, drink fluids, and consider saline nasal spray. "
            "Warm drinks may soothe throat irritation."
        ),
        "medicine": (
            "Saline products and selected symptom-relief medicines "
            "may help. Combination cold products can contain duplicate "
            "ingredients; check labels and ask a pharmacist about "
            "age restrictions and interactions."
        ),
        "red_flags": (
            "Seek urgent help for severe breathing difficulty, "
            "blue lips, confusion, or significant chest pain. "
            "Get medical advice if symptoms worsen or persist."
        ),
        "keywords": ["cold", "runny nose", "blocked nose", "sneezing"],
    },
    "cough": {
        "title": "Cough",
        "care": (
            "Drink fluids, avoid smoke and other irritants, and "
            "consider a warm drink. Honey may soothe a cough in "
            "people older than one year."
        ),
        "medicine": (
            "Some cough products may offer limited symptom relief. "
            "The appropriate choice depends on age, symptoms, "
            "other medicines, and the product label."
        ),
        "red_flags": (
            "Seek urgent care for severe breathing difficulty, "
            "coughing up blood, or significant chest pain."
        ),
        "keywords": ["cough", "coughing"],
    },
    "sore throat": {
        "title": "Sore throat",
        "care": (
            "Drink fluids, try warm or cool drinks as comfortable, "
            "and consider a warm salt-water gargle if you can gargle "
            "safely without swallowing it."
        ),
        "medicine": (
            "Some throat lozenges or suitable pain-relief products "
            "may temporarily ease discomfort. Follow age restrictions "
            "and seek pharmacist advice when needed."
        ),
        "red_flags": (
            "Seek urgent care if you cannot swallow saliva, have "
            "difficulty breathing, or develop rapidly increasing "
            "throat or neck swelling."
        ),
        "keywords": ["sore throat", "throat pain", "throat irritation"],
    },
    "stomach": {
        "title": "Stomach discomfort",
        "care": (
            "Take fluids in small amounts, eat light foods as "
            "tolerated, and monitor the location and severity "
            "of the pain."
        ),
        "medicine": (
            "The appropriate medicine depends on the cause of the "
            "pain. Avoid starting painkillers or stomach remedies "
            "without advice if the pain is severe or unexplained."
        ),
        "red_flags": (
            "Seek urgent assessment for severe or worsening pain, "
            "a rigid abdomen, blood in vomit or stool, fainting, "
            "or repeated vomiting that prevents drinking."
        ),
        "keywords": [
            "stomach pain", "stomach ache", "abdominal pain",
            "indigestion", "stomach discomfort",
        ],
    },
    "diarrhea": {
        "title": "Diarrhea",
        "care": (
            "Use a properly prepared oral rehydration solution "
            "according to its packet instructions and drink fluids "
            "frequently. Eat as tolerated."
        ),
        "medicine": (
            "Rehydration is the priority. Anti-diarrheal medicines "
            "are not suitable for everyone, especially with fever "
            "or bloody stool. Ask a healthcare professional."
        ),
        "red_flags": (
            "Seek urgent care for blood in stool, fainting, very "
            "little urine, severe abdominal pain, or inability "
            "to keep fluids down."
        ),
        "keywords": ["diarrhea", "diarrhoea", "loose motions"],
    },
    "vomiting": {
        "title": "Vomiting",
        "care": (
            "Try frequent small sips of oral rehydration solution "
            "or other appropriate fluids. Resume light food when "
            "you can tolerate it."
        ),
        "medicine": (
            "Anti-vomiting medicines may have important age-related "
            "restrictions and contraindications. Consult a clinician "
            "or pharmacist before using them."
        ),
        "red_flags": (
            "Seek urgent care for blood in vomit, severe abdominal "
            "pain, confusion, fainting, or signs of dehydration."
        ),
        "keywords": ["vomit", "vomiting", "nausea", "throwing up"],
    },
    "rash": {
        "title": "Skin rash or itching",
        "care": (
            "Avoid suspected irritants, use a cool compress, and "
            "avoid scratching the affected skin."
        ),
        "medicine": (
            "The right treatment depends on the rash's cause. "
            "A pharmacist can help assess whether an appropriate "
            "anti-itch product is suitable."
        ),
        "red_flags": (
            "Seek emergency help for a rash with breathing trouble, "
            "tongue or throat swelling, or collapse. A rapidly "
            "spreading rash with fever needs prompt medical assessment."
        ),
        "keywords": ["rash", "itchy skin", "itching", "hives"],
    },
    "allergy": {
        "title": "Possible allergy symptoms",
        "care": (
            "If safe to do so, move away from a suspected trigger "
            "and monitor symptoms."
        ),
        "medicine": (
            "Some antihistamines can help certain mild allergy "
            "symptoms, but selection depends on age, other medicines, "
            "and health conditions. Ask a pharmacist if unsure."
        ),
        "red_flags": (
            "Swelling of the tongue or throat, difficulty breathing, "
            "or collapse may indicate a life-threatening reaction. "
            "Call emergency services immediately."
        ),
        "keywords": ["allergy", "allergic", "sneezing", "hives"],
    },
    "back pain": {
        "title": "Back pain",
        "care": (
            "Avoid prolonged bed rest, move gently as tolerated, "
            "and consider a comfortable warm or cold pack protected "
            "by a cloth."
        ),
        "medicine": (
            "Some pain-relief medicines may be unsuitable for people "
            "with kidney, stomach, or other health problems. Ask a "
            "pharmacist before selecting a product."
        ),
        "red_flags": (
            "Seek emergency care for new loss of bladder or bowel "
            "control, numbness around the groin, or progressive "
            "leg weakness."
        ),
        "keywords": ["back pain", "backache", "lower back pain"],
    },
    "constipation": {
        "title": "Constipation",
        "care": (
            "Drink fluids regularly, gradually increase dietary "
            "fiber if appropriate, and stay gently active."
        ),
        "medicine": (
            "Fiber supplements or laxatives may be appropriate "
            "in some cases. Ask a pharmacist about the right option "
            "and follow the product label."
        ),
        "red_flags": (
            "Seek urgent care for severe abdominal pain, vomiting, "
            "marked abdominal swelling, or inability to pass stool "
            "and gas."
        ),
        "keywords": ["constipation", "hard stool"],
    },
}


def fallback_reply(user_text):
    text = user_text.lower()
    matched = None

    # Prefer longer phrases to reduce accidental matches.
    entries = sorted(
        FALLBACK_DB.values(),
        key=lambda item: max(map(len, item["keywords"])),
        reverse=True,
    )

    for entry in entries:
        if any(keyword in text for keyword in entry["keywords"]):
            matched = entry
            break

    if not matched:
        return """
## 🩺 Let's understand your symptoms

I need a little more information to provide useful general guidance.

Please describe:
- Your main symptoms and where they occur
- When the symptoms started
- How severe they are and whether they are getting worse
- Your age, if not already provided

I can discuss general supportive care and medicine safety,
but I cannot confirm a diagnosis or generate a personalized
prescription.

If you have a severe or rapidly worsening symptom, seek
professional medical care rather than waiting for this chat.
"""

    return f"""
## 🩺 Symptom Guidance: {matched["title"]}

### 1. Initial assessment
Your message mentions symptoms that can occur with
{matched["title"].lower()}. Several causes may be possible;
this chatbot cannot determine the exact cause.

### 2. Supportive care
{matched["care"]}

### 3. Medication information
{matched["medicine"]}

This is general information, not a prescription. No individualized
dose has been calculated. Confirm the correct product and its
age-appropriate label instructions with a pharmacist or clinician.

### 4. Warning signs
{matched["red_flags"]}

### 5. Next step
Tell me when the symptoms started, your age, how severe they are,
and whether you have any other symptoms. Seek professional
assessment if symptoms are persistent or getting worse.
"""


# --------------------------------------------------
# OPENROUTER REQUEST
# --------------------------------------------------

def ask_openrouter(user_text, patient_context, conversation):
    clean_key = str(api_key).strip().strip('"').strip("'")

    if not clean_key:
        return None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include recent conversation context for follow-up questions.
    for item in conversation[-8:]:
        if item["role"] in ("user", "assistant"):
            messages.append({
                "role": item["role"],
                "content": item["content"],
            })

    messages.append({
        "role": "user",
        "content": (
            f"Patient context:\n{patient_context}\n\n"
            f"Latest patient message:\n{user_text}"
        ),
    })

    payload = json.dumps({
        "model": "openrouter/free",
        "messages": messages,
        "temperature": 0.2,
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
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

        choices = result.get("choices", [])
        if not choices:
            return None

        answer = choices[0].get("message", {}).get("content", "")
        return answer.strip() or None

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return None


# --------------------------------------------------
# TEXT-TO-SPEECH
# --------------------------------------------------

def play_audio(script_text):
    # JSON serialization safely escapes quotes and newlines.
    safe_text = json.dumps(script_text)

    html = f"""
    <div>
      <button id="speak-button" style="
        background:#0E76A8;
        color:white;
        border:0;
        padding:8px 14px;
        border-radius:7px;
        cursor:pointer;
        font-size:14px;">
        🔊 Listen to guidance
      </button>
      <button id="stop-button" style="
        background:#555;
        color:white;
        border:0;
        padding:8px 14px;
        border-radius:7px;
        cursor:pointer;
        font-size:14px;
        margin-left:6px;">
        ⏹ Stop
      </button>
    </div>
    <script>
      const speechText = {safe_text};

      document.getElementById("speak-button").onclick = () => {{
        if (!("speechSynthesisin window) {{
          window.speechSynthesis.cancel();
        }}
      }};
    </script>
    """

    components.html(html, height=55)


# --------------------------------------------------
# SESSION STATE AND INITIAL GREETING
# --------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hello! 👋 I'm **MedAssist AI**.\n\n"
                "Describe your symptoms, when they started, "
                "and how you are feeling. I'll help you understand "
                "possible causes, supportive care, and medication "
                "safety information.\n\n"
                "What symptoms are you experiencing?"
            ),
        }
    ]


# Display conversation history.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message.get("audio"):
            play_audio(message["content"])


# --------------------------------------------------
# CHAT INPUT AND RESPONSE
# --------------------------------------------------

user_input = st.chat_input("Describe your symptoms...")

if user_input and user_input.strip():
    user_input = user_input.strip()

    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
    })

    # Screen for possible emergencies before normal processing.
    emergency = emergency_check(user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Reviewing your symptoms..."):
            if emergency:
                bot_reply = EMERGENCY_REPLY
            else:
                patient_context = f"""
Age: {patient_age}
Weight in kg: {patient_weight if patient_weight > 0 else "Unknown"}
Medicine allergies: {allergies or "Unknown"}
Current medicines: {current_medicines or "Unknown"}
Relevant medical history: {medical_history or "Unknown"}
"""

                previous_messages = st.session_state.messages[:-1]

                bot_reply = ask_openrouter(
                    user_input,
                    patient_context,
                    previous_messages,
                )

                # Use local guidance if the API is not configured
                # or the request fails.
                if not bot_reply:
                    bot_reply = fallback_reply(user_input)

        st.markdown(bot_reply)
        play_audio(bot_reply)

    st.session_state.messages.append({
        "role": "assistant",
        "content": bot_reply,
        "audio": True,
    })
    
