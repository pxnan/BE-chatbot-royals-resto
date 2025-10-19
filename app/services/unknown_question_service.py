from app.models.database import get_db_connection

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

def get_unknown_questions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pertanyaan_unknow ORDER BY id DESC")
        data = cursor.fetchall()
        conn.commit()
        cursor.close()
        conn.close()
        return data
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None