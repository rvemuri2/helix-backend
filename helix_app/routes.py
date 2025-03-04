
import json
import re
from datetime import datetime
from flask import Blueprint, request, jsonify
import openai

from .app import db
from .models import User, Sequence, SequenceStep, ChatMessage

from .utils import (
    load_db_conversation,
    extract_step_number,
    classify_intent,
    function_definitions
)

main_bp = Blueprint("main_bp", __name__)

@main_bp.route("/api/classify", methods=["POST"])
def classify():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    if not user_input:
        return jsonify({"intent": "new_sequence"})
    intent = classify_intent(user_input)
    return jsonify({"intent": intent})


@main_bp.route("/api/sequence/update", methods=["PUT"])
def update_sequence():
    data = request.get_json()
    sequence_id = data.get("sequenceId")
    step_number = data.get("stepNumber")
    field = data.get("field")
    value = data.get("value")

    if not sequence_id or not step_number or not field:
        return jsonify({"error": "Missing required parameters."}), 400

    step = SequenceStep.query.filter_by(sequence_id=sequence_id, step_number=step_number).first()
    if not step:
        return jsonify({"error": "Step not found."}), 404

    if field == "stepTitle":
        step.title = value
    elif field == "stepContent":
        step.content = value
    else:
        return jsonify({"error": "Invalid field."}), 400

    db.session.commit()
    return jsonify({"message": "Step updated."}), 200


