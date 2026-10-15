import io
import re
from datetime import date, datetime

import requests
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)

st.set_page_config(page_title="MedAssist AI - Clinical Assistant", page_icon="🩺", layout="wide")

SYSTEM_PROMPT = """
You are MedAssist AI, an educational symptom-triage assistant, not a doctor.
Use empathetic, plain language. Ask focused follow-up questions when important details are missing.
Consider the conversation history, patient age, symptom duration, severity, allergies, conditions and current medicines when provided.
Explain possible causes as possibilities, never as a confirmed diagnosis. Offer conservative, non-drug supportive care when appropriate.
Do not prescribe medicines, choose a patient-specific medicine, or provide patient-specific dose, frequency or duration.
Do not create prescription instructions. If the user asks about medicines, recommend review by a licensed clinician or pharmacist, especially for children, pregnancy, allergies, chronic conditions or other medicines.
Always screen for emergency symptoms. If a potential emergency is mentioned, put urgent action first and advise contacting local emergency services / going to an emergency department. Do not delay urgent care with more questions.
Avoid overconfident claims, fabricated evidence, and overly technical jargon.
End with a brief reminder that this is educational guidance and is not a substitute for professional medical assessment.
Structure answers with headings when useful: Summary, Follow-up questions, Supportive care, When to seek urgent help.
"""

EMERGENCY_RULES = [
    (r"\b(chest pain|chest pressure|crushing chest|pain in (my )?(left arm|jaw))\b",
     "Chest pain/pressure can be an emergency. Seek emergency medical care now, especially with breathlessness, sweating, nausea, or pain spreading to the arm/jaw."),
    (r"\b(can't breathe|cannot breathe|severe shortness of breath|struggling to breathe|blue lips)\b",
     "Severe breathing difficulty or blue lips can be an emergency. Call your local emergency number now."),
    (r"\b(face droop|slurred speech|sudden weakness|one-sided weakness|sudden confusion)\b",
     "These can be signs of a stroke. Call your local emergency number now; do not drive yourself."),
    (r"\b(unconscious|not waking|seizure lasting|severe bleeding|bleeding won't stop)\b",
     "This may be an emergency. Call your local emergency number now."),
    (r"\b(swollen tongue|throat closing|anaphylaxis)\b",
     "Possible severe allergic reaction: call your local emergency number now."),
    (r"\b(suicidal|want to kill myself|overdose|took too many pills)\b",
     "Please get urgent in-person help now. If there may have been an overdose or immediate danger, call local emergency services or go to the nearest emergency department. Stay with a trusted person if possible."),
]

def emergency_messages(text):
    lowered = text.lower()
    found = []
    for pattern, message in EMERGENCY_RULES:
        if re.search(pattern, lowered):
            found.append(message)
    return list(dict.fromkeys(found))

def get_api_key():
    try:
        key = st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        key = ""
    if not key:
        key = st.session_state.get("session_api_key", "")
    return str(key).strip().strip('"').strip("'")

def ask_model(messages, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "MedAssist AI",
    }
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.2,
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def build_pdf(patient, symptoms, assessment, medication_rows, notes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ClinicTitle", parent=styles["Title"], alignment=TA_CENTER,
        textColor=colors.HexColor("#155E75"), fontSize=19, leading=23, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="SmallNote", parent=styles["BodyText"], fontSize=8, leading=10,
        textColor=colors.HexColor("#555555")
    ))
    styles.add(ParagraphStyle(
        name="SectionHead", parent=styles["Heading2"], textColor=colors.HexColor("#155E75"),
        fontSize=12, leading=15, spaceBefore=10, spaceAfter=5
    ))
    story = [
        Paragraph("MedAssist AI", styles["ClinicTitle"]),
        Paragraph("CONSULTATION SUMMARY — NOT A PRESCRIPTION", styles["Heading3"]),
        Paragraph(
            "Educational triage report for clinician review. AI output is not a diagnosis, "
            "medical order, or substitute for an examination.", styles["SmallNote"]
        ),
        Spacer(1, 8),
    ]
    patient_data = [
        ["Patient name", patient.get("name") or "Not provided",
         "Report date", date.today().strftime("%d %b %Y")],
        ["Age", patient.get("age") or "Not provided",
         "Sex (optional)", patient.get("sex") or "Not provided"],
        ["Allergies", patient.get("allergies") or "Not provided",
         "Current medicines", patient.get("medicines") or "Not provided"],
        ["Relevant conditions", patient.get("conditions") or "Not provided",
         "Symptom duration", patient.get("duration") or "Not provided"],
    ]
    t = Table(patient_data, colWidths=[28*mm, 48*mm, 30*mm, 48*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#E6F4F1")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#E6F4F1")),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#B7C9CC")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [t, Paragraph("Symptoms reported", styles["SectionHead"]),
              Paragraph(escape_pdf(symptoms or "Not provided"), styles["BodyText"]),
              Paragraph("AI-generated triage summary", styles["SectionHead"]),
              Paragraph(escape_pdf(assessment or "No assessment available."), styles["BodyText"])]

    story.append(Paragraph("Medication review — clinician to complete", styles["SectionHead"]))
    story.append(Paragraph(
        "No medicines or dosing instructions are generated by this chatbot. A licensed clinician "
        "must independently decide whether medication is appropriate and verify every order.", styles["SmallNote"]
    ))
    med_data = [["Medicine / strength", "Dose", "Route", "Frequency", "Duration", "Clinician initials"]]
    for row in medication_rows:
        med_data.append([row.get(k, "") or "—" for k in
                         ["medicine", "dose", "route", "frequency", "duration", "initials"]])
    mt = Table(med_data, colWidths=[34*mm, 20*mm, 19*mm, 27*mm, 22*mm, 30*mm], repeatRows=1)
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#155E75")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#B7C9CC")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story += [mt, Paragraph("Clinician notes / follow-up plan", styles["SectionHead"]),
              Paragraph(escape_pdf(notes or "Not provided"), styles["BodyText"]),
              Spacer(1, 12),
              Paragraph(
                  "Safety: If symptoms are severe, rapidly worsening, or suggest an emergency, "
                  "seek urgent medical care rather than relying on this report.", styles["SmallNote"]
              )]
    doc.build(story)
    return buffer.getvalue()

