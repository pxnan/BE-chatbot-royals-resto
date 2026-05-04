import sys
import traceback
import logging
import os
import csv
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import jwt
from psycopg2 import errors as psycopg2_errors

# Load environment variables
load_dotenv()

# ===================== Konfigurasi Logging =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# ===================== Konfigurasi =====================
DATABASE_URL = os.getenv("DATABASE_URL")
FLASK_ENV = os.getenv("FLASK_ENV", "production")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_str.split(",")] if allowed_origins_str else ["*"]

API_KEY = os.getenv("API_KEY", "RoyalsResto2024SecureKey!@#$")
API_KEY_HEADER = "X-API-Key"

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "royal_resto_chatbot_secret_key_2024")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

app = Flask(__name__)

CORS(app)

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
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
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
    if not DATABASE_URL:
        logger.error("DATABASE_URL not set")
        return None
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def get_db_cursor(conn, dictionary=True):
    if conn is None:
        return None
    if dictionary:
        from psycopg2.extras import RealDictCursor
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

# ===================== Lazy loading untuk model =====================
model_qa = None
vectorizer_qa = None
answers = []
pertanyaan_list = []
kategori_list = []
_models_loaded = False

def load_models_and_data():
    global model_qa, vectorizer_qa, answers, pertanyaan_list, kategori_list, _models_loaded
    if _models_loaded:
        return
    _models_loaded = True

    # Load model if exists
    model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
    try:
        if os.path.exists(model_path):
            import pickle
            with open(model_path, 'rb') as f:
                qa_data = pickle.load(f)
                model_qa = qa_data['model']
                vectorizer_qa = qa_data['vectorizer']
                answers = qa_data['answers']
                pertanyaan_list = qa_data['questions']
                kategori_list = qa_data.get('categories', [])
            logger.info(f"Model loaded: {len(pertanyaan_list)} questions")
        else:
            logger.warning("Model file not found, chatbot will use fallback")
    except Exception as e:
        logger.error(f"Error loading model: {e}")

    # Load dataset from database (not from CSV)
    load_dataset_from_db()

def load_dataset_from_db():
    """Load dataset dari tabel database (dataset)"""
    global pertanyaan_list, answers, kategori_list
    conn = get_db_connection()
    if conn is None:
        logger.error("Database not available, cannot load dataset")
        return
    try:
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT pertanyaan, jawaban, kategori FROM dataset ORDER BY id")
        rows = cursor.fetchall()
        pertanyaan_list = [row['pertanyaan'] for row in rows]
        answers = [row['jawaban'] for row in rows]
        kategori_list = [row['kategori'] for row in rows]
        logger.info(f"Dataset loaded from DB: {len(pertanyaan_list)} questions")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error loading dataset from DB: {e}")

def save_unknown_question(question):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO pertanyaan_unknow (pertanyaan) VALUES (%s)", (question,))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Save unknown error: {e}")

# ==================== ENDPOINTS =====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/chat', methods=['POST', 'OPTIONS'])
@api_key_required
def chat():
    if request.method == 'OPTIONS':
        return '', 200
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    load_models_and_data()

    if model_qa is None or vectorizer_qa is None:
        save_unknown_question(user_input)
        return jsonify({
            'pertanyaan': user_input,
            'jawaban': "Maaf, model chatbot belum tersedia. Silakan latih model terlebih dahulu.",
            'status': 'error'
        })

    from preprocessing import preprocess
    import numpy as np
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
        logger.error(f"Decision function error: {e}")
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

# ==================== AUTHENTICATION ====================
@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'error': 'Username dan password harus diisi', 'authenticated': False}), 400

    conn = get_db_connection()
    if conn is None:
        # Fallback untuk testing tanpa database
        if username == 'admin' and password == 'admin123':
            token = generate_token(1, 'admin', 'super_admin')
            return jsonify({
                'authenticated': True,
                'token': token,
                'admin': {'id': 1, 'username': 'admin', 'email': 'admin@royalsresto.com', 'full_name': 'Administrator', 'role': 'super_admin'},
                'expires_in': JWT_EXPIRATION_HOURS * 3600
            }), 200
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

