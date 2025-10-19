import pickle
import pandas as pd
from app.utils.preprocessing import preprocess

# Load model kategori
with open('model/tfidf_vectorizer_category.pkl', 'rb') as f:
    vectorizer_cat = pickle.load(f)
with open('model/svm_model_category.pkl', 'rb') as f:
    model_cat = pickle.load(f)

# Load dataset untuk mendapatkan kategori
df = pd.read_csv('data/dataset.csv')
df['processed'] = df['pertanyaan'].apply(preprocess)

# Load model jawaban per kategori
answer_models = {}
answer_vectorizers = {}
for cat in df['kategori'].unique():
    try:
        with open(f'model/svm_model_answer_{cat}.pkl', 'rb') as f:
            answer_models[cat] = pickle.load(f)
        with open(f'model/vectorizer_answer_{cat}.pkl', 'rb') as f:
            answer_vectorizers[cat] = pickle.load(f)
    except FileNotFoundError:
        print(f"[WARNING] Model untuk kategori '{cat}' tidak ditemukan.")