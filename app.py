import streamlit as st

# Page layout & styling
st.set_page_config(page_title="MedAssist AI", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI")
st.subheader("Medical Information & Assistance Assistant")
st.caption(
    "⚠️ **Disclaimer:** Educational demonstration only. This system provides "
    "general health information and symptom guidance. It cannot provide a formal medical "
    "diagnosis. Please consult a qualified physician for healthcare needs."
)

# Knowledge Base
MEDICAL_DATABASE = {
    "fever": {
        "alias": ["temperature", "chills", "febrile"],
        "causes": "Viral infections (common cold, flu), bacterial infections, or systemic inflammation.",
        "follow_up": "How high has your body temperature reached, and how many days has it lasted?",
        "care": "Maintain hydration with water and electrolyte drinks, get plenty of rest, and stay in a cool room.",
        "red_flags": "Temperature over 103°F (39.4°C), stiff neck, confusion, or difficulty breathing."
    },
    "cough": {
        "alias": ["coughing", "phlegm", "mucus", "bronchitis"],
        "causes": "Respiratory irritation, viral bronchitis, post-nasal drip, or seasonal allergies.",
        "follow_up": "Is your cough dry, or are you coughing up thick phlegm?",
        "care": "Perform steam inhalation, drink warm soothing liquids, and avoid cold/dry air.",
        "red_flags": "Coughing up blood, sharp chest pain when inhaling, or persistent shortness of breath."
    },
    "sore throat": {
        "alias": ["throat", "pharyngitis", "tonsil", "swallowing pain"],
        "causes": "Viral pharyngitis, acute tonsillitis, or seasonal viral infections.",
        "follow_up": "Are you able to swallow liquids comfortably, and are your tonsils swollen?",
        "care": "Gargle with warm salt water three times daily and consume warm, soft foods.",
        "red_flags": "Inability to swallow liquids or open your mouth fully, or severe breathing difficulty."
    },
    "headache": {
        "alias": ["head ache", "migraine", "head pain"],
        "causes": "Tension, dehydration, digital screen eye strain, or migraine.",
        "follow_up": "Is it a dull band of tension across your head or a sharp throbbing pain?",
        "care": "Rest in a quiet, dark environment, hydrate with 500 mL of water, and apply a cool compress.",
        "red_flags": "Sudden severe 'thunderclap' headache, onset after a head injury, or confusion."
    },
    "stomach pain": {
        "alias": ["stomach", "abdominal pain", "belly ache", "cramp", "gastritis"],
        "causes": "Indigestion, gastritis, dietary irritation, or gastroenteritis.",
        "follow_up": "Is the discomfort sharp or crampy, and does it worsen before or after meals?",
        "care": "Eat a mild diet (bananas, rice, toast), avoid fried/spicy items, and take small sips of water.",
        "red_flags": "Severe localized lower-right abdominal pain, continuous vomiting, or high fever."
    },
    "cold": {
        "alias": ["runny nose", "congestion", "sneezing", "blocked nose", "sinus"],
        "causes": "Rhinovirus (common cold) or seasonal allergic rhinitis.",
        "follow_up": "Is the nasal drainage clear or thick, and are you having sneezing fits?",
        "care": "Use saline nasal sprays, inhale warm steam, and rest with your head elevated.",
        "red_flags": "Swelling around the eyes/face or symptoms worsening after one week."
    },
    "chest pain": {
        "alias": ["chest pressure", "chest tightness"],
        "causes": "Muscle strain, acid reflux (GERD), or cardiovascular complications.",
        "follow_up": "Does it change when pressing your chest ribs, or does it feel like heavy internal pressure?",
        "care": "Cease physical exertion immediately and rest in an upright position.",
        "red_flags": "CRITICAL EMERGENCY: Squeezing central pressure spreading to the arm or jaw. Call emergency medical help immediately."
    }
}

def analyze(text):
    text_lower = text.lower()
    matches = []
    for key, val in MEDICAL_DATABASE.items():
        if key in text_lower or any(alias in text_lower for alias in val["alias"]):
            matches.append((key, val))
    return matches

# Chat session memory
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Enter symptoms (e.g., fever, cough, sore throat)...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Accumulate entire conversation context
    full_context = " ".join([m["content"] for m in st.session_state.messages])
    matches = analyze(full_context)

    with st.chat_message("assistant"):
        if not matches:
            bot_reply = (
                "Hello! Please describe your symptoms in detail "
                "(for example: fever, sore throat, cough, headache, or stomach discomfort)."
            )
        else:
            primary_name, details = matches[-1]
            all_symptoms = ", ".join([name.title() for name, _ in matches])
            bot_reply = (
                f"**Identified Symptom:** {primary_name.title()}\n"
                f"*(Active Context Tracking: {all_symptoms})*\n\n"
                f"• **Potential Common Causes:** {details['causes']}\n\n"
                f"• **Recommended Self-Care:** {details['care']}\n\n"
                f"• **⚠️ Red-Flag Warnings:** {details['red_flags']}\n\n"
                f"👉 **Doctor Follow-Up Question:** {details['follow_up']}\n\n"
                f"*Please consult a qualified medical professional if symptoms persist.*"
            )
        st.markdown(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            
