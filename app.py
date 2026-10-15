import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.request
import re

st.set_page_config(page_title="MedAssist AI - Clinical Assistant", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI - Clinical Assistant")
st.caption("⚠️ **Educational Demonstration Only.** This assistant provides clinical triage guidance and supportive general information. It does not provide medical diagnoses, prescriptions, or individualized drug dosages. Always consult a certified healthcare professional.")

api_key = st.secrets.get("OPENROUTER_API_KEY", None)
if not api_key:
    with st.sidebar:
        st.subheader("⚙️ Cloud Model Setup")
        api_key = st.text_input("OpenRouter API Key (Optional)", type="password", help="Paste your API key or leave blank to use the internal clinical engine.")
        if st.button("Reset Session"):
            st.session_state.messages = []
            st.rerun()

SYSTEM_PROMPT = """
You are MedAssist AI, an educational clinical triage assistant.
Workflow:
Provide a complete, structured clinical synthesis in a single response immediately upon the user stating their symptoms:
  1. Clinical Impression & Physiological Correlation.
  2. Evidence-Based Supportive Care (non-pharmacological home measures).
  3. General Over-the-Counter (OTC) Categories: Mention common standard OTC drug classes (e.g., antipyretics like paracetamol/ibuprofen for fever, topical antifungals like clotrimazole, antihistamines like cetirizine/levocetirizine). Explicitly state that dosage instructions depend on age, weight, and clinical history, and must be confirmed via product packaging labels or by consulting a pharmacist/physician.
  4. Critical Emergency Red-Flag Warning Signs requiring urgent hospital care.
Safety: Do NOT calculate or prescribe specific milligram dosages, frequencies, or prescription medications.
"""

FALLBACK_DB = {
    "fever": (
        "Systemic Febrile Syndrome",
        "Maintain oral hydration with electrolyte fluids, rest in a cool ventilated room, and wear lightweight clothing.",
        "Common over-the-counter options include antipyretics such as paracetamol (acetaminophen) or ibuprofen. Dosing depends strictly on the individual's age and body weight—always refer directly to the product packaging instructions or consult a licensed pharmacist.",
        "Temperature exceeding 103°F (39.4°C), stiff neck, confusion, petechial rash, or difficulty breathing."
    ),
    "fungus": (
        "Superficial Fungal / Dermatophyte Irritation",
        "Keep the skin clean and completely dry, wear loose breathable fabrics, and avoid sharing towels or personal items.",
        "Common over-the-counter options include topical antifungals such as clotrimazole cream or terbinafine cream. Application instructions, age suitability, and duration vary by formulation—check the manufacturer packaging or ask a pharmacist.",
        "Spreading cellulitis (rapid heat, severe swelling), open oozing sores, or involvement near the eyes."
    ),
    "allergy": (
        "Allergic Rhinitis / Histaminic Response",
        "Avoid known allergen triggers, use cool compresses over irritated areas, and rinse nasal passages with isotonic saline.",
        "Common over-the-counter options include second-generation antihistamines such as cetirizine, levocetirizine, or loratadine. Dosing guidelines differ across age groups—review the package label carefully or speak with a healthcare provider.",
        "ANAPHYLAXIS: Swelling of lips, tongue, or throat, tightness in chest, wheezing, or difficulty swallowing."
    ),
    "throat": (
        "Acute Pharyngitis & Throat Irritation",
        "Gargle with warm saline solution (1/2 tsp salt in warm water) several times daily and drink warm soothing liquids.",
        "Common over-the-counter options include anesthetic throat lozenges and mild analgesics like paracetamol. Check package guidelines for age restrictions, and visit a doctor if the sore throat lasts longer than 3–4 days.",
        "Inability to swallow fluids, difficulty opening your mouth, stridor, or shortness of breath."
    ),
    "cough": (
        "Acute Bronchial / Respiratory Irritation",
        "Use warm steam inhalation for 10–15 minutes, stay well hydrated, and use a cool mist humidifier.",
        "Common over-the-counter options include expectorants like guaifenesin or demulcent cough syrups. Review product labeling for age limits and dosing intervals, and consult a doctor if the cough persists.",
        "Coughing up blood, sharp chest pain upon inhalation, or persistent shortness of breath."
    ),
    "headache": (
        "Cephalalgia / Tension Headache",
        "Rest in a quiet, dark environment, drink 500 mL of water, and apply a cool cloth to the forehead.",
        "Common over-the-counter options include analgesics such as paracetamol or ibuprofen. Follow label guidelines to avoid overuse, and consult a doctor if headaches recur frequently.",
        "Sudden severe 'thunderclap' onset, neurological deficits, fever with stiff neck, or post-head trauma."
    )
}

def fallback_reply(user_text):
    text_lower = user_text.lower()
    matched = None
    for key, data in FALLBACK_DB.items():
        if key in text_lower or (key == "fungus" and any(w in text_lower for w in ["fungal", "ringworm", "itch"])) or (key == "allergy" and any(w in text_lower for w in ["allergic", "sneezing", "hives"])):
            matched = data
            break
    if not matched:
        matched = (
            "General Health Discomfort",
            "Rest comfortably, maintain good hydration, and monitor your symptoms closely.",
            "Discuss suitable non-prescription options with a certified pharmacist or medical professional based on your specific age and symptoms.",
            "Sudden severe pain, shortness of breath, high continuous fever, or loss of consciousness."
        )
    
    return (
        f"### 🩺 Clinical Triage Synthesis: {matched[0]}\n\n"
        f"• **Physiological Correlation:** Presentation is consistent with localized irritation, inflammation, or immune activation.\n\n"
        f"• **Evidence-Based Supportive Care:**\n  - {matched[1]}\n\n"
        f"• **General OTC Considerations:**\n  - {matched[2]}\n\n"
        f"• ⚠️ **Critical Red-Flag Escalation Thresholds:**\n  - {matched[3]}\n\n"
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

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("audio"):
            play_audio(msg["content"])

user_input = st.chat_input("State your health symptoms...")

if user_input:
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
            openrouter_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ]
            
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
            bot_reply = fallback_reply(user_input)

        st.markdown(bot_reply)
        play_audio(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply, "audio": True})
        
