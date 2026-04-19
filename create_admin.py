import bcrypt
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

def create_admin():
    # Koneksi ke database
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    
    cursor = conn.cursor()
    
    # Data admin
    username = "admin"
    password = "admin123"
    email = "admin@royalsresto.com"
    full_name = "Administrator"
    role = "super_admin"
    
    # Hash password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    # Cek apakah admin sudah ada
    cursor.execute("SELECT id FROM admin WHERE username = %s", (username,))
    existing = cursor.fetchone()
    
    if existing:
        # Update password admin yang ada
        cursor.execute(
            "UPDATE admin SET password = %s WHERE username = %s",
            (hashed_password, username)
        )
        print(f"Password admin '{username}' telah diupdate!")
    else:
        # Insert admin baru
        cursor.execute(
            "INSERT INTO admin (username, password, email, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
            (username, hashed_password, email, full_name, role, True)
        )
        print(f"Admin '{username}' berhasil dibuat!")
    
    conn.commit()
    
    # Verifikasi
    cursor.execute("SELECT id, username, email, role FROM admin WHERE username = %s", (username,))
    admin = cursor.fetchone()
    print(f"\nData Admin:")
    print(f"ID: {admin[0]}")
    print(f"Username: {admin[1]}")
    print(f"Email: {admin[2]}")
    print(f"Role: {admin[3]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    create_admin()