import pickle
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
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
import secrets

# ===================== Load .env =====================
load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

FLASK_ENV = os.getenv("FLASK_ENV", "development")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://royals-resto-bot.vercel.app").split(",")

# ===================== Konfigurasi API Key =====================
API_KEY = os.getenv("API_KEY", "RoyalsResto2024SecureKey!@#$")
API_KEY_HEADER = "X-API-Key"

# ===================== Konfigurasi JWT =====================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "royal_resto_chatbot_secret_key_2024")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

# ===================== Inisialisasi Flask =====================
app = Flask(__name__)

# ===================== KONFIGURASI CORS YANG BENAR =====================
# Izinkan semua origin untuk development
CORS(app, 
    origins=ALLOWED_ORIGINS,
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Requested-With"],
    supports_credentials=False,
    max_age=86400)

# ===================== HANDLE PREFLIGHT REQUEST MANUAL =====================
@app.before_request
def handle_preflight():
    """Handle preflight OPTIONS request untuk semua route"""
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key, X-Requested-With")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH")
        response.headers.add("Access-Control-Allow-Credentials", "false")
        response.headers.add("Access-Control-Max-Age", "86400")
        return response, 200

# ===================== Helper Functions =====================
def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(admin_id, username, role):
    payload = {
        'admin_id': admin_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except:
        return None

def token_required(f):
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
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip API key check untuk development (optional)
        if FLASK_ENV == "development":
            return f(*args, **kwargs)
        
        api_key = request.headers.get(API_KEY_HEADER)
        
        if not api_key:
            return jsonify({'error': 'API Key tidak ditemukan', 'authenticated': False}), 401
        
        if api_key != API_KEY:
            return jsonify({'error': 'API Key tidak valid', 'authenticated': False}), 401
        
        return f(*args, **kwargs)
    return decorated

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip = request.remote_addr
    return ip

# ===================== Database Connection =====================
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"[DB ERROR] Connection failed: {e}")
        raise

def get_db_cursor(conn, dictionary=True):
    if dictionary:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

# ===================== Load Model =====================
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

kategori_list = df['kategori'].tolist() if 'kategori' in df.columns else []

# ===================== Save Unknown Question =====================
def save_unknown_question(question):
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=False)
        query = "INSERT INTO pertanyaan_unknow (pertanyaan) VALUES (%s)"
        cursor.execute(query, (question,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

# ===================== FUNGSI HELPER UNTUK CSV =====================
def load_dataset_from_csv(csv_path):
    """Load dataset dari CSV file"""
    pertanyaan_list_temp = []
    jawaban_list_temp = []
    kategori_list_temp = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) >= 3:
                    pertanyaan_list_temp.append(row[0])
                    jawaban_list_temp.append(row[1])
                    kategori_list_temp.append(row[2])
                elif len(row) == 2:
                    pertanyaan_list_temp.append(row[0])
                    jawaban_list_temp.append(row[1])
                    kategori_list_temp.append('umum')
                elif len(row) == 1:
                    pertanyaan_list_temp.append(row[0])
                    jawaban_list_temp.append('')
                    kategori_list_temp.append('umum')
    except FileNotFoundError:
        print(f"[WARNING] File {csv_path} not found, creating new file")
        # Create header
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
    
    return pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp

def save_dataset_to_csv(csv_path, pertanyaan_list, jawaban_list, kategori_list):
    """Save dataset ke CSV file"""
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
        for p, j, k in zip(pertanyaan_list, jawaban_list, kategori_list):
            writer.writerow([p, j, k])

# ===================== ENDPOINTS =====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cek-csv', methods=['GET', 'OPTIONS'])
def cek_csv():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
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

@app.route('/chat', methods=['POST', 'OPTIONS'])
@api_key_required
def chat():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
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

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Username dan password harus diisi', 'authenticated': False}), 400
        
        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=True)
        
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
        return jsonify({'error': 'Terjadi kesalahan saat login', 'authenticated': False}), 500