def escape_pdf(value):
    value = str(value or "")
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br/>"))

st.title("🩺 MedAssist AI — Clinical Assistant")
st.caption(
    "Educational demonstration only. Provides symptom-triage information, not diagnoses or prescriptions. "
    "For severe symptoms, contact local emergency services."
)

with st.sidebar:
    st.subheader("⚙️ Model setup")
    if not get_api_key():
        st.session_state.session_api_key = st.text_input(
            "OpenRouter API key", type="password",
            help="Prefer setting OPENROUTER_API_KEY in Streamlit secrets."
        )
    else:
        st.success("API key configured.")
    st.caption("Voice input works in supported browsers.")
    components.html("""
    <script>
    function startDictation() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { alert("Speech recognition is not supported in this browser."); return; }
      const recognition = new SR();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        const box = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
        if (box) {
          const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value').set;
          setter.call(box, transcript);
          box.dispatchEvent(new Event('input', {bubbles:true}));
          box.focus();
        } else { alert("Please click the chat box and try voice input again."); }
        document.getElementById("voice-status").textContent = "Captured: " + transcript;
      };
      recognition.onerror = function() {
        document.getElementById("voice-status").textContent = "Voice input failed. Try again or type your symptoms.";
      };
      recognition.start();
      document.getElementById("voice-status").textContent = "Listening…";
    }
    </script>
    <button onclick="startDictation()" style="width:100%;padding:8px;border:0;border-radius:6px;background:#176B55;color:white;font-weight:600;">🎙️ Speak symptoms</button>
    <p id="voice-status" style="font-size:12px;">Use microphone permission when prompted.</p>
    """, height=85)

    if st.button("Reset conversation", use_container_width=True):
        st.session_state.chat_messages = []
        st.rerun()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "latest_assessment" not in st.session_state:
    st.session_state.latest_assessment = ""

with st.expander("🧾 Patient intake form (optional)", expanded=True):
    with st.form("patient_intake"):
        c1, c2 = st.columns(2)
        with c1:
            patient_name = st.text_input("Patient name (optional)")
            age = st.number_input("Age", min_value=0, max_value=120, value=18, step=1)
            sex = st.selectbox("Sex (optional)", ["Not provided", "Female", "Male", "Intersex", "Prefer not to say"])
            duration = st.text_input("How long have symptoms been present?")
        with c2:
            allergies = st.text_area("Known allergies (include 'unknown' if unsure)", height=70)
            conditions = st.text_area("Existing conditions / pregnancy if relevant", height=70)
            medicines = st.text_area("Current medicines or supplements", height=70)
        symptoms = st.text_area("Main symptoms and severity", height=100,
                                placeholder="Describe symptoms, when they started, severity, and anything that makes them better or worse.")
        intake_submit = st.form_submit_button("Save patient details")
    if intake_submit:
        st.session_state.patient = {
            "name": patient_name.strip(),
            "age": str(age) if age else "",
            "sex": "" if sex in ("Not provided", "Prefer not to say") else sex,
            "duration": duration.strip(),
            "allergies": allergies.strip(),
            "conditions": conditions.strip(),
            "medicines": medicines.strip(),
        }
        st.session_state.intake_symptoms = symptoms.strip()
        st.success("Patient details saved for this session.")
        urgent = emergency_messages(symptoms)
        if urgent:
            for item in urgent:
                st.error(item)

