import os
import re
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file in parent directory
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Set GEMINI_API_KEY from GOOGLE_API_KEY for compatibility
if os.getenv('GOOGLE_API_KEY'):
    os.environ['GEMINI_API_KEY'] = os.getenv('GOOGLE_API_KEY')


class IntentEngine:
    """
    Deterministic intent token generator with strict validation and budget tracking.
    """

    # Define action types and their MANDATORY parameters with estimated budgets
    ACTION_SCHEMAS = {
        "BOOK_FLIGHT": {
            "required": ["origin", "destination", "date", "website", "price"],
            "optional": ["airline", "class", "flight_number", "time"],
            "budget_range": {"low": 100, "medium": 300, "high": 800, "currency": "USD"}
        },
        "BOOK_TRAIN": {
            "required": ["origin", "destination", "date", "time", "website", "price"],
            "optional": ["train_number", "class", "seat_type"],
            "budget_range": {"low": 20, "medium": 80, "high": 200, "currency": "USD"}
        },
        "BOOK_HOTEL": {
            "required": ["hotel_name", "location", "check_in", "check_out", "website", "price"],
            "optional": ["room_type", "rating", "amenities", "guests"],
            "budget_range": {"low": 50, "medium": 150, "high": 400, "currency": "USD per night"}
        },
        "BOOK_RESTAURANT": {
            "required": ["restaurant_name", "location", "date", "time", "website", "price"],
            "optional": ["cuisine", "party_size", "reservation_id"],
            "budget_range": {"low": 15, "medium": 50, "high": 150, "currency": "USD per person"}
        },
        "BOOK_ATTRACTION": {
            "required": ["attraction_name", "location", "date", "time", "website", "price"],
            "optional": ["ticket_type", "duration"],
            "budget_range": {"low": 10, "medium": 40, "high": 100, "currency": "USD"}
        },
        "BOOK_TRANSPORT": {
            "required": ["transport_type", "from_location", "to_location", "date", "time", "price"],
            "optional": ["service_name", "vehicle_type"],
            "budget_range": {"low": 10, "medium": 30, "high": 80, "currency": "USD"}
        },
        "MAKE_PAYMENT": {
            "required": ["amount", "merchant", "payment_method", "date", "time"],
            "optional": ["currency", "description"],
            "budget_range": {"low": 0, "medium": 100, "high": 500, "currency": "USD"}
        }
    }

    @staticmethod
    def get_budget_display(action_type):
        """
        Get formatted budget display for an action type.
        """
        schema = IntentEngine.ACTION_SCHEMAS.get(action_type, {})
        budget = schema.get('budget_range', {"low": 0, "medium": 0, "high": 0, "currency": "USD"})

        return (f"💰 Typical Budget: "
                f"Low: ${budget['low']} | "
                f"Medium: ${budget['medium']} | "
                f"High: ${budget['high']} {budget['currency']}")

    @staticmethod
    def validate_step_data(action_type, step_data, step_description):
        """
        Validate that all required fields are present.
        Returns (is_valid, missing_fields)
        """
        schema = IntentEngine.ACTION_SCHEMAS.get(action_type, {"required": [], "optional": []})
        required_fields = schema['required']

        missing_fields = []
        for field in required_fields:
            if field not in step_data or not step_data[field]:
                missing_fields.append(field)

        return len(missing_fields) == 0, missing_fields

    @staticmethod
    def calculate_confidence(action_type, step_data):
        """
        Calculate confidence based on data completeness.
        """
        schema = IntentEngine.ACTION_SCHEMAS.get(action_type, {"required": [], "optional": []})
        required_fields = schema['required']
        optional_fields = schema.get('optional', [])

        if not required_fields:
            return 0.5

        required_present = sum(1 for field in required_fields if field in step_data and step_data[field])
        required_ratio = required_present / len(required_fields)

        if required_ratio < 1.0:
            return round(required_ratio * 0.6, 2)

        optional_present = sum(1 for field in optional_fields if field in step_data and step_data[field])
        optional_bonus = (optional_present / max(len(optional_fields), 1)) * 0.15

        confidence = min(0.85 + optional_bonus, 1.0)
        return round(confidence, 2)

    @staticmethod
    def extract_action_type(step_description):
        """
        Deterministically extract action type from step description.
        """
        step_lower = step_description.lower()

        if "flight" in step_lower or "fly" in step_lower or "airplane" in step_lower:
            return "BOOK_FLIGHT"
        elif "train" in step_lower or "rail" in step_lower or "shinkansen" in step_lower:
            return "BOOK_TRAIN"
        elif "hotel" in step_lower or "accommodation" in step_lower or "check-in" in step_lower or "check in" in step_lower:
            return "BOOK_HOTEL"
        elif "restaurant" in step_lower or "dine" in step_lower or "dinner" in step_lower or "lunch" in step_lower or "breakfast" in step_lower or "cafe" in step_lower:
            return "BOOK_RESTAURANT"
        elif "ticket" in step_lower or "attraction" in step_lower or "museum" in step_lower or "tour" in step_lower or "temple" in step_lower or "shrine" in step_lower:
            return "BOOK_ATTRACTION"
        elif "taxi" in step_lower or "uber" in step_lower or "transport" in step_lower or "bus" in step_lower:
            return "BOOK_TRANSPORT"
        elif "pay" in step_lower or "payment" in step_lower:
            return "MAKE_PAYMENT"
        else:
            return "GENERAL_ACTION"

    @classmethod
    def generate_intent_token(cls, step_number, step_description, step_data):
        """
        Generate a deterministic intent token for a plan step.
        """
        action_type = cls.extract_action_type(step_description)
        is_valid, missing_fields = cls.validate_step_data(action_type, step_data, step_description)
        confidence = cls.calculate_confidence(action_type, step_data)

        payload = {
            "action": action_type,
            "step_number": step_number,
            "description": step_description,
            "confidence": confidence,
            "data_complete": is_valid,
            "missing_fields": missing_fields if missing_fields else None,
            "budget": cls.ACTION_SCHEMAS.get(action_type, {}).get('budget_range', {})
        }

        for key, value in step_data.items():
            if value:
                payload[key] = value

        intent_token = {
            "type": "INTENT_TOKEN",
            "payload": payload
        }

        return intent_token