# ==================== ENDPOINT LAINNYA (tambahkan OPTIONS handler) ====================
@app.route('/kategori', methods=['GET', 'OPTIONS'])
@api_key_required
def get_kategori():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        df_temp = pd.read_csv(csv_path, encoding='utf-8')
        categories = sorted(df_temp['kategori'].unique().tolist())
        return jsonify({'kategori': categories})
    except Exception as e:
        print(f"[ERROR] Get kategori: {e}")
        return jsonify({'error': 'Gagal mengambil daftar kategori'}), 500

@app.route('/model-info', methods=['GET', 'OPTIONS'])
@api_key_required
def model_info():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
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

@app.route('/pertanyaan-unknown', methods=['GET', 'OPTIONS'])
@api_key_required
def get_unknown_questions():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=True)

        cursor.execute(
            "SELECT * FROM pertanyaan_unknow ORDER BY id DESC LIMIT %s OFFSET %s",
            (per_page, offset)
        )
        data = cursor.fetchall()

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

@app.route('/get-all-data', methods=['GET', 'OPTIONS'])
@api_key_required
def get_all_data():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
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

# ==================== ENDPOINT UNTUK KELOLA ADMIN ====================
@app.route('/api/admins', methods=['GET', 'OPTIONS'])
@api_key_required
@token_required
def get_all_admins():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        # Hanya super admin yang bisa mengakses
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk mengakses halaman ini'}), 403
        
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        search = request.args.get('search', default='', type=str)
        
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=True)
        
        query = "SELECT id, username, email, full_name, role, is_active, last_login, created_at FROM admin WHERE 1=1"
        params = []
        
        if search:
            query += " AND (username ILIKE %s OR email ILIKE %s OR full_name ILIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        admins = cursor.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM admin WHERE 1=1"
        count_params = []
        
        if search:
            count_query += " AND (username ILIKE %s OR email ILIKE %s OR full_name ILIKE %s)"
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

@app.route('/api/admins', methods=['POST', 'OPTIONS'])
@api_key_required
@token_required
def create_admin():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
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
        cursor = get_db_cursor(conn, dictionary=True)
        
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

@app.route('/api/admins/<int:admin_id>', methods=['PUT', 'OPTIONS'])
@api_key_required
@token_required
def update_admin(admin_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk mengupdate admin'}), 403
        
        data = request.json
        email = data.get('email', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'admin')
        is_active = data.get('is_active', True)
        
        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=True)
        
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

