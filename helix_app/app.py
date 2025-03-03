import os
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.url_map.strict_slashes = False

    CORS(app)

   
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///helix_database.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

   
    db.init_app(app)

    
    with app.app_context():
        db.create_all()

    
    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
