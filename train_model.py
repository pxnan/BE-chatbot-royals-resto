import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from preprocessing import preprocess

# ===== Load Dataset =====
df = pd.read_csv('data/dataset.csv')

# Preprocessing
df['processed'] = df['pertanyaan'].astype(str).apply(preprocess)

# ===== Stage 1: Train SVM Kategori =====
X_cat = df['processed']
y_cat = df['kategori']

vectorizer_cat = TfidfVectorizer()
X_cat_tfidf = vectorizer_cat.fit_transform(X_cat)

model_cat = LinearSVC()
model_cat.fit(X_cat_tfidf, y_cat)

# Save model kategori
with open('model/tfidf_vectorizer_category.pkl', 'wb') as f:
    pickle.dump(vectorizer_cat, f)
with open('model/svm_model_category.pkl', 'wb') as f:
    pickle.dump(model_cat, f)

print("✅ Stage 1: Model kategori berhasil dilatih dan disimpan!")

# ===== Stage 2: Train SVM QA (semua pertanyaan dalam satu model) =====
X_qa = df['processed']
# Label adalah indeks jawaban
y_qa = list(range(len(df)))

vectorizer_qa = TfidfVectorizer()
X_qa_tfidf = vectorizer_qa.fit_transform(X_qa)

model_qa = LinearSVC()
model_qa.fit(X_qa_tfidf, y_qa)

# Simpan semua data QA dalam satu file, termasuk kategori
qa_data = {
    'model': model_qa,
    'vectorizer': vectorizer_qa,
    'answers': df['jawaban'].tolist(),
    'questions': df['pertanyaan'].tolist(),
    'categories': df['kategori'].tolist()  # ✅ tambahkan kategori
}

with open('model/model_qa.pkl', 'wb') as f:
    pickle.dump(qa_data, f)

print("✅ Stage 2: Model QA semua pertanyaan beserta kategori berhasil dilatih dan disimpan di 'model_qa.pkl'!")
