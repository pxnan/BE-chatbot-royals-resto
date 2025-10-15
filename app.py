import pickle
import pandas as pd
import mysql.connector
from preprocessing import preprocess
from flask import Flask, request, jsonify
from flask_cors import CORS

# ===================== Inisialisasi Flask =====================
app = Flask(__name__)
CORS(app, origins="*")

# ===================== Fungsi Koneksi Database MySQL =====================
def get_db_connection():
    """Buat koneksi baru ke database setiap request"""
    return mysql.connector.connect(
        host="localhost",
        user="root",             # ubah sesuai user MySQL kamu
        password="",             # ubah sesuai password MySQL kamu
        database="chatbot_royals_resto"
    )

# ===================== Load Model Kategori =====================
with open('model/tfidf_vectorizer_category.pkl', 'rb') as f:
    vectorizer_cat = pickle.load(f)
with open('model/svm_model_category.pkl', 'rb') as f:
    model_cat = pickle.load(f)

# ===================== Load Dataset =====================
df = pd.read_csv('data/dataset.csv')
df['processed'] = df['pertanyaan'].apply(preprocess)

# ===================== Load Model Jawaban per Kategori =====================
answer_models = {}
answer_vectorizers = {}
for cat in df['kategori'].unique():
    try:
        with open(f'model/svm_model_answer_{cat}.pkl', 'rb') as f:
            answer_models[cat] = pickle.load(f)
        with open(f'model/vectorizer_answer_{cat}.pkl', 'rb') as f:
            answer_vectorizers[cat] = pickle.load(f)
    except FileNotFoundError:
        print(f"[WARNING] Model untuk kategori '{cat}' tidak ditemukan.")

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
        print(f"[DB] Pertanyaan tidak dikenal disimpan: {question}")
    except Exception as e:
        print(f"[DB ERROR] {e}")

# ===================== Endpoint Chat =====================
@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    processed_input = preprocess(user_input)

    # ===== Stage 1: Prediksi Kategori =====
    X_input_cat = vectorizer_cat.transform([processed_input])
    predicted_category = model_cat.predict(X_input_cat)[0]

    # Pastikan kategori punya model jawaban
    if predicted_category not in answer_models:
        save_unknown_question(user_input)
        return jsonify({
            'pertanyaan': user_input,
            'kategori': predicted_category,
            'jawaban': "Mohon maaf, saya belum mengerti pertanyaan Anda."
        })

    # ===== Stage 2: Prediksi Jawaban =====
    vectorizer_answer = answer_vectorizers[predicted_category]
    model_answer = answer_models[predicted_category]

    X_input_answer = vectorizer_answer.transform([processed_input])

    # ===== Cek confidence dari SVM =====
    try:
        scores = model_answer.decision_function(X_input_answer)
        max_score = max(scores[0]) if len(scores.shape) > 1 else scores[0]
    except Exception:
        max_score = 0

    threshold = 0.0  # bisa kamu sesuaikan, makin tinggi makin ketat

    # ===== Jika confidence rendah, simpan ke database =====
    if max_score < threshold:
        save_unknown_question(user_input)
        predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda."
    else:
        predicted_answer = model_answer.predict(X_input_answer)[0]

    return jsonify({
        'pertanyaan': user_input,
        'kategori': predicted_category,
        'jawaban': predicted_answer
    })

# ===================== Endpoint Ambil Semua Pertanyaan Tidak Dikenal =====================
@app.route('/pertanyaan-unknown', methods=['GET'])
def get_unknown_questions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM pertanyaan_unknow ORDER BY id DESC")
        data = cursor.fetchall()

        # Pastikan commit agar data terbaru terbaca
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify(data)

    except Exception as e:
        print(f"[DB ERROR] {e}")
        return jsonify({'error': 'Gagal mengambil data dari database'}), 500

# ===================== Jalankan Server =====================
if __name__ == '__main__':
    app.run(debug=True)
