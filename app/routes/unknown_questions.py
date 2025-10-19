from flask import Blueprint, jsonify
from app.services.unknown_question_service import get_unknown_questions

unknown_bp = Blueprint('unknown', __name__)

@unknown_bp.route('/pertanyaan-unknown', methods=['GET'])
def get_unknown_questions_route():
    data = get_unknown_questions()
    if data is None:
        return jsonify({'error': 'Gagal mengambil data dari database'}), 500
    return jsonify(data)