@app.route('/api/admins/<int:admin_id>/reset-password', methods=['POST', 'OPTIONS'])
@api_key_required
@token_required
def reset_admin_password(admin_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk reset password'}), 403
        
        data = request.json
        new_password = data.get('new_password', '').strip()
        
        if not new_password or len(new_password) < 6:
            return jsonify({'error': 'Password minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=True)
        
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

@app.route('/api/admins/<int:admin_id>', methods=['DELETE', 'OPTIONS'])
@api_key_required
@token_required
def delete_admin(admin_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk menghapus admin'}), 403
        
        if request.admin['admin_id'] == admin_id:
            return jsonify({'error': 'Anda tidak dapat menghapus akun Anda sendiri'}), 400
        
        conn = get_db_connection()
        cursor = get_db_cursor(conn, dictionary=True)
        
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
    
# ===================== ENDPOINT UNTUK ADMIN PROFILE =====================
@app.route('/admin-profile', methods=['GET', 'OPTIONS'])
@api_key_required
@token_required
def get_admin_profile():
    """Endpoint untuk mendapatkan profil admin yang sedang login"""
    if request.method == 'OPTIONS':
        return '', 200
        
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
        
        if not admin:
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        # Format datetime
        if admin['last_login']:
            admin['last_login'] = admin['last_login'].strftime('%Y-%m-%d %H:%M:%S')
        if admin['created_at']:
            admin['created_at'] = admin['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({'admin': admin}), 200
        
    except Exception as e:
        print(f"[ERROR] Get admin profile: {e}")
        return jsonify({'error': 'Terjadi kesalahan'}), 500

# ===================== ENDPOINT UNTUK GET SINGLE DATA =====================
@app.route('/get-data/<int:index>', methods=['GET', 'OPTIONS'])
@api_key_required
def get_data_by_index(index):
    """Endpoint untuk mendapatkan data berdasarkan index"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_list_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        return jsonify({
            'index': index,
            'pertanyaan': pertanyaan_list_temp[index],
            'jawaban': jawaban_list_temp[index],
            'kategori': kategori_list_temp[index]
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Get data by index: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK BULK DELETE =====================
@app.route('/delete-bulk-data', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_bulk_data():
    """Endpoint untuk menghapus multiple data sekaligus"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        indices = data.get('indices', [])
        
        if not indices:
            return jsonify({'error': 'Tidak ada index yang dipilih'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        # Hapus dari index terbesar ke terkecil agar tidak mengganggu urutan
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(pertanyaan_list_temp):
                del pertanyaan_list_temp[index]
                del jawaban_list_temp[index]
                del kategori_list_temp[index]
        
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
        return jsonify({
            'message': f'{len(indices)} data berhasil dihapus',
            'status': 'success',
            'deleted_count': len(indices)
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Delete bulk data: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK REGISTER ADMIN BARU =====================
@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register_admin():
    """Endpoint untuk registrasi admin baru (tanpa token)"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()
        full_name = data.get('full_name', '').strip()
        
        if not username or not password or not email or not full_name:
            return jsonify({'error': 'Semua field harus diisi'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Cek username sudah ada
        cursor.execute("SELECT id FROM admin WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username sudah digunakan'}), 409
        
        # Cek email sudah ada
        cursor.execute("SELECT id FROM admin WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Email sudah digunakan'}), 409
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Insert admin baru (default role = admin)
        cursor.execute("""
            INSERT INTO admin (username, password, email, full_name, role, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, hashed_password, email, full_name, 'admin', True))
        
        conn.commit()
        new_id = cursor.lastrowid
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Registrasi berhasil, silakan login',
            'admin_id': new_id
        }), 201
        
    except Exception as e:
        print(f"[ERROR] Register admin: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK STATISTIK DASHBOARD =====================
@app.route('/api/stats', methods=['GET', 'OPTIONS'])
@api_key_required
def get_dashboard_stats():
    """Endpoint untuk mendapatkan statistik dashboard"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        # Total admin
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM admin")
        total_admin = cursor.fetchone()['total']
        
        # Total admin aktif
        cursor.execute("SELECT COUNT(*) as total FROM admin WHERE is_active = true")
        total_active_admin = cursor.fetchone()['total']
        
        # Total unknown questions
        cursor.execute("SELECT COUNT(*) as total FROM pertanyaan_unknow")
        total_unknown = cursor.fetchone()['total']
        
        # Total login hari ini
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) as total FROM login_logs 
            WHERE login_status = 'success' AND DATE(login_time) = %s
        """, (today,))
        today_logins = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_admin': total_admin,
            'total_active_admin': total_active_admin,
            'total_unknown_questions': total_unknown,
            'today_logins': today_logins,
            'total_questions': len(pertanyaan_list),
            'total_categories': len(set(kategori_list)) if kategori_list else 0,
            'model_loaded': model_qa is not None
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Get stats: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK EXPORT DATA =====================
@app.route('/api/export-data', methods=['GET', 'OPTIONS'])
@api_key_required
def export_data():
    """Endpoint untuk export data dataset ke format CSV"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Baca file CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return sebagai file download
        from flask import Response
        return Response(
            content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=dataset_export.csv'}
        ), 200
        
    except Exception as e:
        print(f"[ERROR] Export data: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK SEARCH DATA =====================
@app.route('/api/search-data', methods=['GET', 'OPTIONS'])
@api_key_required
def search_data():
    """Endpoint untuk pencarian data dengan filter"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        query = request.args.get('q', '').strip()
        kategori = request.args.get('kategori', '').strip()
        
        if not query:
            return jsonify({'data': [], 'total': 0}), 200
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        results = []
        for i, (p, j, k) in enumerate(zip(pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)):
            if query.lower() in p.lower():
                if kategori and k != kategori:
                    continue
                results.append({
                    'index': i,
                    'pertanyaan': p,
                    'jawaban': j,
                    'kategori': k
                })
        
        return jsonify({
            'data': results[:50],  # Batasi 50 hasil
            'total': len(results)
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Search data: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK LOGIN LOGS =====================
@app.route('/api/login-logs', methods=['GET', 'OPTIONS'])
@api_key_required
@token_required
def get_login_logs():
    """Endpoint untuk mendapatkan log login (hanya super admin)"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk mengakses halaman ini'}), 403
        
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT l.*, a.username as admin_username 
            FROM login_logs l
            LEFT JOIN admin a ON l.admin_id = a.id
            ORDER BY l.login_time DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        logs = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as total FROM login_logs")
        total_data = cursor.fetchone()['total']
        total_pages = (total_data + per_page - 1) // per_page
        
        cursor.close()
        conn.close()
        
        # Format datetime
        for log in logs:
            if log['login_time']:
                log['login_time'] = log['login_time'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total_data,
            'total_pages': total_pages,
            'data': logs
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Get login logs: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK RESET DATABASE =====================
@app.route('/api/reset-database', methods=['POST', 'OPTIONS'])
@token_required
def reset_database():
    """Endpoint untuk reset unknown questions (hanya super admin)"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin untuk reset database'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Hapus semua unknown questions
        cursor.execute("DELETE FROM pertanyaan_unknow")
        deleted_unknown = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Database berhasil direset',
            'deleted_unknown_questions': deleted_unknown
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Reset database: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK TAMBAH DATA =====================
@app.route('/tambah-data', methods=['POST', 'OPTIONS'])
@api_key_required
def tambah_data():
    """Endpoint untuk menambahkan data baru ke dataset"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
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
        
        # Load dataset yang sudah ada
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        # Cek duplikasi (case insensitive)
        if pertanyaan_baru.lower() in [p.lower() for p in pertanyaan_list_temp]:
            return jsonify({
                'error': f'Pertanyaan "{pertanyaan_baru}" sudah ada di dataset',
                'status': 'duplicate'
            }), 409
        
        # Tambah data baru
        pertanyaan_list_temp.append(pertanyaan_baru)
        jawaban_list_temp.append(jawaban_baru)
        kategori_list_temp.append(kategori_baru)
        
        # Simpan ke CSV
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
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
    
# ===================== ENDPOINT TRAINING MODEL =====================
@app.route('/train-model', methods=['POST', 'OPTIONS'])
@api_key_required
def train_model():
    """Endpoint untuk melatih ulang model dengan dataset terbaru"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        start_time = time.time()
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Load dataset tanpa pandas (gunakan csv reader)
        pertanyaan_train = []
        jawaban_train = []
        kategori_train = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) >= 3:
                        pertanyaan_train.append(row[0].strip())
                        jawaban_train.append(row[1].strip())
                        kategori_train.append(row[2].strip())
                    elif len(row) == 2:
                        pertanyaan_train.append(row[0].strip())
                        jawaban_train.append(row[1].strip())
                        kategori_train.append('umum')
                    elif len(row) == 1:
                        pertanyaan_train.append(row[0].strip())
                        jawaban_train.append('')
                        kategori_train.append('umum')
        except FileNotFoundError:
            return jsonify({'error': 'File dataset tidak ditemukan'}), 404
        
        if len(pertanyaan_train) == 0:
            return jsonify({'error': 'Dataset kosong. Silakan tambah data terlebih dahulu.'}), 400
        
        print(f"[TRAIN] Loading {len(pertanyaan_train)} questions...")
        
        # Preprocessing
        print("[TRAIN] Preprocessing data...")
        processed_list = []
        for q in pertanyaan_train:
            processed_list.append(preprocess(q))
        
        # Vectorizing
        print("[TRAIN] Vectorizing text...")
        vectorizer = TfidfVectorizer()
        X_train_tfidf = vectorizer.fit_transform(processed_list)
        
        # Training
        print("[TRAIN] Training SVM model...")
        y_train = list(range(len(pertanyaan_train)))
        model = LinearSVC()
        model.fit(X_train_tfidf, y_train)
        
        # Saving model
        print("[TRAIN] Saving model...")
        qa_data_new = {
            'model': model,
            'vectorizer': vectorizer,
            'answers': jawaban_train,
            'questions': pertanyaan_train,
            'categories': kategori_train
        }
        
        model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        with open(model_path, 'wb') as f:
            pickle.dump(qa_data_new, f)
        
        # Update global variables
        global model_qa, vectorizer_qa, answers, pertanyaan_list, kategori_list
        model_qa = model
        vectorizer_qa = vectorizer
        answers = jawaban_train
        pertanyaan_list = pertanyaan_train
        kategori_list = kategori_train
        
        training_time = time.time() - start_time
        
        print(f"[TRAIN] Training completed in {training_time:.2f} seconds")
        
        return jsonify({
            'message': 'Model berhasil dilatih',
            'training_time': f'{training_time:.2f} detik',
            'total_data': len(pertanyaan_train),
            'total_questions': len(pertanyaan_train),
            'categories_count': len(set(kategori_train)),
            'status': 'success'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Train model: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Terjadi kesalahan saat training: {str(e)}'}), 500

# ===================== ENDPOINT UNTUK DELETE DATA =====================
@app.route('/delete-data', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_data():
    """Endpoint untuk menghapus data pertanyaan berdasarkan index"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        index = data.get('index')
        
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Load dataset yang sudah ada
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_list_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        # Hapus data
        del pertanyaan_list_temp[index]
        del jawaban_list_temp[index]
        del kategori_list_temp[index]
        
        # Simpan ke CSV
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
        return jsonify({
            'message': 'Data berhasil dihapus',
            'status': 'success'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Delete data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ===================== ENDPOINT UNTUK UPDATE DATA =====================
@app.route('/update-data', methods=['PUT', 'OPTIONS'])
@api_key_required
def update_data():
    """Endpoint untuk mengupdate data pertanyaan berdasarkan index"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        index = data.get('index')
        pertanyaan_baru = data.get('pertanyaan', '').strip()
        jawaban_baru = data.get('jawaban', '').strip()
        kategori_baru = data.get('kategori', '').strip()
        
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
        
        # Load dataset yang sudah ada
        pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_list_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        # Update data
        pertanyaan_list_temp[index] = pertanyaan_baru
        jawaban_list_temp[index] = jawaban_baru
        kategori_list_temp[index] = kategori_baru
        
        # Simpan ke CSV
        save_dataset_to_csv(csv_path, pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp)
        
        return jsonify({
            'message': 'Data berhasil diupdate',
            'status': 'success'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Update data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete-unknown', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_unknown():
    """Endpoint untuk menghapus satu pertanyaan tidak dikenal berdasarkan ID"""
    if request.method == 'OPTIONS':
        return '', 200
    
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
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Delete unknown: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete-all-unknown', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_all_unknown():
    """Endpoint untuk menghapus semua pertanyaan tidak dikenal"""
    if request.method == 'OPTIONS':
        return '', 200
    
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

# ===================== ENDPOINT LOGOUT =====================
@app.route('/logout', methods=['POST', 'OPTIONS'])
@api_key_required
@token_required
def logout():
    """Endpoint untuk logout admin"""
    if request.method == 'OPTIONS':
        return '', 200
    
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
        
        return jsonify({
            'message': 'Logout berhasil',
            'authenticated': False
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Logout: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat logout'}), 500


# ===================== ENDPOINT VERIFY TOKEN =====================
@app.route('/verify-token', methods=['GET', 'OPTIONS'])
@api_key_required
def verify_token_endpoint():
    """Endpoint untuk memverifikasi token"""
    if request.method == 'OPTIONS':
        return '', 200
    
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


# ===================== ENDPOINT CHANGE PASSWORD =====================
@app.route('/change-password', methods=['POST', 'OPTIONS'])
@api_key_required
@token_required
def change_password():
    """Endpoint untuk mengganti password admin"""
    if request.method == 'OPTIONS':
        return '', 200
    
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
        
        # Hapus semua session kecuali yang sekarang
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

# Tambahkan handler OPTIONS untuk semua route yang belum ditangani
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return jsonify({}), 200

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Royal's Resto Chatbot API Server")
    print("=" * 50)
    print(f"📡 Server running on: http://localhost:{FLASK_PORT}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"🌍 Environment: {FLASK_ENV}")
    print("=" * 50)
    
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT)