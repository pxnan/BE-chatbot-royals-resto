import pickle
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score
import seaborn as sns
import matplotlib.pyplot as plt
from preprocessing import preprocess
import numpy as np

# ===== Load QA Model Tunggal =====
with open('model/model_qa.pkl', 'rb') as f:
    qa_data = pickle.load(f)

model_qa = qa_data['model']
vectorizer_qa = qa_data['vectorizer']
categories = qa_data['categories']  # kategori setiap pertanyaan

# ===== Load Dataset Testing =====
df_test = pd.DataFrame({
    'pertanyaan': [
        "Makanan vegetarian apakah ada?",
        "Ada promo akhir pekan?",
        "Dimana alamat Royal's Resto?",
        "Apakah ada kursi untuk bayi?",
        "Bisa pesan makanan lewat GoFood?",
        "Bayar pakai QRIS bisa?",
        "Disini terima reservasi tidak?"
    ],
    'kategori': [
        "menu",
        "promo",
        "informasi_umum",
        "fasilitas",
        "layanan",
        "pembayaran",
        "reservasi"
    ]
})

# Preprocess pertanyaan
df_test['processed'] = df_test['pertanyaan'].apply(preprocess)

# Transform pertanyaan testing
X_test_tfidf = vectorizer_qa.transform(df_test['processed'])

# Prediksi indeks jawaban
y_pred_indices = model_qa.predict(X_test_tfidf)

# Ambil kategori prediksi berdasarkan indeks jawaban
y_pred_categories = [categories[i] for i in y_pred_indices]
y_true_categories = df_test['kategori'].tolist()

# ===== Hitung Akurasi Kategori =====
accuracy = accuracy_score(y_true_categories, y_pred_categories) * 100
print(f"Accuracy Kategori: {accuracy:.2f}%\n")

# ===== Confusion Matrix Kategori =====
unique_categories = list(set(categories))
cm = confusion_matrix(y_true_categories, y_pred_categories, labels=unique_categories)
plt.figure(figsize=(8,6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=unique_categories, yticklabels=unique_categories)
plt.xlabel("Predicted Category")
plt.ylabel("Actual Category")
plt.title("Confusion Matrix - Kategori QA")
plt.show()

# ===== Classification Report Kategori =====
print("Classification Report - Kategori:\n")
print(classification_report(y_true_categories, y_pred_categories))