def ask_yes_no_questions(questions):
    """
    Ask yes/no questions with 'other' option and display reasoning.
    LIMITED TO 10 QUESTIONS MAX.
    """
    if len(questions) > 10:
        print(f"\n⚠️  Limiting to 10 most critical questions (from {len(questions)} total)\n")
        questions = questions[:10]

    responses = {}
    print("\n" + "="*80)
    print("🤖 GEMINI NEEDS MORE INFORMATION TO COMPLETE YOUR TRAVEL PLAN")
    print("="*80)
    print(f"\nPlease answer these {len(questions)} yes/no questions to help me create")
    print("accurate intent tokens and booking details.\n")

    for i, question_data in enumerate(questions, 1):
        print("-" * 80)
        print(f"\n📍 Question {i} of {len(questions)}")
        print("━" * 80)

        # Display why we're asking
        if question_data.get('why_asking'):
            print(f"\n🎯 Why we're asking: {question_data['why_asking']}")

        # Display budget context if available
        if question_data.get('budget_info'):
            print(f"\n{question_data['budget_info']}")

        # Display the yes/no question
        print(f"\n❓ {question_data['question']}")

        # Display context/examples
        if question_data.get('context'):
            print(f"\n💡 {question_data['context']}")

        # Get input with yes/no/other options
        print(f"\n{'▸' * 40}")
        print("   Options:")
        print("   - Type 'yes' or 'y' to confirm")
        print("   - Type 'no' or 'n' to decline")
        print("   - Type anything else to provide a custom answer")
        print()

        answer = input("   Your answer: ").strip()

        while not answer:
            print("   ⚠️  Please provide an answer to continue.")
            answer = input("   Your answer: ").strip()

        # Normalize yes/no responses
        answer_lower = answer.lower()
        if answer_lower in ['yes', 'y']:
            answer = 'yes'
        elif answer_lower in ['no', 'n']:
            answer = 'no'

        responses[question_data['id']] = {
            'question': question_data['question'],
            'answer': answer,
            'field': question_data.get('field'),
            'step': question_data.get('step')
        }
        print()

    print("="*80)
    print("✅ Thank you! Processing your answers...")
    print("="*80 + "\n")
    return responses


