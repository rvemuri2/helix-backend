import os
import openai
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI()
openai.api_key = os.getenv("OPENAI_API_KEY")

CONVERSATION_HISTORY = []

function_definitions = [
    {
        "name": "performTaskInSequences",
        "description": (
            "Implement the user's request in 3-4 concrete steps. "
            "If the user's request is too vague, FIRST ask ONE clarifying question, then proceed with generating the steps. "
            "Each step should contain the actual text for that part of the request, fully written and usable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sequence_title": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_title": {"type": "string"},
                            "step_content": {"type": "string"}
                        },
                        "required": ["step_title", "step_content"]
                    }
                }
            },
            "required": ["sequence_title", "steps"]
        }
    }
]

SYSTEM_PROMPT = (
    "You are Helix, an AI assistant that generates well-written multi-step sequences. "
    "If the user's request lacks enough detail, ask **ONLY ONE** focused clarifying question, then generate the sequence. "
    "DO NOT ask more than one question before generating the sequence. "
    "Make sure the question is directly related to the user's request, and avoid broad or off-topic questions. "
    "Once the user answers, generate 3-4 steps that are **fully written and usable**. "
    "Do not list generic steps—each step must contain actual content."
    "Example:\n"
    "**Step 1: Greeting**\n"
    "Hi {{first_name}}, I wanted to reach out about...\n"
    "**Step 2: Explain the offer**\n"
    "We are offering..."
)

if not CONVERSATION_HISTORY:
    CONVERSATION_HISTORY.append({"role": "system", "content": SYSTEM_PROMPT})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_input = data.get('message', '')

    if not openai.api_key:
        return jsonify({"reply": "Missing OpenAI API key.", "sequence": []}), 400

    
    last_message = CONVERSATION_HISTORY[-1] if CONVERSATION_HISTORY else None
    if last_message and last_message["role"] == "assistant" and "?" in last_message["content"]:
        
        CONVERSATION_HISTORY.append({"role": "user", "content": user_input})
    else:
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Does the following request lack enough details to generate content? Answer only 'yes' or 'no'."},
                {"role": "user", "content": user_input}
            ],
            temperature=0
        )

        needs_clarification = response.choices[0].message.content.strip().lower() == "yes"

        if needs_clarification:
            
            clarification_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Generate ONE short, specific clarifying question for this request. The question should be **on-topic** and only help complete the request."},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7
            )

            clarifying_question = clarification_response.choices[0].message.content.strip()
            CONVERSATION_HISTORY.append({"role": "assistant", "content": clarifying_question})

            return jsonify({"reply": clarifying_question, "sequence": []})

    CONVERSATION_HISTORY.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=CONVERSATION_HISTORY,
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
            except json.JSONDecodeError as e:
                args = {}
                print("JSON decode error:", e)

            title = args.get("sequence_title", "No Title")
            steps = args.get("steps", [])

            formatted_steps = []
            for i, step in enumerate(steps[:4], start=1):
                formatted_steps.append({
                    "stepNumber": i,
                    "stepTitle": step.get("step_title", f"Step {i}"),
                    "stepContent": step.get("step_content", "")
                })

            ai_reply = "Here's your sequence. See the Sequence panel."

            CONVERSATION_HISTORY.append({"role": "assistant", "content": ai_reply})

            return jsonify({"reply": ai_reply, "sequence": formatted_steps})
        else:
            ai_reply = "I attempted to call an unknown function."
            CONVERSATION_HISTORY.append({"role": "assistant", "content": ai_reply})
            return jsonify({"reply": ai_reply, "sequence": []})
    else:
        ai_reply = choice.message.content
        CONVERSATION_HISTORY.append({"role": "assistant", "content": ai_reply})
        return jsonify({"reply": ai_reply, "sequence": []})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
