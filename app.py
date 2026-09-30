import streamlit as st
import re

st.set_page_config(page_title="MedAssist AI", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI")
st.subheader("Medical Information & Assistance Chatbot")
st.caption(
    "⚠️ **Disclaimer:** Educational demonstration only. This system provides "
    "general health information and symptom guidance. It cannot provide a formal medical "
    "diagnosis. Please consult a qualified physician for healthcare needs."
)

# Symptom Knowledge Base
KNOWLEDGE_BASE = {
    "fever": {
        "alias": ["fever", "temperature", "chills", "febrile", "hot"],
        "follow_up": "How high has your temperature been? Do you also have cough, difficulty breathing, or body pain?",
        "causes": "common viral infections (like influenza or the common cold), bacterial infections, or systemic inflammation.",
        "care": "Maintain regular hydration with water or electrolyte solutions, get adequate rest, and stay in a comfortably ventilated room.",
        "red_flag": "Temperature exceeding 103°F (39.4°C), stiff neck, confusion, or persistent vomiting."
    },
    "sore throat": {
        "alias": ["sore throat", "throat", "pharyngitis", "tonsil", "swallowing"],
        "follow_up": "Are you able to swallow liquids comfortably, and do you notice swollen tonsils or ear pain?",
        "causes": "viral pharyngitis, acute tonsillitis, or seasonal upper respiratory irritation.",
        "care": "Gargle with warm salt water 2-3 times daily, drink soothing warm teas or broths, and avoid dry air.",
        "red_flag": "Severe difficulty swallowing saliva, inability to open your mouth fully, or stridor (noisy breathing)."
    },
    "cough": {
        "alias": ["cough", "coughing", "phlegm", "mucus", "bronchitis"],
        "follow_up": "Is your cough mostly dry, or are you coughing up thick phlegm? Do you feel any chest tightness?",
        "causes": "upper respiratory tract irritation, viral bronchitis, allergies, or post-nasal drip.",
        "care": "Try steam inhalation, drink warm fluids with honey, and avoid secondhand smoke.",
        "red_flag": "Coughing up blood, sharp chest pain when breathing, or persistent shortness of breath."
    },
    "headache": {
        "alias": ["headache", "head ache", "migraine", "head pain"],
        "follow_up": "Is the discomfort a dull pressure band across your head, or a sharp throbbing pain on one side?",
        "causes": "tension, physical fatigue, dehydration, screen eye strain, or migraine.",
        "care": "Rest in a quiet, dark room, hydrate with 500 mL of water, and apply a cool forehead compress.",
        "red_flag": "Sudden severe 'thunderclap' headache, onset after head trauma, or accompanied by confusion."
    },
    "stomach pain": {
        "alias": ["stomach", "abdominal", "belly", "cramp", "gastritis", "indigestion"],
        "follow_up": "Where is the pain located, and are you experiencing any nausea, vomiting, or diarrhea?",
        "causes": "indigestion, mild gastritis, dietary irritation, or viral gastroenteritis.",
        "care": "Stick to a bland diet (bananas, rice, applesauce, toast) and take small, frequent sips of water.",
        "red_flag": "Intense localized lower-right abdominal pain, continuous vomiting, or black/bloody stool."
    },
    "shortness of breath": {
        "alias": ["breath", "breathing", "breathless", "dyspnea", "wheezing"],
        "follow_up": "Did this sensation come on suddenly, and do you hear a whistling sound when breathing out?",
        "causes": "bronchial asthma flare, respiratory infection, or allergic reaction.",
        "care": "Sit upright, loosen restrictive clothing, and take slow, relaxed breaths.",
        "red_flag": "Severe chest tightness, inability to speak full sentences, or blue-tinted lips/nails (seek immediate emergency care)."
    }
}

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "recognized_symptoms" not in st.session_state:
    st.session_state.recognized_symptoms = []
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0

def detect_symptoms(text):
    found = []
    text_clean = text.lower()
    for name, data in KNOWLEDGE_BASE.items():
        if any(re.search(r'\b' + re.escape(alias) + r'\b', text_clean) for alias in data["alias"]):
            found.append(name)
    return found

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Enter symptoms or answer questions...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.turn_count += 1

    current_mentions = detect_symptoms(user_input)
    for s in current_mentions:
        if s not in st.session_state.recognized_symptoms:
            st.session_state.recognized_symptoms.append(s)

    all_symptoms = st.session_state.recognized_symptoms

    with st.chat_message("assistant"):
        # Turn 1: Initial greeting and focused clinical clarification
        if st.session_state.turn_count == 1:
            if "fever" in all_symptoms or "sore throat" in all_symptoms or "cough" in all_symptoms:
                bot_reply = "How high has your temperature been? Do you also have cough, difficulty breathing, or body pain?"
            elif all_symptoms:
                primary = all_symptoms[-1]
                bot_reply = f"I understand. {KNOWLEDGE_BASE[primary]['follow_up']}"
            else:
                bot_reply = (
                    "Hello! I am MedAssist AI. Could you describe your symptoms in detail? "
                    "(For instance, are you having a fever, sore throat, cough, headache, or stomach discomfort?)"
                )
        
        # Turn 2 and beyond: Synthesis, clinical correlations, and guidance
        else:
            if all_symptoms:
                symptom_summary = ", ".join([s.title() for s in all_symptoms])
                
                # Check for respiratory cluster
                is_respiratory = any(s in ["fever", "sore throat", "cough", "shortness of breath"] for s in all_symptoms)
                
                causes = "several respiratory infections" if is_respiratory else "common viral or systemic conditions"
                
                bot_reply = (
                    f"These symptoms can occur with {causes}. I can provide general information, "
                    f"but I cannot diagnose you. Because you have a persistent fever, consider "
                    f"consulting a healthcare professional, particularly if symptoms worsen.\n\n"
                    f"**Identified Context:** {symptom_summary}\n\n"
                    f"• **Recommended Self-Care:** Stay well hydrated, prioritize complete rest, and gargle with warm salt water if throat irritation continues.\n"
                    f"• **Safety Escalation:** Seek prompt medical evaluation if you experience breathing difficulty, severe chest pressure, or a temperature rising above 103°F (39.4°C)."
                )
            else:
                bot_reply = (
                    "Thank you for sharing. Could you specify if you are feeling any additional symptoms "
                    "such as fever, throat irritation, body aches, or shortness of breath?"
                )

        st.markdown(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    
