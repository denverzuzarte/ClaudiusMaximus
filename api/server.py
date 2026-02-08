from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import yaml
import logging
import hmac
import hashlib
import os
import sys
import json
import re
import requests
import stripe
from datetime import datetime
from dateutil import parser as date_parser

# Add parent directory to path to import intent_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from intent_engine import IntentEngine, get_travel_plan_with_intents, prioritize_missing_fields, parse_step_wise_plan

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
if not stripe.api_key:
    logger.warning('STRIPE_SECRET_KEY not found in environment variables')

# Load policy configuration
def load_policy():
    policy_path = os.path.join(os.path.dirname(__file__), '..', 'manager', 'policy_travel.yaml')
    with open(policy_path, 'r') as f:
        return yaml.safe_load(f)

POLICY = load_policy()

def generate_armor_token(message: str, secret: str) -> str:
    """Generate HMAC token for intent verification"""
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

def evaluate_payment_policy(amount: float, merchant: str) -> dict:
    """
    Evaluate payment against policy rules
    Returns: {passed: bool, checks: [list of check results]}
    """
    checks = []
    all_passed = True
    
    # Extract payment policy rules
    payment_policy = None
    for policy in POLICY.get('policies', []):
        if policy.get('tool') == 'execute_payment':
            payment_policy = policy
            break
    
    if not payment_policy:
        return {
            'passed': False,
            'checks': [{'rule': 'POLICY_NOT_FOUND', 'result': 'FAIL'}]
        }
    
    # Check 1: Merchant allowlist (simplified - checking if verified)
    merchant_check = {
        'rule': 'MERCHANT_ALLOWLIST',
        'result': 'PASS'
    }
    
    # Assume ELECTRICITY_BOARD is a verified merchant
    verified_merchants = ['ELECTRICITY_BOARD', 'WATER_UTILITY', 'TELECOM_PROVIDER']
    is_verified = merchant in verified_merchants
    
    if is_verified:
        max_amount = 50000  # Verified merchant limit
        merchant_check['result'] = 'PASS'
    else:
        max_amount = 5000  # Unverified vendor limit
        merchant_check['result'] = 'PASS'
    
    checks.append(merchant_check)
    
    # Check 2: Transaction amount limit
    amount_check = {
        'rule': 'MAX_TRANSACTION_AMOUNT',
        'result': 'PASS' if amount <= 5000 else 'FAIL',
        'expected': '≤ 5000',
        'actual': amount
    }
    
    if amount > 5000:
        all_passed = False
    
    checks.append(amount_check)
    
    return {
        'passed': all_passed,
        'checks': checks
    }

def build_execution_trace(user_input: str, amount: float, merchant: str, policy_result: dict) -> dict:
    """
    Build the complete execution trace with all 6 stages
    """
    # Stage 1: USER_INPUT
    stages = [{
        'type': 'USER_INPUT',
        'payload': {
            'text': user_input
        }
    }]
    
    # Stage 2: REASONING
    stages.append({
        'type': 'REASONING',
        'payload': {
            'text': f'The user wants to pay a recurring utility bill. I should identify the merchant ({merchant}), validate the amount (₹{amount}), and propose a payment.'
        }
    })
    
    # Stage 3: PLAN
    stages.append({
        'type': 'PLAN',
        'payload': {
            'steps': [
                f'Identify {merchant.replace("_", " ").lower()}',
                f'Retrieve bill amount: ₹{amount}',
                'Propose a payment intent',
                'Submit for policy evaluation'
            ]
        }
    })
    
    # Stage 4: INTENT_TOKEN
    stages.append({
        'type': 'INTENT_TOKEN',
        'payload': {
            'action': 'PAY_BILL',
            'amount': amount,
            'merchant': merchant,
            'confidence': 0.91
        }
    })
    
    # Stage 5: POLICY_EVALUATION
    stages.append({
        'type': 'POLICY_EVALUATION',
        'payload': {
            'checks': policy_result['checks']
        }
    })
    
    # Stage 6: MCP_OUTCOME
    outcome_status = 'EXECUTED' if policy_result['passed'] else 'BLOCKED'
    outcome_payload = {
        'status': outcome_status
    }
    
    if not policy_result['passed']:
        failed_check = next((c for c in policy_result['checks'] if c['result'] == 'FAIL'), None)
        if failed_check:
            outcome_payload['reason'] = failed_check['rule']
    
    stages.append({
        'type': 'MCP_OUTCOME',
        'payload': outcome_payload
    })
    
    return {
        'stages': stages,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'execution_id': f'exec_{datetime.utcnow().timestamp()}'
    }

@app.route('/api/execute', methods=['POST'])
def execute_request():
    """
    Main API endpoint for processing execution requests from frontend
    """
    try:
        data = request.json
        user_input = data.get('text', '')
        
        logger.info(f"Received execution request: {user_input}")
        
        # Parse the request to extract intent
        # For demo, we'll use simple keyword matching
        # In production, this would use LLM for intent extraction
        
        amount = 6200  # Default from user request
        merchant = 'ELECTRICITY_BOARD'
        
        # Try to extract amount from user input
        if 'electricity' in user_input.lower():
            merchant = 'ELECTRICITY_BOARD'
        elif 'water' in user_input.lower():
            merchant = 'WATER_UTILITY'
        elif 'telecom' in user_input.lower() or 'phone' in user_input.lower():
            merchant = 'TELECOM_PROVIDER'
        
        # Evaluate against policy
        policy_result = evaluate_payment_policy(amount, merchant)
        
        # Build execution trace
        trace = build_execution_trace(user_input, amount, merchant, policy_result)
        
        logger.info(f"Execution result: {trace['stages'][-1]['payload']['status']}")
        
        return jsonify(trace)
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/policy', methods=['GET'])
def get_policy():
    """
    Get current policy configuration
    """
    return jsonify(POLICY)

@app.route('/api/health', methods=['GET'])
def health():
    """
    Health check endpoint
    """
    return jsonify({'status': 'healthy', 'service': 'armouriq-api'})

