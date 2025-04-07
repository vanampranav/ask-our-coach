from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai
import redis
import json
from langdetect import detect
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for development
CORS(app)

# Set your OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")

# Initialize Redis client (make sure Redis is running locally)
#redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
redis_client = redis.from_url(redis_url, decode_responses=True)


@app.route('/')
def index():
    return "<h2>Fitness Chatbot Backend is Running</h2>"

@app.route('/chat', methods=['OPTIONS', 'POST'])
def chat_with_gpt():
    try:
        if request.method == 'OPTIONS':
            response = jsonify({"message": "CORS preflight successful"})
            response.status_code = 204
            return response

        data = request.get_json()
        prompt = data.get('prompt', '')

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # Redis cache
        cached_response = redis_client.get(prompt)  
        if cached_response:
            return jsonify({"reply": json.loads(cached_response)})

        # Call OpenAI
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are a fitness assistant. ALWAYS respond in English regardless of the input language.

IMPORTANT: All responses MUST be in English, even if the user's prompt is in another language.

MEAL_PLAN:
Provide a detailed meal plan for each section (Breakfast, Snack, Lunch, Dinner) with multiple items listed and clear varieties. Use numbers (1., 2., 3.) instead of dashes. The meal type (e.g., Breakfast, Snack) and all meal descriptions must be in English.

WORKOUT_PLAN:
- If the user specifies a number of days (e.g., '3 days', '5 days'), provide a workout plan for exactly that many days.
- If no specific days are mentioned, provide a standard 7-day plan.
- Each day should be clearly marked as 'Day 1:', 'Day 2:', etc.
- List multiple exercises per day, each numbered for better readability.
- All sections and exercise descriptions MUST be in English.
- For muscle gain focus on progressive overload and proper exercise splits.

Ensure each section follows this format exactly to maintain readability and parsing integrity.
Remember: ALWAYS respond in English regardless of the input language."""},
                {"role": "user", "content": prompt}
            ]
        )

        reply = response.choices[0].message.content
        redis_client.setex(prompt, 24 * 60 * 60, json.dumps(reply))  # cache for 24 hours

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run locally
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)