def extract_structured_data(step_text):
    """
    Extract structured data from step text with enhanced patterns.
    """
    data = {}

    # Extract dates
    date_pattern = r'(?:on\s+)?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|Day\s+\d+)'
    dates = re.findall(date_pattern, step_text, re.IGNORECASE)
    if dates:
        data['date'] = dates[0]

    # Extract times
    time_patterns = [
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
        r'(\d{1,2}\s*(?:AM|PM|am|pm))',
        r'at\s+(\d{1,2}:\d{2})',
        r'(\d{1,2}h\d{2})',
    ]

    for pattern in time_patterns:
        times = re.findall(pattern, step_text, re.IGNORECASE)
        if times:
            data['time'] = times[0]
            break

    if 'time' not in data:
        if 'morning' in step_text.lower() or 'breakfast' in step_text.lower():
            data['time'] = '9:00 AM'
        elif 'afternoon' in step_text.lower() or 'lunch' in step_text.lower():
            data['time'] = '1:00 PM'
        elif 'evening' in step_text.lower() or 'dinner' in step_text.lower():
            data['time'] = '7:00 PM'

    # Extract prices
    price_patterns = [
        r'(?:¥|JPY)\s*(\d+(?:,\d{3})*)',
        r'(?:[$]|USD)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(?:€|EUR)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(\d+(?:,\d{3})*)\s*(?:JPY|USD|EUR|yen|dollars)',
    ]

    for pattern in price_patterns:
        prices = re.findall(pattern, step_text, re.IGNORECASE)
        if prices:
            data['price'] = prices[0].replace(',', '')
            break

    # Extract websites
    website_patterns = [
        r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.(?:com|net|org|co\.uk|co\.jp|io))',
        r'on\s+([A-Z][a-zA-Z0-9]+(?:\.com|\.jp|\.net))',
        r'via\s+([A-Z][a-zA-Z0-9]+(?:\.com|\.jp|\.net))',
    ]

    for pattern in website_patterns:
        websites = re.findall(pattern, step_text, re.IGNORECASE)
        if websites:
            website = websites[0]
            if '.' not in website:
                website = website + '.com'
            data['website'] = website.lower()
            break

    # Extract locations
    location_patterns = [
        r'from\s+([A-Z][a-zA-Z\s]+?(?:Airport|Station|Terminal))',
        r'to\s+([A-Z][a-zA-Z\s]+?(?:Airport|Station|Terminal))',
        r'at\s+([A-Z][a-zA-Z\s&\'-]+?)(?:\s*\(|,|\.|$)',
        r'Location:\s*([A-Z][^(]+?)(?:\(|$)',
        r'in\s+([A-Z][a-zA-Z\s]+?)(?:\s+area|,|\.|$)',
    ]

    for pattern in location_patterns:
        locations = re.findall(pattern, step_text)
        if locations:
            location = locations[0].strip()

            if 'from' in step_text.lower() and 'to' in step_text.lower():
                from_match = re.search(r'from\s+([A-Z][a-zA-Z\s]+?)(?:\s+to|\()', step_text)
                to_match = re.search(r'to\s+([A-Z][a-zA-Z\s]+?)(?:\s*\(|,|\.)', step_text)
                if from_match:
                    data['origin'] = from_match.group(1).strip()
                if to_match:
                    data['destination'] = to_match.group(1).strip()
            else:
                data['location'] = location
            break

    # Extract specific names
    name_patterns = [
        r'(?:hotel|stay at)\s+([A-Z][a-zA-Z\s&\'-]+?)(?:\s*\(|,|\.|\s+in)',
        r'(?:restaurant|cafe|dine at)\s+([A-Z][a-zA-Z\s&\'-]+?)(?:\s*\(|,|\.)',
        r'(?:visit|explore)\s+([A-Z][a-zA-Z\s&\'-]+?)(?:\s*\(|,|\.)',
    ]

    for pattern in name_patterns:
        names = re.findall(pattern, step_text, re.IGNORECASE)
        if names:
            name = names[0].strip()
            if 'hotel' in step_text.lower() or 'stay' in step_text.lower():
                data['hotel_name'] = name
            elif 'restaurant' in step_text.lower() or 'cafe' in step_text.lower() or 'dine' in step_text.lower():
                data['restaurant_name'] = name
            else:
                data['attraction_name'] = name
            break

    # Check-in/Check-out for hotels
    checkin_pattern = r'(?:check-in|check in).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
    checkout_pattern = r'(?:check-out|check out).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'

    checkin = re.search(checkin_pattern, step_text, re.IGNORECASE)
    checkout = re.search(checkout_pattern, step_text, re.IGNORECASE)

    if checkin:
        data['check_in'] = checkin.group(1)
    if checkout:
        data['check_out'] = checkout.group(1)

    return data