@app.route('/api/execute-with-intent', methods=['POST'])
def execute_with_intent():
    """
    Execute request using intent engine - generates questions first
    """
    try:
        data = request.json
        user_input = data.get('text', '')
        user_responses = data.get('responses', None)
        
        logger.info(f"Intent-based execution request: {user_input}")
        
        # Check if we need to ask questions first
        if not user_responses:
            # Detect request type for context-aware fallback questions
            user_input_lower = user_input.lower()
            is_flight = any(word in user_input_lower for word in ['flight', 'fly', 'plane', 'airline'])
            is_hotel = any(word in user_input_lower for word in ['hotel', 'stay', 'accommodation', 'room'])
            
            # Context-aware fallback questions
            if is_flight:
                questions = [
                    {'id': 'q1', 'question': 'Where are you departing from (origin city)?', 'field': 'origin', 'step': 1},
                    {'id': 'q2', 'question': 'Where are you flying to (destination city)?', 'field': 'destination', 'step': 2},
                    {'id': 'q3', 'question': 'What is your departure date?', 'field': 'departure_date', 'step': 3},
                    {'id': 'q4', 'question': 'How many passengers?', 'field': 'travelers', 'step': 4},
                    {'id': 'q5', 'question': 'What is your budget per person?', 'field': 'budget', 'step': 5}
                ]
            elif is_hotel:
                questions = [
                    {'id': 'q1', 'question': 'Which city or area do you want to stay in?', 'field': 'location', 'step': 1},
                    {'id': 'q2', 'question': 'What is your check-in date?', 'field': 'check_in', 'step': 2},
                    {'id': 'q3', 'question': 'What is your check-out date?', 'field': 'check_out', 'step': 3},
                    {'id': 'q4', 'question': 'How many guests?', 'field': 'travelers', 'step': 4},
                    {'id': 'q5', 'question': 'What is your budget per night?', 'field': 'budget', 'step': 5}
                ]
            else:
                # Generic travel planning
                questions = [
                    {'id': 'q1', 'question': 'Where do you want to travel?', 'field': 'destination', 'step': 1},
                    {'id': 'q2', 'question': 'What are your travel dates?', 'field': 'dates', 'step': 2},
                    {'id': 'q3', 'question': 'What is your total budget?', 'field': 'budget', 'step': 3},
                    {'id': 'q4', 'question': 'How many people are traveling?', 'field': 'travelers', 'step': 4},
                    {'id': 'q5', 'question': 'Any specific preferences?', 'field': 'preferences', 'step': 5}
                ]
            
            # Try to generate AI questions (with short timeout and fallback)
            try:
                api_key = os.getenv('GOOGLE_API_KEY')
                logger.info(f"Attempting AI question generation (API key present: {bool(api_key)})")
                if api_key:
                    # Create context-aware prompt based on user request
                    question_prompt = f"""You are a friendly travel assistant. The user asked: "{user_input}"

Analyze what they're asking for and generate EXACTLY 5 essential questions to help complete their request.

CRITICAL Guidelines:

For FLIGHT bookings:
1. Ask for ORIGIN city/airport (where flying FROM) - field: "origin"
2. Ask for DESTINATION city/airport (where flying TO) - field: "destination"  
3. Ask for DEPARTURE date - field: "departure_date"
4. Ask for NUMBER of passengers - field: "travelers"
5. Ask for BUDGET per person or class preference - field: "budget" or "flight_class"

For HOTEL bookings:
1. Ask for LOCATION/city - field: "location"
2. Ask for CHECK-IN date - field: "check_in"
3. Ask for CHECK-OUT date - field: "check_out"
4. Ask for NUMBER of guests - field: "travelers"
5. Ask for BUDGET per night or room type - field: "budget"

Format as JSON array:
[
  {{"id": "q1", "question": "Where are you flying from?", "field": "origin"}},
  {{"id": "q2", "question": "Where are you flying to?", "field": "destination"}},
  ...
]

IMPORTANT:
- For flights, ALWAYS ask origin and destination as SEPARATE questions
- Use simple field names: origin, destination, departure_date, check_in, check_out, location, budget, travelers
- Output ONLY the JSON array, no other text"""

                    # Use OpenAI API instead of Gemini
                    openai_key = os.getenv('OPENAI_API_KEY')
                    if not openai_key:
                        raise ValueError('OPENAI_API_KEY not found in environment')
                    
                    q_url = "https://api.openai.com/v1/chat/completions"
                    q_payload = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "You are a helpful travel planning assistant. Always respond with valid JSON."},
                            {"role": "user", "content": question_prompt}
                        ],
                        "temperature": 0.7
                    }
                    
                    logger.info(f"Requesting AI-generated questions for: {user_input}")
                    q_response = requests.post(
                        q_url, 
                        json=q_payload, 
                        headers={"Authorization": f"Bearer {openai_key}"},
                        timeout=10
                    )
                    q_response.raise_for_status()
                    q_data = q_response.json()
                    q_text = q_data['choices'][0]['message']['content'].strip()
                    # Remove markdown code blocks if present
                    q_text = re.sub(r'^```json\s*', '', q_text)
                    q_text = re.sub(r'```\s*$', '', q_text)
                    
                    questions = json.loads(q_text)
                    logger.info("✓ Using AI-generated questions")
            except Exception as e:
                logger.warning(f"Question generation failed ({type(e).__name__}), using fallback")
            
            # Add metadata for frontend
            for i, q in enumerate(questions):
                if 'step' not in q:
                    q['step'] = i + 1
                q['why_asking'] = 'This helps us find the best options for your trip.'
                q['budget_info'] = '💰 Typical range: $100 - $800 per person'
                
            return jsonify({
                'needs_questions': True,
                'questions': questions,
                'reasoning': 'Let me gather some details to plan your perfect trip...'
            })
        
        # User has answered questions, now generate the travel plan
        logger.info("User responses received, generating travel plan...")
        
        # Detect request type
        user_input_lower = user_input.lower()
        is_flight = any(word in user_input_lower for word in ['flight', 'fly', 'plane', 'airline'])
        
        # Generate plan with intent engine
        if is_flight:
            overhead_prompt = (
                "You are an intelligent flight booking agent researching real-world options.\n"
                "IMPORTANT: You are providing ESTIMATES based on typical market prices. You do not have real-time pricing data.\n\n"
                
                "Your job is to:\n"
                "1. Use your knowledge of airlines that operate on the requested route\n"
                "2. Provide a REALISTIC price estimate for the route\n"
                "3. Recommend a specific flight option with typical departure times\n"
                "4. Be honest about the estimate nature\n\n"
                
                "CRITICAL PRICING GUIDELINES:\n"
                "- Domestic Indian flights (< 2 hours): ₹3,000 - ₹8,000\n"
                "- Domestic Indian flights (2-4 hours): ₹4,000 - ₹12,000\n"
                "- Short international flights (India to nearby): $80 - $300\n"
                "- International long-haul: $400+\n"
                "- If user's budget is unrealistic, RECOMMEND a realistic price and explain why\n\n"
                
                "Structure your response as:\n"
                "<Reasoning>\n"
                "Explain what airlines operate this route and provide a realistic price estimate based on typical market rates.\n"
                "</Reasoning>\n\n"
                
                "<Plan>\n"
                "**Recommended Flight:**\n\n"
                "**Airline:** [Actual airline name]\n"
                "**Route:** [Origin to Destination]\n"
                "**Departure Date:** [Date]\n"
                "**Departure Time:** [Typical time]\n"
                "**Arrival Time:** [Typical time]\n"
                "**Estimated Price:** [Realistic amount per person - DO NOT match unrealistic budgets]\n"
                "**Booking Website:** [Airline website or booking platform]\n"
                "**Why this flight:** [Brief explanation]\n\n"
                "**Next Step:** Review the details above. If everything looks good, click 'Proceed to Book' to confirm your reservation.\n"
                "</Plan>\n\n"
            )
        else:
            overhead_prompt = (
                "You are an intelligent hotel booking agent. Your job is to:\n"
                "1. Research REAL hotels based on the user's requirements\n"
                "2. Analyze which options best match their budget, dates, and preferences\n"
                "3. Recommend ONE specific hotel you've researched\n"
                "4. Provide complete booking details so they can proceed\n\n"
                
                "CRITICAL: Use your knowledge of real hotels and booking platforms. "
                "Recommend actual properties that exist, not hypothetical examples.\n\n"
                
                "Structure your response as:\n"
                "<Reasoning>\n"
                "Explain what you researched, what options you considered, and why you're recommending this specific choice.\n"
                "</Reasoning>\n\n"
                
                "<Plan>\n"
                "**Recommended Hotel:**\n\n"
                "**Hotel Name:** [Actual hotel name]\n"
                "**Address:** [Complete address]\n"
                "**Check-in:** [Date and time]\n"
                "**Check-out:** [Date and time]\n"
                "**Price:** [Amount per night in user's currency]\n"
                "**Booking Website:** [Booking.com or other platform]\n"
            "**Why this hotel:** [Brief explanation of why it meets safety, budget, and location requirements]\n\n"
            "**Next Step:** Review the details above. If everything looks good, click 'Proceed to Book' to confirm your reservation.\n"
            "</Plan>\n\n"
        )
        
        if user_responses:
            overhead_prompt += "\n📋 User answers:\n"
            for response_data in user_responses:
                answer = response_data.get('answer', '')
                if answer not in ['yes', 'no']:
                    overhead_prompt += f"For {response_data.get('field')}: {answer}\n"
            overhead_prompt += "\n"
        
        overhead_prompt += "User Request: "
        full_prompt = overhead_prompt + user_input
        
        # Use OpenAI API instead of Gemini
        import requests
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            raise ValueError('OPENAI_API_KEY not found in environment')
        
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a professional travel research assistant. Research real options and provide specific recommendations."},
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.3
        }
        
        response = requests.post(
            url, 
            json=payload,
            headers={"Authorization": f"Bearer {openai_key}"},
            timeout=30
        )
        response.raise_for_status()
        response_data = response.json()
        raw_text = response_data['choices'][0]['message']['content']
        
        # Extract reasoning and plan
        reasoning_match = re.search(r'<Reasoning>(.*?)</Reasoning>', raw_text, re.DOTALL)
        plan_match = re.search(r'<Plan>(.*?)</Plan>', raw_text, re.DOTALL)
        
        reasoning_content = reasoning_match.group(1).strip() if reasoning_match else "Analyzing your request..."
        
        if plan_match:
            plan_content = plan_match.group(1).strip()
        else:
            # If no plan tags found, try to extract content after reasoning
            if reasoning_match:
                # Get everything after the </Reasoning> tag
                after_reasoning = raw_text.split('</Reasoning>', 1)
                plan_content = after_reasoning[1].strip() if len(after_reasoning) > 1 else raw_text
            else:
                plan_content = raw_text
        
        # Remove any remaining XML-style tags from plan content  
        plan_content = re.sub(r'</?(?:Reasoning|Plan)>', '', plan_content).strip()
        
        # Remove duplicate reasoning text from plan if present
        # Split by common delimiters and only keep content starting from "**Recommended"
        if '**Recommended' in plan_content:
            plan_content = plan_content[plan_content.index('**Recommended'):]
        elif '**Hotel Name:**' in plan_content:
            plan_content = plan_content[plan_content.index('**Hotel Name:**'):]
        elif '**Airline:**' in plan_content:
            plan_content = plan_content[plan_content.index('**Airline:**'):]
        
        # Extract user-provided data from responses
        user_data = {}
        if user_responses:
            for response_data in user_responses:
                field = response_data.get('field', '')
                answer = response_data.get('answer', '')
                if field and answer:
                    user_data[field] = answer
        
        # Extract booking details from AI's plan to satisfy intent validation
        booking_info = {}
        if plan_content:
            # Extract hotel/flight details that AI recommended
            hotel_match = re.search(r'\*\*(?:Hotel Name|Airline):\*\*\s*(.+)', plan_content)
            website_match = re.search(r'\*\*Booking (?:Website|Platform):\*\*\s*(.+)', plan_content)
            price_match = re.search(r'\*\*(?:Estimated )?Price:\*\*\s*(.+)', plan_content)
            address_match = re.search(r'\*\*Address:\*\*\s*(.+)', plan_content)
            route_match = re.search(r'\*\*Route:\*\*\s*(.+)', plan_content)
            
            if hotel_match:
                booking_info['hotel_name'] = hotel_match.group(1).strip()
            if website_match:
                booking_info['website'] = website_match.group(1).strip()
            if price_match:
                booking_info['price'] = price_match.group(1).strip()
            if address_match:
                booking_info['location'] = address_match.group(1).strip()
            if route_match:
                # For flights: "BOM to LON" -> extract origin and destination
                route = route_match.group(1).strip()
                if ' to ' in route.lower():
                    parts = route.split(' to ')
                    if len(parts) == 2:
                        booking_info['origin'] = parts[0].strip()
                        booking_info['destination'] = parts[1].strip()
        
        # Parse steps and generate intent tokens with user responses
        steps = parse_step_wise_plan(plan_content)
        
        # Detect primary action type from original user request (not from plan steps)
        user_input_lower = user_input.lower()
        primary_action = None
        if any(word in user_input_lower for word in ['flight', 'fly', 'airplane', 'plane']):
            primary_action = 'BOOK_FLIGHT'
        elif any(word in user_input_lower for word in ['hotel', 'accommodation', 'stay', 'room']):
            primary_action = 'BOOK_HOTEL'
        elif any(word in user_input_lower for word in ['train', 'rail']):
            primary_action = 'BOOK_TRAIN'
        elif any(word in user_input_lower for word in ['restaurant', 'dinner', 'lunch']):
            primary_action = 'BOOK_RESTAURANT'
        intent_tokens = []
        
        for step in steps:
            # Merge user-provided data with extracted structured data
            structured_data = step['structured_data'].copy() if step['structured_data'] else {}
            
            # Intelligently map questionnaire fields to structured data
            for field, value in user_data.items():
                if not value:
                    continue
                    
                # Direct field matches
                if field in structured_data:
                    continue  # Don't override existing parsed data
                
                # Smart field mapping based on field name patterns
                field_lower = field.lower()
                
                # Origin/departure mappings
                if any(x in field_lower for x in ['origin', 'departure', 'departing', 'from']):
                    if 'origin' not in structured_data:
                        structured_data['origin'] = value
                
                # Destination/location mappings
                if any(x in field_lower for x in ['destination', 'location', 'where', 'city']):
                    if 'destination' not in structured_data:
                        structured_data['destination'] = value
                
                # Date mappings (all date-related fields)
                if any(x in field_lower for x in ['date', 'when', 'check_in', 'check_out', 'checkin', 'checkout']):
                    if 'date' not in structured_data:
                        structured_data['date'] = value
                
                # Budget/price mappings
                if any(x in field_lower for x in ['budget', 'cost']):
                    if 'budget' not in structured_data:
                        structured_data['budget'] = value
                
                # Travelers/guests mappings
                if any(x in field_lower for x in ['traveler', 'people', 'guest', 'person', 'pax']):
                    if 'travelers' not in structured_data:
                        structured_data['travelers'] = value
                
                # Preferences mappings
                if any(x in field_lower for x in ['preference', 'requirement', 'special', 'note']):
                    if 'preferences' not in structured_data:
                        structured_data['preferences'] = value
                
                # Also add the raw field for reference
                structured_data[field] = value
            
            # Merge booking info extracted from AI's plan (hotel_name, website, price, etc.)
            # Price from AI should always override/supplement user budget
            for key, value in booking_info.items():
                if key == 'price':  # Always add AI's recommended price
                    structured_data['price'] = value
                elif key not in structured_data and value:
                    structured_data[key] = value
            
            # Generate token with primary action override from user request
            token = IntentEngine.generate_intent_token(
                step['step_number'],
                step['description'],
                structured_data
            )
            
            # Override action type with primary action detected from user request
            if primary_action and token.get('payload'):
                token['payload']['action'] = primary_action
            
            intent_tokens.append(token)
        
        # Build execution trace with intent tokens
        trace = build_trace_from_intents(user_input, intent_tokens, reasoning_content, plan_content)
        
        logger.info(f"Intent-based execution completed")
        return jsonify(trace)
        
    except Exception as e:
        logger.error(f"Error in intent execution: {str(e)}")
        return jsonify({'error': str(e)}), 500

