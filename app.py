import streamlit as st
import streamlit.components.v1 as components
import requests
import re

st.set_page_config(page_title="MedAssist AI - Clinical Assistant", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI - Clinical Assistant")
st.caption("⚠️ **Educational Demonstration Only.** This assistant provides clinical triage guidance and supportive self-care advice. It does not provide medical diagnoses or prescriptions. For severe symptoms, consult a certified physician immediately.")

# Retrieve OpenRouter Key securely from Streamlit Secrets or Sidebar
api_key = st.secrets.get("OPENROUTER_API_KEY", None)

with st.sidebar:
    st.subheader("⚙️ Cloud Model Setup")
    if not api_key:
        api_key = st.text_input("OpenRouter API Key (Optional)", type="password", help="Paste your key here or save it in Streamlit Secrets.")
    else:
        st.success("API Key detected from Secrets!")
    
    if st.button("Reset Session"):
        st.session_state.messages = []
        st.session_state.turns = 0
        st.rerun()

SYSTEM_PROMPT = """
You are MedAssist AI, an expert, empathetic clinical triage assistant for an educational exhibition.
Workflow instructions:
- Turn 1: Empathetically acknowledge every symptom or trauma mentioned (e.g., knee scrapes, headaches, falls, sprains). Ask 2 focused clinical follow-up questions regarding severity, duration, or injury mechanics.
- Turn 2+: Synthesize cumulative symptoms. Provide:
  1. Clinical Impression & Physiological Correlation.
  2. Evidence-Based Supportive Care & Non-Pharmacological Regimen.
  3. Critical Emergency Red-Flag Warning Signs requiring immediate doctor/ER evaluation.
Safety: Do NOT prescribe medications or dosages. Keep formatting structured and concise.
"""

# 25 Clinical Conditions Fallback Engine
FALLBACK_DB = {
    "neck": ("Cervical Muscular Strain / Torticollis", "Can you bring your chin down flush to touch your chest without excruciating pain or resistance?", "Apply warm moist compresses for 15 mins, rest cervical muscles, and avoid sudden rotational movements.", "Severe neck stiffness with high pyrexia, photophobia, or purple rash (Meningitis suspicion)."),
    "ankle": ("Ankle Ligamentous Inversion Sprain", "Did the trauma involve immediate localized swelling, an audible pop, or inability to take 4 independent steps?", "Follow R.I.C.E.: Rest joint, apply protected Ice for 15 mins, light Compression bandage, and Elevate above heart level.", "Inability to bear weight immediately (Ottawa ankle rule), gross deformity, or severe neurovascular numbness."),
    "knee": ("Knee Arthralgia & Ligamentous Strain", "Did the knee lock, twist violently, or swell within the first 2 hours of injury?", "Cease weight-bearing loading, apply protected cryotherapy for 15 mins twice daily, and keep leg elevated.", "Rapid swelling within 2 hours, inability to straighten knee fully, or joint redness with fever."),
    "back": ("Lumbar Paraspinal Strain & Lumbago", "Does discomfort radiate past the knee down the leg, or cause numbness in the groin/saddle area?", "Avoid bed rest >24h; maintain gentle walking, apply alternating warm compresses, and sleep with a knee pillow.", "Cauda Equina flags: loss of bowel/bladder control, saddle numbness, or sudden progressive lower limb weakness."),
    "wrist": ("Acute Wrist Ligamentous Distension", "Did this follow a fall onto an outstretched hand, and is there tenderness in the anatomical snuffbox?", "Immobilize wrist in neutral alignment with a splint, apply cold packs, and avoid gripping motions.", "Tenderness in anatomical snuffbox (scaphoid fracture suspicion), acute pallor, or persistent thumb numbness."),
    "fever": ("Systemic Febrile Syndrome", "What is the peak temperature recorded, and has it lasted longer than 48 hours?", "Maintain oral hydration with electrolyte fluids (35 mL/kg/day target), rest in a 21°C ventilated space, and wear breathable clothing.", "Core temperature >103°F (39.4°C), altered consciousness, stiff neck, petechiae, or continuous vomiting."),
    "throat": ("Acute Pharyngitis & Tonsillitis", "Are you able to swallow liquids comfortably, and are there visible tonsillar white exudates?", "Gargle with warm saline (1/2 tsp salt in 250ml water) 3 times daily, drink warm broths, and rest your voice.", "Inability to swallow saliva (pooling), trismus (inability to open mouth fully), stridor, or asymmetrical tonsillar swelling."),
    "cough": ("Acute Bronchitis & Respiratory Irritation", "Is the cough dry and hacking or productive with discolored or thick phlegm?", "Perform warm steam inhalation for 10-15 mins, sip warm fluids with honey, and maintain indoor humidity.", "Hemoptysis (coughing blood), respiratory rate >24/min, sharp pleuritic chest pain on inhalation, or dyspnea."),
    "cold": ("Viral Rhinosinusitis (Common Cold)", "Is nasal drainage watery or thickened, and have symptoms persisted beyond 10 days without relief?", "Administer isotonic saline nasal irrigation, elevate head 30 degrees during sleep, and hydrate well.", "Periorbital eye swelling, severe unilateral facial pain with secondary fever spike, or stiff neck."),
    "shortness of breath": ("Acute Dyspnea & Bronchospasm Exacerbation", "Did breathlessness commence acutely, and do you perceive end-expiratory whistling or wheezing?", "Adopt High-Fowler's posture (sit upright leaning slightly forward), loosen chest clothing, practice pursed-lip breathing.", "CRITICAL: Central cyanosis (blue lips/fingers), intercostal retractions, inability to speak 2 words, or diaphoresis."),
    "chest": ("Thoracic Discomfort / Cardiac & Musculoskeletal Triage", "Does the pain fluctuate when pressing on ribs, or feel like deep substernal crushing pressure?", "Immediately cease all physical activity, rest seated upright with back support, and avoid heavy oral intake.", "CRITICAL: Crushing retrosternal pressure radiating to jaw or left arm, cold diaphoresis, dyspnea, or nausea."),
    "stomach": ("Acute Dyspepsia & Gastroenteritis", "Where is the pain localized (upper or lower), and does it correlate chronologically with meals?", "Withhold heavy/fatty foods for 4-6 hours, adopt the BRAT diet (bananas, rice, applesauce, toast), and sip clear fluids.", "Surgical flags: localized right lower quadrant rebound tenderness (McBurney point), board-like rigidity, hematemesis."),
    "diarrhea": ("Acute Infectious/Osmotic Gastroenteritis", "What is the 24-hour frequency of loose evacuations, and is there visible blood or dark mucus?", "Immediately initiate Oral Rehydration Salts (ORS) solution sip-by-sip after each loose stool; avoid dairy and sugar.", "Grossly bloody or black melenic stool, postural syncope, absence of urination >8h, or high fever."),
    "vomit": ("Acute Emesis & Gastric Intolerance", "Can you retain small sips of water without immediately vomiting, and what color is the vomitus?", "Total gastric rest (NPO) for 60 mins post-vomit, then introduce 1 teaspoon (5ml) clear electrolyte fluid every 10 mins.", "Coffee-ground emesis, bright hematemesis, unrelenting localized pain, or persistent neurological lethargy."),
    "head": ("Cephalalgia / Tension-Type & Migraine", "Is discomfort a bilateral compressive band or unilateral pulsatile throbbing with light sensitivity?", "Retire into a sound-attenuated, darkened room, drink 500-750 mL fluid immediately, and apply cold temporal compress.", "Thunderclap onset (peak in <60 seconds), focal motor deficits, neck stiffness with pyrexia, or post-trauma."),
    "acid reflux": ("Gastroesophageal Reflux Disease (GERD)", "Does burning intensify during supine reclining, and do you experience sour fluid regurgitation?", "Elevate bed head 15 cm, remain upright 3 hours after meals, avoid late heavy meals, chocolate, and caffeine.", "Progressive dysphagia (food feeling stuck behind sternum), odynophagia, unexplained weight loss, or vomiting."),
    "dizziness": ("Vestibular Dysfunction & Orthostatic Lightheadedness", "Do you perceive rotational spinning when turning your head, or lightheaded faintness upon standing?", "Sit or lie down flat immediately upon onset to prevent mechanical falls; change postures slowly in 60-second steps.", "HINTS red flags: new speech slurring, acute limb ataxia (cannot stand unaided), double vision, or sudden hearing drop."),
    "rash": ("Acute Urticaria & Contact Dermatitis", "Are lesions raised, blanching under pressure, or rapidly expanding across body surfaces?", "Wash gently with cool sterile water and mild non-soap syndet, apply cold damp compresses, avoid scratch friction.", "ANAPHYLAXIS: Concurrent angioedema (swelling of lips, tongue, or throat), wheezing, stridor, or syncope."),
    "burn": ("Superficial / Partial-Thickness Thermal Injury", "Are there intact or ruptured fluid blisters, and does the area exceed the size of your palm?", "Irrigate immediately under cool running tap water for 20 continuous minutes; avoid ice, butter, or toothpaste.", "Burns covering face, hands, major joints, or genitalia; circumferential burns; or white painless leathery eschar."),
    "fatigue": ("Systemic Asthenia & Post-Viral Fatigue", "Has this fatigue persisted beyond two weeks, and does it remain unrefreshed by 8 hours of sleep?", "Practice energy budgeting, ensure balanced complex carbohydrates and protein intake, and drink 2L water daily.", "Sudden focal limb weakness, exertional syncope, unexplained weight loss, or heavy nocturnal drenching sweats."),
    "eye": ("Acute Conjunctivitis & Ocular Irritation", "Is there yellow/green discharge gluing lids shut upon waking, or predominantly watery itching?", "Apply cool sterile compresses over closed eyes, discontinue contact lenses immediately, and practice hand hygiene.", "Marked reduction in visual acuity, severe deep ciliary eye pain, severe photophobia, or pupil asymmetry."),
    "ear": ("Otalgia / Otitis Media & Externa", "Does pulling the earlobe or tragus elicit severe pain, or did this follow swimming or an upper respiratory cold?", "Keep auditory canal strictly dry, rest head elevated, and apply a warm dry external compress over mastoid area.", "Purulent or hemorrhagic canal drainage, redness/swelling behind earlobe (mastoiditis), or facial weakness."),
    "constipation": ("Colonic Dysmotility & Constipation", "When was your last complete evacuation, and are you passing abdominal flatus (gas) normally?", "Increase dietary soluble fiber (psyllium, oats) to 25-30g daily, drink 2.5L water daily, and walk 20 mins daily.", "Obstipation (total inability to pass both stool and gas), severe distension, continuous vomiting, or rectal bleeding."),
    "heat exhaustion": ("Thermoregulatory Strain & Heat Exhaustion", "Are you sweating profusely, or has perspiration ceased while your skin feels dry and burning hot?", "Move immediately to an air-conditioned room, apply cold damp towels to neck/axillae/groin, and sip chilled water.", "HEAT STROKE: Anhidrosis (no sweating), core temp >104°F (40°C), confusion, ataxia, seizures, or loss of consciousness."),
    "mouth ulcer": ("Minor Aphthous Stomatitis", "Is the lesion a solitary shallow round crater with an erythematous halo inside the mouth?", "Rinse with warm saline (1/2 tsp salt in 200ml warm water) 4 times daily, avoid spicy/acidic foods, and use soft brush.", "Ulcers persisting continuously beyond 14 days, recurrent extensive clusters, or concurrent genital sores.")
}

def fallback_reply(user_text, turn_count):
    text_lower = user_text.lower()
    matched = None
    for key, data in FALLBACK_DB.items():
        if key in text_lower or (key == "ankle" and any(w in text_lower for w in ["twist", "sprain", "foot"])):
            matched = data
            break
    if not matched:
        matched = ("General Bodily Discomfort", "When did this sensation start, and does it worsen with movement or rest?", "Ensure adequate oral hydration, rest comfortably, and observe symptom progression.", "Sudden severe pain, shortness of breath, high persistent fever, or fainting.")
    
    if turn_count <= 1:
        return f"### Clinical Assessment Registered: {matched[0]}\n\n• **Initial Observation:** I have recorded your presentation regarding **{matched[0]}**.\n\n👉 **Focused Clinical Inquiry:** {matched[1]}\n\n*Please share details so I can calibrate supportive care and check for escalation thresholds.*"
    else:
        return f"### Clinical Triage Synthesis: {matched[0]}\n\n• **Physiological Correlation:** Symptoms are consistent with localized irritation, inflammation, or mechanical strain in the affected tissue.\n\n• **Evidence-Based Supportive Care:**\n  - {matched[2]}\n\n• ⚠️ **Critical Red-Flag Escalation Thresholds:**\n  - {matched[3]}\n\n*Reminder: Educational demonstration tool. If symptoms persist or worsen, please consult a certified doctor immediately.*"

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
            "Hello! I am your clinical triage assistant. I analyze physiological symptoms, "
            "provide evidence-based supportive care protocols, and screen for critical emergency red flags.\n\n"
            "👉 **How can I assist you today?** Describe any bodily discomfort, symptoms, or injury you are experiencing."
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
            messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}]
            for m in st.session_state.messages:
                messages_payload.append({
                    "role": "user" if m["role"] == "user" else "assistant",
                    "content": m["content"]
                })
            
            # Using active, free Google Gemma 3 model on OpenRouter
            payload = {
                "model": "google/gemma-3-27b-it:free",
                "messages": messages_payload,
                "temperature": 0.3
            }
            
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=20
                )
                if resp.status_code == 200:
                    data = resp.json()
                    bot_reply = data["choices"][0]["message"]["content"]
                    used_cloud = True
                else:
                    st.error(f"OpenRouter Error ({resp.status_code}): {resp.text}")
            except Exception as err:
                st.error(f"Network Error: {err}")

        if not used_cloud:
            bot_reply = fallback_reply(user_input, st.session_state.turns)

        st.markdown(bot_reply)
        play_audio(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply, "audio": True})
        