@main_bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"reply": "Missing user_id.", "sequence": []}), 400

    
    user = User.query.get(user_id)
    if not user:
        user = User(id=user_id)
        db.session.add(user)
        db.session.commit()

        default_msg = ChatMessage(user_id=user_id, message="How can I help you?", sender="ai")
        db.session.add(default_msg)
        db.session.commit()

    user_input = data.get("message", "").strip()
    if not user_input:
        return jsonify({"reply": "Empty message.", "sequence": []}), 400

    
    user_msg = ChatMessage(user_id=user_id, message=user_input, sender="user")
    db.session.add(user_msg)
    db.session.commit()

    
    intent = classify_intent(user_input)
    print("Classified intent:", intent)

    active_sequence = Sequence.query.filter_by(user_id=user_id).order_by(Sequence.created_at.desc()).first()

    if intent == "add_step":
        if not active_sequence:
            return jsonify({"reply": "No active sequence to add a step to.", "sequence": []}), 400

        existing_steps = SequenceStep.query.filter_by(sequence_id=active_sequence.id).order_by(SequenceStep.step_number).all()
        steps_text = "\n".join([f"{s.title} - {s.content}" for s in existing_steps])

        prompt = (
            "You are Helix, an AI assistant that appends a new step to an existing sequence. "
            "Do not modify any existing steps. The current sequence is:\n"
            + steps_text +
            "\nBased on the following user request, generate one new step as a JSON object with keys 'step_title' and 'step_content'. "
            "Ensure the style matches the existing steps. Do not change any other step."
        )
        messages_to_send = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ]

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages_to_send,
                temperature=0.7
            )
        except Exception as e:
            print("OpenAI API Error:", e)
            return jsonify({"reply": "Error calling OpenAI API", "sequence": []}), 500

        ai_output = response.choices[0].message.content.strip()
        
        if ai_output.startswith("```json"):
            ai_output = ai_output[len("```json"):].strip()
        if ai_output.endswith("```"):
            ai_output = ai_output[:-3].strip()

        
        try:
            new_step = json.loads(ai_output)
        except json.JSONDecodeError:
            
            new_step = {"step_title": ai_output, "step_content": ai_output}

        
        last_step = existing_steps[-1] if existing_steps else None
        new_num = last_step.step_number + 1 if last_step else 1

        seq_step = SequenceStep(
            sequence_id=active_sequence.id,
            step_number=new_num,
            title=new_step.get("step_title", f"Step {new_num}"),
            content=new_step.get("step_content", "")
        )
        db.session.add(seq_step)
        db.session.commit()

        updated_steps = [
            {
                "stepNumber": s.step_number,
                "stepTitle": s.title,
                "stepContent": s.content
            }
            for s in SequenceStep.query.filter_by(sequence_id=active_sequence.id).order_by(SequenceStep.step_number)
        ]

        ai_reply = "New step added to the sequence."
        conf_msg = ChatMessage(user_id=user_id, message=ai_reply, sender="ai")
        db.session.add(conf_msg)
        db.session.commit()

        return jsonify({
            "reply": ai_reply,
            "intent": intent,
            "sequence": updated_steps,
            "sequenceId": active_sequence.id
        })

    elif intent == "edit_step":
        if not active_sequence:
            return jsonify({"reply": "No active sequence to edit.", "sequence": []}), 400

        target_num = extract_step_number(user_input)
        if target_num == "last":
            existing_steps = SequenceStep.query.filter_by(
                sequence_id=active_sequence.id
            ).order_by(SequenceStep.step_number.desc()).all()
            if existing_steps:
                target_num = existing_steps[0].step_number
            else:
                return jsonify({"reply": "No steps available to edit.", "sequence": []}), 400

        if not target_num:
            return jsonify({"reply": "Could not determine which step to edit.", "sequence": []}), 400

        target_step = SequenceStep.query.filter_by(
            sequence_id=active_sequence.id,
            step_number=target_num
        ).first()

        if not target_step:
            return jsonify({"reply": f"Step {target_num} not found.", "sequence": []}), 404

        
        existing_steps = SequenceStep.query.filter_by(
            sequence_id=active_sequence.id
        ).order_by(SequenceStep.step_number).all()

        context_str = "\n".join([
            f"Step {s.step_number}: {s.title} - {s.content}"
            for s in existing_steps
        ])

        prompt = (
            f"You are Helix, a friendly AI assistant. The current sequence is:\n{context_str}\n"
            f"Your task is to update only the content of step {target_num} (currently titled '{target_step.title}') "
            "so that it fits naturally with the rest of the sequence in a warm, human tone. "
            f"Incorporate the following user request into the revised content: {user_input}\n"
            "Return only the final revised version of the step content as a single paragraph without any step number, title, or markdown formatting. "
            "If a new title is warranted due to a topic shift, output the new title on the first line (without markdown symbols), "
            "followed by the revised content on the next line. Do not modify any other step."
        )

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.7
            )
        except Exception as e:
            print("OpenAI API Error:", e)
            return jsonify({"reply": "Error calling OpenAI API for step edit", "sequence": []}), 500

        ai_response = response.choices[0].message.content.strip()

        if "clarify" in ai_response.lower():
            clar_msg = ChatMessage(user_id=user_id, message=ai_response, sender="ai")
            db.session.add(clar_msg)
            db.session.commit()

            updated_steps = [
                {
                    "stepNumber": s.step_number,
                    "stepTitle": s.title,
                    "stepContent": s.content
                }
                for s in existing_steps
            ]
            return jsonify({
                "reply": ai_response,
                "intent": "clarification",
                "sequence": updated_steps,
                "sequenceId": active_sequence.id
            })
        else:
            
            if "\n" in ai_response:
                parts = ai_response.split("\n", 1)
                proposed_title = parts[0].strip()
                proposed_content = parts[1].strip()
                
                new_title = (
                    proposed_title if proposed_title.lower() != target_step.title.lower()
                    else target_step.title
                )
                final_revision = proposed_content
            else:
                new_title = target_step.title
                final_revision = ai_response

            
            pattern = r"^" + re.escape(target_step.title) + r"[\s:\-]*"
            final_revision = re.sub(pattern, "", final_revision).strip()

            target_step.title = new_title
            target_step.content = final_revision
            db.session.add(target_step)
            db.session.commit()

            updated_steps = [
                {
                    "stepNumber": s.step_number,
                    "stepTitle": s.title,
                    "stepContent": s.content
                }
                for s in SequenceStep.query.filter_by(sequence_id=active_sequence.id).order_by(SequenceStep.step_number)
            ]
            ai_confirm = f"Step {target_num} updated."
            confirm_msg = ChatMessage(user_id=user_id, message=ai_confirm, sender="ai")
            db.session.add(confirm_msg)
            db.session.commit()

            return jsonify({
                "reply": ai_confirm,
                "intent": intent,
                "sequence": updated_steps,
                "sequenceId": active_sequence.id
            })

    elif intent == "new_sequence":
        if active_sequence:
            db.session.delete(active_sequence)
            db.session.commit()

        from .utils import load_db_conversation
        db_history = load_db_conversation(user_id)

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=db_history,
                functions=function_definitions,
                function_call="auto",
                temperature=0.7
            )
        except Exception as e:
            print("OpenAI API Error:", e)
            return jsonify({"reply": "Error calling OpenAI API", "sequence": []}), 500

        choice = response.choices[0]
        if choice.finish_reason == "function_call":
            fn_name = choice.message.function_call.name
            fn_args_json = choice.message.function_call.arguments
            if fn_name == "performTaskInSequences":
                try:
                    args = json.loads(fn_args_json) if isinstance(fn_args_json, str) else fn_args_json
                except json.JSONDecodeError:
                    args = {}

                title = args.get("sequence_title", "No Title")
                steps_data = args.get("steps", [])

                new_sequence = Sequence(user_id=user_id, title=title)
                db.session.add(new_sequence)
                db.session.commit()

                formatted_steps = []
                for i, step in enumerate(steps_data[:4], start=1):
                    seq_step = SequenceStep(
                        sequence_id=new_sequence.id,
                        step_number=i,
                        title=step.get("step_title", f"Step {i}"),
                        content=step.get("step_content", "")
                    )
                    db.session.add(seq_step)
                    formatted_steps.append({
                        "stepNumber": i,
                        "stepTitle": seq_step.title,
                        "stepContent": seq_step.content
                    })
                db.session.commit()

                ai_reply = "Here's your sequence. See the Sequence panel."
                confirm_msg = ChatMessage(user_id=user_id, message=ai_reply, sender="ai")
                db.session.add(confirm_msg)
                db.session.commit()

                return jsonify({
                    "reply": ai_reply,
                    "intent": intent,
                    "sequence": formatted_steps,
                    "sequenceId": new_sequence.id
                })
            else:
                ai_reply = "I attempted to call an unknown function."
                return jsonify({"reply": ai_reply, "sequence": []})
        else:
           
            ai_reply = choice.message.content
            ai_msg = ChatMessage(user_id=user_id, message=ai_reply, sender="ai")
            db.session.add(ai_msg)
            db.session.commit()
            return jsonify({"reply": ai_reply, "intent": intent, "sequence": []})

    else:
        return jsonify({
            "reply": "Unable to classify request. Please try again.",
            "sequence": []
        })


