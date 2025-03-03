from datetime import datetime
from .app import db

class User(db.Model):
    id = db.Column(db.String, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Sequence(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    steps = db.relationship(
        "SequenceStep",
        backref="sequence",
        cascade="all, delete-orphan"
    )

class SequenceStep(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sequence_id = db.Column(db.Integer, db.ForeignKey("sequence.id"), nullable=False)
    step_number = db.Column(db.Integer)
    title = db.Column(db.String)
    content = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String)
    sender = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
