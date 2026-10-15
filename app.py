import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.request
import re

st.set_page_config(page_title="MedAssist AI - Clinical Assistant", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI - Clinical Assistant")
st.caption("⚠️ **Educational Demonstration Only.** This assistant provides clinical triage guidance and supportive general information. It does not provide medical diagnoses or drug prescriptions. Always consult a certified healthcare professional.")

api_key = st.secrets.get("OPENROUTER_API_KEY", None)
if not api_key:
    with st.sidebar:
        st.subheader("⚙️ Cloud Model Setup")
        api_key = st.text_input("OpenRouter API Key (Optional)", type="password", help="Paste your API key or leave blank to use the internal clinical engine.")
        if st.button("Reset Session"):
            st.session_state.messages = []
            st.session_state.turns = 0
            st.rerun()

SYSTEM_PROMPT = """
You are MedAssist AI, an educational clinical triage assistant.
Workflow:
- Turn 1: Empathetically acknowledge user symptoms. Ask 2 clinical follow-up questions (onset, severity, or triggers).
- Turn 2+: Provide structured synthesis:
  1. Clinical Impression & Physiological Correlation.
  2. Evidence-Based Supportive Care (non-pharmacological home measures).
  3. General Over-the-Counter (OTC) Categories: Mention common standard OTC classes for temporary symptom relief (e.g., antipyretics for fever, topical antifungals, antihistamines). Explicitly state that dosage instructions depend on age/weight and must be confirmed via product packaging labels or by consulting a pharmacist/physician.
  4. Critical Emergency Red-Flag Warning Signs requiring urgent hospital care.
Safety: Do NOT calculate or prescribe specific milligram dosages, frequencies, or prescription medications.
"""

FALLBACK_DB = {
    "fever": (
        "Systemic Febrile Syndrome",
        "What is your highest measured temperature, and how many days has it been present?",
        "Maintain oral hydration with electrolyte fluids, rest in a cool ventilated room, and wear lightweight clothing.",
        "Over-the-counter fever relievers/pain relievers (such as paracetamol or ibuprofen) are commonly used for temporary fever reduction. Exact dosage varies by age and weight—always follow package directions or consult a pharmacist.",
        "Temperature exceeding 103°F (39.4°C), stiff neck, confusion, or difficulty breathing."
    ),
    "fungus": (
        "Superficial Fungal / Dermatophyte Irritation",
        "Where is the affected area located, and is there severe redness, cracking, or burning?",
        "Keep the skin clean and completely dry, wear loose breathable fabrics, and avoid sharing towels or personal items.",
        "Common over-the-counter topical antifungals (such as clotrimazole cream or terbinafine cream) may be applied for superficial skin irritations. Refer to the manufacturer label for proper usage and duration, and visit a doctor if the rash worsens.",
        "Spreading cellulitis (rapid heat, severe swelling), open oozing sores, or involvement near the eyes."
    ),
    "allergy": (
        "Allergic Rhinitis / Histaminic Response",
        "Are your symptoms triggered by pollen, dust, or certain foods, and do you experience eye itching or sneezing?",
        "Avoid known allergen triggers, use cool compresses over irritated areas, and rinse nasal passages with isotonic saline.",
        "Over-the-counter oral antihistamines (such as cetirizine or loratadine) are frequently used to manage sneezing, itching, and hives. Follow product packaging for age-specific guidelines or consult a healthcare provider.",
        "ANAPHYLAXIS: Swelling of lips, tongue, or throat, tightness in chest, wheezing, or difficulty swallowing."
    ),
    "throat": (
        "Acute Pharyngitis & Throat Irritation",
        "Are you experiencing painful swallowing, and have you noticed white spots on your tonsils?",
        "Gargle with warm saline solution (1/2 tsp salt in warm water) several times daily and drink warm soothing liquids.",
        "Over-the-counter anesthetic throat lozenges or mild pain relievers may provide temporary soothing. If throat pain lasts longer than 3–4 days or worsens, consult a doctor to evaluate for bacterial infection.",
        "Inability to swallow fluids, difficulty opening your mouth, stridor, or shortness of breath."
    ),
    "cough": (
        "Acute Bronchial / Respiratory Irritation",
        "Is the cough dry and tickling or producing colored mucus?",
        "Use warm steam inhalation for 10–15 minutes, stay well hydrated, and use a cool mist humidifier.",
        "Over-the-counter demulcent syrups or guaifenesin expectorants may help manage cough discomfort. Always review package labels for age appropriateness and speak with a pharmacist.",
        "Coughing up blood, sharp chest pain upon inhalation, or persistent shortness of breath."
    ),
    "headache": (
        "Cephalalgia / Tension Headache",
        "Is the pain a dull band around the head or localized throbbing on one side?",
        "Rest in a quiet, dark environment, drink 500 mL of water, and apply a cool cloth to the forehead.",
        "Over-the-counter analgesics (such as paracetamol or ibuprofen) are commonly used for temporary relief. Check package instructions and avoid medication overuse.",
        "Sudden severe 'thunderclap' onset, neurological deficits, fever with stiff neck, or post-head trauma."
    )
}

def fallback_reply(user_text, turn_count):
    text_lower = user_text.lower()
    matched = None
    for key, data in FALLBACK_DB.items():
        if key in text_lower or (key == "fungus" and any(w in text_lower for w in ["fungal", "ringworm", "itch"])):
            matched = data
            break
    if not matched:
        matched = (
            "General Health Discomfort",
            "When did this discomfort start, and does it improve or worsen with rest?",
            "Rest comfortably, maintain good hydration, and monitor your symptoms closely.",
            "Discuss suitable non-prescription options with a certified pharmacist or medical professional based on your specific age and symptoms.",
            "Sudden severe pain, shortness of breath, high continuous fever, or loss of consciousness."
        )
    
    if turn_count <= 1:
        return (
            f"### Clinical Assessment Registered: {matched[0]}\n\n"
            f"• **Initial Observation:** Recorded presentation for **{matched[0]}**.\n\n"
            f"👉 **Focused Clinical Inquiry:** {matched[1]}\n\n"
            f"*Please reply with your details to assess supportive care options and emergency screening thresholds.*"
        )
    else:
        return (
            f"### Clinical Triage Synthesis: {matched[0]}\n\n"
            f"• **Physiological Correlation:** Presentation is consistent with localized irritation, inflammation, or immune activation.\n\n"
            f"• **Evidence-Based Supportive Care:**\n  - {matched[2]}\n\n"
            f"• **General OTC Considerations:**\n  - {matched[3]}\n\n"
            f"• ⚠️ **Critical Red-Flag Escalation Thresholds:**\n  - {matched[4]}\n\n"
            f"*Note: For demonstration and educational purposes only. If symptoms persist or worsen, visit a certified doctor immediately.*"
        )

def play_audio(script_text):
    clean = re.sub(r'[*_#`⚠️👉🔊•\-]', '', script_text)
    clean = " ".join(clean.replace('"', '').replace("'", "").replace('\n', ' ').split())
    html = f"""
    <script>
    function speakText() {{
        window.speechSynthesis.cancel();
        const msg = new SpeechSynthesisUtterance("{clean}");
        msg.rate = 0.95;
        msg.pitch = 1.0;
        window.speechSynthesis.speak(msg);
    }}
    </script>
    <button onclick="speakText()" style="
        background-color: #0E76A8;
        color: white;
        border: none;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        font-size: 13px;
        margin-top: 6px;
    ">🔊 Listen to Clinical Guidance</button>
    """
    components.html(html, height=45)

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "### 🩺 MedAssist AI - Clinical Assistant\n"
            "Hello! I am your clinical triage assistant. I evaluate symptoms, "
            "provide evidence-based supportive care protocols, discuss general OTC considerations, and screen for emergency red flags.\n\n"
            "👉 **How can I assist you today?** Describe any health symptoms or bodily discomfort you are experiencing."
        ),
        "audio": True
    }]
if "turns" not in st.session_state:
    st.session_state.turns = 0

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("audio"):
            play_audio(msg["content"])

user_input = st.chat_input("State your health symptoms or answer clinical inquiries...")

if user_input:
    st.session_state.turns += 1
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input, "audio": False})

    with st.chat_message("assistant"):
        bot_reply = ""
        used_cloud = False

        if api_key and str(api_key).strip():
            clean_key = str(api_key).strip().strip('"').strip("'")
            headers = {
                "Authorization": f"Bearer {clean_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://streamlit.io",
                "X-Title": "MedAssist AI"
            }
            openrouter_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for m in st.session_state.messages:
                openrouter_messages.append({
                    "role": "user" if m["role"] == "user" else "assistant",
                    "content": m["content"]
                })
            
            payload = json.dumps({
                "model": "openrouter/free",
                "messages": openrouter_messages,
                "temperature": 0.3
            }).encode("utf-8")
            
            try:
                req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=payload, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    bot_reply = result["choices"][0]["message"]["content"]
                    used_cloud = True
            except Exception:
                used_cloud = False

        if not used_cloud:
            bot_reply = fallback_reply(user_input, st.session_state.turns)

        st.markdown(bot_reply)
        play_audio(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply, "audio": True})
        
