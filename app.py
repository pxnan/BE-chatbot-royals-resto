import pickle
import pandas as pd
import mysql.connector
from preprocessing import preprocess
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import numpy as np
from dotenv import load_dotenv
import csv
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import time
import subprocess
import sys

# ===================== Load .env =====================
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

FLASK_ENV = os.getenv("FLASK_ENV")
FLASK_DEBUG = os.getenv("FLASK_DEBUG")
FLASK_PORT = int(os.getenv("FLASK_PORT"))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")

# ===================== Inisialisasi Flask =====================
app = Flask(__name__)
CORS(app, origins=ALLOWED_ORIGINS)

# ===================== Fungsi Koneksi Database MySQL =====================
def get_db_connection():
    """Buat koneksi baru ke database setiap request"""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# ===================== Load Model QA Tunggal =====================
model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
with open(model_path, 'rb') as f:
    qa_data = pickle.load(f)

model_qa = qa_data['model']
vectorizer_qa = qa_data['vectorizer']
answers = qa_data['answers']
pertanyaan_list = qa_data['questions']

# ===================== Load Dataset =====================
csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
df = pd.read_csv(csv_path, encoding='utf-8')
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

    # Ambil top-N pertanyaan mirip
    top_n = 3
    top_indices = np.argsort(scores)[::-1][:top_n]
    top_scores = scores[top_indices]

    # Prediksi Jawaban Normal
    max_score = top_scores[0]
    threshold = -0.8
    ambiguity_threshold = 0.1
    
    if max_score < threshold:
        save_unknown_question(user_input)
        predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda."
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': predicted_answer,
            'status': 'unknown'
        })
    
    # Deteksi Ambiguitas dengan pengecekan exact match
    elif len(top_scores) > 1 and abs(top_scores[0] - top_scores[1]) < ambiguity_threshold:
        # Cek apakah input user sama persis dengan salah satu pertanyaan di dataset
        exact_match = False
        exact_match_idx = -1
        
        # Cari exact match (case insensitive, strip whitespace)
        user_input_clean = user_input.lower().strip()
        for idx, pertanyaan in enumerate(pertanyaan_list):
            if user_input_clean == pertanyaan.lower().strip():
                exact_match = True
                exact_match_idx = idx
                break
        
        if exact_match:
            # Jika exact match, langsung berikan jawaban tanpa ambigu
            predicted_answer = answers[exact_match_idx] if 0 <= exact_match_idx < len(answers) else "Jawaban tidak ditemukan"
            print(f"Exact match found: {user_input} -> Index: {exact_match_idx}")
            return jsonify({
                'pertanyaan': user_input,
                'jawaban': predicted_answer,
                'status': 'ok'
            })
        
        # Jika tidak exact match, tampilkan opsi ambigu
        similar_questions = [pertanyaan_list[i] for i in top_indices]
        return jsonify({
            'pertanyaan': user_input,
            'opsi_pertanyaan': similar_questions,
            'jawaban': "Pertanyaan mana yang kamu maksud?",
            'status': 'ambigu'
        })
    
    # Kondisi normal (tidak ambigu, skor tinggi)
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
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM pertanyaan_unknow ORDER BY id DESC LIMIT %s OFFSET %s",
            (per_page, offset)
        )
        data = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as total FROM pertanyaan_unknow")
        total_data = cursor.fetchone()['total']
        total_pages = (total_data + per_page - 1) // per_page

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


