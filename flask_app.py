import os
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sentence_transformers import SentenceTransformer, util
from langdetect import detect, DetectorFactory
from transformers import pipeline
from dotenv import load_dotenv
import markupsafe # For input sanitization

# Ensure consistent language detection
DetectorFactory.seed = 0

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret")
CORS(app)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Load Dataset
DATASET_PATH = "diseases_dataset.csv"
df = pd.read_csv(DATASET_PATH)

# Initialize Models
# SentenceTransformer for symptom matching (Force CPU for stability on most hosting)
try:
    similarity_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
except Exception as e:
    print(f"Error loading Similarity Model: {e}")
    similarity_model = None

# Pre-compute symptom embeddings for all 4 languages to support multilingual matching
symptom_columns = ['symptoms_en', 'symptoms_kn', 'symptoms_te', 'symptoms_hi']
disease_name_columns = ['disease_name_en', 'disease_name_kn', 'disease_name_te', 'disease_name_hi']
prevention_columns = ['prevention_en', 'prevention_kn', 'prevention_te', 'prevention_hi']

# Flatten all symptoms for similarity search
all_symptoms = []
symptom_to_disease_map = [] # Store (disease_index, language_code)

for idx, row in df.iterrows():
    for lang_col in symptom_columns:
        lang_code = lang_col.split('_')[1]
        all_symptoms.append(str(row[lang_col]))
        symptom_to_disease_map.append((idx, lang_code))

if similarity_model:
    symptom_embeddings = similarity_model.encode(all_symptoms, convert_to_tensor=True)
else:
    symptom_embeddings = None

# LLM Fallback (distilgpt2)
try:
    llm_pipeline = pipeline("text-generation", model="distilgpt2", device=-1) # -1 is CPU
except Exception as e:
    print(f"Error loading LLM: {e}")
    llm_pipeline = None

def get_detected_lang(text):
    if not any(c.isalpha() for c in text):
        return 'en'
    try:
        lang = detect(text)
        if lang in ['en', 'kn', 'te', 'hi']:
            return lang
        return 'en' # Default to English
    except Exception:
        return 'en'

def get_prevention_list(prevention_text):
    # Split by comma or period and clean up
    points = [p.strip() for p in prevention_text.replace('.', ',').split(',') if p.strip()]
    return points

# Multilingual Intelligence Configuration
LLM_LANG_CONFIG = {
    'en': {
        'disclaimer_name': "Health Disclaimer",
        'disclaimer_measures': ["Health queries only.", "No medical match found.", "Describe symptoms.", "Consult a professional."],
        'lang_name': "English",
        'assessment_label': "Condition",
        'consult_label': "Consult a doctor.",
        'info_prefix': "Information: "
    },
    'hi': {
        'disclaimer_name': "स्वास्थ्य अस्वीकरण",
        'disclaimer_measures': ["केवल स्वास्थ्य प्रश्न।", "कोई मिलान नहीं मिला।", "लक्षणों का वर्णन करें।", "डॉक्टर से सलाह लें।"],
        'lang_name': "Hindi",
        'assessment_label': "स्थिति",
        'consult_label': "डॉक्टर से मिलें।",
        'info_prefix': "जानकारी: "
    },
    'kn': {
        'disclaimer_name': "ಆರೋಗ್ಯ ನಿರಾಕರಣೆ",
        'disclaimer_measures': ["ಕೇವಲ ಆರೋಗ್ಯ ವಿಚಾರಣೆಗಳು.", "ಯಾವುದೇ ಹೊಂದಾಣಿಕೆ ಇಲ್ಲ.", "ಲಕ್ಷಣಗಳನ್ನು ವಿವರಿಸಿ.", "ತಜ್ಞರನ್ನು ಸಂಪರ್ಕಿಸಿ."],
        'lang_name': "Kannada",
        'assessment_label': "ಸ್ಥಿತಿ",
        'consult_label': "ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ.",
        'info_prefix': "ಮಾಹಿತಿ: "
    },
    'te': {
        'disclaimer_name': "ఆరోగ్య నిరాకరణ",
        'disclaimer_measures': ["ఆరోగ్య ప్రశ్నల కోసం మాత్రమే.", "వైద్యపరమైన సరిపోలిక లేదు.", "దయచేసి లక్షణాలను వివరించండి.", "నిపుణుడిని సంప్రదించండి."],
        'lang_name': "Telugu",
        'assessment_label': "ఆరోగ్య స్థితి",
        'consult_label': "వైద్యుడిని సంప్రదించండి.",
        'info_prefix': "సమాచారం: "
    }
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat():
    data = request.json or {}
    user_input = data.get('message', '')
    
    # Input Sanitization
    user_input = markupsafe.escape(user_input.strip())
    
    if not user_input:
        return jsonify({
            "mode": "dataset",
            "language": "en",
            "disease_name": "Error",
            "preventive_measures": ["Please provide a valid symptom or disease name."],
            "confidence_score": 0.0
        }), 400

    # 1. Handle Language (Manual selection or Auto-detection)
    provided_lang = data.get('language', 'auto')
    if provided_lang != 'auto' and provided_lang in ['en', 'kn', 'te', 'hi']:
        lang = provided_lang
    else:
        lang = get_detected_lang(user_input)
    
    # Get lang-specific config or default to EN
    l_cfg = LLM_LANG_CONFIG.get(lang, LLM_LANG_CONFIG['en'])

    # 2. Case B: Disease Name Lookup
    matched_disease_idx = -1
    # Sort diseases by length (descending) to match longer names first
    sorted_indices = sorted(range(len(df)), key=lambda i: len(str(df.iloc[i]['disease_name_en'])), reverse=True)
    
    for idx in sorted_indices:
        row = df.iloc[idx]
        for col in disease_name_columns:
            if str(row[col]).lower() in user_input.lower():
                matched_disease_idx = idx
                break
        if matched_disease_idx != -1: break

    # If it's a direct disease name
    if matched_disease_idx != -1:
        disease_name = df.iloc[matched_disease_idx][f'disease_name_{lang}']
        prevention_text = df.iloc[matched_disease_idx][f'prevention_{lang}']
        
        return jsonify({
            "mode": "dataset",
            "language": lang,
            "disease_name": disease_name,
            "preventive_measures": get_prevention_list(prevention_text),
            "confidence_score": 1.0
        })

    # 3. Case A: Symptom Matching
    if similarity_model is not None and symptom_embeddings is not None:
        user_embedding = similarity_model.encode(user_input, convert_to_tensor=True)
        cosine_scores = util.cos_sim(user_embedding, symptom_embeddings)[0]
        
        # Explicit type conversion for lint stability
        scores_arr = cosine_scores.cpu().numpy()
        best_match_idx = int(np.argmax(scores_arr))
        max_score = float(scores_arr[best_match_idx])

        if max_score >= 0.65:
            # Dataset Mode
            match_data = symptom_to_disease_map[best_match_idx]
            match_row_idx = int(match_data[0]) 
            disease_data = df.iloc[match_row_idx]
            
            return jsonify({
                "mode": "dataset",
                "language": lang,
                "disease_name": str(disease_data[f'disease_name_{lang}']),
                "preventive_measures": get_prevention_list(str(disease_data[f'prevention_{lang}'])),
                "confidence_score": float(np.round(max_score, 2))
            })
    else:
        max_score = 0.0

    # 4. Multi-Tiered Intelligence System
    
    # Tier 4: Non-Medical Shield
    if max_score < 0.20:
        return jsonify({
            "mode": "disclaimer",
            "language": lang,
            "disease_name": l_cfg['disclaimer_name'],
            "preventive_measures": l_cfg['disclaimer_measures'],
            "confidence_score": float(np.round(max_score, 2))
        })

    # Tier 2: Grounded Neural Prediction (Confidence Score >= 0.20)
    # Merged General Mode into AI Reasoning for better intelligence responsiveness.
    context_data = ""
    candidates = [] # Store (EN_Name, Target_Name, Target_Measures) for strict mapping
    if similarity_model is not None and symptom_embeddings is not None:
        user_embedding = similarity_model.encode(user_input, convert_to_tensor=True)
        cosine_scores = util.cos_sim(user_embedding, symptom_embeddings)[0]
        top_indices = np.argsort(cosine_scores.cpu().numpy())[-3:][::-1]
        
        context_parts = []
        for match_idx in top_indices:
            m_entry = symptom_to_disease_map[int(match_idx)]
            d_idx = int(m_entry[0])
            row = df.iloc[d_idx]
            en_n = str(row['disease_name_en'])
            tg_n = str(row[f'disease_name_{lang}'])
            tg_p = str(row[f'prevention_{lang}'])
            candidates.append({'en': en_n, 'tg': tg_n, 'p': tg_p})
            # Provide English names for superior LLM reasoning quality
            context_parts.append(f"Condition: {en_n}")
        context_data = " | ".join(context_parts)

    if llm_pipeline:
        # Prompt LLM in English for maximum reasoning quality on distilgpt2
        prompt = (
            f"Context: {context_data}\n"
            f"User: {user_input}\n"
            "Task: Identify the likely disease from the context. Output ONLY the disease name.\n"
            "Result:"
        )
        
        try:
            llm_response = llm_pipeline(prompt, max_new_tokens=30, num_return_sequences=1, truncation=True, pad_token_id=50256)
            predicted_en = llm_response[0]['generated_text'].split("Result:")[-1].strip()
            
            # Strict Translation Match
            final_disease = str(l_cfg['assessment_label'])
            final_measures = [str(l_cfg['consult_label'])]
            
            # Find best candidate by simple string match (e.g. "Flu" in "Common Flu")
            best_cand = candidates[0] if candidates else None
            for cand in candidates:
                if str(cand['en']).lower() in predicted_en.lower() or predicted_en.lower() in str(cand['en']).lower():
                    best_cand = cand
                    break
            
            if best_cand:
                final_disease = str(best_cand['tg'])
                final_measures = get_prevention_list(str(best_cand['p']))[:4]
            
            disease_name = str(final_disease)
            points = final_measures
            
        except Exception as e:
            print(f"Reasoning Synthesis Error: {e}")
            points = [str(l_cfg['consult_label'])]
            disease_name = str(l_cfg['assessment_label'])
    else:
        points = [str(l_cfg['consult_label'])]
        disease_name = "System Fallback"

    if not points:
        points = [str(l_cfg['consult_label'])]

    # Final logic for the frontend response
    final_score = float(np.round(max_score, 2))
    return jsonify({
        "mode": "llm",
        "language": str(lang),
        "disease_name": str(disease_name),
        "display_title": f"{str(l_cfg['info_prefix'])}{str(disease_name)}",
        "preventive_measures": [str(p) for p in points],
        "confidence_score": final_score
    })

if __name__ == '__main__':
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
