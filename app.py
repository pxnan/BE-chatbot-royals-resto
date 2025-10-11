import pickle
import pandas as pd
from preprocessing import preprocess
from flask import Flask, request, jsonify

# Load model kategori
with open('model/tfidf_vectorizer_category.pkl', 'rb') as f:
    vectorizer_cat = pickle.load(f)
with open('model/svm_model_category.pkl', 'rb') as f:
    model_cat = pickle.load(f)

# Load dataset
df = pd.read_csv('data/dataset.csv')
df['processed'] = df['pertanyaan'].apply(preprocess)

# Load semua model jawaban per kategori
answer_models = {}
answer_vectorizers = {}
for cat in df['kategori'].unique():
    with open(f'model/svm_model_answer_{cat}.pkl', 'rb') as f:
        answer_models[cat] = pickle.load(f)
    with open(f'model/vectorizer_answer_{cat}.pkl', 'rb') as f:
        answer_vectorizers[cat] = pickle.load(f)

app = Flask(__name__)

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    processed_input = preprocess(user_input)

    # ===== Stage 1: Prediksi kategori =====
    X_input_cat = vectorizer_cat.transform([processed_input])
    predicted_category = model_cat.predict(X_input_cat)[0]

    # ===== Stage 2: Prediksi jawaban =====
    vectorizer_answer = answer_vectorizers[predicted_category]
    model_answer = answer_models[predicted_category]

    X_input_answer = vectorizer_answer.transform([processed_input])

    # Gunakan decision function SVM untuk confidence
    try:
        scores = model_answer.decision_function(X_input_answer)
        max_score = max(scores[0]) if len(scores.shape) > 1 else scores[0]
    except:
        max_score = 0

    threshold = 0.0  # Bisa disesuaikan dataset
    if max_score < threshold:
        predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda."
    else:
        predicted_answer = model_answer.predict(X_input_answer)[0]

    return jsonify({
        'pertanyaan': user_input,
        'kategori': predicted_category,
        'jawaban': predicted_answer
    })

if __name__ == '__main__':
    app.run(debug=True)
