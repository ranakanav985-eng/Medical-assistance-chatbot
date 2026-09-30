import streamlit as st
import re

# Page Configuration
st.set_page_config(page_title="MedAssist AI", page_icon="🩺", layout="centered")

st.title("🩺 MedAssist AI")
st.subheader("Clinical Information & Triage Assistant")
st.caption(
    "⚠️ **Disclaimer:** Educational demonstration only. This system provides "
    "evidence-informed symptom analysis and supportive self-care guidance. It does "
    "not provide a formal medical diagnosis. Always consult a qualified physician for treatment."
)

# 16 Common Disease Categories
CLINICAL_DATABASE = {
    "fever": {
        "alias": ["fever", "temperature", "chills", "febrile", "hot body", "pyrexia"],
        "follow_up": "How high has your temperature reached on a thermometer, and how many days has it persisted?",
        "causes": "common viral infections (like influenza or adenovirus), bacterial infections, or acute systemic inflammation.",
        "care": "Drink 2–3 liters of water or oral rehydration fluids daily, rest in a cool, ventilated room, and wear lightweight cotton clothing.",
        "red_flag": "Temperature above 103°F (39.4°C), stiff neck, confusion, inability to stay awake, or a dark purple rash.",
        "flag_phrase": "Because your elevated temperature has persisted"
    },
    "sore throat": {
        "alias": ["sore throat", "throat", "pharyngitis", "tonsil", "swallowing pain", "scratchy throat"],
        "follow_up": "Are you able to swallow liquids comfortably, and do you see white patches on your tonsils or have ear pain?",
        "causes": "viral pharyngitis, acute tonsillitis, streptococcal infection (strep throat), or acid reflux irritation.",
        "care": "Gargle with warm salt water (1/2 tsp salt in warm water) 3 times daily, drink warm herbal broths, and avoid rough or spicy foods.",
        "red_flag": "Inability to swallow your own saliva, inability to open the mouth fully (trismus), drooling, or labored breathing.",
        "flag_phrase": "Because your throat irritation and pain are active"
    },
    "cough": {
        "alias": ["cough", "coughing", "phlegm", "mucus", "bronchitis", "hack"],
        "follow_up": "Is your cough completely dry, or are you bringing up thick yellow, green, or clear mucus?",
        "causes": "viral bronchitis, upper respiratory tract irritation, seasonal allergic cough, post-nasal drip, or asthma.",
        "care": "Inhale warm steam for 10 minutes, drink warm water with honey, use a bedroom humidifier, and avoid secondhand smoke.",
        "red_flag": "Coughing up blood or rust-colored phlegm, sharp localized chest pain when inhaling, or wheezing.",
        "flag_phrase": "Because your cough is persistent"
    },
    "cold": {
        "alias": ["cold", "runny nose", "congestion", "sneezing", "blocked nose", "nasal drip", "sinus"],
        "follow_up": "Is your nasal discharge clear and watery or thick and discolored, and do you feel intense facial pressure?",
        "causes": "rhinovirus (the common cold), allergic rhinitis, or acute viral sinusitis.",
        "care": "Use gentle isotonic saline nasal sprays, practice warm steam inhalation, elevate your head during sleep, and hydrate well.",
        "red_flag": "Swelling or severe tenderness around the eyes and forehead, high spiking fever, or symptoms worsening after 10 days.",
        "flag_phrase": "Because upper respiratory congestion is present"
    },
    "headache": {
        "alias": ["headache", "head ache", "migraine", "head pain", "temple pain"],
        "follow_up": "Does it feel like a tight band pressing around your head, or a pulsating, throbbing pain on one side?",
        "causes": "tension headache, dehydration, digital screen eye strain, irregular sleep, or migraine.",
        "care": "Rest in a quiet, dark room, drink at least 500 mL of water immediately, avoid bright screens, and apply a cool forehead compress.",
        "red_flag": "Sudden catastrophic 'thunderclap' onset, headache following a head injury, sudden speech slurring, or weakness.",
        "flag_phrase": "Because your headache has lasted through the day"
    },
    "stomach pain": {
        "alias": ["stomach", "abdominal", "belly", "cramp", "gastritis", "indigestion", "tummy", "gut"],
        "follow_up": "Is the discomfort in your upper abdomen, lower abdomen, or all over, and does it worsen before or after meals?",
        "causes": "indigestion (dyspepsia), acute gastritis, dietary irritation, gas bloating, or mild gastroenteritis.",
        "care": "Follow the BRAT diet (bananas, white rice, applesauce, toast), avoid milk, fatty, or spicy meals, and take slow sips of water.",
        "red_flag": "Intense localized lower-right abdominal pain, rigid or stone-hard abdomen, persistent vomiting, or black/bloody stool.",
        "flag_phrase": "Because your abdominal discomfort is persistent"
    },
    "diarrhea": {
        "alias": ["diarrhea", "diarrhoea", "loose stool", "loose motion", "watery stool"],
        "follow_up": "How many loose episodes have occurred today, and have you noticed any blood, mucus, or severe cramping?",
        "causes": "acute infectious gastroenteritis (stomach bug), foodborne illness, dietary sensitivity, or waterborne pathogens.",
        "care": "Drink Oral Rehydration Salt (ORS) solution after every loose stool, avoid dairy, caffeine, and greasy meals, and rest.",
        "red_flag": "Stool containing visible red blood or dark tarry matter, inability to retain fluids for 12 hours, dizziness, or dry mouth/eyes.",
        "flag_phrase": "Because frequent loose stools risk dehydration"
    },
    "vomiting": {
        "alias": ["vomit", "vomiting", "nausea", "throwing up", "puke", "queasy"],
        "follow_up": "Are you able to keep small sips of water down without vomiting immediately, and how long has it lasted?",
        "causes": "acute viral gastroenteritis, food poisoning, gastritis, motion sickness, or inner ear vertigo.",
        "care": "Rest your stomach for 1 hour without food or drink, then introduce 1 teaspoon of clear electrolyte fluids every 5 minutes.",
        "red_flag": "Vomiting bright blood or dark coffee-ground material, severe unrelenting stomach pain, or profound dizziness/fainting.",
        "flag_phrase": "Because persistent vomiting prevents fluid intake"
    },
    "skin rash": {
        "alias": ["rash", "itching", "itchy", "hives", "red spots", "skin allergy", "welts", "eczema"],
        "follow_up": "Is the rash raised, fluid-filled, spreading rapidly, or accompanied by severe burning or itching?",
        "causes": "contact dermatitis, urticaria (allergic hives), viral exanthem, heat rash, or atopic eczema flare.",
        "care": "Wash the area gently with lukewarm water and mild fragrance-free soap, apply a cool damp cloth, and avoid scratching.",
        "red_flag": "Hives that spread within minutes alongside swelling of the lips, tongue, or eyelids, or difficulty breathing (Anaphylaxis).",
        "flag_phrase": "Because your skin rash is actively spreading"
    },
    "shortness of breath": {
        "alias": ["breath", "breathing", "breathless", "dyspnea", "wheezing", "gasping"],
        "follow_up": "Did this breathlessness start suddenly, and do you feel wheezing or tightness in your chest?",
        "causes": "bronchial asthma flare, acute bronchitis, hyperventilation from anxiety, or allergic bronchospasm.",
        "care": "Sit upright immediately, loosen tight collars or waistbands, take slow pursed-lip breaths, and use a rescue inhaler if prescribed.",
        "red_flag": "CRITICAL EMERGENCY: Inability to speak more than a couple of words without pausing, blue/gray lips or nails, or gasping.",
        "flag_phrase": "Because breathing difficulty requires immediate clinical caution"
    },
    "chest pain": {
        "alias": ["chest pain", "chest pressure", "chest tightness", "angina"],
        "follow_up": "Does the discomfort change when you take a deep breath or push on your ribs, or does it feel like deep heaviness?",
        "causes": "costochondritis (chest wall inflammation), intercostal muscle strain, acid reflux (GERD), or cardiovascular issues.",
        "care": "Cease all physical exertion instantly, rest in a supportive seated position, and loosen clothing around the chest.",
        "red_flag": "CRITICAL EMERGENCY: Crushing pressure radiating to the left arm, neck, or jaw, combined with cold sweat and nausea. Call an ambulance immediately.",
        "flag_phrase": "Because acute chest discomfort is a potential emergency"
    },
    "joint pain": {
        "alias": ["joint pain", "knee pain", "ankle pain", "wrist pain", "arthritis", "sprain", "swollen joint"],
        "follow_up": "Did this follow a twist or fall, and is the joint visibly red, warm, or swollen to the touch?",
        "causes": "ligament sprain, tendonitis from overuse, reactive post-viral arthritis, or joint strain.",
        "care": "Follow the R.I.C.E. protocol: Rest the joint, apply Ice wrapped in a towel for 15 minutes, wrap with light Compression, and Elevate.",
        "red_flag": "Complete inability to bear any weight on the limb, visible joint deformity, or an intensely red, feverish, hot joint.",
        "flag_phrase": "Because joint inflammation and mobility loss are present"
    },
    "back pain": {
        "alias": ["back pain", "lower back", "spine pain", "lumbago", "back ache"],
        "follow_up": "Is the ache localized to your lower back, or does sharp shooting pain travel down your leg into your foot?",
        "causes": "lumbar muscle strain from lifting or poor sitting posture, ligament sprain, or disc irritation.",
        "care": "Avoid prolonged bed rest; engage in gentle walking, apply a warm compress for 15 minutes, and maintain good lumbar support.",
        "red_flag": "Numbness in the groin or saddle area, loss of bowel or bladder control, or progressive weakness in both legs.",
        "flag_phrase": "Because back stiffness and pain are ongoing"
    },
    "eye irritation": {
        "alias": ["eye", "conjunctivitis", "pink eye", "eye redness", "watery eyes", "eye discharge"],
        "follow_up": "Is there yellow or green crusting that sticks your eyelids together in the morning, or is it mostly watery and itchy?",
        "causes": "viral or bacterial conjunctivitis (pink eye), seasonal ocular allergies, or screen-related dry eye.",
        "care": "Apply a cool, damp cotton pad over closed eyelids, avoid rubbing, wash hands frequently, and avoid wearing contact lenses.",
        "red_flag": "Severe deep eye pain, sudden changes in vision or blurriness, or extreme sensitivity to ordinary indoor light.",
        "flag_phrase": "Because eye redness and irritation are present"
    },
    "ear pain": {
        "alias": ["ear pain", "ear ache", "earache", "clogged ear", "ear discharge"],
        "follow_up": "Do you feel fluid discharge from the ear canal, or did this start right after swimming or having a cold?",
        "causes": "otitis media (middle ear infection), otitis externa (swimmer's ear), or referred pain from a sore throat.",
        "care": "Keep the ear completely dry, apply a warm dry compress outside the outer ear, and rest with your head elevated.",
        "red_flag": "Yellow or bloody fluid draining from the ear, swelling or redness behind the earlobe, or dizziness and loss of balance.",
        "flag_phrase": "Because ear pain can indicate localized infection"
    },
    "fatigue": {
        "alias": ["fatigue", "tiredness", "exhaustion", "weakness", "lethargic", "drowsy"],
        "follow_up": "How long have you felt this exhausted, and are you sleeping at least 7 to 8 hours each night?",
        "causes": "post-viral recovery phase, sleep deprivation, nutritional deficiencies (iron or vitamin D), or dehydration.",
        "care": "Maintain consistent sleep timings, drink at least 2 liters of water daily, consume whole fruits and proteins, and take short walks.",
        "red_flag": "Sudden profound muscle weakness, unexplained fainting (syncope), chest tightness, or extreme shortness of breath.",
        "flag_phrase": "Because unrefreshing fatigue is ongoing"
    }
}

# State Management
if "messages" not in st.session_state:
    st.session_state.messages = []
if "recognized_symptoms" not in st.session_state:
    st.session_state.recognized_symptoms = []
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0

def detect_symptoms(text):
    found = []
    text_clean = text.lower()
    for name, data in CLINICAL_DATABASE.items():
        if any(re.search(r'\b' + re.escape(alias) + r'\b', text_clean) for alias in data["alias"]):
            found.append(name)
    return found

# Render Chat History
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
        # Turn 1: Empathetic clarification based on detected symptoms
        if st.session_state.turn_count == 1:
            if "fever" in all_symptoms and "sore throat" in all_symptoms:
                bot_reply = "How high has your temperature been? Do you also have cough, difficulty breathing, or body pain?"
            elif all_symptoms:
                primary = all_symptoms[0]
                bot_reply = f"I understand. {CLINICAL_DATABASE[primary]['follow_up']}"
            else:
                bot_reply = (
                    "Hello! I am MedAssist AI. Could you describe what symptoms you are experiencing? "
                    "(For instance: fever, cough, stomach pain, headache, skin rash, or joint swelling?)"
                )
        
        # Turn 2 and beyond: Dynamic, clinically accurate guidance
        else:
            if all_symptoms:
                # Use the primary registered symptom for clinical relevance
                primary = all_symptoms[0]
                data = CLINICAL_DATABASE[primary]
                symptom_summary = ", ".join([s.title() for s in all_symptoms])

                bot_reply = (
                    f"These symptoms can occur with {data['causes']} I can provide general information, "
                    f"but I cannot diagnose you. {data['flag_phrase']}, consider consulting a healthcare "
                    f"professional, particularly if symptoms worsen.\n\n"
                    f"**Identified Context:** {symptom_summary}\n\n"
                    f"• **Recommended Self-Care:** {data['care']}\n\n"
                    f"• **Safety Escalation:** Seek urgent clinical evaluation if you observe: {data['red_flag']}"
                )
            else:
                bot_reply = (
                    "Thank you for the additional information. Could you specify what specific discomfort or symptoms you are experiencing?"
                )

        st.markdown(bot_reply)
        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