def parse_step_wise_plan(plan_text):
    """
    Parse the step-wise plan and extract structured data for each step.
    """
    steps = []

    step_pattern = r'(?:Step\s+)?(\d+)[.:]?\s+(.*?)(?=(?:Step\s+)?\d+[.:]|$)'
    matches = re.finditer(step_pattern, plan_text, re.DOTALL | re.IGNORECASE)

    for match in matches:
        step_num = int(match.group(1))
        step_content = match.group(2).strip()

        if len(step_content) < 10:
            continue

        step_data = extract_structured_data(step_content)

        steps.append({
            "step_number": step_num,
            "description": step_content,
            "structured_data": step_data
        })

    return steps


def create_yes_no_question(field, step_num, action, step_description, suggested_value=None):
    """
    Create a yes/no question with context, reasoning, and budget info.
    """
    # Get budget info for this action type
    budget_display = IntentEngine.get_budget_display(action)

    question_templates = {
        'time': {
            'question': f"For Step {step_num}, should we schedule this at {suggested_value or '9:00 AM'}?" if suggested_value else f"For Step {step_num}, is morning time (9:00 AM) suitable?",
            'context': f"This is for: {step_description[:100]}..." + (f" Current suggestion: {suggested_value}" if suggested_value else ""),
            'why_asking': f"We need an exact time to create a valid booking token. This ensures proper scheduling and availability checks.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, 'no' to suggest different time, or type your preferred time (e.g., '2:30 PM')"
        },
        'date': {
            'question': f"For Step {step_num}, should this be on {suggested_value or 'the first day'}?" if suggested_value else f"Should Step {step_num} happen on the first day of your trip?",
            'context': f"Activity: {step_description[:100]}...",
            'why_asking': "Exact dates help avoid conflicts and ensure all bookings are properly sequenced.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, 'no' for different date, or type the specific date (e.g., 'December 15, 2024')"
        },
        'price': {
            'question': f"For Step {step_num}, is a budget of ${suggested_value or '100'} acceptable?" if suggested_value else f"Is a budget of $100 reasonable for Step {step_num}?",
            'context': f"For: {step_description[:100]}...",
            'why_asking': "Budget information helps filter options and ensures we stay within your spending limits.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, 'no' for different budget, or type your budget (e.g., '$250' or '€150')"
        },
        'website': {
            'question': f"Should we book Step {step_num} through {suggested_value or 'Booking.com'}?" if suggested_value else f"Should we use Booking.com for Step {step_num}?",
            'context': f"Booking: {step_description[:100]}...",
            'why_asking': "Knowing the exact platform helps generate the correct booking URL and ensures compatibility.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to use this site, 'no' to skip, or type preferred website (e.g., 'Expedia.com')"
        },
        'origin': {
            'question': f"Should Step {step_num} depart from {suggested_value or 'Tokyo Station'}?" if suggested_value else f"Will Step {step_num} start from your hotel location?",
            'context': f"Travel details: {step_description[:100]}...",
            'why_asking': "The departure point is essential for accurate travel time and route planning.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, 'no' for different origin, or type the location (e.g., 'Tokyo Narita Airport')"
        },
        'destination': {
            'question': f"Should Step {step_num} arrive at {suggested_value or 'Osaka Station'}?" if suggested_value else f"Is the destination for Step {step_num} the city center?",
            'context': f"Travel destination: {step_description[:100]}...",
            'why_asking': "The arrival location is needed to complete transportation booking and estimate costs.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, 'no' for different destination, or type the location"
        },
        'location': {
            'question': f"Should Step {step_num} take place at {suggested_value or 'the suggested venue'}?" if suggested_value else f"Do you want Step {step_num} in the city center?",
            'context': f"Location details: {step_description[:100]}...",
            'why_asking': "A precise location ensures accurate directions and helps with making reservations.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, or provide the exact address/location name"
        },
        'hotel_name': {
            'question': f"Would you like to stay at {suggested_value or 'a 3-star hotel'}?" if suggested_value else f"Should we look for mid-range hotels for Step {step_num}?",
            'context': f"Hotel details: {step_description[:100]}...",
            'why_asking': "The specific hotel name is required for making a reservation.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' for this hotel, 'no' to skip, or type the hotel name"
        },
        'restaurant_name': {
            'question': f"Should we book {suggested_value or 'a local restaurant'} for Step {step_num}?" if suggested_value else f"Do you want to dine at a popular local restaurant for Step {step_num}?",
            'context': f"Dining at: {step_description[:100]}...",
            'why_asking': "Restaurant name is needed for reservation systems and availability checks.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, or type the restaurant name you prefer"
        },
        'attraction_name': {
            'question': f"Should Step {step_num} be at {suggested_value or 'the main tourist attraction'}?" if suggested_value else f"Do you want to visit the most popular attraction for Step {step_num}?",
            'context': f"Visiting: {step_description[:100]}...",
            'why_asking': "The specific attraction name helps us find ticket booking information.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, or type the attraction name"
        },
        'check_in': {
            'question': f"Should hotel check-in for Step {step_num} be on {suggested_value or 'arrival day'}?" if suggested_value else f"Will you check in on the first day for Step {step_num}?",
            'context': f"Hotel check-in: {step_description[:100]}...",
            'why_asking': "Check-in date is required for hotel reservations.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, or type the check-in date"
        },
        'check_out': {
            'question': f"Should hotel check-out for Step {step_num} be on {suggested_value or 'last day'}?" if suggested_value else f"Will you check out on the final day for Step {step_num}?",
            'context': f"Hotel check-out: {step_description[:100]}...",
            'why_asking': "Check-out date is required to complete hotel reservation.",
            'budget_info': budget_display,
            'suggested_answer': "Answer 'yes' to confirm, or type the check-out date"
        }
    }

    template = question_templates.get(field, {
        'question': f"Is the suggested {field} acceptable for Step {step_num}?",
        'context': f"Details: {step_description[:100]}...",
        'why_asking': f"This {field} is required to generate a complete intent token.",
        'budget_info': budget_display,
        'suggested_answer': "Answer 'yes', 'no', or provide specific details"
    })

    # Add metadata for processing
    template['id'] = f"step_{step_num}_{field}"
    template['field'] = field
    template['step'] = step_num
    template['action_type'] = action

    return template


