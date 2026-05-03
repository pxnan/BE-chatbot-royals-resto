import pickle
import mysql.connector
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import re
import csv
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import bcrypt
import jwt
from functools import wraps
import secrets
import time
import numpy as np
from dotenv import load_dotenv

# ===================== Load .env =====================
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

FLASK_ENV = os.getenv("FLASK_ENV")
FLASK_DEBUG = os.getenv("FLASK_DEBUG")
FLASK_PORT = int(os.getenv("FLASK_PORT", 8080))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

# ===================== Konfigurasi API Key =====================
API_KEY = os.getenv("API_KEY", "RoyalsResto2024SecureKey!@#$")
API_KEY_HEADER = "X-API-Key"

# ===================== Konfigurasi JWT =====================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "royal_resto_chatbot_secret_key_2024")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

# ===================== FUNGSI PREPROCESSING (Tanpa NLTK) =====================
def preprocess(text):
    """
    Preprocessing teks tanpa NLTK - hanya menggunakan regex dan string methods
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters, keep only alphanumeric and spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove numbers (opsional, bisa dihapus jika ingin mempertahankan angka)
    text = re.sub(r'\d+', '', text)
    
    return text

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

def api_key_required(f):
    """Decorator untuk memproteksi endpoint dengan API Key"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get(API_KEY_HEADER)
        
        if not api_key:
            return jsonify({'error': 'API Key tidak ditemukan', 'authenticated': False}), 401
        
        if api_key != API_KEY:
            return jsonify({'error': 'API Key tidak valid', 'authenticated': False}), 401
        
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

# ===================== FUNGSI LOAD DATASET (Tanpa Pandas) =====================
def load_dataset_from_csv(csv_path):
    """
    Load dataset dari CSV tanpa pandas - menggunakan csv module
    """
    pertanyaan_list = []
    jawaban_list = []
    kategori_list = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pertanyaan_list.append(row.get('pertanyaan', ''))
                jawaban_list.append(row.get('jawaban', ''))
                kategori_list.append(row.get('kategori', ''))
    except FileNotFoundError:
        print(f"[WARNING] File not found: {csv_path}")
        # Buat file CSV default jika tidak ada
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
            writer.writerow(['Halo', 'Halo! Selamat datang di Royal\'s Resto. Ada yang bisa saya bantu?', 'sapaan'])
            writer.writerow(['Menu apa saja yang tersedia?', 'Kami menyediakan berbagai macam masakan Nusantara dan Internasional.', 'menu'])
        # Load ulang setelah buat file
        return load_dataset_from_csv(csv_path)
    except Exception as e:
        print(f"[ERROR] Load CSV: {e}")
        
    return pertanyaan_list, jawaban_list, kategori_list

def save_dataset_to_csv(csv_path, pertanyaan_list, jawaban_list, kategori_list):
    """
    Save dataset ke CSV tanpa pandas
    """
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
        for p, j, k in zip(pertanyaan_list, jawaban_list, kategori_list):
            writer.writerow([p, j, k])

# ===================== Load Dataset Awal =====================
csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
pertanyaan_list, answers, kategori_list = load_dataset_from_csv(csv_path)

# ===================== LOAD MODEL (Jika ada) =====================
model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
model_qa = None
vectorizer_qa = None

if os.path.exists(model_path):
    try:
        with open(model_path, 'rb') as f:
            qa_data = pickle.load(f)
        model_qa = qa_data.get('model')
        vectorizer_qa = qa_data.get('vectorizer')
        answers = qa_data.get('answers', answers)
        pertanyaan_list = qa_data.get('questions', pertanyaan_list)
        print("[INFO] Model loaded successfully")
    except Exception as e:
        print(f"[WARNING] Could not load model: {e}")

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

# ===================== ENDPOINT CHATBOT (dengan API Key) =====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
@api_key_required
def chat():
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    processed_input = preprocess(user_input)
    
    # Jika model belum ada, beri respons default
    if model_qa is None or vectorizer_qa is None:
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': "Maaf, model belum dilatih. Silakan lakukan training terlebih dahulu di halaman admin.",
            'status': 'error'
        })
    
    X_input_qa = vectorizer_qa.transform([processed_input])

    if X_input_qa.nnz == 0:
        save_unknown_question(user_input)
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': "Mohon maaf, saya belum mengerti pertanyaan Anda. Tim kami akan segera mempelajari pertanyaan ini.",
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
        predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda. Tim kami akan segera mempelajari pertanyaan ini."
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
        
        similar_questions = [pertanyaan_list[i] for i in top_indices if i < len(pertanyaan_list)]
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
@api_key_required
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
@api_key_required
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
@api_key_required
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

