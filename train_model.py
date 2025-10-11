import pandas as pd
import pickle
from preprocessing import preprocess
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

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

# ===== Stage 2: Simpan TF-IDF untuk setiap kategori =====
category_vectorizers = {}
for cat in df['kategori'].unique():
    df_cat = df[df['kategori'] == cat]
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(df_cat['processed'])
    y = df_cat['jawaban']
    model = LinearSVC()
    model.fit(X, y)
    
    # Simpan
    with open(f'model/svm_model_answer_{cat}.pkl', 'wb') as f:
        pickle.dump(model, f)
    with open(f'model/vectorizer_answer_{cat}.pkl', 'wb') as f:
        pickle.dump(vectorizer, f)


print("✅ Stage 2: TF-IDF vectorizer per kategori berhasil disimpan!")