def validate_policy_rules(intent_tokens):
    """
    Sophisticated policy validation - checks feasibility, governance, and constraints
    Returns: (is_valid, failures_list)
    """
    failures = []
    
    for token in intent_tokens:
        payload = token['payload']
        action = payload.get('action', 'UNKNOWN')
        
        # Extract common fields
        origin = payload.get('origin', '').lower()
        destination = payload.get('destination', '').lower()
        location = payload.get('location', '').lower()
        budget_str = str(payload.get('budget', '0'))
        price_str = str(payload.get('price', '0'))
        travelers_str = str(payload.get('travelers', '1'))
        date_str = payload.get('date', '') or payload.get('departure_date', '') or payload.get('check_in', '')
        confidence = payload.get('confidence', 0.0)
        
        # Parse budget and price (extract numeric value)
        budget = 0
        price = 0
        try:
            import re
            budget_match = re.search(r'[\d,]+', budget_str.replace(',', ''))
            if budget_match:
                budget = float(budget_match.group())
            
            price_match = re.search(r'[\d,]+', price_str.replace(',', ''))
            if price_match:
                price = float(price_match.group())
        except:
            pass
        
        # Parse travelers
        travelers = 1
        try:
            travelers_match = re.search(r'\d+', travelers_str)
            if travelers_match:
                travelers = int(travelers_match.group())
        except:
            travelers = 1
        
        # ===== 1️⃣ INPUT-LEVEL FAILURES =====
        
        # Check origin == destination
        if origin and destination and origin == destination:
            failures.append({
                'action': action,
                'category': 'INPUT_VALIDATION',
                'reason': 'Origin and destination cannot be the same location',
                'severity': 'BLOCK'
            })
        
        # Check date in past
        if date_str:
            try:
                booking_date = date_parser.parse(date_str, fuzzy=True)
                if booking_date.date() < datetime.now().date():
                    failures.append({
                        'action': action,
                        'category': 'INPUT_VALIDATION',
                        'reason': 'Booking date is in the past',
                        'severity': 'BLOCK'
                    })
            except:
                pass
        
        # Check negative/zero values
        if travelers <= 0:
            failures.append({
                'action': action,
                'category': 'INPUT_VALIDATION',
                'reason': 'Number of travelers must be at least 1',
                'severity': 'BLOCK'
            })
        
        if budget <= 0:
            failures.append({
                'action': action,
                'category': 'INPUT_VALIDATION',
                'reason': 'Budget must be greater than zero',
                'severity': 'BLOCK'
            })
        
        # ===== 2️⃣ POLICY-SCOPE FAILURES =====
        
        # Blacklisted destinations (restricted regions)
        blacklist = ['syria', 'north korea', 'afghanistan', 'crimea']
        if destination in blacklist or location in blacklist:
            failures.append({
                'action': action,
                'category': 'POLICY_RESTRICTED',
                'reason': f'Travel to {destination or location} is restricted by corporate policy',
                'severity': 'BLOCK_AND_LOG'
            })
        
        # Time-based governance (booking too soon)
        if date_str and action == 'BOOK_FLIGHT':
            try:
                booking_date = date_parser.parse(date_str, fuzzy=True)
                days_until = (booking_date.date() - datetime.now().date()).days
                
                # International flights require 72+ hours notice
                if days_until < 3 and destination not in ['domestic', 'india']:
                    failures.append({
                        'action': action,
                        'category': 'POLICY_TIME',
                        'reason': f'International flight booking requires 72 hours advance notice (currently {days_until} days)',
                        'severity': 'REQUIRE_HUMAN_APPROVAL'
                    })
            except:
                pass
        
        # ===== 3️⃣ BUDGET REASONING FAILURES =====
        
        # Simple budget validation: 10% threshold
        # Compare AI's recommended price against user's stated budget
        if budget > 0 and price > 0:
            price_vs_budget_ratio = price / budget
            overage_percent = int((price_vs_budget_ratio - 1) * 100)
            
            # Price exceeds budget by more than 10% - BLOCKED
            if price_vs_budget_ratio > 1.1:
                failures.append({
                    'action': action,
                    'category': 'BUDGET_EXCEEDED',
                    'reason': f'Recommended price ({price_str}) exceeds budget ({budget_str}) by {overage_percent}% - not approved',
                    'severity': 'BLOCK'
                })
            # Price is within 10% of budget - requires approval for minor overage
            elif price_vs_budget_ratio > 1.0:
                failures.append({
                    'action': action,
                    'category': 'BUDGET_CLOSE',
                    'reason': f'Recommended price ({price_str}) is {overage_percent}% over budget ({budget_str}) - requires approval',
                    'severity': 'REQUIRE_HUMAN_APPROVAL'
                })
        
        # Aggregate budget cap (group spending limit)
        GROUP_CAP = 200000  # ₹2 lakh group limit
        total_budget = budget * travelers
        if total_budget > GROUP_CAP:
            failures.append({
                'action': action,
                'category': 'BUDGET_EXCEEDED',
                'reason': f'Total group budget (₹{int(total_budget)}) exceeds organizational cap (₹{GROUP_CAP})',
                'severity': 'REQUIRE_HUMAN_APPROVAL'
            })
        
        # ===== 4️⃣ CLASS & JUSTIFICATION FAILURES =====
        
        # Check if description mentions business/first class
        description = payload.get('description', '').lower()
        if 'business class' in description or 'first class' in description:
            # Business class on short domestic flights
            if origin and destination:
                domestic_indicators = ['delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata']
                is_domestic = any(d in origin or d in destination for d in domestic_indicators)
                
                if is_domestic:
                    failures.append({
                        'action': action,
                        'category': 'CLASS_JUSTIFICATION',
                        'reason': 'Business class not justified for domestic short-haul flights',
                        'severity': 'REQUIRE_HUMAN_APPROVAL'
                    })
        
        # ===== 5️⃣ CONFIDENCE & UNCERTAINTY FAILURES =====
        
        # NOTE: Confidence checks are disabled - we rely on data_complete validation instead
        # Individual token confidence can be misleading when Gemini's plan is parsed into multiple steps
        # The aggregate confidence (shown in Stage 4) is what matters, and it's based on data completeness
        
        # Uncomment below only if you want strict confidence thresholds IN ADDITION to data validation:
        # if confidence < 0.7:
        #     failures.append({
        #         'action': action,
        #         'category': 'LOW_CONFIDENCE',
        #         'reason': f'Agent confidence insufficient ({int(confidence*100)}%) for autonomous execution',
        #         'severity': 'REQUIRE_HUMAN_APPROVAL'
        #     })
        # 
        # if confidence < 0.5:
        #     failures.append({
        #         'action': action,
        #         'category': 'VERY_LOW_CONFIDENCE',
        #         'reason': f'Agent confidence critically low ({int(confidence*100)}%) - unable to proceed',
        #         'severity': 'BLOCK'
        #     })
        
        # ===== 6️⃣ HOTEL-SPECIFIC VALIDATIONS =====
        
        if action == 'BOOK_HOTEL':
            # Extract hotel-specific fields
            # Check 'guests' first, then fall back to 'travelers' field
            guests_str = str(payload.get('guests', payload.get('travelers', '0')))
            check_in_str = payload.get('check_in', '')
            check_out_str = payload.get('check_out', '')
            
            # Parse number of guests
            guests = 0
            try:
                guests_match = re.search(r'\d+', guests_str)
                if guests_match:
                    guests = int(guests_match.group())
            except:
                guests = 0
            
            # 2️⃣ Occupancy violation (HARD BLOCK)
            MAX_GUESTS_PER_ROOM = 4
            if guests <= 0:
                failures.append({
                    'action': action,
                    'category': 'INVALID_OCCUPANCY',
                    'reason': 'Number of guests must be at least 1',
                    'severity': 'BLOCK'
                })
            elif guests > MAX_GUESTS_PER_ROOM:
                failures.append({
                    'action': action,
                    'category': 'INVALID_OCCUPANCY',
                    'reason': f'Number of guests ({guests}) exceeds maximum per room ({MAX_GUESTS_PER_ROOM})',
                    'severity': 'BLOCK'
                })
            
            # 3️⃣ Excessive stay duration (SOFT FAIL)
            if check_in_str and check_out_str:
                try:
                    check_in = date_parser.parse(check_in_str, fuzzy=True)
                    check_out = date_parser.parse(check_out_str, fuzzy=True)
                    stay_duration = (check_out - check_in).days
                    
                    MAX_STAY_NIGHTS = 14
                    if stay_duration > MAX_STAY_NIGHTS:
                        failures.append({
                            'action': action,
                            'category': 'EXCESSIVE_STAY_LENGTH',
                            'reason': f'Stay duration ({stay_duration} nights) exceeds maximum ({MAX_STAY_NIGHTS} nights) - requires approval',
                            'severity': 'REQUIRE_HUMAN_APPROVAL'
                        })
                except:
                    pass
            
            # 5️⃣ Budget realism check (SOFT FAIL)
            # Define city minimum thresholds (per night)
            CITY_MIN_BUDGET = {
                'paris': 3000,      # ~₹3,000/night minimum
                'london': 3500,
                'new york': 4000,
                'tokyo': 2500,
                'dubai': 2000,
                'singapore': 2500,
                'mumbai': 1500,
                'delhi': 1500,
                'bangalore': 1200,
                'default': 1000     # Generic minimum
            }
            
            if check_in_str and check_out_str and budget > 0:
                try:
                    check_in = date_parser.parse(check_in_str, fuzzy=True)
                    check_out = date_parser.parse(check_out_str, fuzzy=True)
                    stay_duration = (check_out - check_in).days
                    
                    if stay_duration > 0:
                        budget_per_night = budget / stay_duration
                        
                        # Determine city minimum
                        city_key = location.lower() if location else 'default'
                        city_min = CITY_MIN_BUDGET.get(city_key, CITY_MIN_BUDGET['default'])
                        
                        if budget_per_night < city_min:
                            failures.append({
                                'action': action,
                                'category': 'BUDGET_NOT_FEASIBLE_FOR_LOCATION',
                                'reason': f'Budget per night (₹{int(budget_per_night)}) is below minimum for {location or "this location"} (₹{city_min}) - may not find suitable accommodation',
                                'severity': 'REQUIRE_HUMAN_APPROVAL'
                            })
                except:
                    pass
    
    # Determine if any BLOCK-level failure exists
    has_block = any(f['severity'] in ['BLOCK', 'BLOCK_AND_LOG'] for f in failures)
    
    return (not has_block and len(failures) == 0), failures