@app.route('/logout', methods=['POST', 'OPTIONS'])
@token_required
def logout():
    if request.method == 'OPTIONS':
        return '', 200
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_sessions WHERE session_token = %s", (token,))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass
    return jsonify({'message': 'Logout berhasil', 'authenticated': False}), 200

@app.route('/verify-token', methods=['GET', 'OPTIONS'])
def verify_token_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

@app.route('/change-password', methods=['POST', 'OPTIONS'])
@token_required
def change_password():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
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

    new_hash = hash_password(new_password)
    cursor.execute("UPDATE admin SET password = %s, updated_at = NOW() WHERE id = %s", (new_hash, admin_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Password berhasil diubah'}), 200

@app.route('/admin-profile', methods=['GET', 'OPTIONS'])
@token_required
def get_admin_profile():
    if request.method == 'OPTIONS':
        return '', 200
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

# ==================== KELOLA ADMIN ====================
@app.route('/api/admins', methods=['GET', 'OPTIONS'])
@token_required
def get_all_admins():
    if request.method == 'OPTIONS':
        return '', 200
    if request.admin['role'] != 'super_admin':
        return jsonify({'error': 'Anda tidak memiliki izin'}), 403
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    if conn is None:
        return jsonify({'data': [], 'total_data': 0, 'page': page, 'per_page': per_page, 'total_pages': 1}), 200

    cursor = get_db_cursor(conn, dictionary=True)
    base_query = "SELECT id, username, email, full_name, role, is_active, last_login, created_at FROM admin WHERE 1=1"
    params = []
    if search:
        base_query += " AND (username ILIKE %s OR email ILIKE %s OR full_name ILIKE %s)"
        sp = f"%{search}%"
        params.extend([sp, sp, sp])
    query = base_query + " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    admins = cursor.fetchall()
    # total count
    count_query = "SELECT COUNT(*) as total FROM admin WHERE 1=1"
    if search:
        count_query += " AND (username ILIKE %s OR email ILIKE %s OR full_name ILIKE %s)"
        cursor.execute(count_query, [sp, sp, sp])
    else:
        cursor.execute(count_query)
    total = cursor.fetchone()['total']
    total_pages = (total + per_page - 1) // per_page
    for admin in admins:
        if admin.get('last_login'):
            admin['last_login'] = admin['last_login'].strftime('%Y-%m-%d %H:%M:%S')
        if admin.get('created_at'):
            admin['created_at'] = admin['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    cursor.close()
    conn.close()
    return jsonify({'page': page, 'per_page': per_page, 'total_data': total, 'total_pages': total_pages, 'data': admins}), 200

@app.route('/api/admins', methods=['POST', 'OPTIONS'])
@token_required
def create_admin():
    if request.method == 'OPTIONS':
        return '', 200
    if request.admin['role'] != 'super_admin':
        return jsonify({'error': 'Tidak memiliki izin'}), 403
    data = request.json or {}
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
    hashed = hash_password(password)
    cursor.execute("INSERT INTO admin (username, password, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
                   (username, hashed, email, full_name, role, is_active))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'message': 'Admin berhasil dibuat', 'admin_id': new_id}), 201

@app.route('/api/admins/<int:admin_id>', methods=['PUT', 'OPTIONS'])
@token_required
def update_admin(admin_id):
    if request.method == 'OPTIONS':
        return '', 200
    if request.admin['role'] != 'super_admin':
        return jsonify({'error': 'Tidak memiliki izin'}), 403
    data = request.json or {}
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
    cursor.execute("UPDATE admin SET email=%s, full_name=%s, role=%s, is_active=%s, updated_at=NOW() WHERE id=%s",
                   (email, full_name, role, is_active, admin_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Admin berhasil diupdate'}), 200

@app.route('/api/admins/<int:admin_id>/reset-password', methods=['POST', 'OPTIONS'])
@token_required
def reset_admin_password(admin_id):
    if request.method == 'OPTIONS':
        return '', 200
    if request.admin['role'] != 'super_admin':
        return jsonify({'error': 'Tidak memiliki izin'}), 403
    data = request.json or {}
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
    hashed = hash_password(new_password)
    cursor.execute("UPDATE admin SET password=%s, updated_at=NOW() WHERE id=%s", (hashed, admin_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Password berhasil direset'}), 200

@app.route('/api/admins/<int:admin_id>', methods=['DELETE', 'OPTIONS'])
@token_required
def delete_admin(admin_id):
    if request.method == 'OPTIONS':
        return '', 200
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

# ==================== UNKNOWN QUESTIONS ====================
@app.route('/pertanyaan-unknown', methods=['GET', 'OPTIONS'])
def get_unknown_questions():
    if request.method == 'OPTIONS':
        return '', 200
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    conn = get_db_connection()
    if conn is None:
        return jsonify({'data': [], 'total_data': 0, 'page': page, 'per_page': per_page, 'total_pages': 1}), 200
    cursor = get_db_cursor(conn, dictionary=True)
    cursor.execute("SELECT * FROM pertanyaan_unknow ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
    data = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM pertanyaan_unknow")
    total = cursor.fetchone()['total']
    cursor.close()
    conn.close()
    total_pages = (total + per_page - 1) // per_page
    return jsonify({'page': page, 'per_page': per_page, 'total_data': total, 'total_pages': total_pages, 'data': data}), 200

@app.route('/delete-unknown', methods=['DELETE', 'OPTIONS'])
def delete_unknown():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
    unknown_id = data.get('id')
    if not unknown_id:
        return jsonify({'error': 'ID tidak ditemukan'}), 400
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Pertanyaan berhasil dihapus (demo)'}), 200
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pertanyaan_unknow WHERE id = %s", (unknown_id,))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    if affected == 0:
        return jsonify({'error': 'Data tidak ditemukan'}), 404
    return jsonify({'message': 'Pertanyaan berhasil dihapus', 'status': 'success'}), 200

@app.route('/delete-all-unknown', methods=['DELETE', 'OPTIONS'])
def delete_all_unknown():
    if request.method == 'OPTIONS':
        return '', 200
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Semua pertanyaan berhasil dihapus (demo)', 'deleted_count': 0}), 200
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pertanyaan_unknow")
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    return jsonify({'message': f'{affected} pertanyaan berhasil dihapus', 'status': 'success', 'deleted_count': affected}), 200

# ==================== KATEGORI & MODEL INFO ====================
@app.route('/kategori', methods=['GET', 'OPTIONS'])
def get_kategori():
    if request.method == 'OPTIONS':
        return '', 200
    load_models_and_data()
    categories = sorted(list(set(kategori_list))) if kategori_list else []
    return jsonify({'kategori': categories})

@app.route('/model-info', methods=['GET', 'OPTIONS'])
def model_info():
    if request.method == 'OPTIONS':
        return '', 200
    load_models_and_data()
    return jsonify({
        'total_questions': len(pertanyaan_list),
        'total_answers': len(answers),
        'categories': sorted(list(set(kategori_list))) if kategori_list else [],
        'model_loaded': model_qa is not None,
        'vectorizer_loaded': vectorizer_qa is not None
    })

# ==================== DATASET MANAGEMENT (Database only) ====================
@app.route('/get-all-data', methods=['GET', 'OPTIONS'])
def get_all_data():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        # Ambil parameter query
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str).strip()
        kategori_filter = request.args.get('kategori', '', type=str).strip()
        offset = (page - 1) * per_page

        # Koneksi database
        conn = get_db_connection()
        if conn is None:
            logger.error("Database connection failed in get-all-data")
            return jsonify({'error': 'Database tidak tersedia'}), 500

        cursor = get_db_cursor(conn, dictionary=True)

        # Bangun query dasar
        base_query = """
            SELECT id, pertanyaan, jawaban, kategori
            FROM dataset
            WHERE 1=1
        """
        params = []

        if search:
            base_query += " AND pertanyaan ILIKE %s"
            params.append(f"%{search}%")

        if kategori_filter:
            base_query += " AND kategori = %s"
            params.append(kategori_filter)

        # Hitung total data (tanpa LIMIT/OFFSET)
        count_query = f"SELECT COUNT(*) as total FROM ({base_query}) AS sub"
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Query dengan pagination
        query = base_query + " ORDER BY id LIMIT %s OFFSET %s"
        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()

        # Format data untuk frontend
        data = []
        for row in rows:
            data.append({
                'index': row['id'] - 1,      # Frontend menggunakan index 0-based
                'id': row['id'],
                'pertanyaan': row['pertanyaan'],
                'jawaban': row['jawaban'],
                'kategori': row['kategori']
            })

        cursor.close()
        conn.close()

        # Kirim response
        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_data': total,
            'total_pages': total_pages,
            'data': data,
            'categories': []   # Bisa diambil dari endpoint /kategori jika perlu
        }), 200

    except psycopg2_errors.UndefinedTable as e:
        logger.error(f"Table 'dataset' does not exist: {e}")
        return jsonify({'error': 'Tabel dataset belum dibuat di database. Jalankan migration SQL terlebih dahulu.'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get-all-data: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Terjadi kesalahan: {str(e)}'}), 500

@app.route('/tambah-data', methods=['POST', 'OPTIONS'])
def tambah_data():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
    pertanyaan = data.get('pertanyaan', '').strip()
    jawaban = data.get('jawaban', '').strip()
    kategori = data.get('kategori', '').strip()
    if not pertanyaan or not jawaban or not kategori:
        return jsonify({'error': 'Semua field harus diisi'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500

    cursor = conn.cursor()
    # Cek duplikat
    cursor.execute("SELECT id FROM dataset WHERE pertanyaan ILIKE %s", (pertanyaan,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'error': f'Pertanyaan "{pertanyaan}" sudah ada', 'status': 'duplicate'}), 409
    cursor.execute("INSERT INTO dataset (pertanyaan, jawaban, kategori) VALUES (%s, %s, %s)", (pertanyaan, jawaban, kategori))
    conn.commit()
    cursor.close()
    conn.close()
    load_dataset_from_db()  # Refresh memory
    return jsonify({
        'message': 'Data berhasil ditambahkan',
        'data': {'pertanyaan': pertanyaan, 'jawaban': jawaban, 'kategori': kategori},
        'status': 'success'
    }), 201

@app.route('/update-data', methods=['PUT', 'OPTIONS'])
def update_data():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
    index = data.get('index')
    pertanyaan = data.get('pertanyaan', '').strip()
    jawaban = data.get('jawaban', '').strip()
    kategori = data.get('kategori', '').strip()
    if index is None:
        return jsonify({'error': 'Index tidak ditemukan'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500

    cursor = get_db_cursor(conn, dictionary=True)
    # Dapatkan id berdasarkan urutan (index)
    cursor.execute("SELECT id FROM dataset ORDER BY id")
    ids = [row['id'] for row in cursor.fetchall()]
    if index < 0 or index >= len(ids):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Index tidak valid'}), 400
    target_id = ids[index]
    cursor.execute("UPDATE dataset SET pertanyaan=%s, jawaban=%s, kategori=%s WHERE id=%s",
                   (pertanyaan, jawaban, kategori, target_id))
    conn.commit()
    cursor.close()
    conn.close()
    load_dataset_from_db()
    return jsonify({'message': 'Data berhasil diupdate', 'status': 'success'}), 200

@app.route('/delete-data', methods=['DELETE', 'OPTIONS'])
def delete_data():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
    index = data.get('index')
    if index is None:
        return jsonify({'error': 'Index tidak ditemukan'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500

    cursor = get_db_cursor(conn, dictionary=True)
    cursor.execute("SELECT id FROM dataset ORDER BY id")
    ids = [row['id'] for row in cursor.fetchall()]
    if index < 0 or index >= len(ids):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Index tidak valid'}), 400
    target_id = ids[index]
    cursor.execute("DELETE FROM dataset WHERE id=%s", (target_id,))
    conn.commit()
    cursor.close()
    conn.close()
    load_dataset_from_db()
    return jsonify({'message': 'Data berhasil dihapus', 'status': 'success'}), 200

@app.route('/delete-bulk-data', methods=['DELETE', 'OPTIONS'])
def delete_bulk_data():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
    indices = data.get('indices', [])
    if not indices:
        return jsonify({'error': 'Tidak ada index yang dipilih'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500

    cursor = get_db_cursor(conn, dictionary=True)
    cursor.execute("SELECT id FROM dataset ORDER BY id")
    ids = [row['id'] for row in cursor.fetchall()]
    to_delete = []
    for idx in indices:
        if 0 <= idx < len(ids):
            to_delete.append(ids[idx])
    if not to_delete:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Tidak ada data valid'}), 400
    cursor.execute("DELETE FROM dataset WHERE id = ANY(%s)", (to_delete,))
    conn.commit()
    cursor.close()
    conn.close()
    load_dataset_from_db()
    return jsonify({'message': f'{len(to_delete)} data berhasil dihapus', 'status': 'success'}), 200

# ==================== TRAINING MODEL ====================
@app.route('/train-model', methods=['POST', 'OPTIONS'])
def train_model():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        import pickle
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        from preprocessing import preprocess
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return jsonify({'error': 'Library tidak tersedia di server ini. Training tidak dapat dilakukan.'}), 500

    start_time = time.time()
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500

    cursor = get_db_cursor(conn, dictionary=True)
    cursor.execute("SELECT pertanyaan, jawaban, kategori FROM dataset ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if len(rows) == 0:
        return jsonify({'error': 'Dataset kosong'}), 400

    q_list = [row['pertanyaan'] for row in rows]
    a_list = [row['jawaban'] for row in rows]
    k_list = [row['kategori'] for row in rows]

    processed = [preprocess(q) for q in q_list]
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(processed)
    y = list(range(len(q_list)))
    model = LinearSVC()
    model.fit(X, y)

    model_path = os.path.join(os.getenv("MODEL_BASE_PATH", "model/"), 'model_qa.pkl')
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'vectorizer': vectorizer,
            'answers': a_list,
            'questions': q_list,
            'categories': k_list
        }, f)

    global _models_loaded
    _models_loaded = False
    load_models_and_data()

    training_time = time.time() - start_time
    return jsonify({
        'message': 'Model berhasil dilatih',
        'training_time': f'{training_time:.2f} detik',
        'total_data': len(q_list),
        'categories_count': len(set(k_list)),
        'status': 'success'
    }), 200

# ==================== DEBUG (CSV masih dipertahankan untuk keperluan debugging) ====================
csv_path = os.getenv("DATA_PATH", "data/dataset.csv")

@app.route('/cek-csv', methods=['GET', 'OPTIONS'])
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
def fix_csv():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        # Baca data dari database, lalu ekspor ke CSV
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Database tidak tersedia'}), 500
        cursor = get_db_cursor(conn, dictionary=True)
        cursor.execute("SELECT pertanyaan, jawaban, kategori FROM dataset ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
            for row in rows:
                writer.writerow([row['pertanyaan'], row['jawaban'], row['kategori']])
        return jsonify({'message': 'CSV berhasil diperbaiki dari database', 'total_rows': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ADDITIONAL ENDPOINTS ====================
@app.route('/get-data/<int:index>', methods=['GET', 'OPTIONS'])
def get_data_by_index(index):
    if request.method == 'OPTIONS':
        return '', 200
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500
    cursor = get_db_cursor(conn, dictionary=True)
    cursor.execute("SELECT id, pertanyaan, jawaban, kategori FROM dataset ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    if index < 0 or index >= len(rows):
        return jsonify({'error': 'Index tidak valid'}), 400
    row = rows[index]
    return jsonify({
        'index': index,
        'id': row['id'],
        'pertanyaan': row['pertanyaan'],
        'jawaban': row['jawaban'],
        'kategori': row['kategori']
    }), 200

@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register_admin():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json or {}
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
    hashed = hash_password(password)
    cursor.execute("INSERT INTO admin (username, password, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
                   (username, hashed, email, full_name, 'admin', True))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({'message': 'Registrasi berhasil', 'admin_id': new_id}), 201

@app.route('/api/stats', methods=['GET', 'OPTIONS'])
def get_dashboard_stats():
    if request.method == 'OPTIONS':
        return '', 200
    load_models_and_data()
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

@app.route('/api/export-data', methods=['GET', 'OPTIONS'])
def export_data():
    if request.method == 'OPTIONS':
        return '', 200
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500
    cursor = get_db_cursor(conn, dictionary=True)
    cursor.execute("SELECT pertanyaan, jawaban, kategori FROM dataset ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['pertanyaan', 'jawaban', 'kategori'])
    for row in rows:
        writer.writerow([row['pertanyaan'], row['jawaban'], row['kategori']])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=dataset_export.csv'}), 200

@app.route('/api/search-data', methods=['GET', 'OPTIONS'])
def search_data():
    if request.method == 'OPTIONS':
        return '', 200
    query = request.args.get('q', '').strip()
    kategori = request.args.get('kategori', '').strip()
    if not query:
        return jsonify({'data': [], 'total': 0}), 200

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database tidak tersedia'}), 500

    cursor = get_db_cursor(conn, dictionary=True)
    base_sql = "SELECT id, pertanyaan, jawaban, kategori FROM dataset WHERE pertanyaan ILIKE %s"
    params = [f"%{query}%"]
    if kategori:
        base_sql += " AND kategori = %s"
        params.append(kategori)
    base_sql += " ORDER BY id LIMIT 50"
    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    results = []
    for row in rows:
        results.append({
            'index': row['id'] - 1,
            'id': row['id'],
            'pertanyaan': row['pertanyaan'],
            'jawaban': row['jawaban'],
            'kategori': row['kategori']
        })
    cursor.close()
    conn.close()
    return jsonify({'data': results, 'total': len(results)}), 200

@app.route('/api/login-logs', methods=['GET', 'OPTIONS'])
@token_required
def get_login_logs():
    if request.method == 'OPTIONS':
        return '', 200
    if request.admin['role'] != 'super_admin':
        return jsonify({'error': 'Tidak memiliki izin'}), 403
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    if conn is None:
        return jsonify({'data': [], 'total_data': 0}), 200
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
    total = cursor.fetchone()['total']
    total_pages = (total + per_page - 1) // per_page
    cursor.close()
    conn.close()
    for log in logs:
        if log.get('login_time'):
            log['login_time'] = log['login_time'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'page': page, 'per_page': per_page, 'total_data': total, 'total_pages': total_pages, 'data': logs}), 200

@app.route('/api/reset-database', methods=['POST', 'OPTIONS'])
@token_required
def reset_database():
    if request.method == 'OPTIONS':
        return '', 200
    if request.admin['role'] != 'super_admin':
        return jsonify({'error': 'Tidak memiliki izin'}), 403
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Database berhasil direset (demo)', 'deleted_unknown_questions': 0}), 200
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pertanyaan_unknow")
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Database berhasil direset', 'deleted_unknown_questions': deleted}), 200

# ==================== Global Error Handler ====================
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({'error': 'Internal server error', 'message': str(e) if app.debug else 'Terjadi kesalahan'}), 500

if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=FLASK_PORT)