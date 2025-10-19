from app.models.ml_models import answer_models, answer_vectorizers

def predict_answer(processed_input, category, threshold=0.0):
    if category not in answer_models:
        return None, 0

    vectorizer_answer = answer_vectorizers[category]
    model_answer = answer_models[category]

    X_input_answer = vectorizer_answer.transform([processed_input])

    try:
        scores = model_answer.decision_function(X_input_answer)
        max_score = max(scores[0]) if len(scores.shape) > 1 else scores[0]
    except Exception:
        max_score = 0

    if max_score < threshold:
        return None, max_score
    else:
        predicted_answer = model_answer.predict(X_input_answer)[0]
        return predicted_answer, max_score