def build_trace_from_intents(user_input, intent_tokens, reasoning, plan):
    """
    Build execution trace from intent tokens
    """
    # Generate execution ID for this request
    execution_id = f'intent_{datetime.utcnow().timestamp()}'
    
    stages = []
    
    # Stage 1: USER_INPUT
    stages.append({
        'type': 'USER_INPUT',
        'payload': {'text': user_input}
    })
    
    # Stage 2: REASONING
    stages.append({
        'type': 'REASONING',
        'payload': {'text': reasoning}
    })
    
    # Stage 3: PLAN
    plan_steps = plan.strip().split('\n') if plan else ['Preparing your booking recommendation...']
    
    # Filter out XML tags and empty lines from plan steps
    plan_steps = [
        step.strip() for step in plan_steps 
        if step.strip() and not re.match(r'^</?(?:Reasoning|Plan)>$', step.strip())
    ]
    
    stages.append({
        'type': 'PLAN',
        'payload': {'steps': plan_steps}
    })
    
    # Stage 4: INTENT_TOKEN - Validate completeness AND policy rules
    all_tokens_valid = True
    failed_reasons = []
    total_confidence = 0
    
    # First pass: Check data completeness
    for token in intent_tokens:
        payload = token['payload']
        is_complete = payload.get('data_complete', False)
        
        if not is_complete:
            all_tokens_valid = False
            missing = payload.get('missing_fields', [])
            action = payload.get('action', 'ACTION')
            failed_reasons.append({
                'action': action,
                'category': 'MISSING_DATA',
                'reason': f"Missing required fields: {', '.join(missing[:3])}",
                'severity': 'BLOCK'
            })
            total_confidence += 0.3  # Low confidence for incomplete
        else:
            total_confidence += 0.95  # High confidence for complete
    
    # Second pass: Advanced policy validation (only if data is complete)
    if all_tokens_valid:
        policy_valid, policy_failures = validate_policy_rules(intent_tokens)
        if not policy_valid or policy_failures:
            all_tokens_valid = False
            failed_reasons.extend(policy_failures)
    
    avg_confidence = total_confidence / len(intent_tokens) if intent_tokens else 0.5
    
    if intent_tokens:
        first_token = intent_tokens[0]['payload']
        stages.append({
            'type': 'INTENT_TOKEN',
            'payload': {
                'action': first_token.get('action', 'BOOK_HOTEL'),
                'steps': len(intent_tokens),
                'confidence': avg_confidence,
                'complete_steps': sum(1 for t in intent_tokens if t['payload'].get('data_complete', False))
            }
        })
    
    # Stage 5: MCP_OUTCOME - Decide based on intent validation
    
    # Extract price information from intent tokens for display
    price_display = None
    if intent_tokens and len(intent_tokens) > 0:
        first_token = intent_tokens[0]['payload']
        price = first_token.get('price', '')
        if price:
            price_display = price
    
    if all_tokens_valid:
        # All intents are valid - APPROVE and redirect to payment
        outcome_status = 'APPROVED'
        outcome_payload = {
            'status': outcome_status,
            'reason': 'ALL_INTENTS_VALIDATED',
            'message': f'All requirements validated with {int(avg_confidence * 100)}% confidence. Redirecting to payment gateway...',
            'payment_url': f'http://localhost:5001/payment/{execution_id}',
            'execution_id': execution_id,
            'confidence': avg_confidence,
            'price': price_display
        }
    else:
        # Some intents failed - determine if it needs human approval or hard block
        requires_approval = any(f.get('severity') == 'REQUIRE_HUMAN_APPROVAL' for f in failed_reasons)
        hard_block = any(f.get('severity') in ['BLOCK', 'BLOCK_AND_LOG'] for f in failed_reasons)
        
        if hard_block:
            outcome_status = 'BLOCKED'
            outcome_message = 'Request blocked due to policy violations. Unable to proceed.'
        elif requires_approval:
            outcome_status = 'REQUIRES_APPROVAL'
            outcome_message = 'Request requires human approval due to governance constraints.'
        else:
            outcome_status = 'BLOCKED'
            outcome_message = 'Intent validation failed. Unable to proceed with booking.'
        
        # Group failures by category
        categorized_failures = {}
        for f in failed_reasons:
            category = f.get('category', 'OTHER')
            if category not in categorized_failures:
                categorized_failures[category] = []
            categorized_failures[category].append(f)
        
        # Deduplicate failures by category + reason combination
        seen = set()
        deduplicated_failures = []
        for f in failed_reasons:
            # Create a unique key from category and reason
            key = (f.get('category', 'OTHER'), f.get('reason', ''))
            if key not in seen:
                seen.add(key)
                deduplicated_failures.append(f)
        
        # Format triggered rules for UI
        triggered_rules = list(categorized_failures.keys())
        
        outcome_payload = {
            'status': outcome_status,
            'reason': 'POLICY_VALIDATION_FAILED' if requires_approval else 'INTENT_VALIDATION_FAILED',
            'message': outcome_message,
            'failures': deduplicated_failures,
            'triggered_rules': triggered_rules,
            'requires_human_approval': requires_approval,
            'confidence': avg_confidence,
            'price': price_display
        }
        
        # Add payment URL for human approval flow
        if requires_approval:
            outcome_payload['payment_url'] = f'http://localhost:5001/payment/{execution_id}'
            outcome_payload['execution_id'] = execution_id
    
    stages.append({
        'type': 'MCP_OUTCOME',
        'payload': outcome_payload
    })
    
    return {
        'stages': stages,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'execution_id': execution_id,
        'intent_tokens': intent_tokens
    }