@app.route('/tambah-data', methods=['POST'])
def tambah_data():
    """
    Endpoint untuk menambahkan data baru ke dataset CSV
    Request body: {
        "pertanyaan": "contoh pertanyaan",
        "jawaban": "contoh jawaban",
        "kategori": "nama_kategori"
    }
    """
    try:
        # Ambil data dari request
        data = request.json
        pertanyaan_baru = data.get('pertanyaan', '').strip()
        jawaban_baru = data.get('jawaban', '').strip()
        kategori_baru = data.get('kategori', '').strip()
        
        # Validasi input
        if not pertanyaan_baru:
            return jsonify({'error': 'Pertanyaan tidak boleh kosong'}), 400
        if not jawaban_baru:
            return jsonify({'error': 'Jawaban tidak boleh kosong'}), 400
        if not kategori_baru:
            return jsonify({'error': 'Kategori tidak boleh kosong'}), 400
        
        # Path ke file CSV
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # ============= METHOD 1: Menggunakan pandas (Paling Reliable) =============
        try:
            # Baca file CSV yang sudah ada
            df_existing = pd.read_csv(csv_path, encoding='utf-8')
            
            # Buat dataframe baru untuk data yang akan ditambahkan
            df_new = pd.DataFrame([{
                'pertanyaan': pertanyaan_baru,
                'jawaban': jawaban_baru,
                'kategori': kategori_baru
            }])
            
            # Cek duplikasi
            if pertanyaan_baru.lower() in df_existing['pertanyaan'].str.lower().values:
                return jsonify({
                    'error': f'Pertanyaan "{pertanyaan_baru}" sudah ada di dataset',
                    'status': 'duplicate'
                }), 409
            
            # Gabungkan dataframe
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            
            # Simpan kembali ke CSV (index=False untuk menghindari kolom index tambahan)
            df_combined.to_csv(csv_path, index=False, encoding='utf-8')
            
            print(f"[DEBUG] Data added successfully using pandas. Total rows: {len(df_combined)}")
            
        except Exception as pandas_error:
            # Jika pandas gagal, fallback ke csv writer
            print(f"[WARNING] Pandas method failed: {pandas_error}, falling back to csv.writer")
            
            # Baca file untuk cek duplikasi
            existing_questions = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) > 0 and row[0]:
                        existing_questions.append(row[0].lower())
            
            # Cek duplikasi
            if pertanyaan_baru.lower() in existing_questions:
                return jsonify({
                    'error': f'Pertanyaan "{pertanyaan_baru}" sudah ada di dataset',
                    'status': 'duplicate'
                }), 409
            
            # Tulis data baru dengan memastikan baris baru
            with open(csv_path, 'a', encoding='utf-8', newline='\n') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator='\n')
                writer.writerow([pertanyaan_baru, jawaban_baru, kategori_baru])
            
            print(f"[DEBUG] Data added successfully using csv.writer")
        
        return jsonify({
            'message': 'Data berhasil ditambahkan ke CSV. Silakan latih model untuk mengupdate chatbot.',
            'data': {
                'pertanyaan': pertanyaan_baru,
                'jawaban': jawaban_baru,
                'kategori': kategori_baru
            },
            'status': 'success'
        }), 201
        
    except Exception as e:
        print(f"[ERROR] Tambah data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500


@app.route('/train-model', methods=['POST'])
def train_model():
    """
    Endpoint untuk melatih ulang model dengan dataset terbaru
    """
    try:
        start_time = time.time()
        
        # Path ke file CSV
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Load dataset
        print("[TRAIN] Loading dataset...")
        df_train = pd.read_csv(csv_path, encoding='utf-8')
        
        # Preprocessing
        print("[TRAIN] Preprocessing data...")
        df_train['processed'] = df_train['pertanyaan'].astype(str).apply(preprocess)
        
        # Persiapan data untuk training
        X_train = df_train['processed']
        y_train = list(range(len(df_train)))
        
        # Vectorizer
        print("[TRAIN] Vectorizing text...")
        vectorizer = TfidfVectorizer()
        X_train_tfidf = vectorizer.fit_transform(X_train)
        
        # Training model
        print("[TRAIN] Training SVM model...")
        model = LinearSVC()
        model.fit(X_train_tfidf, y_train)
        
        # Simpan model
        print("[TRAIN] Saving model...")
        qa_data_new = {
            'model': model,
            'vectorizer': vectorizer,
            'answers': df_train['jawaban'].tolist(),
            'questions': df_train['pertanyaan'].tolist(),
            'categories': df_train['kategori'].tolist()
        }
        
        model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(qa_data_new, f)
        
        # Update global variables di app
        global model_qa, vectorizer_qa, answers, pertanyaan_list, df
        model_qa = model
        vectorizer_qa = vectorizer
        answers = df_train['jawaban'].tolist()
        pertanyaan_list = df_train['pertanyaan'].tolist()
        df = df_train
        
        training_time = time.time() - start_time
        
        print(f"[TRAIN] Training completed in {training_time:.2f} seconds")
        
        return jsonify({
            'message': 'Model berhasil dilatih',
            'training_time': f'{training_time:.2f} detik',
            'total_data': len(df_train),
            'total_questions': len(pertanyaan_list),
            'categories_count': len(df_train['kategori'].unique()),
            'status': 'success'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Train model: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Terjadi kesalahan saat training: {str(e)}'}), 500


@app.route('/kategori', methods=['GET'])
def get_kategori():
    """
    Endpoint untuk mendapatkan daftar kategori unik dari dataset
    """
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        categories = sorted(df_temp['kategori'].unique().tolist())
        return jsonify({'kategori': categories})
    except Exception as e:
        print(f"[ERROR] Get kategori: {e}")
        return jsonify({'error': 'Gagal mengambil daftar kategori'}), 500


@app.route('/model-info', methods=['GET'])
def model_info():
    """
    Endpoint untuk mendapatkan informasi tentang model yang sedang digunakan
    """
    try:
        return jsonify({
            'total_questions': len(pertanyaan_list),
            'total_answers': len(answers),
            'categories': sorted(df['kategori'].unique().tolist()),
            'model_loaded': model_qa is not None,
            'vectorizer_loaded': vectorizer_qa is not None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/cek-csv', methods=['GET'])
def cek_csv():
    """Endpoint untuk debugging - melihat isi CSV"""
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse CSV untuk melihat struktur
        import csv
        reader = csv.reader(lines)
        rows = list(reader)
        
        return jsonify({
            'total_lines': len(lines),
            'total_rows': len(rows),
            'last_5_rows': rows[-5:] if len(rows) >= 5 else rows,
            'file_path': csv_path,
            'raw_last_5_lines': lines[-5:] if len(lines) >= 5 else lines
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/fix-csv', methods=['POST'])
def fix_csv():
    """Endpoint untuk memperbaiki format CSV yang bermasalah"""
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Baca file dengan pandas (akan handle berbagai masalah)
        df_temp = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='skip')
        
        # Simpan ulang dengan format yang benar
        backup_path = csv_path.replace('.csv', '_backup.csv')
        import shutil
        shutil.copy(csv_path, backup_path)
        
        df_temp.to_csv(csv_path, index=False, encoding='utf-8')
        
        return jsonify({
            'message': 'CSV berhasil diperbaiki',
            'backup_path': backup_path,
            'total_rows': len(df_temp)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Tambahkan endpoint berikut ke dalam app.py

@app.route('/get-all-data', methods=['GET'])
def get_all_data():
    """Endpoint untuk mendapatkan semua data dari dataset CSV dengan pagination"""
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        search = request.args.get('search', default='', type=str)
        kategori_filter = request.args.get('kategori', default='', type=str)
        
        offset = (page - 1) * per_page
        
        # Baca dataset
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        
        # Filter berdasarkan search
        if search:
            df_temp = df_temp[df_temp['pertanyaan'].str.contains(search, case=False, na=False)]
        
        # Filter berdasarkan kategori
        if kategori_filter:
            df_temp = df_temp[df_temp['kategori'] == kategori_filter]
        
        total_data = len(df_temp)
        total_pages = (total_data + per_page - 1) // per_page
        
        # Pagination
        df_paginated = df_temp.iloc[offset:offset + per_page]
        
        # Konversi ke list of dict
        data = df_paginated.reset_index().to_dict('records')
        
        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total_data,
            'total_pages': total_pages,
            'data': data,
            'categories': sorted(df_temp['kategori'].unique().tolist())
        })
        
    except Exception as e:
        print(f"[ERROR] Get all data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/update-data', methods=['PUT'])
def update_data():
    """Endpoint untuk mengupdate data pertanyaan berdasarkan index"""
    try:
        data = request.json
        index = data.get('index')
        pertanyaan_baru = data.get('pertanyaan', '').strip()
        jawaban_baru = data.get('jawaban', '').strip()
        kategori_baru = data.get('kategori', '').strip()
        
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        
        if index < 0 or index >= len(df_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        # Update data
        df_temp.at[index, 'pertanyaan'] = pertanyaan_baru
        df_temp.at[index, 'jawaban'] = jawaban_baru
        df_temp.at[index, 'kategori'] = kategori_baru
        
        # Simpan ke CSV
        df_temp.to_csv(csv_path, index=False, encoding='utf-8')
        
        return jsonify({
            'message': 'Data berhasil diupdate',
            'status': 'success'
        })
        
    except Exception as e:
        print(f"[ERROR] Update data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete-data', methods=['DELETE'])
def delete_data():
    """Endpoint untuk menghapus data pertanyaan berdasarkan index"""
    try:
        data = request.json
        index = data.get('index')
        
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        
        if index < 0 or index >= len(df_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        # Hapus data
        df_temp = df_temp.drop(index).reset_index(drop=True)
        
        # Simpan ke CSV
        df_temp.to_csv(csv_path, index=False, encoding='utf-8')
        
        return jsonify({
            'message': 'Data berhasil dihapus',
            'status': 'success'
        })
        
    except Exception as e:
        print(f"[ERROR] Delete data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete-unknown', methods=['DELETE'])
def delete_unknown():
    """Endpoint untuk menghapus pertanyaan tidak dikenal"""
    try:
        data = request.json
        unknown_id = data.get('id')
        
        if unknown_id is None:
            return jsonify({'error': 'ID tidak ditemukan'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM pertanyaan_unknow WHERE id = %s", (unknown_id,))
        conn.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        conn.close()
        
        if affected_rows == 0:
            return jsonify({'error': 'Data tidak ditemukan'}), 404
        
        return jsonify({
            'message': 'Pertanyaan berhasil dihapus',
            'status': 'success'
        })
        
    except Exception as e:
        print(f"[ERROR] Delete unknown: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete-all-unknown', methods=['DELETE'])
def delete_all_unknown():
    """Endpoint untuk menghapus semua pertanyaan tidak dikenal"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM pertanyaan_unknow")
        conn.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': f'{affected_rows} pertanyaan berhasil dihapus',
            'status': 'success',
            'deleted_count': affected_rows
        })
        
    except Exception as e:
        print(f"[ERROR] Delete all unknown: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT)