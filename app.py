import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="MedAssist AI", page_icon="🩺", layout="centered")

# Header & Safety Disclaimer
st.title("🩺 MedAssist AI - Medical Assistance Chatbot")
st.caption(
    "⚠️ **Disclaimer:** This tool provides general medical information and symptom guidance only. "
    "It is not a doctor and cannot provide formal diagnoses. "
    "Please consult a certified healthcare professional for medical concerns."
)

# API Key handling
api_key = st.secrets.get("GEMINI_API_KEY", None)
if not api_key:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

if not api_key:
    st.info("Please enter your Gemini API Key in the left sidebar to start chatting.")
    st.stop()

client = genai.Client(api_key=api_key)

# Behavior instructions
SYSTEM_PROMPT = """
You are MedAssist, a supportive medical assistance chatbot for an educational demonstration.
Follow these rules:
1. Ask 1-2 clarifying follow-up questions regarding symptoms (duration, severity, accompanying issues).
2. Suggest potential common causes without confirming a diagnosis.
3. Offer basic self-care and non-prescription wellness advice.
4. Flag severe or emergency symptoms (chest pain, shortness of breath, high persistent fever) that require immediate hospital care.
5. Keep explanations clear, empathetic, and organized in short bullet points.
"""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display past messages
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["parts"][0])

# Chat input
user_input = st.chat_input("Describe your symptoms (e.g., fever, cough)...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "parts": [user_input]})

    formatted_contents = [
        types.Content(
            role=m["role"],
            parts=[types.Part.from_text(text=m["parts"][0])]
        )
        for m in st.session_state.chat_history
    ]

    with st.chat_message("assistant"):
        with st.spinner("Analyzing symptoms..."):
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=formatted_contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3
                ),
            )
            bot_reply = response.text
            st.markdown(bot_reply)

    st.session_state.chat_history.append({"role": "model", "parts": [bot_reply]})
          
