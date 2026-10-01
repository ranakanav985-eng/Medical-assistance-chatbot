import streamlit as st
import streamlit.components.v1 as components
import re

st.set_page_config(page_title="MedAssist AI", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI - Clinical Assistant")
st.caption("⚠️ **Educational Demonstration Only.** This assistant provides general clinical triage and supportive advice. It does not provide medical diagnoses or prescriptions. For severe symptoms, consult a certified physician immediately.")

# Comprehensive 25-condition clinical knowledge base (compact, single-line format)
DB = {
    "ankle_sprain": (["twisted ankle", "ankle", "twisted", "sprain", "twisted my ankle", "foot pain", "twisted foot"], "Ankle Inversion/Eversion Ligamentous Sprain", "Musculoskeletal", "Did the trauma involve immediate localized swelling, an audible pop, or inability to take 4 independent steps?", "Implement R.I.C.E.: Rest limb, apply Ice for 15-20 mins every 3 hours, wrap with Compression bandage, and Elevate above heart level.", "Inability to bear weight immediately, severe bone tenderness over malleolus (Ottawa Rule), gross deformity, or severe numbness."),
    "knee_pain": (["knee", "patella", "meniscus", "knee sprain", "twisted knee"], "Knee Arthralgia / Meniscal & Ligamentous Strain", "Musculoskeletal", "Did you experience joint locking, sudden 'giving way', or acute anterior clicking during flexion?", "Cease weight-bearing loading, apply protected cryotherapy for 15 mins twice daily, and keep leg elevated.", "Rapid joint effusion within 2 hours, inability to extend leg fully, or local erythema with systemic fever."),
    "wrist_strain": (["wrist", "twisted wrist", "sprained wrist", "carpal"], "Acute Wrist Ligamentous Distension", "Musculoskeletal", "Did this follow a fall onto an outstretched hand, and is there tenderness in the anatomical snuffbox?", "Immobilize wrist in neutral alignment with a splint, apply cold packs, and avoid gripping motions.", "Tenderness in anatomical snuffbox (scaphoid fracture suspicion), acute pallor, or persistent thumb numbness."),
    "back_pain": (["back", "lower back", "lumbago", "spine", "lumbar", "back spasm"], "Lumbar Paraspinal Strain & Mechanical Lumbago", "Musculoskeletal", "Does discomfort radiate past the knee down the leg, or cause numbness in the groin/saddle area?", "Avoid bed rest >24h; maintain gentle walking, apply alternating warm compresses, and sleep with a knee pillow.", "Cauda Equina flags: loss of bowel/bladder control, saddle numbness, or sudden progressive lower limb weakness."),
    "neck_stiffness": (["stiff neck", "neck pain", "cervical", "wry neck", "torticollis"], "Cervical Muscular Spasm / Acute Torticollis", "Musculoskeletal", "Can you bring your chin down flush to touch your chest without excruciating pain or involuntary knee flexion?", "Apply moist heat compresses to paraspinal muscles, perform gentle rotations, and use cervical support.", "CRITICAL: Severe nuchal rigidity accompanied by sudden high fever, photophobia, or purple rash (Meningitis)."),
    "fever": (["fever", "temperature", "chills", "febrile", "pyrexia", "hot"], "Systemic Febrile Syndrome", "Infectious/Systemic", "What is the peak core temperature recorded, and how many continuous hours has it persisted?", "Maintain oral hydration with electrolyte fluids (35 mL/kg/day target), rest in a 21°C ventilated space, wear light cotton.", "Core temperature >103°F (39.4°C), altered consciousness, stiff neck, petechiae, or continuous vomiting."),
    "sore_throat": (["throat", "pharyngitis", "tonsil", "swallowing", "swallow"], "Acute Pharyngitis & Tonsillitis", "Respiratory/ENT", "Are you able to swallow liquids comfortably, and are there visible tonsillar white exudates?", "Gargle with warm saline (1/2 tsp salt in 250ml warm water) 3 times daily, drink warm broths, rest voice.", "Inability to swallow saliva (pooling), trismus (can't open mouth fully), stridor, or asymmetrical tonsillar swelling."),
    "cough": (["cough", "coughing", "phlegm", "mucus", "bronchitis"], "Acute Bronchitis & Respiratory Irritation", "Respiratory", "Is the cough dry and hacking or productive with discolored, thick, or purulent sputum?", "Perform warm steam inhalation for 10-15 mins, sip warm fluids with honey, and maintain indoor humidity.", "Hemoptysis (coughing blood), respiratory rate >24/min, sharp pleuritic chest pain on inhalation, or dyspnea."),
    "cold": (["cold", "runny nose", "congestion", "sneezing", "blocked nose", "sinus"], "Viral Rhinosinusitis (Common Cold)", "Respiratory/ENT", "Is nasal drainage watery or thickened, and have symptoms persisted beyond 10 days without relief?", "Administer isotonic saline nasal irrigation, elevate head 30 degrees during sleep, and hydrate well.", "Periorbital eye swelling, severe unilateral facial pain with secondary fever spike, or stiff neck."),
    "shortness_of_breath": (["shortness of breath", "breathless", "dyspnea", "wheezing", "gasping", "breath", "breathe"], "Acute Dyspnea & Reactive Airway Exacerbation", "Cardiopulmonary", "Did breathlessness commence acutely, and do you perceive end-expiratory whistling or wheezing?", "Adopt High-Fowler's posture (sit upright leaning slightly forward), loosen chest clothing, practice pursed-lip breathing.", "CRITICAL: Central cyanosis (blue lips/fingers), intercostal retractions, inability to speak 2 words, or diaphoresis."),
    "chest_pain": (["chest pain", "chest pressure", "chest tightness", "angina", "sternum"], "Thoracic Discomfort / Cardiac & Musculoskeletal Triage", "Cardiovascular", "Does discomfort fluctuate with rib palpation and breathing, or present as deep substernal tightness?", "Immediately cease all physical activity, rest seated upright with back support, and avoid heavy oral intake.", "CRITICAL: Crushing retrosternal pressure radiating to jaw or left arm, cold diaphoresis, dyspnea, or nausea."),
    "stomach_pain": (["stomach", "abdominal", "belly", "cramp", "gastritis", "indigestion", "tummy", "gut"], "Acute Abdominal Discomfort & Dyspepsia", "Gastrointestinal", "Where is the pain focalized (epigastric, lower right quadrant), and does it correlate with meals?", "Withhold heavy/fatty foods for 4-6 hours, adopt the BRAT diet (bananas, rice, applesauce, toast), sip clear fluids.", "Surgical flags: localized right lower quadrant rebound tenderness (McBurney point), board-like rigidity, hematemesis."),
    "diarrhea": (["diarrhea", "diarrhoea", "loose stool", "watery stool", "loose motion"], "Acute Infectious/Osmotic Gastroenteritis", "Gastrointestinal", "What is the 24-hour frequency of loose evacuations, and is there visible blood or dark mucus?", "Immediately initiate Oral Rehydration Salts (ORS) solution sip-by-sip after each loose stool; avoid dairy and sugar.", "Grossly bloody or black melenic stool, postural syncope, absence of urination >8h, or high fever."),
    "vomiting": (["vomit", "vomiting", "nausea", "throwing up", "puke", "queasy"], "Acute Emesis & Gastric Intolerance", "Gastrointestinal", "Can you retain small sips of water without immediately vomiting, and what color is the vomitus?", "Total gastric rest (NPO) for 60 mins post-vomit, then introduce 1 teaspoon (5ml) clear electrolyte fluid every 10 mins.", "Coffee-ground emesis, bright hematemesis, unrelenting localized pain, or persistent neurological lethargy."),
    "acid_reflux": (["acid reflux", "heartburn", "gerd", "acidity", "sour burp"], "Gastroesophageal Reflux Disease (GERD)", "Gastrointestinal", "Does burning intensify during supine reclining, and do you experience sour fluid regurgitation?", "Elevate bed head 15 cm, remain upright 3 hours after meals, avoid late heavy meals, chocolate, and caffeine.", "Progressive dysphagia (food feeling stuck behind sternum), odynophagia, unexplained weight loss, or vomiting."),
    "headache": (["headache", "head ache", "migraine", "temple pain", "forehead pain"], "Cephalalgia / Tension-Type & Migraine Syndrome", "Neurological", "Is discomfort a bilateral compressive band or unilateral pulsatile throbbing with light sensitivity?", "Retire into a sound-attenuated, darkened room, drink 500-750 mL fluid immediately, apply cold temporal compress.", "Thunderclap onset (peak in <60 seconds), focal motor deficits, neck stiffness with pyrexia, or post-trauma."),
    "dizziness": (["dizziness", "dizzy", "vertigo", "spinning", "lightheaded", "unsteady"], "Vestibular Dysfunction & Orthostatic Lightheadedness", "Neurological", "Do you perceive rotational spinning when turning your head, or lightheaded faintness upon standing?", "Sit or lie down flat immediately upon onset to prevent mechanical falls; change postures slowly in 60-second steps.", "HINTS red flags: new speech slurring, acute limb ataxia (cannot stand unaided), double vision, or sudden hearing drop."),
    "skin_rash": (["rash", "hives", "itching", "itchy", "urticaria", "red spots", "welts", "eczema"], "Acute Urticaria & Contact Dermatitis", "Dermatology", "Are lesions raised, blanching under pressure, or rapidly expanding across body surfaces?", "Wash gently with cool sterile water and mild non-soap syndet, apply cold damp compresses, avoid scratch friction.", "ANAPHYLAXIS: Concurrent angioedema (swelling of lips, tongue, or throat), wheezing, stridor, or syncope."),
    "burn": (["burn", "scald", "heat burn", "sunburn", "burned"], "Superficial / Partial-Thickness Thermal Injury", "Dermatology", "Are there intact or ruptured fluid blisters, and does the area exceed the size of your palm?", "Irrigate immediately under cool running tap water for 20 continuous minutes; avoid ice, butter, or toothpaste.", "Burns covering face, hands, major joints, or genitalia; circumferential burns; or white painless leathery eschar."),
    "fatigue": (["fatigue", "tiredness", "exhaustion", "weakness", "lethargy", "drowsy"], "Systemic Asthenia & Post-Viral Fatigue", "Systemic", "Has this fatigue persisted beyond two weeks, and does it remain unrefreshed by 8 hours of sleep?", "Practice energy budgeting, ensure balanced complex carbohydrates and protein intake, drink 2L water daily.", "Sudden focal limb weakness, exertional syncope, unexplained weight loss, or heavy nocturnal drenching sweats."),
    "eye_irritation": (["eye", "conjunctivitis", "pink eye", "eye redness", "watery eye"], "Acute Conjunctivitis & Ocular Irritation", "Ophthalmology", "Is there yellow/green discharge gluing lids shut upon waking, or predominantly watery itching?", "Apply cool sterile compresses over closed eyes, discontinue contact lenses immediately, practice hand hygiene.", "Marked reduction in visual acuity, severe deep ciliary eye pain, severe photophobia, or pupil asymmetry."),
    "ear_pain": (["ear pain", "ear ache", "earache", "clogged ear", "ear discharge"], "Otalgia / Otitis Media & Externa", "ENT", "Does pulling the earlobe or tragus elicit severe pain, or did this follow swimming or an upper respiratory cold?", "Keep auditory canal strictly dry, rest head elevated, apply a warm dry external compress over mastoid area.", "Purulent or hemorrhagic canal drainage, redness/swelling behind the earlobe (mastoiditis), or facial weakness."),
    "constipation": (["constipation", "hard stool", "bowel strain", "cant poop"], "Colonic Dysmotility & Constipation", "Gastrointestinal", "When was your last complete evacuation, and are you passing abdominal flatus (gas) normally?", "Increase dietary soluble fiber (psyllium, oats) to 25-30g daily, drink 2.5L water daily, and walk 20 mins daily.", "Obstipation (total inability to pass both stool and gas), severe distension, continuous vomiting, or rectal bleeding."),
    "heat_exhaustion": (["heat exhaustion", "heat stroke", "sunstroke", "overheating"], "Thermoregulatory Strain & Heat Exhaustion", "Environmental", "Are you sweating profusely, or has perspiration ceased while your skin feels dry and burning hot?", "Move immediately to an air-conditioned room, apply cold damp towels to neck/axillae/groin, sip chilled water.", "HEAT STROKE: Anhidrosis (no sweating), core temp >104°F (40°C), confusion, ataxia, seizures, or loss of consciousness."),
    "mouth_ulcer": (["mouth ulcer", "canker sore", "tongue sore", "lip ulcer"], "Minor Aphthous Stomatitis", "Oral/Mucosal", "Is the lesion a solitary shallow round crater with an erythematous halo inside the mouth?", "Rinse with warm saline (1/2 tsp salt in 200ml warm water) 4 times daily, avoid spicy/acidic foods, use soft brush.", "Ulcers persisting continuously beyond 14 days, recurrent extensive clusters, or concurrent genital sores.")
}

# 1. Automatic greeting loads on the very first screen
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "### 🩺 MedAssist AI - Clinical Assistant\n"
            "Hello! I am your clinical triage assistant. I analyze physiological symptoms, "
            "provide evidence-based supportive care protocols, and screen for critical emergency red flags.\n\n"
            "👉 **How can I assist you today?** Please describe what bodily discomfort, trauma, or symptoms you are experiencing (e.g., ankle sprain, fever, cough, chest pressure, headache, or stomach ache)."
        ),
        "audio": True
    }]
if "active_symptoms" not in st.session_state:
    st.session_state.active_symptoms = []
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0

def detect_clinical_keys(text):
    text_clean = text.lower()
    matched = []
    for key, data in DB.items():
        all_terms = [key.replace("_", " ")] + data[0]
        for term in all_terms:
            if re.search(r'(?:\b|\W)' + re.escape(term) + r'(?:\b|\W)', text_clean):
                if key not in matched:
                    matched.append(key)
                break
    return matched

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

# Render existing chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("audio"):
            play_audio(msg["content"])

user_input = st.chat_input("Describe your symptoms or answer the doctor's questions...")

if user_input:
    st.session_state.turn_count += 1
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input, "audio": False})

    detected = detect_clinical_keys(user_input)
    for k in detected:
        if k not in st.session_state.active_symptoms:
            st.session_state.active_symptoms.append(k)

    active = st.session_state.active_symptoms

    with st.chat_message("assistant"):
        # Turn 1: Immediate recognition of initial symptom + targeted clinical inquiry
        if st.session_state.turn_count == 1:
            if active:
                p = active[0]
                cond = DB[p]
                reply = (
                    f"### Clinical Assessment Registered: {cond[1]}\n"
                    f"*Domain:* **{cond[2]}**\n\n"
                    f"• **Initial Observation:** I have recorded your presentation regarding **{cond[1]}**.\n\n"
                    f"👉 **Focused Clinical Inquiry:** {cond[3]}\n\n"
                    f"*Please reply with your specifics so I can calibrate supportive care and screen for escalation thresholds.*"
                )
            else:
                reply = "Could you specify your bodily symptoms in more detail (such as ankle pain, fever, chest tightness, sore throat, severe headache, or stomach cramps) so I can assist your triage?"
        # Turn 2+: Comprehensive synthesis, supportive regimen, and safety red flags
        else:
            if active:
                p = active[0]
                cond = DB[p]
                all_titles = " • ".join([DB[k][1] for k in active])
                reply = (
                    f"### Clinical Triage Synthesis: {cond[1]}\n"
                    f"**Cumulative Active Context:** {all_titles}\n\n"
                    f"• **Evidence-Based Supportive Care Regimen:**\n"
                    f"  {cond[4]}\n\n"
                    f"• ⚠️ **Critical Red-Flag Escalation Thresholds:**\n"
                    f"  {cond[5]}\n\n"
                    f"*Reminder: Educational triage tool only. If symptoms intensify, functional weight-bearing is compromised, or red flags manifest, consult a certified physician immediately.*"
                )
            else:
                reply = "Thank you for the update. Could you state where the primary discomfort is located or if there are other accompanying symptoms so that I may direct clinical guidance appropriately?"

        st.markdown(reply)
        play_audio(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply, "audio": True})
    