@main_bp.route("/api/load", methods=["GET"])
def load_history():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    chats = ChatMessage.query.filter_by(
        user_id=user_id
    ).order_by(ChatMessage.created_at.asc()).all()

    chat_history = [
        {
            "sender": msg.sender,
            "message": msg.message,
            "timestamp": msg.created_at.isoformat()
        }
        for msg in chats
    ]
    if not chat_history or (
        chat_history[0]["sender"] != "ai"
        or chat_history[0]["message"] != "How can I help you?"
    ):
        default_intro = {
            "sender": "ai",
            "message": "How can I help you?",
            "timestamp": datetime.utcnow().isoformat()
        }
        chat_history.insert(0, default_intro)

    sequences = Sequence.query.filter_by(
        user_id=user_id
    ).order_by(Sequence.created_at.asc()).all()

    sequences_data = []
    for seq in sequences:
        steps = SequenceStep.query.filter_by(sequence_id=seq.id).order_by(
            SequenceStep.step_number.asc()
        ).all()
        sequences_data.append({
            "sequence_id": seq.id,
            "title": seq.title,
            "steps": [
                {
                    "stepNumber": s.step_number,
                    "stepTitle": s.title,
                    "stepContent": s.content
                }
                for s in steps
            ]
        })

    print(f"Loaded history for user {user_id}: {len(chat_history)} messages, {len(sequences_data)} sequences")
    return jsonify({
        "chat_history": chat_history,
        "sequences": sequences_data
    })
