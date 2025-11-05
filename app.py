import pickle
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor  # untuk cursor dictionary
from preprocessing import preprocess
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import numpy as np
from dotenv import load_dotenv

# ===================== Load .env =====================
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")  # gunakan DATABASE_URL dari Vercel
FLASK_ENV = os.getenv("FLASK_ENV", "development")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True") == "True"
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

# ===================== Inisialisasi Flask =====================
app = Flask(__name__)
CORS(app, origins=ALLOWED_ORIGINS)

# ===================== Fungsi Koneksi PostgreSQL =====================
def get_db_connection():
    """Koneksi PostgreSQL dengan dictionary cursor"""
    return psycopg2.connect(DB_URL, sslmode='require', cursor_factory=RealDictCursor)

# ===================== Load Model QA =====================
with open(os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl'), 'rb') as f:
    qa_data = pickle.load(f)

model_qa = qa_data['model']
vectorizer_qa = qa_data['vectorizer']
answers = qa_data['answers']
pertanyaan_list = qa_data['questions']

# ===================== Load Dataset =====================
df = pd.read_csv(os.getenv("DATA_PATH", "data/dataset.csv"))
df['processed'] = df['pertanyaan'].apply(preprocess)

# ===================== Simpan Pertanyaan Tidak Dikenal =====================
def save_unknown_question(question):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pertanyaan_unknow (pertanyaan) VALUES (%s)",
            (question,)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

# ===================== Routes =====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    processed_input = preprocess(user_input)
    X_input_qa = vectorizer_qa.transform([processed_input])

    if X_input_qa.nnz == 0:
        save_unknown_question(user_input)
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': "Mohon maaf, saya belum mengerti pertanyaan Anda.",
            'status': 'unknown'
        })

    try:
        scores = model_qa.decision_function(X_input_qa)
        if len(scores.shape) > 1:
            scores = scores.flatten()
        else:
            scores = np.array(scores)
    except Exception as e:
        print(f"Error calculating confidence: {e}")
        scores = np.array([0])

    top_n = 5
    top_indices = np.argsort(scores)[::-1][:top_n]
    top_scores = scores[top_indices]

    ambiguity_threshold = 0.5
    if len(top_scores) > 1 and abs(top_scores[0] - top_scores[1]) < ambiguity_threshold:
        similar_questions = [pertanyaan_list[i] for i in top_indices]
        return jsonify({
            'pertanyaan': user_input,
            'opsi_pertanyaan': similar_questions,
            'jawaban': "Pertanyaan mana yang kamu maksud?",
            'status': 'ambigu'
        })

    max_score = top_scores[0]
    threshold = -1
    if max_score < threshold:
        save_unknown_question(user_input)
        predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda."
    else:
        predicted_index = model_qa.predict(X_input_qa)[0]
        if 0 <= predicted_index < len(answers):
            predicted_answer = answers[predicted_index]
        else:
            save_unknown_question(user_input)
            predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda."

    return jsonify({
        'pertanyaan': user_input,
        'jawaban': predicted_answer,
        'status': 'ok'
    })

@app.route('/pertanyaan-unknown', methods=['GET'])
def get_unknown_questions():
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, pertanyaan FROM pertanyaan_unknow ORDER BY id DESC LIMIT %s OFFSET %s",
            (per_page, offset)
        )
        data = cursor.fetchall()  # RealDictCursor membuat list of dict otomatis

        cursor.execute("SELECT COUNT(*) as total FROM pertanyaan_unknow")
        total_data = cursor.fetchone()['total']
        total_pages = (total_data + per_page - 1) // per_page

        cursor.close()
        conn.close()

        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total_data,
            'total_pages': total_pages,
            'data': data
        })

    except Exception as e:
        print(f"[DB ERROR] {e}")
        return jsonify({'error': 'Gagal mengambil data dari database'}), 500

if __name__ == '__main__':
    app.run()