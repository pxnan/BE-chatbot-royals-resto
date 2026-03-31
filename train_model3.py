import pandas as pd
import pickle
import time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from preprocessing import preprocess

# ===== Load Dataset =====
df = pd.read_csv('data/dataset.csv')

# Preprocessing
df['processed'] = df['pertanyaan'].astype(str).apply(preprocess)

# ===== Train SVM QA dengan Kernel Polynomial Degree 2 =====
X_qa = df['processed']
# Label adalah indeks jawaban
y_qa = list(range(len(df)))

# Vectorizer - batasi fitur untuk mempercepat polynomial degree 2
vectorizer_qa = TfidfVectorizer()

print("🔧 Transforming text to TF-IDF features...")
X_qa_tfidf = vectorizer_qa.fit_transform(X_qa)

print("\n🚀 Training model dengan kernel Polynomial Degree 2...")

start_time = time.time()

# Model SVM dengan kernel polynomial degree 2
model_qa = SVC(
    kernel='poly',          # Kernel polynomial
    degree=2,               # Quadratic polynomial
    coef0=1,                # Constant term in kernel function
    C=1.0,                  # Regularization parameter
    random_state=42,
    verbose=True,           # Tampilkan progress training
    max_iter=2000           # Batasi iterasi maksimal
)

model_qa.fit(X_qa_tfidf, y_qa)

training_time = time.time() - start_time

print(f"\n✅ Model Polynomial Degree 2 berhasil dilatih!")
print(f"⏱️  Waktu training: {training_time:.2f} detik")

# Simpan semua data QA dalam satu file
qa_data = {
    'model': model_qa,
    'vectorizer': vectorizer_qa,
    'answers': df['jawaban'].tolist(),
    'questions': df['pertanyaan'].tolist(),
    'categories': df['kategori'].tolist(),
    'kernel': 'poly',
    'params': {
        'degree': 2,
        'coef0': 1,
        'C': 1.0,
        'kernel_type': 'quadratic'
    },
    'training_info': {
        'training_time': training_time,
        'n_support_vectors': model_qa.n_support_.sum(),
        'n_samples': X_qa_tfidf.shape[0],
        'n_features': X_qa_tfidf.shape[1]
    }
}

# Simpan model
output_filename = 'model/model_qa_poly_degree2.pkl'
with open(output_filename, 'wb') as f:
    pickle.dump(qa_data, f)

print(f"\n💾 Model berhasil disimpan di '{output_filename}'")