@app.route('/change-password', methods=['POST'])
@api_key_required
@token_required
def change_password():
    try:
        data = request.json
        old_password = data.get('old_password', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        if not old_password or not new_password or not confirm_password:
            return jsonify({'error': 'Semua field harus diisi'}), 400
        
        if new_password != confirm_password:
            return jsonify({'error': 'Password baru tidak cocok'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'Password minimal 6 karakter'}), 400
        
        admin_id = request.admin['admin_id']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT password FROM admin WHERE id = %s", (admin_id,))
        admin = cursor.fetchone()
        
        if not admin:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        if not verify_password(old_password, admin['password']):
            cursor.close()
            conn.close()
            return jsonify({'error': 'Password lama salah'}), 401
        
        new_password_hash = hash_password(new_password)
        
        cursor.execute(
            "UPDATE admin SET password = %s, updated_at = NOW() WHERE id = %s",
            (new_password_hash, admin_id)
        )
        conn.commit()
        
        current_token = request.headers.get('Authorization')
        if current_token and current_token.startswith('Bearer '):
            current_token = current_token[7:]
        
        cursor.execute(
            "DELETE FROM admin_sessions WHERE admin_id = %s AND session_token != %s",
            (admin_id, current_token)
        )
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Password berhasil diubah'}), 200
        
    except Exception as e:
        print(f"[ERROR] Change password: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat mengganti password'}), 500

# ===================== ENDPOINT KELOLA ADMIN (HANYA SUPER ADMIN) =====================
@app.route('/api/admins', methods=['GET'])
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
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
@api_key_required
def tambah_data():
    try:
        data = request.json
        pertanyaan_baru = data.get('pertanyaan', '').strip()
        jawaban_baru = data.get('jawaban', '').strip()
        kategori_baru = data.get('kategori', '').strip()
        
        if not pertanyaan_baru or not jawaban_baru or not kategori_baru:
            return jsonify({'error': 'Semua field harus diisi'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        # Check duplicate
        if pertanyaan_baru.lower() in [p.lower() for p in pertanyaan_list_temp]:
            return jsonify({'error': f'Pertanyaan "{pertanyaan_baru}" sudah ada di dataset', 'status': 'duplicate'}), 409
        
        # Add new data
        pertanyaan_list_temp.append(pertanyaan_baru)
        jawaban_list_temp.append(jawaban_baru)
        kategori_list_temp.append(kategori_baru)
        
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
        return jsonify({
            'message': 'Data berhasil ditambahkan ke CSV. Silakan latih model untuk mengupdate chatbot.',
            'data': {'pertanyaan': pertanyaan_baru, 'jawaban': jawaban_baru, 'kategori': kategori_baru},
            'status': 'success'
        }), 201
        
    except Exception as e:
        print(f"[ERROR] Tambah data: {e}")
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

@app.route('/get-all-data', methods=['GET'])
@api_key_required
def get_all_data():
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        search = request.args.get('search', default='', type=str)
        kategori_filter = request.args.get('kategori', default='', type=str)
        
        offset = (page - 1) * per_page
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        # Filter data
        filtered_pertanyaan = []
        filtered_jawaban = []
        filtered_kategori = []
        filtered_indices = []
        
        for i, (p, j, k) in enumerate(zip(pertanyaan_temp, jawaban_temp, kategori_temp)):
            if search and search.lower() not in p.lower():
                continue
            if kategori_filter and k != kategori_filter:
                continue
            filtered_pertanyaan.append(p)
            filtered_jawaban.append(j)
            filtered_kategori.append(k)
            filtered_indices.append(i)
        
        total_data = len(filtered_pertanyaan)
        total_pages = (total_data + per_page - 1) // per_page
        
        # Pagination
        end_idx = min(offset + per_page, total_data)
        data = []
        for i in range(offset, end_idx):
            data.append({
                'index': filtered_indices[i],
                'pertanyaan': filtered_pertanyaan[i],
                'jawaban': filtered_jawaban[i],
                'kategori': filtered_kategori[i]
            })
        
        # Get unique categories
        unique_categories = list(set(kategori_temp))
        
        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total_data,
            'total_pages': total_pages,
            'data': data,
            'categories': sorted(unique_categories)
        })
        
    except Exception as e:
        print(f"[ERROR] Get all data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update-data', methods=['PUT'])
@api_key_required
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
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_list_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        pertanyaan_list_temp[index] = pertanyaan_baru
        jawaban_list_temp[index] = jawaban_baru
        kategori_list_temp[index] = kategori_baru
        
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
        return jsonify({'message': 'Data berhasil diupdate', 'status': 'success'}), 200
        
    except Exception as e:
        print(f"[ERROR] Update data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete-data', methods=['DELETE'])
@api_key_required
def delete_data():
    try:
        data = request.json
        index = data.get('index')
        
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_list_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        del pertanyaan_list_temp[index]
        del jawaban_list_temp[index]
        del kategori_list_temp[index]
        
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
        return jsonify({'message': 'Data berhasil dihapus', 'status': 'success'}), 200
        
    except Exception as e:
        print(f"[ERROR] Delete data: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT TRAINING MODEL =====================
@app.route('/train-model', methods=['POST'])
@api_key_required
def train_model():
    try:
        start_time = time.time()
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Load dataset tanpa pandas
        pertanyaan_list_train, jawaban_list_train, kategori_list_train = load_dataset_from_csv(csv_path)
        
        if len(pertanyaan_list_train) == 0:
            return jsonify({'error': 'Dataset kosong. Silakan tambah data terlebih dahulu.'}), 400
        
        print(f"[TRAIN] Loading {len(pertanyaan_list_train)} questions...")
        
        # Preprocessing
        processed_list = [preprocess(q) for q in pertanyaan_list_train]
        
        # Vectorizing
        vectorizer = TfidfVectorizer()
        X_train_tfidf = vectorizer.fit_transform(processed_list)
        
        # Training
        y_train = list(range(len(pertanyaan_list_train)))
        model = LinearSVC()
        model.fit(X_train_tfidf, y_train)
        
        # Saving model
        qa_data_new = {
            'model': model,
            'vectorizer': vectorizer,
            'answers': jawaban_list_train,
            'questions': pertanyaan_list_train,
            'categories': kategori_list_train
        }
        
        model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        with open(model_path, 'wb') as f:
            pickle.dump(qa_data_new, f)
        
        # Update global variables
        global model_qa, vectorizer_qa, answers, pertanyaan_list
        model_qa = model
        vectorizer_qa = vectorizer
        answers = jawaban_list_train
        pertanyaan_list = pertanyaan_list_train
        
        training_time = time.time() - start_time
        
        return jsonify({
            'message': 'Model berhasil dilatih',
            'training_time': f'{training_time:.2f} detik',
            'total_data': len(pertanyaan_list_train),
            'total_questions': len(pertanyaan_list_train),
            'categories_count': len(set(kategori_list_train)),
            'status': 'success'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Train model: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Terjadi kesalahan saat training: {str(e)}'}), 500

# ===================== ENDPOINT KATEGORI & INFO =====================
@app.route('/kategori', methods=['GET'])
@api_key_required
def get_kategori():
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        _, _, kategori_list_temp = load_dataset_from_csv(csv_path)
        categories = sorted(list(set(kategori_list_temp)))
        return jsonify({'kategori': categories})
    except Exception as e:
        print(f"[ERROR] Get kategori: {e}")
        return jsonify({'error': 'Gagal mengambil daftar kategori'}), 500

@app.route('/model-info', methods=['GET'])
@api_key_required
def model_info():
    try:
        return jsonify({
            'total_questions': len(pertanyaan_list),
            'total_answers': len(answers),
            'categories': sorted(list(set(kategori_list))) if kategori_list else [],
            'model_loaded': model_qa is not None,
            'vectorizer_loaded': vectorizer_qa is not None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT DEBUG =====================
@app.route('/cek-csv', methods=['GET'])
@api_key_required
def cek_csv():
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
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
@api_key_required
def fix_csv():
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Baca CSV dengan csv module
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        # Backup
        backup_path = csv_path.replace('.csv', '_backup.csv')
        import shutil
        if os.path.exists(csv_path):
            shutil.copy(csv_path, backup_path)
        
        # Simpan ulang
        save_dataset_to_csv(csv_path, pertanyaan_temp, jawaban_temp, kategori_temp)
        
        return jsonify({
            'message': 'CSV berhasil diperbaiki',
            'backup_path': backup_path,
            'total_rows': len(pertanyaan_temp)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK GENERATE API KEY (HANYA SUPER ADMIN) =====================
@app.route('/api/generate-api-key', methods=['POST'])
@token_required
def generate_new_api_key():
    """Endpoint untuk generate API Key baru (hanya super admin)"""
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk generate API Key'}), 403
        
        # Generate API Key baru
        new_api_key = secrets.token_hex(32)
        
        # Untuk sementara, return key nya saja
        return jsonify({
            'message': 'API Key baru berhasil digenerate',
            'api_key': new_api_key
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Generate API Key: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== MAIN =====================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Royal's Resto Chatbot API Server (Optimized Version)")
    print("=" * 50)
    print(f"📡 Server running on: http://localhost:{FLASK_PORT}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"📊 Dataset path: {csv_path}")
    print(f"🤖 Model path: {model_path}")
    print("⚠️  Semua endpoint memerlukan API Key di header: X-API-Key")
    print("=" * 50)
    
    # Buat folder yang diperlukan jika belum ada
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    app.run(debug=FLASK_DEBUG == 'True', port=FLASK_PORT, host='0.0.0.0')