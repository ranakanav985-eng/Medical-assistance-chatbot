import streamlit as st
import streamlit.components.v1 as components
import re

st.set_page_config(page_title="MedAssist AI", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI - Clinical Assistant")
st.caption("⚠️ **Educational Demonstration Only.** This assistant provides general clinical triage and supportive advice. It does not provide medical diagnoses or prescriptions. For severe symptoms, consult a certified physician immediately.")

# 24 Comprehensive Clinical Categories
DB = {
    "fever": (["temperature", "chills", "febrile", "pyrexia"], "systemic immune response, acute viral illness (influenza), or localized bacterial infection.", "How high has your temperature reached, and have you noticed rigors or sweating?", "Maintain oral hydration with electrolyte solutions, rest in a ventilated space, and wear breathable clothing.", "Temperature exceeding 103°F (39.4°C), stiff neck, altered mental status, or non-blanching purpuric rash."),
    "sore throat": (["throat", "pharyngitis", "tonsil", "swallowing pain"], "acute pharyngitis, viral tonsillitis, streptococcal infection, or acid laryngitis.", "Are you able to swallow liquids comfortably, and are there visible tonsillar exudates?", "Gargle with warm saline (1/2 tsp salt in 250ml warm water) 3 times daily, consume soft foods, and stay hydrated.", "Inability to swallow saliva, trismus (inability to open mouth), stridor, or unilateral peritonsillar swelling."),
    "cough": (["coughing", "phlegm", "mucus", "bronchitis"], "acute viral tracheobronchitis, reactive airway disease, post-nasal drip, or environmental irritation.", "Is the cough non-productive (dry) or productive with purulent or discolored sputum?", "Perform warm steam inhalation, consume warm liquids with honey, and avoid exposure to smoke or cold air.", "Hemoptysis (coughing blood), respiratory distress, or localized pleuritic chest pain on inspiration."),
    "cold": (["runny nose", "congestion", "sneezing", "sinus", "blocked nose"], "acute viral rhinosinusitis (rhinovirus/adenovirus) or seasonal allergic rhinitis.", "Is nasal drainage watery or thickened, and do you experience acute periorbital facial pain?", "Utilize isotonic saline nasal irrigation, ensure restful recovery, and elevate head during sleep.", "Marked facial edema, periorbital swelling, severe cephalalgia, or persistent spikes in fever."),
    "headache": (["head ache", "migraine", "cephalea", "temple pain"], "tension cephalalgia, cervicogenic strain, dehydration, or acute migraine episode.", "Does this feel like a bilateral band-like compression or unilateral throbbing with photophobia?", "Rest in a quiet, dark environment, hydrate with 500-750 mL fluid, and place a cool compress over temples.", "Sudden onset 'thunderclap' cephalalgia, focal neurological deficits, neck stiffness, or post-head injury."),
    "stomach pain": (["abdominal", "belly", "gastritis", "indigestion", "cramps"], "functional dyspepsia, acute gastroenteritis, gastroesophageal irritation, or mesenteric spasm.", "Where is the pain focalized (epigastric, lower quadrants), and does it correlate with oral intake?", "Follow the BRAT diet (bananas, rice, applesauce, toast), avoid high-fat meals, and take modest fluid sips.", "Acute localized right lower quadrant pain, involuntary muscular guarding, or hematemesis/melena."),
    "diarrhea": (["loose stool", "loose motions", "watery stool", "dysentery"], "acute viral or bacterial gastroenteritis, secretory enteritis, or osmotic dietary distress.", "How many loose bowel episodes have occurred in the last 24 hours, and is there visible blood?", "Initiate immediate Oral Rehydration Salts (ORS) regimen, avoid dairy and refined sugars, and rest.", "Hematochezia (bloody stool), postural syncope, signs of hypovolemia, or cessation of urination."),
    "vomiting": (["nausea", "throwing up", "emesis", "queasy"], "acute infectious gastroenteritis, foodborne illness, gastroparesis, or labyrinthine disturbance.", "Can you tolerate small teaspoon sips of water without immediately vomiting?", "Withhold solid foods; administer small sips of clear fluids every 10-15 minutes after 1 hour of gastric rest.", "Vomiting frank blood or dark ground material, unremitting abdominal pain, or lethargy."),
    "skin rash": (["rash", "itching", "hives", "urticaria", "eczema", "welts"], "allergic contact dermatitis, acute urticaria, viral exanthem, or cutaneous sensitivity.", "Is the lesion pruritic (itchy), blistering, or expanding rapidly over body surfaces?", "Cleanse with cool water and neutral syndet soap, apply cold damp compresses, and avoid friction.", "Concurrent lip, tongue, or periorbital angioedema, breathing compromise (Anaphylaxis), or targetoid lesions."),
    "shortness of breath": (["breathless", "dyspnea", "wheezing", "gasping", "breath"], "bronchospasm/asthma exacerbation, acute bronchitis, pneumonia, or hyperventilation.", "Did breathlessness commence acutely, and do you hear expiratory wheezing sounds?", "Maintain a high-Fowler's (upright) posture, loosen tight clothing, and practice pursed-lip breathing.", "Inability to speak complete phrases, central cyanosis (blue lips/fingers), or accessory muscle retractions."),
    "chest pain": (["chest pressure", "chest tightness", "angina"], "costochondritis, intercostal musculoskeletal strain, esophageal reflux, or cardiac compromise.", "Does the discomfort fluctuate with palpation and respiration, or feel like substernal pressure?", "Discontinue physical exertion immediately, remain seated upright, and avoid sudden movements.", "CRITICAL: Crushing retrosternal pressure radiating to jaw or left arm, diaphoresis, and profound dyspnea."),
    "joint pain": (["arthritis", "knee pain", "swollen joint", "sprain", "ankle pain"], "acute ligamentous sprain, reactive post-infectious arthralgia, tendonitis, or joint synovitis.", "Was there recent mechanical trauma, and is the joint erythematous, warm, or swollen?", "Implement R.I.C.E.: Rest joint, apply protected Ice for 15 mins, light Compression wrap, and Elevate.", "Total inability to bear weight, gross anatomical joint deformity, or acute septic erythema with fever."),
    "back pain": (["lower back", "lumbago", "spine ache", "lumbar strain"], "paraspinal muscle strain, lumbar postural dysfunction, or acute ligamentous irritation.", "Is discomfort localized to the lumbar region or radiating past the knee down the leg?", "Avoid static bed rest; engage in light ambulation, maintain lumbar support, and apply heat compresses.", "Bowel or bladder dysfunction, saddle area paresthesia (groin numbness), or acute lower limb weakness."),
    "eye irritation": (["conjunctivitis", "pink eye", "eye redness", "watery eye"], "viral or bacterial conjunctivitis, allergic keratoconjunctivitis, or dry eye syndrome.", "Is there yellow/green mucopurulent discharge gluing lids shut, or predominantly watery itching?", "Apply cool sterile compresses over closed eyes, discontinue contact lenses, and maintain hand hygiene.", "Marked visual acuity loss, severe deep ocular pain, photophobia, or corneal opacification."),
    "ear pain": (["earache", "clogged ear", "ear discharge", "otitis"], "otitis media, otitis externa, Eustachian tube dysfunction, or referred dental/pharyngeal pain.", "Is there active canal discharge, or did discomfort follow swimming or an upper respiratory illness?", "Keep external auditory canal dry, rest head elevated, and apply a warm dry external compress.", "Post-auricular mastoid swelling/erythema, purulent bloody discharge, facial asymmetry, or vertigo."),
    "fatigue": (["tiredness", "exhaustion", "lethargy", "weakness"], "post-infectious asthenia, physiological sleep deficit, hypovolemia, or metabolic depletion.", "How many continuous days has this fatigue persisted, and is nighttime sleep restorative?", "Establish circadian sleep consistency (7-8 hours), ensure 2L fluid intake daily, and optimize nutrition.", "Profound syncope (fainting), acute focal motor weakness, chest pain, or marked exertional dyspnea."),
    "acid reflux": (["heartburn", "gerd", "acidity", "sour burp", "indigestion"], "gastroesophageal reflux disease, lower esophageal transient relaxations, or dietary irritation.", "Do you experience retrosternal burning after meals, particularly when reclining flat?", "Elevate head of bed by 15 cm, consume smaller frequent meals, and avoid eating 3 hours prior to sleep.", "Progressive dysphagia (food sticking in esophagus), involuntary weight loss, or persistent hematemesis."),
    "dizziness": (["vertigo", "lightheaded", "spinning", "unsteady"], "benign paroxysmal positional vertigo, vestibular neuritis, or orthostatic hypotension.", "Does the room feel as though it is spinning, or do you feel lightheaded upon standing quickly?", "Avoid sudden postural shifts, sit immediately when feeling unsteady, and maintain adequate hydration.", "Concurrent diplopia (double vision), dysarthria (slurred speech), limb ataxia, or sudden hearing deficit."),
    "constipation": (["hard stool", "bowel strain", "infrequent stool"], "reduced dietary soluble fiber, inadequate fluid intake, or sluggish colonic transit.", "When was your last complete evacuation, and do you experience significant rectal straining?", "Increase dietary soluble fiber (psyllium, oats, prunes), drink 2.5L water daily, and engage in daily walks.", "Inability to pass flatus (gas), severe localized abdominal distension, vomiting, or rectal bleeding."),
    "neck stiffness": (["stiff neck", "cervical strain", "wry neck", "torticollis"], "cervical muscular spasm, poor postural alignment during sleep, or acute meningeal irritation.", "Can you bring your chin down to touch your chest without excruciating pain or resistance?", "Apply a warm compress to paraspinal muscles, perform gentle range-of-motion rotations, avoid strain.", "CRITICAL: Inability to touch chin to chest (nuchal rigidity) accompanied by high fever and photophobia."),
    "burn": (["minor burn", "scald", "heat burn", "sunburn"], "first-degree thermal injury, superficial partial-thickness scald, or solar ultraviolet erythema.", "Are there intact or ruptured fluid blisters, and what is the approximate surface area affected?", "Cool immediately under gentle running tap water for 10-20 minutes; avoid ice, butter, or harsh agents.", "Blistering on face, hands, major joints, or genitalia; circumferential burns; or painless leathery skin."),
    "insomnia": (["sleeplessness", "cant sleep", "wakefulness"], "sleep onset association disorder, circadian disruption, anxiety, or excessive caffeine consumption.", "Is your difficulty falling asleep, staying asleep, or waking prematurely without unrefreshing rest?", "Practice strict sleep hygiene: keep bedroom dark and cool (18°C), avoid screens 60 mins prior to sleep.", "Severe daytime cognitive impairment, microsleeps during operation of vehicles, or profound depression."),
    "heat exhaustion": (["heat stroke", "sunstroke", "overheating", "excessive heat"], "hyperthermia, dehydration-induced thermoregulatory strain, or prolonged exertion under ambient heat.", "Are you sweating profusely or has sweating ceased while skin remains uncomfortably hot?", "Move immediately to an air-conditioned or shaded room, apply cold damp cloths to neck/groin, and sip cold water.", "CRITICAL: Anhidrosis (lack of sweating), confusion, temperature above 104°F (40°C), seizures (Heat Stroke)."),
    "mouth ulcer": (["canker sore", "aphthous ulcer", "tongue sore", "lip ulcer"], "minor aphthous stomatitis, mechanical cheek bite, or minor oral mucosal irritation.", "Is the ulcer a discreet yellowish crater with an erythematous halo inside the mouth?", "Perform warm saline mouth rinses 3-4 times daily, avoid acidic/spicy foods, and use a soft-bristled toothbrush.", "Ulcers persisting longer than 14 days, recurrent large clusters, or accompanied by genital sores.")
}

if "messages" not in st.session_state: st.session_state.messages = []
if "recognized" not in st.session_state: st.session_state.recognized = []

def detect(text):
    found = []
    t = text.lower()
    for name, data in DB.items():
        aliases = [name] + data[0]
        if any(re.search(r'\b' + re.escape(a) + r'\b', t) for a in aliases):
            found.append(name)
    return found

def play_audio(script_text):
    clean = re.sub(r'[*_#`⚠️👉🔊•]', '', script_text).replace('"', '').replace("'", "")
    clean = " ".join(clean.split())
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
        font-weight: bold;
        cursor: pointer;
        font-size: 13px;
        margin-top: 6px;
    ">🔊 Listen to Doctor's Guidance</button>
    """
    components.html(html, height=45)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("audio"):
            play_audio(msg["content"])

user_input = st.chat_input("State your health symptoms or answer the doctor's questions...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input, "audio": False})

    new_symptoms = detect(user_input)
    for s in new_symptoms:
        if s not in st.session_state.recognized:
            st.session_state.recognized.append(s)

    active = st.session_state.recognized

    with st.chat_message("assistant"):
        if len(st.session_state.messages) <= 2:
            if active:
                p = active[0]
                reply = f"Hello, I am MedAssist AI. I note your report of **{p.title()}**.\n\n👉 **Clinical Inquiry:** {DB[p][2]}"
            else:
                reply = "Hello, I am MedAssist AI. Please specify your symptoms in detail (such as fever, sore throat, cough, stomach pain, rash, headache, or joint pain) so I can assist your triage."
        else:
            if active:
                p = active[0]
                summary = ", ".join([s.title() for s in active])
                reply = (
                    f"### Clinical Impression: {p.title()}\n"
                    f"*Active Triage Context:* **{summary}**\n\n"
                    f"• **Physiological Correlation:** These presentation markers are consistent with {DB[p][1]}\n\n"
                    f"• **Evidence-Based Supportive Care:** {DB[p][3]}\n\n"
                    f"• ⚠️ **Red-Flag Escalation Thresholds:** Seek prompt medical evaluation if you observe: {DB[p][4]}\n\n"
                    f"*Reminder: Educational triage tool only. If clinical symptoms intensify, please consult a certified doctor immediately.*"
                )
            else:
                reply = "Thank you for the update. Could you state your primary bodily symptom or discomfort so that I may direct clinical guidance appropriately?"

        st.markdown(reply)
        play_audio(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply, "audio": True})
