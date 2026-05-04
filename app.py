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

FLASK_ENV = os.getenv("FLASK_ENV", "production")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

# Parse ALLOWED_ORIGINS
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_str.split(",")]
else:
    ALLOWED_ORIGINS = ["*"]

# ===================== Konfigurasi API Key =====================
API_KEY = os.getenv("API_KEY", "RoyalsResto2024SecureKey!@#$")
API_KEY_HEADER = "X-API-Key"

# ===================== Konfigurasi JWT =====================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "royal_resto_chatbot_secret_key_2024")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

# ===================== Inisialisasi Flask =====================
app = Flask(__name__)

# ===================== KONFIGURASI CORS =====================
CORS(app, 
     origins=ALLOWED_ORIGINS,
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
     allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Requested-With"],
     supports_credentials=True,
     max_age=86400)

# ===================== HANDLER PREFLIGHT =====================
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.status_code = 200
        return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 200

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
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

# ===================== Database Connection =====================
def get_db_connection():
    try:
        if not DATABASE_URL:
            return None
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"[DB ERROR] Connection failed: {e}")
        return None

def get_db_cursor(conn, dictionary=True):
    if conn is None:
        return None
    if dictionary:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

# ===================== Load Model =====================
model_qa = None
vectorizer_qa = None
answers = []
pertanyaan_list = []
kategori_list = []

model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
try:
    if os.path.exists(model_path):
        with open(model_path, 'rb') as f:
            qa_data = pickle.load(f)
            model_qa = qa_data['model']
            vectorizer_qa = qa_data['vectorizer']
            answers = qa_data['answers']
            pertanyaan_list = qa_data['questions']
            kategori_list = qa_data.get('categories', [])
        print(f"[INFO] Model loaded: {len(pertanyaan_list)} questions")
except Exception as e:
    print(f"[WARNING] Error loading model: {e}")

# ===================== Load Dataset =====================
csv_path = os.getenv("DATA_PATH", "data/dataset.csv")
df = pd.DataFrame()

try:
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, encoding='utf-8')
        if 'pertanyaan' in df.columns:
            pertanyaan_list = df['pertanyaan'].tolist()
            answers = df['jawaban'].tolist()
            kategori_list = df['kategori'].tolist() if 'kategori' in df.columns else []
        print(f"[INFO] Dataset loaded: {len(pertanyaan_list)} questions")
except Exception as e:
    print(f"[WARNING] Error loading dataset: {e}")

# ===================== Helper CSV Functions =====================
def load_dataset_from_csv(csv_path):
    pertanyaan_list_temp = []
    jawaban_list_temp = []
    kategori_list_temp = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    pertanyaan_list_temp.append(row[0].strip())
                    jawaban_list_temp.append(row[1].strip())
                    kategori_list_temp.append(row[2].strip())
                elif len(row) == 2:
                    pertanyaan_list_temp.append(row[0].strip())
                    jawaban_list_temp.append(row[1].strip())
                    kategori_list_temp.append('umum')
                elif len(row) == 1:
                    pertanyaan_list_temp.append(row[0].strip())
                    jawaban_list_temp.append('')
                    kategori_list_temp.append('umum')
    except FileNotFoundError:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
    return pertanyaan_list_temp, jawaban_list_temp, kategori_list_temp

def save_dataset_to_csv(csv_path, pertanyaan_list, jawaban_list, kategori_list):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
        for i in range(len(pertanyaan_list)):
            p = pertanyaan_list[i]
            j = jawaban_list[i] if i < len(jawaban_list) else ''
            k = kategori_list[i] if i < len(kategori_list) else 'umum'
            writer.writerow([p, j, k])

