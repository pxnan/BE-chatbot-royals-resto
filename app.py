import pickle
import pandas as pd
import mysql.connector
from preprocessing import preprocess
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import numpy as np

# ===================== Inisialisasi Flask =====================
app = Flask(__name__)
CORS(app)

# ===================== Fungsi Koneksi Database MySQL =====================
def get_db_connection():
    """Buat koneksi baru ke database setiap request"""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="chatbot_royals_resto"
    )

# ===================== Load Model QA Tunggal =====================
with open('model/model_qa.pkl', 'rb') as f:
    qa_data = pickle.load(f)

model_qa = qa_data['model']
vectorizer_qa = qa_data['vectorizer']
answers = qa_data['answers']
pertanyaan_list = qa_data['questions']

# ===================== Load Dataset (opsional) =====================
df = pd.read_csv('data/dataset.csv')
df['processed'] = df['pertanyaan'].apply(preprocess)

# ===================== Fungsi Simpan Pertanyaan Tidak Dikenal =====================
def save_unknown_question(question):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO pertanyaan_unknow (pertanyaan) VALUES (%s)"
        cursor.execute(query, (question,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")
        

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

    # ==== CEK jika input tidak punya fitur TF-IDF sama sekali ====
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

    # Ambil top-N pertanyaan mirip (misal 3 teratas)
    top_n = 5
    top_indices = np.argsort(scores)[::-1][:top_n]
    top_scores = scores[top_indices]

    # ===== Deteksi Ambiguitas =====
    ambiguity_threshold = 0.5
    if len(top_scores) > 1 and abs(top_scores[0] - top_scores[1]) < ambiguity_threshold:
        similar_questions = [pertanyaan_list[i] for i in top_indices]
        return jsonify({
            'pertanyaan': user_input,
            'opsi_pertanyaan': similar_questions,
            'jawaban': "Pertanyaan mana yang kamu maksud?",
            'status': 'ambigu'
        })

    # ===== Prediksi Jawaban Normal =====
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
        # Ambil parameter query 'page', default 1
        page = request.args.get('page', default=1, type=int)
        per_page = 10  # jumlah data per halaman
        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Query dengan LIMIT dan OFFSET
        cursor.execute(
            "SELECT * FROM pertanyaan_unknow ORDER BY id DESC LIMIT %s OFFSET %s",
            (per_page, offset)
        )
        data = cursor.fetchall()

        # Ambil total jumlah data untuk info pagination
        cursor.execute("SELECT COUNT(*) as total FROM pertanyaan_unknow")
        total_data = cursor.fetchone()['total']
        total_pages = (total_data + per_page - 1) // per_page  # pembulatan ke atas

        conn.commit()
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
    app.run(debug=True)
