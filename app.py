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
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import time
import bcrypt
import jwt
from functools import wraps

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

# ===================== Konfigurasi JWT =====================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "royal_resto_chatbot_secret_key_2024")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

# ===================== Helper Functions =====================
def hash_password(password):
    """Meng-hash password menggunakan bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    """Memverifikasi password dengan hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(admin_id, username, role):
    """Membuat JWT token untuk session"""
    payload = {
        'admin_id': admin_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

def verify_token(token):
    """Memverifikasi JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator untuk memproteksi endpoint dengan token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token tidak ditemukan', 'authenticated': False}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Token tidak valid atau sudah kadaluarsa', 'authenticated': False}), 401
        
        request.admin = payload
        return f(*args, **kwargs)
    return decorated

def get_client_ip():
    """Mendapatkan IP address client"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip = request.remote_addr
    return ip

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

# ===================== ENDPOINT CHATBOT =====================
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

    top_n = 3
    top_indices = np.argsort(scores)[::-1][:top_n]
    top_scores = scores[top_indices]

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
    
    elif len(top_scores) > 1 and abs(top_scores[0] - top_scores[1]) < ambiguity_threshold:
        exact_match = False
        exact_match_idx = -1
        
        user_input_clean = user_input.lower().strip()
        for idx, pertanyaan in enumerate(pertanyaan_list):
            if user_input_clean == pertanyaan.lower().strip():
                exact_match = True
                exact_match_idx = idx
                break
        
        if exact_match:
            predicted_answer = answers[exact_match_idx] if 0 <= exact_match_idx < len(answers) else "Jawaban tidak ditemukan"
            return jsonify({
                'pertanyaan': user_input,
                'jawaban': predicted_answer,
                'status': 'ok'
            })
        
        similar_questions = [pertanyaan_list[i] for i in top_indices]
        return jsonify({
            'pertanyaan': user_input,
            'opsi_pertanyaan': similar_questions,
            'jawaban': "Pertanyaan mana yang kamu maksud?",
            'status': 'ambigu'
        })
    
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

# ===================== ENDPOINT AUTHENTICATION =====================
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Username dan password harus diisi', 'authenticated': False}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT id, username, password, email, full_name, role, is_active FROM admin WHERE username = %s",
            (username,)
        )
        admin = cursor.fetchone()
        
        ip_address = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        
        if not admin:
            cursor.execute(
                "INSERT INTO login_logs (username, ip_address, user_agent, login_status, failed_reason) VALUES (%s, %s, %s, %s, %s)",
                (username, ip_address, user_agent, 'failed', 'Username tidak ditemukan')
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username atau password salah', 'authenticated': False}), 401
        
        if not admin['is_active']:
            cursor.execute(
                "INSERT INTO login_logs (admin_id, username, ip_address, user_agent, login_status, failed_reason) VALUES (%s, %s, %s, %s, %s, %s)",
                (admin['id'], username, ip_address, user_agent, 'failed', 'Akun tidak aktif')
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'error': 'Akun Anda telah dinonaktifkan. Hubungi administrator.', 'authenticated': False}), 401
        
        if not verify_password(password, admin['password']):
            cursor.execute(
                "INSERT INTO login_logs (admin_id, username, ip_address, user_agent, login_status, failed_reason) VALUES (%s, %s, %s, %s, %s, %s)",
                (admin['id'], username, ip_address, user_agent, 'failed', 'Password salah')
            )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username atau password salah', 'authenticated': False}), 401
        
        token = generate_token(admin['id'], admin['username'], admin['role'])
        
        expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        cursor.execute(
            "INSERT INTO admin_sessions (admin_id, session_token, ip_address, user_agent, expires_at) VALUES (%s, %s, %s, %s, %s)",
            (admin['id'], token, ip_address, user_agent, expires_at)
        )
        
        cursor.execute("UPDATE admin SET last_login = NOW() WHERE id = %s", (admin['id'],))
        
        cursor.execute(
            "INSERT INTO login_logs (admin_id, username, ip_address, user_agent, login_status) VALUES (%s, %s, %s, %s, %s)",
            (admin['id'], username, ip_address, user_agent, 'success')
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        admin_data = {
            'id': admin['id'],
            'username': admin['username'],
            'email': admin['email'],
            'full_name': admin['full_name'],
            'role': admin['role']
        }
        
        return jsonify({
            'message': 'Login berhasil',
            'authenticated': True,
            'token': token,
            'admin': admin_data,
            'expires_in': JWT_EXPIRATION_HOURS * 3600
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Login: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Terjadi kesalahan saat login', 'authenticated': False}), 500

@app.route('/logout', methods=['POST'])
@token_required
def logout():
    try:
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_sessions WHERE session_token = %s", (token,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Logout berhasil', 'authenticated': False}), 200
        
    except Exception as e:
        print(f"[ERROR] Logout: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat logout'}), 500

@app.route('/verify-token', methods=['GET'])
def verify_token_endpoint():
    try:
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'authenticated': False, 'error': 'Token tidak ditemukan'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_token(token)
        
        if not payload:
            return jsonify({'authenticated': False, 'error': 'Token tidak valid atau sudah kadaluarsa'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_sessions WHERE session_token = %s AND expires_at > NOW()", (token,))
        session = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not session:
            return jsonify({'authenticated': False, 'error': 'Session tidak ditemukan'}), 401
        
        return jsonify({
            'authenticated': True,
            'admin_id': payload['admin_id'],
            'username': payload['username'],
            'role': payload['role']
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Verify token: {e}")
        return jsonify({'authenticated': False, 'error': str(e)}), 500

# ===================== ENDPOINT KELOLA ADMIN (HANYA SUPER ADMIN) =====================
@app.route('/api/admins', methods=['GET'])
@token_required
def get_all_admins():
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk mengakses halaman ini'}), 403
        
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        search = request.args.get('search', default='', type=str)
        
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT id, username, email, full_name, role, is_active, last_login, created_at FROM admin WHERE 1=1"
        params = []
        
        if search:
            query += " AND (username LIKE %s OR email LIKE %s OR full_name LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        admins = cursor.fetchall()
        
        count_query = "SELECT COUNT(*) as total FROM admin WHERE 1=1"
        count_params = []
        
        if search:
            count_query += " AND (username LIKE %s OR email LIKE %s OR full_name LIKE %s)"
            count_params.extend([search_param, search_param, search_param])
        
        cursor.execute(count_query, count_params)
        total_data = cursor.fetchone()['total']
        total_pages = (total_data + per_page - 1) // per_page
        
        for admin in admins:
            if admin['last_login']:
                admin['last_login'] = admin['last_login'].strftime('%Y-%m-%d %H:%M:%S')
            if admin['created_at']:
                admin['created_at'] = admin['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total_data,
            'total_pages': total_pages,
            'data': admins
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Get all admins: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admins', methods=['POST'])
@token_required
def create_admin():
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk membuat admin baru'}), 403
        
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'admin')
        is_active = data.get('is_active', True)
        
        if not username or not password or not email or not full_name:
            return jsonify({'error': 'Semua field harus diisi'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM admin WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username sudah digunakan'}), 409
        
        cursor.execute("SELECT id FROM admin WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Email sudah digunakan'}), 409
        
        hashed_password = hash_password(password)
        
        cursor.execute("""
            INSERT INTO admin (username, password, email, full_name, role, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, hashed_password, email, full_name, role, is_active))
        
        conn.commit()
        new_id = cursor.lastrowid
        
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Admin berhasil dibuat', 'admin_id': new_id}), 201
        
    except Exception as e:
        print(f"[ERROR] Create admin: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admins/<int:admin_id>', methods=['PUT'])
@token_required
def update_admin(admin_id):
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk mengupdate admin'}), 403
        
        data = request.json
        email = data.get('email', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'admin')
        is_active = data.get('is_active', True)
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM admin WHERE id = %s", (admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        cursor.execute("SELECT id FROM admin WHERE email = %s AND id != %s", (email, admin_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Email sudah digunakan oleh admin lain'}), 409
        
        cursor.execute("""
            UPDATE admin SET email = %s, full_name = %s, role = %s, is_active = %s, updated_at = NOW()
            WHERE id = %s
        """, (email, full_name, role, is_active, admin_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Admin berhasil diupdate'}), 200
        
    except Exception as e:
        print(f"[ERROR] Update admin: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admins/<int:admin_id>/reset-password', methods=['POST'])
@token_required
def reset_admin_password(admin_id):
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk reset password'}), 403
        
        data = request.json
        new_password = data.get('new_password', '').strip()
        
        if not new_password or len(new_password) < 6:
            return jsonify({'error': 'Password minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM admin WHERE id = %s", (admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        hashed_password = hash_password(new_password)
        cursor.execute("UPDATE admin SET password = %s, updated_at = NOW() WHERE id = %s", (hashed_password, admin_id))
        conn.commit()
        
        cursor.execute("DELETE FROM admin_sessions WHERE admin_id = %s", (admin_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Password berhasil direset'}), 200
        
    except Exception as e:
        print(f"[ERROR] Reset password: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admins/<int:admin_id>', methods=['DELETE'])
@token_required
def delete_admin(admin_id):
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk menghapus admin'}), 403
        
        if request.admin['admin_id'] == admin_id:
            return jsonify({'error': 'Anda tidak dapat menghapus akun Anda sendiri'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM admin WHERE id = %s", (admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        cursor.execute("DELETE FROM admin_sessions WHERE admin_id = %s", (admin_id,))
        cursor.execute("DELETE FROM login_logs WHERE admin_id = %s", (admin_id,))
        cursor.execute("DELETE FROM admin WHERE id = %s", (admin_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Admin berhasil dihapus'}), 200
        
    except Exception as e:
        print(f"[ERROR] Delete admin: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile', methods=['GET'])
@token_required
def get_current_admin_profile():
    try:
        admin_id = request.admin['admin_id']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, username, email, full_name, role, is_active, last_login, created_at 
            FROM admin WHERE id = %s
        """, (admin_id,))
        admin = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if admin:
            if admin['last_login']:
                admin['last_login'] = admin['last_login'].strftime('%Y-%m-%d %H:%M:%S')
            if admin['created_at']:
                admin['created_at'] = admin['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({'admin': admin}), 200
        
    except Exception as e:
        print(f"[ERROR] Get profile: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK UNKNOWN QUESTIONS =====================
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

@app.route('/delete-unknown', methods=['DELETE'])
def delete_unknown():
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
        
        return jsonify({'message': 'Pertanyaan berhasil dihapus', 'status': 'success'}), 200
        
    except Exception as e:
        print(f"[ERROR] Delete unknown: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete-all-unknown', methods=['DELETE'])
def delete_all_unknown():
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
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Delete all unknown: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT KELOLA DATASET =====================
@app.route('/tambah-data', methods=['POST'])
def tambah_data():
    try:
        data = request.json
        pertanyaan_baru = data.get('pertanyaan', '').strip()
        jawaban_baru = data.get('jawaban', '').strip()
        kategori_baru = data.get('kategori', '').strip()
        
        if not pertanyaan_baru or not jawaban_baru or not kategori_baru:
            return jsonify({'error': 'Semua field harus diisi'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        df_existing = pd.read_csv(csv_path, encoding='utf-8')
        df_new = pd.DataFrame([{
            'pertanyaan': pertanyaan_baru,
            'jawaban': jawaban_baru,
            'kategori': kategori_baru
        }])
        
        if pertanyaan_baru.lower() in df_existing['pertanyaan'].str.lower().values:
            return jsonify({'error': f'Pertanyaan "{pertanyaan_baru}" sudah ada di dataset', 'status': 'duplicate'}), 409
        
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.to_csv(csv_path, index=False, encoding='utf-8')
        
        return jsonify({
            'message': 'Data berhasil ditambahkan ke CSV. Silakan latih model untuk mengupdate chatbot.',
            'data': {'pertanyaan': pertanyaan_baru, 'jawaban': jawaban_baru, 'kategori': kategori_baru},
            'status': 'success'
        }), 201
        
    except Exception as e:
        print(f"[ERROR] Tambah data: {e}")
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

@app.route('/get-all-data', methods=['GET'])
def get_all_data():
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        search = request.args.get('search', default='', type=str)
        kategori_filter = request.args.get('kategori', default='', type=str)
        
        offset = (page - 1) * per_page
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        
        if search:
            df_temp = df_temp[df_temp['pertanyaan'].str.contains(search, case=False, na=False)]
        
        if kategori_filter:
            df_temp = df_temp[df_temp['kategori'] == kategori_filter]
        
        total_data = len(df_temp)
        total_pages = (total_data + per_page - 1) // per_page
        
        df_paginated = df_temp.iloc[offset:offset + per_page]
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
        
        df_temp.at[index, 'pertanyaan'] = pertanyaan_baru
        df_temp.at[index, 'jawaban'] = jawaban_baru
        df_temp.at[index, 'kategori'] = kategori_baru
        
        df_temp.to_csv(csv_path, index=False, encoding='utf-8')
        
        return jsonify({'message': 'Data berhasil diupdate', 'status': 'success'}), 200
        
    except Exception as e:
        print(f"[ERROR] Update data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete-data', methods=['DELETE'])
def delete_data():
    try:
        data = request.json
        index = data.get('index')
        
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        
        if index < 0 or index >= len(df_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        df_temp = df_temp.drop(index).reset_index(drop=True)
        df_temp.to_csv(csv_path, index=False, encoding='utf-8')
        
        return jsonify({'message': 'Data berhasil dihapus', 'status': 'success'}), 200
        
    except Exception as e:
        print(f"[ERROR] Delete data: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT TRAINING MODEL =====================
@app.route('/train-model', methods=['POST'])
def train_model():
    try:
        start_time = time.time()
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        print("[TRAIN] Loading dataset...")
        df_train = pd.read_csv(csv_path, encoding='utf-8')
        
        print("[TRAIN] Preprocessing data...")
        df_train['processed'] = df_train['pertanyaan'].astype(str).apply(preprocess)
        
        X_train = df_train['processed']
        y_train = list(range(len(df_train)))
        
        print("[TRAIN] Vectorizing text...")
        vectorizer = TfidfVectorizer()
        X_train_tfidf = vectorizer.fit_transform(X_train)
        
        print("[TRAIN] Training SVM model...")
        model = LinearSVC()
        model.fit(X_train_tfidf, y_train)
        
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
        
        global model_qa, vectorizer_qa, answers, pertanyaan_list, df
        model_qa = model
        vectorizer_qa = vectorizer
        answers = df_train['jawaban'].tolist()
        pertanyaan_list = df_train['pertanyaan'].tolist()
        df = df_train
        
        training_time = time.time() - start_time
        
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
        return jsonify({'error': f'Terjadi kesalahan saat training: {str(e)}'}), 500

# ===================== ENDPOINT KATEGORI & INFO =====================
@app.route('/kategori', methods=['GET'])
def get_kategori():
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

# ===================== ENDPOINT DEBUG =====================
@app.route('/cek-csv', methods=['GET'])
def cek_csv():
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        import csv
        reader = csv.reader(lines)
        rows = list(reader)
        
        return jsonify({
            'total_lines': len(lines),
            'total_rows': len(rows),
            'last_5_rows': rows[-5:] if len(rows) >= 5 else rows,
            'file_path': csv_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fix-csv', methods=['POST'])
def fix_csv():
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8', on_bad_lines='skip')
        
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

if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT)