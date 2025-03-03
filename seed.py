import datetime
from helix_app.app import create_app, db
from helix_app.models import User, Sequence, SequenceStep, ChatMessage

def seed_data():
    app = create_app()
    with app.app_context():
        
        dummy_user = User(
            id="dummy_user_123",
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(dummy_user)
        db.session.commit()

        
        dummy_sequence = Sequence(
            user_id="dummy_user_123",
            title="Test Sequence",
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(dummy_sequence)
        db.session.commit()  

        
        step1 = SequenceStep(
            sequence_id=dummy_sequence.id,
            step_number=1,
            title="Intro Step",
            content="Hey {{First_Name}}, welcome to our dummy sequence!",
            created_at=datetime.datetime.utcnow()
        )
        step2 = SequenceStep(
            sequence_id=dummy_sequence.id,
            step_number=2,
            title="Follow-Up Step",
            content="Here's more information about our dummy data.",
            created_at=datetime.datetime.utcnow()
        )
        db.session.add_all([step1, step2])
        db.session.commit()

        
        chat_msg = ChatMessage(
            user_id="dummy_user_123",
            message="How can I help you?",
            sender="ai",
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(chat_msg)
        db.session.commit()

        print("Dummy data inserted successfully!")

if __name__ == "__main__":
    seed_data()