def prioritize_missing_fields(intent_tokens, steps):
    """
    Prioritize missing fields and create yes/no questions.
    Returns list of up to 10 questions.
    """
    field_priority = {
        'date': 1,
        'time': 2,
        'price': 3,
        'origin': 4,
        'destination': 5,
        'location': 6,
        'hotel_name': 7,
        'check_in': 8,
        'check_out': 9,
        'restaurant_name': 10,
        'attraction_name': 11,
        'website': 12
    }

    missing_info = []

    for token in intent_tokens:
        payload = token['payload']
        if not payload.get('data_complete', True) and payload.get('missing_fields'):
            step_desc = next(
                (s['description'] for s in steps if s['step_number'] == payload['step_number']),
                "Step information not available"
            )

            for field in payload['missing_fields']:
                missing_info.append({
                    'step': payload['step_number'],
                    'action': payload['action'],
                    'field': field,
                    'description': step_desc,
                    'priority': field_priority.get(field, 99)
                })

    missing_info.sort(key=lambda x: (x['priority'], x['step']))

    # Limit to 10 questions
    missing_info = missing_info[:10]

    # Create yes/no questions
    questions = []
    for info in missing_info:
        question = create_yes_no_question(
            info['field'],
            info['step'],
            info['action'],
            info['description']
        )
        questions.append(question)

    return questions


def display_budget_summary(intent_tokens):
    """
    Display total budget summary for all intent tokens.
    """
    print("\n" + "="*80)
    print("💰 BUDGET SUMMARY FOR YOUR PLAN")
    print("="*80)

    total_low = 0
    total_medium = 0
    total_high = 0

    for token in intent_tokens:
        payload = token['payload']
        action = payload['action']
        step_num = payload['step_number']
        budget = payload.get('budget', {})

        if budget:
            print(f"\nStep {step_num}: {action.replace('_', ' ')}")
            print(f"  Low: ${budget.get('low', 0)} | "
                  f"Medium: ${budget.get('medium', 0)} | "
                  f"High: ${budget.get('high', 0)} {budget.get('currency', 'USD')}")

            total_low += budget.get('low', 0)
            total_medium += budget.get('medium', 0)
            total_high += budget.get('high', 0)

    print("\n" + "-"*80)
    print(f"\n📊 TOTAL ESTIMATED BUDGET:")
    print(f"   Low Budget:    ${total_low} USD")
    print(f"   Medium Budget: ${total_medium} USD")
    print(f"   High Budget:   ${total_high} USD")
    print("\n" + "="*80)


