from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai
import redis
import json
from langdetect import detect
import os
from dotenv import load_dotenv
import time
import uuid

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
        force_new = data.get('forceNew', False)

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # Add a unique identifier to the prompt
        unique_id = str(uuid.uuid4())[:8]
        timestamp = int(time.time())
        
        # Cache key will be the original prompt
        cache_key = prompt
        
        # Actual prompt sent to AI includes the unique identifier
        unique_prompt = f"{prompt}\n\nRequest-ID: {unique_id}-{timestamp}"

        # Redis cache (skip if force_new is True)
        if not force_new:
            cached_response = redis_client.get(cache_key)  
            if cached_response:
                return jsonify({"reply": json.loads(cached_response)})

        # Call OpenAI
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are a fitness assistant. ALWAYS respond in English regardless of the input language.

IMPORTANT FORMATTING RULES:
1. All responses MUST be in English, even if the user's prompt is in another language.
2. Default time period is 3 months unless specified otherwise.
3. Default workout days is 7 days per week unless user specifies fewer days (e.g., "4 days").
4. NEVER exceed the number of days requested by the user.
5. EXACTLY 3 items per meal type (no more, no less).
6. EXACTLY 4 exercises per workout day (no more, no less).
7. CRITICAL: The number of days in the MEAL_PLAN must EXACTLY MATCH the number of days in the WORKOUT_PLAN.
8. If user requests "5 days", provide EXACTLY 5 days of both meal AND workout plans.
9. ALWAYS include both MEAL_PLAN and WORKOUT_PLAN sections in your response with clear section headers.

CULTURAL & PERSONAL CUSTOMIZATION:
1. If the user mentions their nationality, country, or cultural background (e.g., "Indian food," "I am from Mexico"), provide meals specific to that culture using authentic ingredients and dishes.
2. If the user mentions dietary restrictions (vegetarian, vegan, halal, kosher, etc.), strictly adhere to those guidelines.
3. If user mentions specific physical attributes (age, weight, height, BMI, gender), customize the plan accordingly with appropriate calorie counts and exercise intensity.
4. For medical conditions (diabetes, hypertension, etc.), include appropriate dietary modifications.
5. Match exercise intensity to stated fitness levels (beginner, intermediate, advanced).

MEAL_PLAN FORMAT:
MEAL_PLAN:
For each day (Day 1 to N, where N is user requested days):
Day X:
- Breakfast (XXX calories):
  1. [Meal item 1]
  2. [Meal item 2]
  3. [Meal item 3]
- Lunch (XXX calories):
  1. [Meal item 1]
  2. [Meal item 2]
  3. [Meal item 3]
- Snack (XXX calories):
  1. [Snack item 1]
  2. [Snack item 2]
  3. [Snack item 3]
- Dinner (XXX calories):
  1. [Meal item 1]
  2. [Meal item 2]
  3. [Meal item 3]

Total Daily Calories: XXXX

WORKOUT_PLAN FORMAT:
WORKOUT_PLAN:
Timeline: X months
Weekly Schedule: Y days per week
Expected Results: [Describe expected results after following this plan for the specified months]

For each day (Day 1 to N, where N is user requested days):
Day X - [Focus Area]:
1. [Exercise 1 with sets/reps]
2. [Exercise 2 with sets/reps]
3. [Exercise 3 with sets/reps]
4. [Exercise 4 with sets/reps]

EXAMPLE RESPONSE FORMAT:
MEAL_PLAN:
Day 1:
- Breakfast (300 calories):
  1. Oatmeal with berries
  2. Greek yogurt
  3. Almonds
- Lunch (400 calories):
  1. Grilled chicken salad
  2. Whole grain bread
  3. Olive oil dressing
- Snack (150 calories):
  1. Apple
  2. Peanut butter
  3. Celery sticks
- Dinner (450 calories):
  1. Baked salmon
  2. Steamed broccoli
  3. Brown rice

Total Daily Calories: 1300

WORKOUT_PLAN:
Timeline: 3 months
Weekly Schedule: 5 days per week
Expected Results: Weight loss of 8-10 pounds, improved muscle tone and cardiovascular health.

Day 1 - Cardio:
1. Jumping jacks (3 sets of 20 reps)
2. High knees (2 minutes)
3. Mountain climbers (3 sets of 15 reps)
4. Jogging in place (5 minutes)

Day 2 - Strength:
1. Push-ups (3 sets of 10 reps)
2. Squats (3 sets of 15 reps)
3. Lunges (3 sets of 10 reps each leg)
4. Plank (3 sets of 30 seconds)

Notes:
- Each meal MUST include calorie count
- Each meal type MUST have EXACTLY 3 items
- Each day MUST have a total calorie count
- Each workout day MUST have EXACTLY 4 exercises
- Workouts MUST be appropriate for the specified fitness level
- Include expected results after following the plan for specified months
- Adjust intensity based on experience level
- Consider any health conditions or dietary restrictions in recommendations
- IMPORTANT: Both MEAL_PLAN and WORKOUT_PLAN must have EXACTLY the same number of days

Remember: ALWAYS respond in English regardless of the input language."""},
                {"role": "user", "content": unique_prompt}
            ]
        )

        reply = response.choices[0].message.content
        
        # Don't cache if force_new is True
        if not force_new:
            redis_client.setex(cache_key, 24 * 60 * 60, json.dumps(reply))  # cache for 24 hours

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check-cache', methods=['OPTIONS', 'POST'])
def check_cache():
    """Endpoint to quickly check if a response is cached without making API call"""
    try:
        if request.method == 'OPTIONS':
            response = jsonify({"message": "CORS preflight successful"})
            response.status_code = 204
            return response

        data = request.get_json()
        prompt = data.get('prompt', '')

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # Parse useful information from the prompt
        prompt_info = {
            "requested_days": 7,  # Default value
            "countries": [],
            "dietary_preferences": [],
            "age": None,
            "gender": None,
        }
        
        # Extract days
        days_match = prompt.lower().find("days")
        if days_match > 0:
            # Look for a number before "days"
            for i in range(days_match - 1, max(0, days_match - 5), -1):
                if prompt[i].isdigit():
                    day_str = ""
                    while i >= 0 and prompt[i].isdigit():
                        day_str = prompt[i] + day_str
                        i -= 1
                    if day_str:
                        prompt_info["requested_days"] = int(day_str)
                        break
        
        # Look for country or cuisine references
        countries = ["indian", "chinese", "mexican", "italian", "japanese", "thai", 
                    "korean", "french", "greek", "mediterranean", "american", "middle eastern",
                    "spanish", "turkish", "brazilian", "vietnamese"]
        
        for country in countries:
            if country.lower() in prompt.lower():
                prompt_info["countries"].append(country)
        
        # Look for dietary preferences
        diets = ["vegetarian", "vegan", "keto", "paleo", "gluten-free", "dairy-free", 
                "low-carb", "high-protein", "halal", "kosher"]
        
        for diet in diets:
            if diet.lower() in prompt.lower():
                prompt_info["dietary_preferences"].append(diet)
        
        # Check Redis cache
        cached_response = redis_client.get(prompt)
        
        if cached_response:
            return jsonify({
                "cached": True,
                "reply": json.loads(cached_response),
                "requestedDays": prompt_info["requested_days"],
                "promptInfo": prompt_info
            })
        
        return jsonify({
            "cached": False,
            "promptInfo": prompt_info
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run locally
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)

