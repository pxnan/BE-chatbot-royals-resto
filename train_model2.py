import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC  # Ganti LinearSVC ke SVC
from preprocessing import preprocess
import time

# ===== Load Dataset =====
df = pd.read_csv('data/dataset.csv')

# Preprocessing
df['processed'] = df['pertanyaan'].astype(str).apply(preprocess)

# ===== Train SVM QA (semua pertanyaan dalam satu model) =====
X_qa = df['processed']
# Label adalah indeks jawaban
y_qa = list(range(len(df)))

vectorizer_qa = TfidfVectorizer()
X_qa_tfidf = vectorizer_qa.fit_transform(X_qa)

# GANTI: Gunakan SVC dengan kernel RBF
print("🚀 Melatih model dengan kernel RBF...")
start_time = time.time()

model_qa = SVC(kernel='rbf', random_state=42)  # Ganti ke SVC dengan kernel RBF
model_qa.fit(X_qa_tfidf, y_qa)

print(f"✅ Model RBF berhasil dilatih dalam {time.time() - start_time:.2f} detik")

# Simpan semua data QA dalam satu file, termasuk kategori
qa_data = {
    'model': model_qa,
    'vectorizer': vectorizer_qa,
    'answers': df['jawaban'].tolist(),
    'questions': df['pertanyaan'].tolist(),
    'categories': df['kategori'].tolist(),
    'kernel': 'rbf'  # Tambahkan info kernel
}

with open('model/model_qa_rbf.pkl', 'wb') as f:
    pickle.dump(qa_data, f)

print("✅ Model QA dengan kernel RBF berhasil disimpan di 'model/model_qa_rbf.pkl'!")