def get_travel_plan_with_intents(user_prompt, user_responses=None, iteration=0):
    """
    Travel planner with yes/no questions and budget display.
    """
    overhead_prompt = (
        "You are a travel planning AI. Provide step-by-step plans with complete details.\n\n"

        "MANDATORY for EVERY step:\n"
        "1. EXACT time (e.g., '10:30 AM', '2:00 PM')\n"
        "2. SPECIFIC date or day\n"
        "3. PRECISE location/address\n"
        "4. EXACT website (e.g., 'Booking.com')\n"
        "5. PRICE estimate\n"
        "6. For travel: origin AND destination\n"
        "7. For hotels: check-in AND check-out dates\n\n"

        "Structure:\n"
        "<Reasoning>Your thinking process</Reasoning>\n\n"
        "<Plan>\n"
        "Step-by-step plan with ALL required details\n"
        "</Plan>\n\n"
    )

    if user_responses:
        overhead_prompt += "\n📋 User answers:\n"
        for response_id, response_data in user_responses.items():
            answer = response_data['answer']
            if answer not in ['yes', 'no']:
                overhead_prompt += f"For {response_data['field']}: {answer}\n"
        overhead_prompt += "\n"

    overhead_prompt += "User Request: "
    full_prompt = overhead_prompt + user_prompt

    client = genai.Client()

    print(f"\n{'='*80}")
    print(f"🤖 GEMINI PROCESSING... (Iteration {iteration + 1})")
    print(f"{'='*80}")

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
        ),
    )
    raw_text = response.text

    reasoning_match = re.search(r'<Reasoning>(.*?)</Reasoning>', raw_text, re.DOTALL)
    plan_match = re.search(r'<Plan>(.*?)</Plan>', raw_text, re.DOTALL)

    reasoning_content = reasoning_match.group(1).strip() if reasoning_match else "Reasoning not found."
    plan_content = plan_match.group(1).strip() if plan_match else raw_text

    print(f"\n⚙️  Generating intent tokens...")
    steps = parse_step_wise_plan(plan_content)
    intent_tokens = []

    for step in steps:
        token = IntentEngine.generate_intent_token(
            step['step_number'],
            step['description'],
            step['structured_data']
        )
        intent_tokens.append(token)

    # Display budget summary
    display_budget_summary(intent_tokens)

    # Check for missing info
    questions = prioritize_missing_fields(intent_tokens, steps)

    if questions and iteration < 2:
        print(f"\n⚠️  Need clarification on {len(questions)} item(s)...")
        new_responses = ask_yes_no_questions(questions)

        if user_responses:
            user_responses.update(new_responses)
        else:
            user_responses = new_responses

        return get_travel_plan_with_intents(user_prompt, user_responses, iteration + 1)

    return reasoning_content, plan_content, intent_tokens


# --- Main Execution ---
if __name__ == "__main__":
    print("="*80)
    print("🌏 TRAVEL PLANNING AGENT WITH INTENT ENGINE")
    print("="*80)

    my_prompt = "I want a 3-day trip to Tokyo focused on anime and food."

    reasoning, plan, intent_tokens = get_travel_plan_with_intents(my_prompt)

    print("\n" + "="*80)
    print("🧠 GEMINI INTERNAL REASONING")
    print("="*80)
    print(reasoning)

    print("\n" + "="*80)
    print("📋 FINAL STEP-WISE TRAVEL PLAN")
    print("="*80)
    print(plan)

    print("\n" + "="*80)
    print("🎯 INTENT TOKENS (Ready for Automation)")
    print("="*80)
    print(json.dumps(intent_tokens, indent=2))

    # Show validation summary
    complete_tokens = sum(1 for t in intent_tokens if t['payload'].get('data_complete', False))
    incomplete_tokens = len(intent_tokens) - complete_tokens

    print("\n" + "="*80)
    print("📊 VALIDATION SUMMARY")
    print("="*80)
    print(f"✅ Complete tokens: {complete_tokens}/{len(intent_tokens)}")
    print(f"⚠️  Incomplete tokens: {incomplete_tokens}/{len(intent_tokens)}")

    if incomplete_tokens > 0:
        print("\n⚠️  Incomplete steps:")
        for token in intent_tokens:
            if not token['payload'].get('data_complete', True):
                print(f"   Step {token['payload']['step_number']}: Missing {token['payload'].get('missing_fields', [])}")

    # Final budget summary
    display_budget_summary(intent_tokens)
