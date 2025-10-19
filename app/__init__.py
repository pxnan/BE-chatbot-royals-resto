from flask import Flask
from flask_cors import CORS
from app.config import Config
from app.routes.chat import chat_bp
from app.routes.unknown_questions import unknown_bp

def create_app():
    app = Flask(__name__)
    CORS(app, origins="*")

    # Register blueprints
    app.register_blueprint(chat_bp)
    app.register_blueprint(unknown_bp)

    return app