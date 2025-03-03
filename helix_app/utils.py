import os
import re
import json
import openai
from .models import ChatMessage
from .app import db

openai.api_key = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = (
    "You are Helix, an AI assistant that generates fully personalized and actionable multi-step sequences "
    "for sales, outreach, or letters. Ask a clarifying question if the user's request is too vague. "
    "The first step must be a personalized greeting and introduction that starts with 'Hey {{First_Name}},' "
    "followed by an introductory paragraph. Subsequent steps should provide the detailed body of the message. "
    "Return your output as a JSON object with two keys: 'step_title' and 'step_content'."
)

function_definitions = [
    {
        "name": "performTaskInSequences",
        "description": (
            "Generate a multi-step sequence based on the user’s request. "
            "Return a JSON object with keys 'sequence_title' and 'steps', where each step is an object with keys 'step_title' and 'step_content'. "
            "If the user's request is vague, ask a clarifying question before generating the sequence."
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


def load_db_conversation(user_id):
    """
    Load conversation history from the DB and prepend the system prompt.
    Map 'ai' messages to 'assistant' for OpenAI context.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    chats = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.created_at).all()
    for msg in chats:
        role = "assistant" if msg.sender == "ai" else "user"
        messages.append({"role": role, "content": msg.message})
    return messages


def extract_step_number(user_input):
    """
    Extract a step number from the user input, supporting:
      - Digit-based references: "step 3"
      - Ordinal words: "the second step" or "step second"
      - Keywords "last" or "final" (returns the string "last")
      - Keywords "intro" or "beginning" (returns 1)
    """
    lower_input = user_input.lower()

    if re.search(r"(last|final)\s+step", lower_input):
        return "last"

    if re.search(r"(intro|beginning)\s+step", lower_input):
        return 1

    match = re.search(r"(?:the\s+)?step\s+(\d+)", lower_input)
    if match:
        return int(match.group(1))

    ordinal_pattern = r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    match = re.search(r"(?:the\s+)?(" + ordinal_pattern + r")\s+step", lower_input)
    if match:
        ordinals = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "sixth": 6,
            "seventh": 7,
            "eighth": 8,
            "ninth": 9,
            "tenth": 10
        }
        return ordinals.get(match.group(1))
    return None


def classify_intent(user_input):
    """
    Use GPT to classify the user's intent based on natural phrasing.

    Possible outputs:
      - "add_step"
      - "edit_step"
      - "new_sequence"
    """
    prompt = (
        "Based on the following user request, classify the intent into one of three categories: "
        "'add_step', 'edit_step', or 'new_sequence'.\n\n"
        "Guidelines:\n"
        "- If the request implies modifying or shortening an existing step (e.g., 'step 3 should be shorter'), output edit_step.\n"
        "- If the request implies inserting an additional step, output add_step.\n"
        "- Otherwise, output new_sequence.\n\n"
        f"User request: {user_input}\n\n"
        "Output only one word: add_step, edit_step, or new_sequence."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            temperature=0
        )
        intent = response.choices[0].message.content.strip().lower()
        if intent in ["add_step", "edit_step", "new_sequence"]:
            return intent
    except Exception as e:
        print("Classification error:", e)
    return "new_sequence"
