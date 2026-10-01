import streamlit as st
import streamlit.components.v1 as components
import re

st.set_page_config(
    page_title="MedAssist AI - Clinical Assistant",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Modern Clinical Dashboard Styling
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stChatMessage { border-radius: 12px; margin-bottom: 10px; }
    .metric-card {
        background: white;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border-left: 4px solid #0E76A8;
        margin-bottom: 12px;
    }
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
        background-color: #e0f2fe;
        color: #0369a1;
    }
</style>
""", unsafe_allow_html=True)

# Comprehensive Multi-Domain Clinical Knowledge Base (35 Medical Conditions)
CLINICAL_KNOWLEDGE_BASE = {
    # 1. Musculoskeletal & Orthopedic
    "ankle_sprain": {
        "title": "Ankle Inversion / Eversion Sprain",
        "system": "Musculoskeletal",
        "keywords": ["twisted ankle", "ankle sprain", "rolled ankle", "ankle pain", "sprained ankle", "ankle injury", "twisted my ankle", "twisted foot"],
        "pathophysiology": "Acute mechanical stretching or microscopic tearing of lateral ankle ligaments (most frequently anterior talofibular and calcaneofibular ligaments) following forced inversion/plantarflexion.",
        "inquiry": "Did the trauma involve immediate localized edema, audible popping, or inability to take four independent steps immediately post-injury?",
        "care_protocol": [
            "Rest: Absolute avoidance of aggravating physical activity or forced weight-bearing.",
            "Ice: 15–20 minutes crushed ice application wrapped in damp linen every 3 hours (avoid direct thermal contact).",
            "Compression: Semi-rigid elastic bandage wrap from metatarsals up to mid-calf, ensuring distal peripheral capillary refill <2s.",
            "Elevation: Position limb above left atrial horizontal plane to facilitate lymphatic drainage."
        ],
        "red_flags": "Ottawa Ankle Rule positive (bony tenderness over posterior 6 cm of lateral/medial malleolus), neurovascular compromise, visible deformity, or total weight-bearing intolerance.",
        "urgency": "Moderate (Clinical Triage L4 / Urgent Care)"
    },
    "knee_pain": {
        "title": "Knee Arthralgia / Patellofemoral & Meniscal Strain",
        "system": "Musculoskeletal",
        "keywords": ["knee pain", "swollen knee", "twisted knee", "runner knee", "knee sprain", "knee injury", "patella", "meniscus"],
        "pathophysiology": "Joint effusion, intra-articular ligamentous strain (ACL/MCL), or localized inflammation of the patellar tendon/bursa secondary to rotational torque or excessive load.",
        "inquiry": "Did you experience joint locking, sudden mechanical instability ('giving way'), or localized anterior clicking during knee flexion?",
        "care_protocol": [
            "Implement mechanical unloading with crutches if ambulation induces antalgic limp.",
            "Ice application for 15 minutes twice daily to diminish secondary vascular congestion.",
            "Perform isometric quadriceps sets with knee extended, avoiding deep loaded squats."
        ],
        "red_flags": "Gross joint effusion appearing within 2 hours of injury, inability to reach full knee extension, or concurrent systemic pyrexia (septic arthritis suspicion).",
        "urgency": "Moderate"
    },
    "wrist_strain": {
        "title": "Acute Wrist / Forearm Ligamentous Distension",
        "system": "Musculoskeletal",
        "keywords": ["wrist pain", "sprained wrist", "twisted wrist", "carpal tunnel", "wrist sprain", "wrist swelling"],
        "pathophysiology": "Hyper-extension or hyper-flexion stress resulting in strain of the scapholunate ligament complex or carpal synovial irritation.",
        "inquiry": "Did injury follow a fall onto an outstretched hand (FOOSH), and is tenderness localized over the anatomical snuffbox?",
        "care_protocol": [
            "Splint wrist in neutral anatomical alignment with a wrist immobilizer.",
            "Apply cryotherapy packs for 12 minutes periodically across the dorsal wrist.",
            "Avoid pronation-supination mechanical strain or gripping motions."
        ],
        "red_flags": "Tenderness in anatomical snuffbox (scaphoid fracture suspicion), median nerve paresthesia (numbness in thumb/index), or acute pallor.",
        "urgency": "Moderate"
    },
    "lower_back_pain": {
        "title": "Lumbar Paraspinal Strain & Mechanical Lumbago",
        "system": "Musculoskeletal",
        "keywords": ["back pain", "lower back", "lumbago", "spine pain", "back spasm", "lumbar strain", "pulled back muscle"],
        "pathophysiology": "Micro-tearing of erector spinae musculature or acute facet joint micro-irritation provoked by improper lifting mechanics or postural fatigue.",
        "inquiry": "Does the discomfort radiate below the popliteal fossa (knee), and have you noticed tingling in the dermatomal distribution of L4-S1?",
        "care_protocol": [
            "Maintain moderate light ambulation; avoid prolonged uninterrupted bed rest >24 hours.",
            "Apply alternating heat packs (15 mins) to relieve involuntary paravertebral spasticity.",
            "Sleep in a lateral recumbent position with a pillow interposed between knees."
        ],
        "red_flags": "Cauda Equina Syndrome indicators: acute bilateral lower extremity weakness, progressive perineal/saddle anesthesia, urinary retention, or fecal incontinence.",
        "urgency": "Urgent if red flags present; otherwise Routine"
    },
    "neck_stiffness": {
        "title": "Cervical Muscular Spasm / Acute Torticollis",
        "system": "Musculoskeletal / Neurological",
        "keywords": ["stiff neck", "neck pain", "cervical strain", "wry neck", "torticollis", "neck spasm"],
        "pathophysiology": "Unilateral or bilateral contracture of sternocleidomastoid or trapezius fibers following poor ergonomic sleep positioning or prolonged static flexion.",
        "inquiry": "Can you touch your chin flush against your chest without eliciting excruciating pain or involuntary reflex knee flexion (Brudzinski sign)?",
        "care_protocol": [
            "Employ moist therapeutic heat compresses to cervical paraspinal zones.",
            "Perform passive range-of-motion rotational stretches within pain-free boundaries.",
            "Ensure a cervical ergonomic pillow that aligns the cervical-thoracic axis."
        ],
        "red_flags": "Nuchal rigidity accompanied by sudden high pyrexia, photophobia, confusion, or a non-blanching purpuric rash (Meningitis screening).",
        "urgency": "High/Emergency if fever/rigidity present"
    },

    # 2. Respiratory & Pulmonary
    "fever": {
        "title": "Febrile Syndrome / Systemic Pyrexia",
        "system": "Infectious / Systemic",
        "keywords": ["fever", "temperature", "febrile", "pyrexia", "hot body", "high temp", "chills", "rigors"],
        "pathophysiology": "Endogenous pyrogen release (IL-1, TNF-alpha) shifting the hypothalamic thermal setpoint upwards in response to viral or bacterial antigens.",
        "inquiry": "What is the peak core temperature recorded via oral/tympanic thermometer, and what is the exact chronological duration in hours/days?",
        "care_protocol": [
            "Maintain strict fluid replacement with water and oral electrolyte fluids (35 mL/kg/day target).",
            "Wear thin, moisture-wicking single-layer cotton apparel in a room maintained at 20–22°C.",
            "Implement lukewarm sponge baths if uncomfortable; avoid ice-cold hydrotherapy (prevents shivering thermogenesis)."
        ],
        "red_flags": "Core pyrexia >103°F (39.4°C) refractory to cooling, altered consciousness, nuchal rigidity, petechiae, or persistent vomiting.",
        "urgency": "High"
    },
    "sore_throat": {
        "title": "Acute Pharyngitis & Tonsillitis",
        "system": "Respiratory / ENT",
        "keywords": ["sore throat", "throat pain", "pharyngitis", "tonsil", "swallowing pain", "scratchy throat", "strep throat", "hurt to swallow"],
        "pathophysiology": "Erythematous mucosal inflammation of the posterior oropharynx secondary to viral pathogens (rhinovirus, adenovirus, EBV) or group A Streptococcus.",
        "inquiry": "Do you present with tonsillar exudates, tender anterior cervical lymphadenopathy, and absence of cough (Centor criteria)?",
        "care_protocol": [
            "Perform warm hypertonic saline gargling (5g sodium chloride in 250 mL sterile warm water) tid.",
            "Consume viscous, soothing fluids (warm bone broths, herbal teas with honey).",
            "Avoid mucosal irritants including citrus acids, hot spices, and environmental aerosols."
        ],
        "red_flags": "Inability to swallow saliva (pooling), trismus (inability to open mandible), stridor, or asymmetrical peritonsillar deviation.",
        "urgency": "High if airway signs present"
    },
    "cough": {
        "title": "Acute Bronchitis & Respiratory Irritation",
        "system": "Respiratory",
        "keywords": ["cough", "coughing", "bronchitis", "phlegm", "mucus", "hacking cough", "wet cough", "dry cough", "productive cough"],
        "pathophysiology": "Hyper-reactive inflammatory response of the tracheobronchial tree stimulating mechanical vagal afferent cough receptors.",
        "inquiry": "Is the cough non-productive (paroxysmal) or productive with purulent, discolored, or rust-colored sputum?",
        "care_protocol": [
            "Employ isotonic steam inhalation for 10–15 minutes bid to loosen mucus plugs.",
            "Maintain optimal room humidity utilizing a cool-mist ultrasonic humidifier.",
            "Administer natural demulcents such as unpasteurized honey (in patients >1 year of age)."
        ],
        "red_flags": "Frank hemoptysis (coughing blood), respiratory rate >24 breaths/min, focal pleuritic chest pain, or oxygen saturation <94%.",
        "urgency": "Moderate to High"
    },
    "cold": {
        "title": "Viral Rhinosinusitis (Common Cold)",
        "system": "Respiratory / ENT",
        "keywords": ["cold", "runny nose", "congestion", "sneezing", "blocked nose", "nasal congestion", "stuffy nose", "sinus pressure"],
        "pathophysiology": "Viral infection (primarily Picornaviridae/Rhinovirus) inducing localized mucosal edema, hyper-secretion, and kinin-mediated nasal vascular dilation.",
        "inquiry": "Is rhinorrhea watery and bilateral, and have symptoms persisted beyond 10 days without clinical improvement?",
        "care_protocol": [
            "Administer buffered isotonic nasal saline irrigations via sinus rinse flask.",
            "Elevate head of the bed 30 degrees during sleep to mitigate nocturnal post-nasal pooling.",
            "Ensure extensive systemic fluid hydration to maintain thin mucus viscosity."
        ],
        "red_flags": "Periorbital or facial cellulitis/swelling, severe persistent unilateral maxillary pain with secondary fever spike ('double sickening').",
        "urgency": "Routine"
    },
    "shortness_of_breath": {
        "title": "Acute Dyspnea & Bronchospasm Exacerbation",
        "system": "Cardiopulmonary",
        "keywords": ["shortness of breath", "breathless", "dyspnea", "breathing difficulty", "wheezing", "gasping", "cant breathe", "can't breathe"],
        "pathophysiology": "Ventilation-perfusion mismatch, reactive airway bronchoconstriction, parenchymal consolidation, or pulmonary venous congestion.",
        "inquiry": "Did dyspnea initiate acutely at rest, and do you experience audible end-expiratory polyphonic wheezes?",
        "care_protocol": [
            "Adopt the High-Fowler's posture: sit upright leaning slightly forward with arms supported (tripod position).",
            "Loosen constrictive chest and abdominal garments immediately.",
            "Perform pursed-lip diaphragmatic breathing to stabilize intra-alveolar pressure."
        ],
        "red_flags": "CRITICAL EMERGENCY: Cyanosis of lips/fingers, intercostal retractions, inability to vocalize more than 2 words without gasping, or diaphoresis.",
        "urgency": "CRITICAL EMERGENCY"
    },
    "chest_pain": {
        "title": "Acute Thoracic Pain / Cardiac & Musculoskeletal Triage",
        "system": "Cardiovascular / Thoracic",
        "keywords": ["chest pain", "chest tightness", "chest pressure", "heart pain", "angina", "sternum pain", "rib pain"],
        "pathophysiology": "Ischemic myocardial strain, intercostal chondrosternal inflammation (costochondritis), or esophageal reflux spasm.",
        "inquiry": "Does the discomfort change with positional movements, rib palpation, and deep inspiration, or present as a heavy retrosternal pressure?",
        "care_protocol": [
            "Immediately cease all physical activity and ambulation.",
            "Assume a seated or semi-reclined resting position with supportive back padding.",
            "Avoid ingesting oral fluids or medications prior to definitive clinical evaluation."
        ],
        "red_flags": "CRITICAL EMERGENCY: Sub-sternal crushing pressure radiating into left arm, jaw, or back, associated with diaphoresis, syncope, and nausea.",
        "urgency": "CRITICAL EMERGENCY"
    },

    # 3. Gastrointestinal & Abdominal
    "stomach_pain": {
        "title": "Acute Abdominal Discomfort & Functional Dyspepsia",
        "system": "Gastrointestinal",
        "keywords": ["stomach pain", "abdominal pain", "belly ache", "stomach cramps", "gastritis", "tummy ache", "gut pain", "stomach hurt"],
        "pathophysiology": "Visceral sensory irritation resulting from gastric hyperacidity, mucosal breakdown, smooth muscle spasm, or peritoneal distension.",
        "inquiry": "Where is the pain strictly localized (epigastric, periumbilical, right lower quadrant), and does it correlate chronologically with meals?",
        "care_protocol": [
            "Withhold solid, heavy, high-lipid, and acidic food substances for 4–6 hours.",
            "Initiate the BRAT regimen (bananas, white rice, applesauce, plain toast) when tolerated.",
            "Consume lukewarm, non-caffeinated peppermint or chamomile infusions."
        ],
        "red_flags": "Surgical abdomen indicators: acute localized right lower quadrant rebound tenderness (McBurney point), board-like abdominal wall rigidity, or hematemesis.",
        "urgency": "High if signs of peritonitis; otherwise Moderate"
    },
    "diarrhea": {
        "title": "Acute Infectious / Osmotic Gastroenteritis",
        "system": "Gastrointestinal",
        "keywords": ["diarrhea", "diarrhoea", "loose stool", "watery stool", "loose motions", "frequent stool", "watery poop"],
        "pathophysiology": "Enterotoxigenic hyper-secretion or osmotic mucosal malabsorption in the ileum and colon driving accelerated transit.",
        "inquiry": "What is the 24-hour volumetric frequency of loose evacuations, and is there macroscopic presence of blood (hematochezia) or mucus?",
        "care_protocol": [
            "Immediately initiate WHO-standard Oral Rehydration Salts (ORS) solution sip-by-sip after every unformed stool.",
            "Strictly avoid lactose, dairy, sucrose-heavy sodas, and caffeine (which accelerate motility).",
            "Maintain restful recumbency to reduce peristaltic reflex excitation."
        ],
        "red_flags": "Grossly bloody or black melenic stools, signs of hypovolemic shock (orthostatic syncope, absence of micturition >8 hours, dry mucous membranes).",
        "urgency": "High if dehydration present"
    },
    "vomiting": {
        "title": "Emesis & Acute Gastric Intolerance",
        "system": "Gastrointestinal",
        "keywords": ["vomiting", "vomit", "nausea", "throwing up", "puke", "puking", "queasy", "upset stomach"],
        "pathophysiology": "Stimulation of the chemoreceptor trigger zone (CTZ) in the area postrema inducing retro-peristaltic coordinated diaphragmatic contraction.",
        "inquiry": "Are you capable of retaining small fluid volumes without regurgitation, and what is the appearance of the vomitus?",
        "care_protocol": [
            "Enforce total gastrointestinal resting: nothing by mouth (NPO) for 60 minutes post-emetic event.",
            "Gradually introduce clear electrolyte solution: 5 mL (one teaspoon) every 5–10 minutes.",
            "Gradually advance to clear broths as tolerated, avoiding rapid ingestion."
        ],
        "red_flags": "Coffee-ground emesis, bright hematemesis, unrelenting localized pain, or persistent neurological lethargy.",
        "urgency": "High"
    },
    "acid_reflux": {
        "title": "Gastroesophageal Reflux Disease (GERD) & Pyrosis",
        "system": "Gastrointestinal",
        "keywords": ["acid reflux", "heartburn", "gerd", "acidity", "sour burp", "acid regurgitation", "chest burning after eating"],
        "pathophysiology": "Transient lower esophageal sphincter (LES) relaxation allowing retrograde passage of acidic gastric contents (pH <4) onto esophageal mucosa.",
        "inquiry": "Does burning intensify during supine post-prandial positioning, and have you noticed sour fluid regurgitation into the hypopharynx?",
        "care_protocol": [
            "Elevate head of the bed frame 15–20 cm (avoid stacking soft pillows which only flexes the neck).",
            "Remain completely upright for at least 3 hours following solid caloric intake.",
            "Eliminate trigger substrates: chocolate, peppermint, high-fat foods, acidic citrus, and caffeinated beverages."
        ],
        "red_flags": "Progressive dysphagia (sensation of food bolus lodged behind sternum), odynophagia, unexplained weight loss, or persistent vomiting.",
        "urgency": "Routine to Moderate"
    },
    "constipation": {
        "title": "Colonic Dysmotility & Acute Constipation",
        "system": "Gastrointestinal",
        "keywords": ["constipation", "constipated", "hard stool", "bowel strain", "cant poop", "cannot pass stool"],
        "pathophysiology": "Prolonged colonic transit resulting in excessive mucosal water absorption and dry, scybalous, difficult-to-expel fecal masses.",
        "inquiry": "How many days have elapsed since your last spontaneous complete bowel evacuation, and are you passing flatus normally?",
        "care_protocol": [
            "Increase dietary soluble and insoluble fiber intake to 25–30g daily (psyllium, legumes, oats, flaxseed).",
            "Maintain daily water intake of 2.5 liters to ensure stool soft consistency.",
            "Engage in daily brisk aerobic walking to stimulate colonic migrating motor complexes."
        ],
        "red_flags": "Obstipation (total inability to pass both feces and gas), severe abdominal distension, fever, or rectal bleeding.",
        "urgency": "Moderate; Emergency if obstipation + vomiting"
    },

    # 4. Neurological & Neuro-Sensory
    "headache": {
        "title": "Cephalalgia / Tension-Type & Migraine Presentation",
        "system": "Neurological",
        "keywords": ["headache", "head pain", "migraine", "temple pain", "forehead pain", "throbbing head", "head ache"],
        "pathophysiology": "Neurovascular trigeminovascular activation (migraine) or sustained pericranial muscular hyper-tonicity and central sensitization (tension-type).",
        "inquiry": "Is the discomfort a bilateral band-like compression or unilateral pulsatile throbbing accompanied by photophobia or phonophobia?",
        "care_protocol": [
            "Retire into a sound-attenuated, completely darkened room and close eyes for 60 minutes.",
            
