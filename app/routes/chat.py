from flask import Blueprint, request, jsonify
from app.utils.preprocessing import preprocess
from app.services.category_predictor import predict_category
from app.services.answer_predictor import predict_answer
from app.services.unknown_question_service import save_unknown_question

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('pertanyaan', '')
    if not user_input:
        return jsonify({'error': 'Pertanyaan kosong'}), 400

    processed_input = preprocess(user_input)
    predicted_category = predict_category(processed_input)

    predicted_answer, confidence = predict_answer(processed_input, predicted_category)

    if predicted_answer is None:
        save_unknown_question(user_input)
        predicted_answer = "Mohon maaf, saya belum mengerti pertanyaan Anda."

    return jsonify({
        'pertanyaan': user_input,
        'kategori': predicted_category,
        'jawaban': predicted_answer
    })