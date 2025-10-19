from app.models.ml_models import vectorizer_cat, model_cat

def predict_category(processed_input):
    X_input_cat = vectorizer_cat.transform([processed_input])
    predicted_category = model_cat.predict(X_input_cat)[0]
    return predicted_category