def save_unknown_question(question):
    conn = get_db_connection()
    if conn is None:
        return
    try:
        cursor = get_db_cursor(conn, dictionary=False)
        cursor.execute("INSERT INTO pertanyaan_unknow (pertanyaan) VALUES (%s)", (question,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

# ==================== ENDPOINT ROOT ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# ==================== ENDPOINT CHAT ====================
@app.route('/chat', methods=['POST', 'OPTIONS'])
@api_key_required
def chat():
    if request.method == 'OPTIONS':
        return '', 200
    
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    if model_qa is None or vectorizer_qa is None:
        save_unknown_question(user_input)
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': "Maaf, model chatbot belum tersedia. Silakan latih model terlebih dahulu.",
            'status': 'error'
        })

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
        scores = scores.flatten() if len(scores.shape) > 1 else np.array(scores)
    except Exception as e:
        print(f"Error calculating confidence: {e}")
        scores = np.array([0])

    top_indices = np.argsort(scores)[::-1][:3]
    top_scores = scores[top_indices]
    max_score = top_scores[0]

    if max_score < -0.8:
        save_unknown_question(user_input)
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': "Mohon maaf, saya belum mengerti pertanyaan Anda.",
            'status': 'unknown'
        })
    
    elif len(top_scores) > 1 and abs(top_scores[0] - top_scores[1]) < 0.1:
        user_input_clean = user_input.lower().strip()
        exact_match_idx = -1
        for idx, pertanyaan in enumerate(pertanyaan_list):
            if user_input_clean == pertanyaan.lower().strip():
                exact_match_idx = idx
                break
        
        if exact_match_idx >= 0:
            return jsonify({
                'pertanyaan': user_input,
                'jawaban': answers[exact_match_idx],
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

# ==================== ENDPOINT AUTHENTICATION ====================
@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Username dan password harus diisi', 'authenticated': False}), 400
        
        conn = get_db_connection()
        if conn is None:
            if username == 'admin' and password == 'admin123':
                return jsonify({
                    'authenticated': True,
                    'message': 'Login berhasil',
                    'token': generate_token(1, 'admin', 'super_admin'),
                    'admin': {'id': 1, 'username': 'admin', 'email': 'admin@royalsresto.com', 'full_name': 'Administrator', 'role': 'super_admin'}
                })
            return jsonify({'error': 'Username atau password salah', 'authenticated': False}), 401
        
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT id, username, password, email, full_name, role, is_active FROM admin WHERE username = %s", (username,))
        admin = cursor.fetchone()
        
        if not admin:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username atau password salah', 'authenticated': False}), 401
        
        if not admin['is_active']:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Akun Anda telah dinonaktifkan.', 'authenticated': False}), 401
        
        if not verify_password(password, admin['password']):
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username atau password salah', 'authenticated': False}), 401
        
        token = generate_token(admin['id'], admin['username'], admin['role'])
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Login berhasil',
            'authenticated': True,
            'token': token,
            'admin': {
                'id': admin['id'],
                'username': admin['username'],
                'email': admin['email'],
                'full_name': admin['full_name'],
                'role': admin['role']
            },
            'expires_in': JWT_EXPIRATION_HOURS * 3600
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Login: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat login', 'authenticated': False}), 500

@app.route('/logout', methods=['POST', 'OPTIONS'])
@api_key_required
@token_required
def logout():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_sessions WHERE session_token = %s", (token,))
            conn.commit()
            cursor.close()
            conn.close()
        return jsonify({'message': 'Logout berhasil', 'authenticated': False}), 200
    except Exception as e:
        print(f"[ERROR] Logout: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat logout'}), 500

@app.route('/verify-token', methods=['GET', 'OPTIONS'])
@api_key_required
def verify_token_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'authenticated': False}), 401
        if token.startswith('Bearer '):
            token = token[7:]
        payload = verify_token(token)
        if not payload:
            return jsonify({'authenticated': False}), 401
        return jsonify({
            'authenticated': True,
            'admin_id': payload['admin_id'],
            'username': payload['username'],
            'role': payload['role']
        }), 200
    except Exception as e:
        return jsonify({'authenticated': False}), 401

@app.route('/change-password', methods=['POST', 'OPTIONS'])
@api_key_required
@token_required
def change_password():
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
        if conn is None:
            return jsonify({'message': 'Password berhasil diubah (demo)'}), 200
        
        cursor = get_db_cursor(conn, dictionary=True)
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
        cursor.execute("UPDATE admin SET password = %s, updated_at = NOW() WHERE id = %s", (new_password_hash, admin_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Password berhasil diubah'}), 200
    except Exception as e:
        print(f"[ERROR] Change password: {e}")
        return jsonify({'error': 'Terjadi kesalahan'}), 500

@app.route('/admin-profile', methods=['GET', 'OPTIONS'])
@api_key_required
@token_required
def get_admin_profile():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        admin_id = request.admin['admin_id']
        conn = get_db_connection()
        if conn is None:
            return jsonify({'admin': {'id': admin_id, 'username': 'admin', 'role': 'super_admin'}}), 200
        
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT id, username, email, full_name, role, is_active, last_login, created_at FROM admin WHERE id = %s", (admin_id,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if admin:
            if admin.get('last_login'):
                admin['last_login'] = admin['last_login'].strftime('%Y-%m-%d %H:%M:%S')
            if admin.get('created_at'):
                admin['created_at'] = admin['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({'admin': admin}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ENDPOINT KELOLA ADMIN ====================
@app.route('/api/admins', methods=['GET', 'OPTIONS'])
@api_key_required
@token_required
def get_all_admins():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Anda tidak memiliki izin'}), 403
        
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        search = request.args.get('search', default='', type=str)
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'data': [], 'total_data': 0, 'page': page, 'per_page': per_page, 'total_pages': 1}), 200
        
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
        
        count_query = "SELECT COUNT(*) as total FROM admin WHERE 1=1"
        if search:
            count_query += " AND (username ILIKE %s OR email ILIKE %s OR full_name ILIKE %s)"
            cursor.execute(count_query, [search_param, search_param, search_param])
        else:
            cursor.execute(count_query)
        total_data = cursor.fetchone()['total']
        total_pages = (total_data + per_page - 1) // per_page
        
        for admin in admins:
            if admin.get('last_login'):
                admin['last_login'] = admin['last_login'].strftime('%Y-%m-%d %H:%M:%S')
            if admin.get('created_at'):
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
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Tidak memiliki izin'}), 403
        
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
        if conn is None:
            return jsonify({'message': 'Admin berhasil dibuat (demo)', 'admin_id': 999}), 201
        
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
        cursor.execute("INSERT INTO admin (username, password, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
                      (username, hashed_password, email, full_name, role, is_active))
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
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Tidak memiliki izin'}), 403
        
        data = request.json
        email = data.get('email', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'admin')
        is_active = data.get('is_active', True)
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'message': 'Admin berhasil diupdate (demo)'}), 200
        
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
            return jsonify({'error': 'Email sudah digunakan'}), 409
        
        cursor.execute("UPDATE admin SET email = %s, full_name = %s, role = %s, is_active = %s, updated_at = NOW() WHERE id = %s",
                      (email, full_name, role, is_active, admin_id))
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
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Tidak memiliki izin'}), 403
        
        data = request.json
        new_password = data.get('new_password', '').strip()
        if not new_password or len(new_password) < 6:
            return jsonify({'error': 'Password minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'message': 'Password berhasil direset (demo)'}), 200
        
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT id FROM admin WHERE id = %s", (admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        hashed_password = hash_password(new_password)
        cursor.execute("UPDATE admin SET password = %s, updated_at = NOW() WHERE id = %s", (hashed_password, admin_id))
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
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Tidak memiliki izin'}), 403
        if request.admin['admin_id'] == admin_id:
            return jsonify({'error': 'Tidak dapat menghapus akun sendiri'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'message': 'Admin berhasil dihapus (demo)'}), 200
        
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT id FROM admin WHERE id = %s", (admin_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Admin tidak ditemukan'}), 404
        
        cursor.execute("DELETE FROM admin WHERE id = %s", (admin_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Admin berhasil dihapus'}), 200
    except Exception as e:
        print(f"[ERROR] Delete admin: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== ENDPOINT UNKNOWN QUESTIONS ====================
@app.route('/pertanyaan-unknown', methods=['GET', 'OPTIONS'])
@api_key_required
def get_unknown_questions():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = 10
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'data': [], 'total_data': 0, 'page': page, 'per_page': per_page, 'total_pages': 1}), 200
        
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT * FROM pertanyaan_unknow ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
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
        return jsonify({'error': str(e)}), 500

@app.route('/delete-unknown', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_unknown():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        unknown_id = data.get('id')
        if unknown_id is None:
            return jsonify({'error': 'ID tidak ditemukan'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'message': 'Pertanyaan berhasil dihapus (demo)'}), 200
        
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
        return jsonify({'error': str(e)}), 500

@app.route('/delete-all-unknown', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_all_unknown():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'message': 'Semua pertanyaan berhasil dihapus (demo)', 'deleted_count': 0}), 200
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pertanyaan_unknow")
        conn.commit()
        affected_rows = cursor.rowcount
        cursor.close()
        conn.close()
        
        return jsonify({'message': f'{affected_rows} pertanyaan berhasil dihapus', 'status': 'success', 'deleted_count': affected_rows}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ENDPOINT KATEGORI & MODEL INFO ====================
@app.route('/kategori', methods=['GET', 'OPTIONS'])
@api_key_required
def get_kategori():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        categories = sorted(list(set(kategori_list))) if kategori_list else []
        return jsonify({'kategori': categories})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/model-info', methods=['GET', 'OPTIONS'])
@api_key_required
def model_info():
    if request.method == 'OPTIONS':
        return '', 200
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

# ==================== ENDPOINT DATASET MANAGEMENT ====================
@app.route('/get-all-data', methods=['GET', 'OPTIONS'])
@api_key_required
def get_all_data():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        search = request.args.get('search', default='', type=str)
        kategori_filter = request.args.get('kategori', default='', type=str)
        offset = (page - 1) * per_page
        
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        filtered_data = []
        for i in range(len(pertanyaan_temp)):
            p = pertanyaan_temp[i]
            j = jawaban_temp[i] if i < len(jawaban_temp) else ''
            k = kategori_temp[i] if i < len(kategori_temp) else 'umum'
            
            if search and search.lower() not in p.lower():
                continue
            if kategori_filter and k != kategori_filter:
                continue
            filtered_data.append({'index': i, 'pertanyaan': p, 'jawaban': j, 'kategori': k})
        
        total_data = len(filtered_data)
        total_pages = (total_data + per_page - 1) // per_page if total_data > 0 else 1
        paginated_data = filtered_data[offset:offset + per_page]
        unique_categories = sorted(list(set(kategori_temp)))
        
        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total_data,
            'total_pages': total_pages,
            'data': paginated_data,
            'categories': unique_categories
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tambah-data', methods=['POST', 'OPTIONS'])
@api_key_required
def tambah_data():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        pertanyaan_baru = data.get('pertanyaan', '').strip()
        jawaban_baru = data.get('jawaban', '').strip()
        kategori_baru = data.get('kategori', '').strip()
        
        if not pertanyaan_baru or not jawaban_baru or not kategori_baru:
            return jsonify({'error': 'Semua field harus diisi'}), 400
        
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        if pertanyaan_baru.lower() in [p.lower() for p in pertanyaan_temp]:
            return jsonify({'error': f'Pertanyaan "{pertanyaan_baru}" sudah ada', 'status': 'duplicate'}), 409
        
        pertanyaan_temp.append(pertanyaan_baru)
        jawaban_temp.append(jawaban_baru)
        kategori_temp.append(kategori_baru)
        save_dataset_to_csv(csv_path, pertanyaan_temp, jawaban_temp, kategori_temp)
        
        return jsonify({
            'message': 'Data berhasil ditambahkan',
            'data': {'pertanyaan': pertanyaan_baru, 'jawaban': jawaban_baru, 'kategori': kategori_baru},
            'status': 'success'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update-data', methods=['PUT', 'OPTIONS'])
@api_key_required
def update_data():
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
        
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        pertanyaan_temp[index] = pertanyaan_baru
        jawaban_temp[index] = jawaban_baru
        kategori_temp[index] = kategori_baru
        save_dataset_to_csv(csv_path, pertanyaan_temp, jawaban_temp, kategori_temp)
        
        return jsonify({'message': 'Data berhasil diupdate', 'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete-data', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_data():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        index = data.get('index')
        if index is None:
            return jsonify({'error': 'Index tidak ditemukan'}), 400
        
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        if index < 0 or index >= len(pertanyaan_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        
        del pertanyaan_temp[index]
        del jawaban_temp[index]
        del kategori_temp[index]
        save_dataset_to_csv(csv_path, pertanyaan_temp, jawaban_temp, kategori_temp)
        
        return jsonify({'message': 'Data berhasil dihapus', 'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ENDPOINT TRAINING MODEL ====================
@app.route('/train-model', methods=['POST', 'OPTIONS'])
@api_key_required
def train_model():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        start_time = time.time()
        
        pertanyaan_train, jawaban_train, kategori_train = load_dataset_from_csv(csv_path)
        
        if len(pertanyaan_train) == 0:
            return jsonify({'error': 'Dataset kosong'}), 400
        
        processed_list = [preprocess(q) for q in pertanyaan_train]
        
        vectorizer = TfidfVectorizer()
        X_train_tfidf = vectorizer.fit_transform(processed_list)
        
        y_train = list(range(len(pertanyaan_train)))
        model = LinearSVC()
        model.fit(X_train_tfidf, y_train)
        
        qa_data_new = {
            'model': model,
            'vectorizer': vectorizer,
            'answers': jawaban_train,
            'questions': pertanyaan_train,
            'categories': kategori_train
        }
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        with open(model_path, 'wb') as f:
            pickle.dump(qa_data_new, f)
        
        global model_qa, vectorizer_qa, answers, pertanyaan_list, kategori_list
        model_qa = model
        vectorizer_qa = vectorizer
        answers = jawaban_train
        pertanyaan_list = pertanyaan_train
        kategori_list = kategori_train
        
        training_time = time.time() - start_time
        
        return jsonify({
            'message': 'Model berhasil dilatih',
            'training_time': f'{training_time:.2f} detik',
            'total_data': len(pertanyaan_train),
            'categories_count': len(set(kategori_train)),
            'status': 'success'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ENDPOINT DEBUG ====================
@app.route('/cek-csv', methods=['GET', 'OPTIONS'])
@api_key_required
def cek_csv():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        rows = list(csv.reader(lines))
        return jsonify({
            'total_lines': len(lines),
            'total_rows': len(rows),
            'last_5_rows': rows[-5:] if len(rows) >= 5 else rows,
            'file_path': csv_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fix-csv', methods=['POST', 'OPTIONS'])
@api_key_required
def fix_csv():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        save_dataset_to_csv(csv_path, pertanyaan_temp, jawaban_temp, kategori_temp)
        return jsonify({'message': 'CSV berhasil diperbaiki', 'total_rows': len(pertanyaan_temp)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ADDITIONAL ENDPOINTS ====================
@app.route('/get-data/<int:index>', methods=['GET', 'OPTIONS'])
@api_key_required
def get_data_by_index(index):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        if index < 0 or index >= len(pertanyaan_temp):
            return jsonify({'error': 'Index tidak valid'}), 400
        return jsonify({
            'index': index,
            'pertanyaan': pertanyaan_temp[index],
            'jawaban': jawaban_temp[index],
            'kategori': kategori_temp[index] if index < len(kategori_temp) else 'umum'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete-bulk-data', methods=['DELETE', 'OPTIONS'])
@api_key_required
def delete_bulk_data():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        indices = data.get('indices', [])
        if not indices:
            return jsonify({'error': 'Tidak ada index yang dipilih'}), 400
        
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(pertanyaan_temp):
                del pertanyaan_temp[index]
                del jawaban_temp[index]
                del kategori_temp[index]
        
        save_dataset_to_csv(csv_path, pertanyaan_temp, jawaban_temp, kategori_temp)
        return jsonify({'message': f'{len(indices)} data berhasil dihapus', 'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register_admin():
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
        if conn is None:
            return jsonify({'message': 'Registrasi berhasil (demo)', 'admin_id': 999}), 201
        
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
        cursor.execute("INSERT INTO admin (username, password, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
                      (username, hashed_password, email, full_name, 'admin', True))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Registrasi berhasil', 'admin_id': new_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET', 'OPTIONS'])
@api_key_required
def get_dashboard_stats():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = get_db_connection()
        total_admin = 0
        total_unknown = 0
        
        if conn:
            cursor = get_db_cursor(conn, dictionary=True)
            cursor.execute("SELECT COUNT(*) as total FROM admin")
            total_admin = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(*) as total FROM pertanyaan_unknow")
            total_unknown = cursor.fetchone()['total']
            cursor.close()
            conn.close()
        
        return jsonify({
            'total_admin': total_admin,
            'total_unknown_questions': total_unknown,
            'total_questions': len(pertanyaan_list),
            'total_categories': len(set(kategori_list)) if kategori_list else 0,
            'model_loaded': model_qa is not None
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-data', methods=['GET', 'OPTIONS'])
@api_key_required
def export_data():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            content = f.read()
        from flask import Response
        return Response(content, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=dataset_export.csv'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-data', methods=['GET', 'OPTIONS'])
@api_key_required
def search_data():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        query = request.args.get('q', '').strip()
        kategori = request.args.get('kategori', '').strip()
        
        if not query:
            return jsonify({'data': [], 'total': 0}), 200
        
        pertanyaan_temp, jawaban_temp, kategori_temp = load_dataset_from_csv(csv_path)
        
        results = []
        for i, (p, j, k) in enumerate(zip(pertanyaan_temp, jawaban_temp, kategori_temp)):
            if query.lower() in p.lower():
                if kategori and k != kategori:
                    continue
                results.append({'index': i, 'pertanyaan': p, 'jawaban': j, 'kategori': k})
        
        return jsonify({'data': results[:50], 'total': len(results)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login-logs', methods=['GET', 'OPTIONS'])
@api_key_required
@token_required
def get_login_logs():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Tidak memiliki izin'}), 403
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'data': [], 'total_data': 0}), 200
        
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)
        offset = (page - 1) * per_page
        
        cursor = get_db_cursor(conn, dictionary=True)
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
        
        for log in logs:
            if log.get('login_time'):
                log['login_time'] = log['login_time'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({'page': page, 'per_page': per_page, 'total_data': total_data, 'total_pages': total_pages, 'data': logs}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset-database', methods=['POST', 'OPTIONS'])
@token_required
def reset_database():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        if request.admin['role'] != 'super_admin':
            return jsonify({'error': 'Tidak memiliki izin'}), 403
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'message': 'Database berhasil direset (demo)', 'deleted_unknown_questions': 0}), 200
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pertanyaan_unknow")
        deleted_unknown = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Database berhasil direset', 'deleted_unknown_questions': deleted_unknown}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Royal's Resto Chatbot API Server")
    print("=" * 50)
    print(f"📡 Server running on: http://localhost:{FLASK_PORT}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"🌍 Environment: {FLASK_ENV}")
    print(f"🤖 Model loaded: {model_qa is not None}")
    print(f"📊 Dataset size: {len(pertanyaan_list)} questions")
    print("=" * 50)
    
    app.run(debug=FLASK_DEBUG,port=FLASK_PORT)