@app.route('/payment/<execution_id>', methods=['GET'])
def payment_gateway(execution_id):
    """
    Create Stripe Checkout Session and redirect to Stripe
    """
    try:
        # Extract price from execution_id or use a default
        # In production, you'd fetch this from a database
        # For demo purposes, using a fixed amount
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'unit_amount': 100000,  # ₹1,000 (amount in paise)
                    'product_data': {
                        'name': 'Travel Booking',
                        'description': f'Booking confirmation for {execution_id[:16]}',
                        'images': ['https://i.imgur.com/EHyR2nP.png'],
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'http://localhost:5001/payment/success?session_id={{CHECKOUT_SESSION_ID}}&execution_id={execution_id}',
            cancel_url=f'http://localhost:5001/payment/cancel?execution_id={execution_id}',
            metadata={
                'execution_id': execution_id
            }
        )
        
        return redirect(checkout_session.url, code=303)
    
    except Exception as e:
        logger.error(f"Stripe checkout error: {str(e)}")
        return jsonify({'error': 'Payment gateway error', 'details': str(e)}), 500

@app.route('/payment/success', methods=['GET'])
def payment_success():
    """
    Payment success page - shown after successful Stripe payment
    """
    session_id = request.args.get('session_id')
    execution_id = request.args.get('execution_id')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Successful - ARMOURIQ</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f766e 0%, #06b6d4 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 20px;
                padding: 56px 48px;
                max-width: 520px;
                width: 100%;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                text-align: center;
            }}
            .success-icon {{
                width: 88px;
                height: 88px;
                margin: 0 auto 28px;
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                animation: scaleIn 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.4);
            }}
            .success-icon svg {{
                width: 48px;
                height: 48px;
                stroke: white;
                stroke-width: 3;
                fill: none;
                stroke-linecap: round;
                stroke-linejoin: round;
            }}
            @keyframes scaleIn {{
                from {{
                    transform: scale(0) rotate(-45deg);
                    opacity: 0;
                }}
                to {{
                    transform: scale(1) rotate(0deg);
                    opacity: 1;
                }}
            }}
            .title {{
                font-size: 32px;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 14px;
                letter-spacing: -0.02em;
            }}
            .subtitle {{
                font-size: 16px;
                color: #64748b;
                margin-bottom: 40px;
                line-height: 1.6;
                font-weight: 400;
            }}
            .details {{
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 16px;
                padding: 28px;
                margin-bottom: 32px;
                text-align: left;
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 18px;
                font-size: 14px;
            }}
            .detail-row:last-child {{
                margin-bottom: 0;
                padding-top: 18px;
                border-top: 1px solid #e2e8f0;
            }}
            .label {{
                color: #64748b;
                font-weight: 500;
            }}
            .value {{
                color: #0f172a;
                font-weight: 600;
                font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
                font-size: 13px;
                background: white;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid #e2e8f0;
            }}
            .status-badge {{
                background: #d1fae5;
                color: #065f46;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.02em;
                border: none;
            }}
            .btn {{
                width: 100%;
                padding: 18px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                text-decoration: none;
                display: inline-block;
                font-family: 'Inter', sans-serif;
            }}
            .btn-primary {{
                background: linear-gradient(135deg, #0f766e 0%, #06b6d4 100%);
                color: white;
                box-shadow: 0 4px 12px rgba(15, 118, 110, 0.3);
            }}
            .btn-primary:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(15, 118, 110, 0.4);
            }}
            .btn-primary:active {{
                transform: translateY(0);
            }}
            .footer {{
                margin-top: 32px;
                font-size: 13px;
                color: #94a3b8;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }}
            .footer-divider {{
                width: 4px;
                height: 4px;
                background: #cbd5e1;
                border-radius: 50%;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">
                <svg viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            <h1 class="title">Payment Successful!</h1>
            <p class="subtitle">Your booking has been confirmed. You'll receive a confirmation email shortly.</p>
            
            <div class="details">
                <div class="detail-row">
                    <span class="label">Transaction ID</span>
                    <span class="value">{session_id[:20] if session_id else 'DEMO'}...</span>
                </div>
                <div class="detail-row">
                    <span class="label">Booking Reference</span>
                    <span class="value">{execution_id[:18] if execution_id else 'N/A'}...</span>
                </div>
                <div class="detail-row">
                    <span class="label">Payment Status</span>
                    <span class="status-badge">CONFIRMED</span>
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="window.close()">
                Close Window
            </button>
            
            <div class="footer">
                <span>Powered by ARMOURIQ</span>
                <div class="footer-divider"></div>
                <span>Secured by Stripe</span>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/payment/cancel', methods=['GET'])
def payment_cancel():
    """
    Payment cancelled page
    """
    execution_id = request.args.get('execution_id')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Cancelled - ARMOURIQ</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #475569 0%, #64748b 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 20px;
                padding: 56px 48px;
                max-width: 520px;
                width: 100%;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                text-align: center;
            }}
            .cancel-icon {{
                width: 88px;
                height: 88px;
                margin: 0 auto 28px;
                background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            }}
            .cancel-icon svg {{
                width: 40px;
                height: 40px;
                stroke: #64748b;
                stroke-width: 3;
                fill: none;
                stroke-linecap: round;
                stroke-linejoin: round;
            }}
            .title {{
                font-size: 32px;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 14px;
                letter-spacing: -0.02em;
            }}
            .subtitle {{
                font-size: 16px;
                color: #64748b;
                margin-bottom: 36px;
                line-height: 1.6;
                font-weight: 400;
            }}
            .info-box {{
                background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                border: 1px solid #fbbf24;
                border-radius: 16px;
                padding: 20px 24px;
                margin-bottom: 32px;
                display: flex;
                align-items: center;
                gap: 14px;
                text-align: left;
            }}
            .info-icon {{
                width: 24px;
                height: 24px;
                background: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
                box-shadow: 0 2px 8px rgba(251, 191, 36, 0.3);
            }}
            .info-icon svg {{
                width: 16px;
                height: 16px;
                stroke: #d97706;
                stroke-width: 2.5;
                fill: none;
                stroke-linecap: round;
                stroke-linejoin: round;
            }}
            .info-text {{
                color: #92400e;
                font-size: 14px;
                line-height: 1.6;
                font-weight: 500;
            }}
            .btn {{
                width: 100%;
                padding: 18px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                text-decoration: none;
                display: inline-block;
                margin-bottom: 12px;
                font-family: 'Inter', sans-serif;
            }}
            .btn-primary {{
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
            }}
            .btn-primary:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
            }}
            .btn-primary:active {{
                transform: translateY(0);
            }}
            .btn-secondary {{
                background: #f1f5f9;
                color: #475569;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }}
            .btn-secondary:hover {{
                background: #e2e8f0;
                transform: translateY(-1px);
            }}
            .booking-info {{
                margin-top: 24px;
                padding-top: 24px;
                border-top: 1px solid #e2e8f0;
            }}
            .booking-label {{
                font-size: 11px;
                font-weight: 600;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 6px;
            }}
            .booking-id {{
                font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
                font-size: 13px;
                color: #64748b;
                background: #f8fafc;
                padding: 8px 14px;
                border-radius: 8px;
                display: inline-block;
            }}
            .footer {{
                margin-top: 28px;
                font-size: 13px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="cancel-icon">
                <svg viewBox="0 0 24 24">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </div>
            <h1 class="title">Payment Cancelled</h1>
            <p class="subtitle">Your payment was cancelled. No charges were made to your account.</p>
            
            <div class="info-box">
                <div class="info-icon">
                    <svg viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                </div>
                <div class="info-text">
                    Your booking is on hold. Complete the payment to confirm your reservation.
                </div>
            </div>
            
            <button class="btn btn-primary" onclick="window.location.href='/payment/{execution_id}'">
                Retry Payment
            </button>
            <button class="btn btn-secondary" onclick="window.location.href='http://localhost:5176'">
                Go Back to Home
            </button>
            
            <div class="booking-info">
                <div class="booking-label">Booking Reference</div>
                <div class="booking-id">{execution_id[:18] if execution_id else 'N/A'}...</div>
            </div>
            
            <div class="footer">
                Powered by ARMOURIQ
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/api/confirm-booking', methods=['POST'])
def confirm_booking():
    """
    Confirm a booking after user approval.
    In a real system, this would:
    1. Validate the execution_id and booking details
    2. Call Amadeus API to make actual booking
    3. Process payment
    4. Send confirmation email
    
    For demo purposes, we'll simulate success.
    """
    try:
        data = request.json
        execution_id = data.get('execution_id')
        details = data.get('details', {})
        
        logger.info(f"Booking confirmation requested for execution {execution_id}")
        logger.info(f"Hotel: {details.get('hotel_name')}, Price: {details.get('price')}")
        
        # In production, this would:
        # 1. Call Amadeus booking API
        # 2. Process payment
        # 3. Send confirmation
        
        # Simulate booking confirmation
        booking_reference = f"BK{datetime.utcnow().timestamp():.0f}"
        
        return jsonify({
            'success': True,
            'booking_reference': booking_reference,
            'message': 'Booking confirmed successfully!',
            'details': details,
            'next_steps': [
                f"Visit {details.get('website', 'the booking website')} to complete payment",
                "Check your email for confirmation",
                "Save your booking reference: " + booking_reference
            ]
        })
        
    except Exception as e:
        logger.error(f"Booking confirmation failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
