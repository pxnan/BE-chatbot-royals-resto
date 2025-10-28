import pandas as pd
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC


# ===== Load Dataset =====
df = pd.read_csv('data/dataset.csv')

# Preprocessing sederhana (gantikan dengan fungsi preprocessing Anda)
def preprocess(text):
    if not isinstance(text, str):
        return ""
    # Contoh preprocessing sederhana
    text = text.lower().strip()
    # Tambahkan preprocessing lain sesuai kebutuhan
    return text

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

# ===== Stage 2: Train SVM untuk matching pertanyaan dalam setiap kategori =====
for cat in df['kategori'].unique():
    df_cat = df[df['kategori'] == cat]
    
    # Untuk setiap kategori, kita train model SVM yang memetakan pertanyaan ke indeks jawaban
    X_qa = df_cat['processed']
    
    # Label adalah indeks dari jawaban
    y_qa = list(range(len(df_cat)))
    
    vectorizer_qa = TfidfVectorizer()
    X_qa_tfidf = vectorizer_qa.fit_transform(X_qa)
    
    model_qa = LinearSVC()
    model_qa.fit(X_qa_tfidf, y_qa)
    
    # Simpan model, vectorizer, dan mapping jawaban untuk kategori ini
    category_data = {
        'model': model_qa,
        'vectorizer': vectorizer_qa,
        'answers': df_cat['jawaban'].tolist(),
        'questions': df_cat['pertanyaan'].tolist()
    }
    
    with open(f'model/svm_qa_model_{cat}.pkl', 'wb') as f:
        pickle.dump(category_data, f)
    
    print(f"✅ Model untuk kategori '{cat}' berhasil disimpan!")

print("✅ Stage 2: Semua model QA per kategori berhasil dilatih dan disimpan!")