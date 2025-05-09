from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, make_response
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from meeting_automation import MeetingAutomation
from llm_service import LLMService
import uuid

# Load environment variables
print("\nLoading environment variables...")
load_dotenv()

# Debug print statements
print(f"SMTP_PASSWORD length: {len(os.getenv('SMTP_PASSWORD', ''))}")
print(f"SMTP_PASSWORD first and last char: {os.getenv('SMTP_PASSWORD', '')[:1]}...{os.getenv('SMTP_PASSWORD', '')[-1:]}")

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, resources={r"/*": {"origins": "*", "supports_credentials": True}})

# Initialize services
meeting_automation = MeetingAutomation()
llm_service = LLMService()

# In-memory storage for meetings and chat context
meetings = []
chat_contexts = {}

@app.route('/')
def index():
    response = make_response(render_template('chat.html'))
    session_id = request.cookies.get('session_id', str(uuid.uuid4()))
    response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
    return response

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'No message provided'}), 400
        
    # Get or create session context
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in chat_contexts:
        chat_contexts[session_id] = {
            'intent': None,
            'time': None,
            'duration': 30,
            'recipients': [],
            'subject': '',
            'content': '',
            'last_question': None,
            'conversation_history': [],
            'generate_joke': False,
            'joke_topic': '',
            'is_recurring': False,
            'recurrence_rule': ''
        }
    
    context = chat_contexts[session_id]
    
    # Add user message to conversation history
    context['conversation_history'].append({
        'role': 'user',
        'content': message
    })
    
    # Check if the message is an email
    if '@' in message and ('meeting' in message.lower() or 'schedule' in message.lower()):
        try:
            # Process the email
            success, result = meeting_automation.process_email(message)
            
            if success:
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "I've processed your meeting request and sent confirmation emails to all participants. They'll need to confirm the meeting before it's scheduled."
                })
                response = jsonify({
                    'response': "I've processed your meeting request and sent confirmation emails to all participants. They'll need to confirm the meeting before it's scheduled.",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response
            else:
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': f"Sorry, I couldn't process your meeting request: {result}"
                })
                response = jsonify({
                    'response': f"Sorry, I couldn't process your meeting request: {result}",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response
                
        except Exception as e:
            context['conversation_history'].append({
                'role': 'assistant',
                'content': f"Sorry, there was an error processing your request: {str(e)}"
            })
            response = jsonify({
                'response': f"Sorry, there was an error processing your request: {str(e)}",
                'show_form': False
            })
            response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
            return response
    
    # Use LLM to understand the intent with context
    understanding = llm_service.understand_intent(message, context)
    print(f"LLM Understanding: {understanding}")  # Debug print
    print(f"Session ID: {session_id}")  # Debug print
    print(f"Current Context: {context}")  # Debug print
    
    if not understanding:
        response = jsonify({
            'response': "I'm sorry, I couldn't understand your request. Could you please rephrase it?",
            'show_form': False
        })
        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
        return response

    try:
        # Update context with new information
        if understanding['intent']:
            context['intent'] = understanding['intent']
        if understanding['time']:
            context['time'] = understanding['time']
        if understanding['duration']:
            context['duration'] = understanding['duration']
        if understanding['recipients']:
            context['recipients'] = understanding['recipients']
        if understanding['subject']:
            context['subject'] = understanding['subject']
        if understanding['content']:
            context['content'] = understanding['content']
        if understanding['is_recurring']:
            context['is_recurring'] = understanding['is_recurring']
        if understanding['recurrence_rule']:
            context['recurrence_rule'] = understanding['recurrence_rule']

        # Handle email sending
        if context['intent'] == 'send_email':
            if not context['recipients'] and context['last_question'] != 'recipients':
                context['last_question'] = 'recipients'
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "Who would you like to send the email to?"
                })
                response = jsonify({
                    'response': "Who would you like to send the email to?",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response

            if not context['subject'] and context['last_question'] != 'subject':
                context['last_question'] = 'subject'
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "What would you like the subject of the email to be?"
                })
                response = jsonify({
                    'response': "What would you like the subject of the email to be?",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response

            if not context['content'] and context['last_question'] != 'content':
                context['last_question'] = 'content'
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "What would you like to say in the email?"
                })
                response = jsonify({
                    'response': "What would you like to say in the email?",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response

            # If we have all required information, send the email
            if context['recipients'] and context['content']:
                try:
                    meeting_automation.send_email(
                        recipients=context['recipients'],
                        subject=context['subject'] or "Email from Meeting Assistant",
                        content=context['content'],
                        generate_joke=context.get('generate_joke', False),
                        joke_topic=context.get('joke_topic', '')
                    )

                    # Add success message to conversation history
                    context['conversation_history'].append({
                        'role': 'assistant',
                        'content': f"I've sent the email to {', '.join(context['recipients'])}."
                    })

                    # Clear context after successful email
                    chat_contexts[session_id] = {
                        'intent': None,
                        'time': None,
                        'duration': 30,
                        'recipients': [],
                        'subject': '',
                        'content': '',
                        'last_question': None,
                        'conversation_history': [],
                        'generate_joke': False,
                        'joke_topic': '',
                        'is_recurring': False,
                        'recurrence_rule': ''
                    }

                    response = jsonify({
                        'response': f"I've sent the email to {', '.join(context['recipients'])}.",
                        'show_form': False
                    })
                    response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                    return response
                except Exception as e:
                    error_message = f"Sorry, there was an error sending the email: {str(e)}"
                    context['conversation_history'].append({
                        'role': 'assistant',
                        'content': error_message
                    })
                    response = jsonify({
                        'response': error_message,
                        'show_form': False
                    })
                    response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                    return response

        # Handle meeting scheduling
        elif context['intent'] == 'schedule_meeting':
            if not context['time'] and context['last_question'] != 'time':
                context['last_question'] = 'time'
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "What time would you like to schedule the meeting?"
                })
                response = jsonify({
                    'response': "What time would you like to schedule the meeting?",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response
            
            if not context['recipients'] and context['last_question'] != 'recipients':
                context['last_question'] = 'recipients'
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "Who would you like to invite to the meeting?"
                })
                response = jsonify({
                    'response': "Who would you like to invite to the meeting?",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response
            
            if not context['subject'] and context['last_question'] != 'subject':
                context['last_question'] = 'subject'
                context['conversation_history'].append({
                    'role': 'assistant',
                    'content': "What would you like to title the meeting?"
                })
                response = jsonify({
                    'response': "What would you like to title the meeting?",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response

            # If we have all required information, schedule the meeting
            if context['time'] and context['recipients']:
                # Schedule the meeting
                meeting = meeting_automation.schedule_meeting(
                    subject=context['subject'] or "Meeting",
                    start_time=context['time'],
                    participants=context['recipients'],
                    duration=context['duration'],
                    is_recurring=context.get('is_recurring', False),
                    recurrence_rule=context.get('recurrence_rule', '')
                )
                
                # Send confirmation
                meeting_automation.send_meeting_confirmation(meeting, context['recipients'])
                
                # Clear context after successful scheduling
                chat_contexts[session_id] = {
                    'intent': None,
                    'time': None,
                    'duration': 30,
                    'recipients': [],
                    'subject': '',
                    'content': '',
                    'last_question': None,
                    'conversation_history': [],
                    'is_recurring': False,
                    'recurrence_rule': ''
                }
                
                response = jsonify({
                    'response': f"Great! I've scheduled a {context['duration']} minute meeting for {context['time'].strftime('%I:%M %p')} with {', '.join(context['recipients'])}. I've sent the calendar invites with Google Meet link.",
                    'show_form': False
                })
                response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
                return response

        # Handle unclear intent
        else:
            context['last_question'] = 'intent'
            context['conversation_history'].append({
                'role': 'assistant',
                'content': "I can help you schedule meetings or send emails. What would you like to do?"
            })
            response = jsonify({
                'response': "I can help you schedule meetings or send emails. What would you like to do?",
                'show_form': False
            })
            response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
            return response

    except Exception as e:
        print(f"Error in chat route: {str(e)}")
        response = jsonify({
            'response': f"Sorry, there was an error: {str(e)}",
            'show_form': False
        })
        response.set_cookie('session_id', session_id, httponly=True, samesite='Lax')
        return response

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        try:
            # Get form data
            subject = request.form['subject']
            date_str = request.form['date']
            time_str = request.form['time']
            duration = int(request.form['duration'])
            participants = request.form['participants'].split('\n')
            participants = [p.strip() for p in participants if p.strip()]

            # Combine date and time
            start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            
            # Schedule meeting
            meeting = meeting_automation.schedule_meeting(
                subject=subject,
                start_time=start_time,
                participants=participants,
                duration=duration
            )

            # Send confirmation emails
            meeting_automation.send_meeting_confirmation(meeting, participants)

            # Add to local storage
            meetings.append(meeting)

            flash('Meeting scheduled successfully!', 'success')
        except Exception as e:
            flash(f'Error scheduling meeting: {str(e)}', 'danger')

        return redirect(url_for('index'))
    
    return render_template('index.html', meetings=meetings)

@app.route('/meetings', methods=['GET'])
def get_meetings():
    return jsonify(meetings)

def main():
    try:
        print("Starting Web Server...")
        # Try different ports if the default one is in use
        port = 3001
        while True:
            try:
                print(f"Available at: http://127.0.0.1:{port}")
                print("Press Ctrl+C to stop the server")
                app.run(host='127.0.0.1', port=port, debug=True)
                break
            except OSError as e:
                if "Address already in use" in str(e):
                    port += 1
                    continue
                raise
    except Exception as e:
        print(f"Error starting server: {str(e)}")

if __name__ == '__main__':
    main() 