patient = st.session_state.get("patient", {})
if patient:
    st.info("Patient details are stored in this browser session only. Avoid entering identifying information for demonstrations.")

st.subheader("💬 Consultation")
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

chat_prompt = st.chat_input("Describe symptoms or answer a follow-up question…")
if chat_prompt:
    is_first_turn = len(st.session_state.chat_messages) == 0
    st.session_state.chat_messages.append({"role": "user", "content": chat_prompt})
    with st.chat_message("user"):
        st.markdown(chat_prompt)

    full_user_context = chat_prompt
    if is_first_turn and patient:
        intake_text = st.session_state.get("intake_symptoms", "")
        if intake_text:
            full_user_context += "\n\nSymptoms from intake form: " + intake_text
        full_user_context += (
            f"\nPatient context: age {patient.get('age') or 'not provided'}; "
            f"symptom duration {patient.get('duration') or 'not provided'}; "
            f"allergies {patient.get('allergies') or 'not provided'}; "
            f"conditions {patient.get('conditions') or 'not provided'}; "
            f"current medicines {patient.get('medicines') or 'not provided'}."
        )

    urgent = emergency_messages(full_user_context)
    if urgent:
        reply = "### ⚠️ Urgent safety notice\n\n" + "\n\n".join(urgent) + \
                "\n\nPlease do not wait for chatbot advice if symptoms are happening now."
    else:
        with st.spinner("Preparing triage guidance…"):
            try:
                key = get_api_key()
                if not key:
                    raise RuntimeError("No API key configured")
                # Include intake details only on the first turn; preserve older conversation turns.
                model_messages = []
                first_user = True
                for m in st.session_state.chat_messages:
                    content = m["content"]
                    if is_first_turn and m["role"] == "user" and first_user:
                        content = full_user_context
                        first_user = False
                    model_messages.append({"role": m["role"], "content": content})
                reply = ask_model(model_messages, key)
            except Exception:
                reply = (
                    "I couldn't reach the AI service just now. Please check the OpenRouter API key "
                    "and connection, then try again. If symptoms are severe or worsening, seek medical care. "
                    "This educational chatbot cannot diagnose or prescribe medication."
                )
    st.session_state.chat_messages.append({"role": "assistant", "content": reply})
    st.session_state.latest_assessment = reply
    st.rerun()

st.divider()
st.subheader("📄 Consultation report & PDF")
st.caption("The report is a summary for discussion with a qualified clinician. It is not a valid prescription.")

default_symptoms = st.session_state.get("intake_symptoms", "")
report_symptoms = st.text_area("Symptoms to include in report", value=default_symptoms, key="report_symptoms")
report_assessment = st.text_area(
    "Consultation summary to include",
    value=st.session_state.get("latest_assessment", ""),
    height=180,
    key="report_assessment",
)
clinician_notes = st.text_area("Clinician notes / follow-up plan (optional)", key="clinician_notes")
st.markdown("**Medication review table** — leave blank for the clinician to complete. The chatbot does not fill medication or dosing details.")
medication_rows = []
for i in range(2):
    with st.expander(f"Medication row {i+1} (clinician use only)", expanded=False):
        a, b, c = st.columns(3)
        with a:
            med_name = st.text_input("Medicine / strength", key=f"med_name_{i}")
            med_dose = st.text_input("Dose", key=f"med_dose_{i}")
        with b:
            med_route = st.text_input("Route", key=f"med_route_{i}")
            med_frequency = st.text_input("Frequency", key=f"med_frequency_{i}")
        with c:
            med_duration = st.text_input("Duration", key=f"med_duration_{i}")
            med_initials = st.text_input("Clinician initials", key=f"med_initials_{i}")
        medication_rows.append({
            "medicine": med_name, "dose": med_dose, "route": med_route,
            "frequency": med_frequency, "duration": med_duration, "initials": med_initials
        })

pdf_patient = dict(patient)
pdf_patient.setdefault("age", "")
if st.button("Generate consultation PDF", type="primary"):
    if not report_symptoms.strip() and not report_assessment.strip():
        st.warning("Add symptoms or a consultation summary before generating the report.")
    else:
        pdf_bytes = build_pdf(pdf_patient, report_symptoms, report_assessment, medication_rows, clinician_notes)
        st.download_button(
            "⬇️ Download consultation report (PDF)",
            data=pdf_bytes,
            file_name=f"medassist_consultation_{date.today().isoformat()}.pdf",
            mime="application/pdf",
        )

st.caption("For emergencies, use local emergency services. Do not use this educational demonstration to decide on medication or delay care.")
    
