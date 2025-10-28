import pickle
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score
import seaborn as sns
import matplotlib.pyplot as plt
from preprocessing import preprocess

# ===== Load model kategori =====
with open('model/tfidf_vectorizer_category.pkl', 'rb') as f:
    vectorizer_cat = pickle.load(f)
with open('model/svm_model_category.pkl', 'rb') as f:
    model_cat = pickle.load(f)

# ===== Data Testing =====
X_test = [
    "Makanan vegetarian apakah ada?",
    "Ada promo akhir pekan?",
    "Dimana alamat Royal's Resto?",
    "Apakah ada kursi untuk bayi?",
    "Bisa pesan makanan lewat GoFood?",
    "Bayar pakai QRIS bisa?",
    "Disini terima reservasi tidak?"
]

y_test = [
    "menu",
    "promo",
    "informasi_umum",
    "fasilitas",
    "layanan",
    "pembayaran",
    "reservasi"
]

# Preprocess data testing
X_test_processed = [preprocess(q) for q in X_test]

# ===== Prediksi kategori =====
X_test_tfidf = vectorizer_cat.transform(X_test_processed)
y_pred = model_cat.predict(X_test_tfidf)

# ===== Confusion Matrix =====
cm = confusion_matrix(y_test, y_pred, labels=model_cat.classes_)

# Visualisasi Confusion Matrix
plt.figure(figsize=(8,6))
sns.heatmap(cm, annot=True, fmt='d', xticklabels=model_cat.classes_, yticklabels=model_cat.classes_, cmap="Blues")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Confusion Matrix - Kategori Chatbot")
plt.show()

# ===== Classification Report & Accuracy dalam persen =====
accuracy = accuracy_score(y_test, y_pred) * 100
print(f"Accuracy: {accuracy:.2f}%\n")  # tampilkan 2 desimal

print("Classification Report:\n")
print(classification_report(y_test, y_pred))
