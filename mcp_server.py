from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import os
from functools import wraps
import re
from email.parser import Parser
from email.policy import default
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

# Load API key and email configuration from environment
API_KEY = os.getenv('MCP_API_KEY', 'dev_key_123')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_EMAIL = os.getenv('SMTP_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# In-memory storage for meetings and context
meetings = []
context_history = []
pending_meetings = {}  # Store pending meeting requests that need confirmation

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('Authorization') != f'Bearer {API_KEY}':
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

def send_confirmation_email(meeting, participants):
    """Send confirmation email to all participants"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Meeting Confirmed: {meeting['subject']}"
        msg['From'] = SMTP_EMAIL
        msg['To'] = ', '.join(participants)
        
        html = f"""
        <html>
            <body>
                <h2>Meeting Confirmed</h2>
                <p>Your meeting has been confirmed with the following details:</p>
                
                <ul>
                    <li><strong>Subject:</strong> {meeting['subject']}</li>
                    <li><strong>Start Time:</strong> {meeting['start_time']}</li>
                    <li><strong>Duration:</strong> {meeting['duration']} minutes</li>
                    <li><strong>Participants:</strong> {', '.join(participants)}</li>
                </ul>
                
                <p>This meeting has been added to your calendar.</p>
                
                <h3>Meeting Details:</h3>
                <pre style="white-space: pre-wrap;">{meeting['content']}</pre>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            
        return True, "Confirmation email sent successfully"
    except Exception as e:
        return False, f"Failed to send confirmation email: {str(e)}"

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'status': 'running',
        'message': 'MCP Server is running',
        'endpoints': {
            '/context': 'POST - Get meeting context',
            '/meetings': 'GET/POST - Manage meetings'
        }
    })

@app.route('/context', methods=['POST'])
@require_api_key
def get_context():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        topic = data.get('topic', '')
        participants = data.get('participants', [])
        history_length = data.get('history_length', 10)
        
        # Get relevant context from history
        relevant_context = []
        for meeting in meetings[-history_length:]:
            if topic.lower() in meeting['subject'].lower() or any(p in meeting['participants'] for p in participants):
                relevant_context.append(meeting)
        
        return jsonify({
            'context': json.dumps(relevant_context),
            'status': 'success'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/meetings', methods=['POST'])
@require_api_key
def create_meeting():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        required_fields = ['subject', 'start_time', 'end_time', 'participants', 'content']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        meeting = {
            'id': len(meetings) + 1,
            'subject': data['subject'],
            'start_time': data['start_time'],
            'end_time': data['end_time'],
            'participants': data['participants'],
            'content': data['content'],
            'timezone': data.get('timezone', 'UTC'),
            'meet_link': data.get('meet_link', ''),
            'calendar_link': data.get('calendar_link', ''),
            'created_at': datetime.now().isoformat()
        }
        
        meetings.append(meeting)
        return jsonify(meeting)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/meetings', methods=['GET'])
@require_api_key
def get_meetings():
    return jsonify(meetings)

@app.route('/process_email', methods=['POST'])
@require_api_key
def process_email():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        email_content = data.get('email_content', '')
        if not email_content:
            return jsonify({'error': 'No email content provided'}), 400
            
        # Parse email content
        email = Parser(policy=default).parsestr(email_content)
        
        # Extract meeting details using regex patterns
        subject = email.get('subject', '')
        body = email.get_payload()
        
        # Format the email content to preserve structure
        formatted_content = body.strip().replace('\n', '<br>')
        
        # Look for common meeting patterns
        time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)|tomorrow at \d{1,2}:\d{2}\s*(?:AM|PM|am|pm)|today at \d{1,2}:\d{2}\s*(?:AM|PM|am|pm))'
        duration_pattern = r'(\d+)\s*(?:min|minutes|hour|hours)'
        participants_pattern = r'(?:^|\s)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        
        # Extract details
        time_match = re.search(time_pattern, body, re.IGNORECASE)
        duration_match = re.search(duration_pattern, body, re.IGNORECASE)
        participants = re.findall(participants_pattern, body)
        
        # Clean up email addresses and remove duplicates
        participants = list(set([email.strip('- ') for email in participants]))
        
        # Extract duration in minutes
        duration = 30  # default duration
        if duration_match:
            duration_value = int(duration_match.group(1))
            if 'hour' in duration_match.group(0).lower():
                duration = duration_value * 60
            else:
                duration = duration_value
        
        if not time_match or not participants:
            return jsonify({'error': 'Could not extract meeting details from email'}), 400
            
        # Create pending meeting request
        meeting_id = len(pending_meetings) + 1
        pending_meeting = {
            'id': meeting_id,
            'subject': subject,
            'proposed_time': time_match.group(1),
            'duration': duration,
            'participants': participants,
            'content': formatted_content,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        pending_meetings[meeting_id] = pending_meeting
        
        # Create full confirmation URL
        base_url = request.host_url.rstrip('/')  # Get the base URL of the server
        if not base_url:
            base_url = "http://localhost:8000"  # Default fallback URL
        confirmation_url = f"{base_url}/confirm_meeting/{meeting_id}"
        
        return jsonify({
            'status': 'pending_confirmation',
            'meeting_id': meeting_id,
            'confirmation_link': confirmation_url,
            'meeting_details': pending_meeting
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/confirm_meeting/<int:meeting_id>', methods=['GET', 'POST'])
def confirm_meeting(meeting_id):
    try:
        # Check if this is an authenticated request
        is_authenticated = request.headers.get('Authorization') == f'Bearer {API_KEY}'
        
        # Get confirmation action from query params (GET) or request body (POST)
        if request.method == 'GET':
            action = request.args.get('action', '')
        else:
            if not is_authenticated:
                return jsonify({'error': 'Unauthorized'}), 401
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            action = data.get('confirm', False)
        
        if not action:
            return jsonify({'error': 'Confirmation status not provided'}), 400
            
        if meeting_id not in pending_meetings:
            return jsonify({'error': 'Meeting request not found'}), 404
            
        meeting = pending_meetings[meeting_id]
        
        if action == 'confirm' or action is True:
            # Convert proposed time to datetime
            proposed_time = meeting['proposed_time']
            if 'tomorrow' in proposed_time.lower():
                start_time = datetime.now() + timedelta(days=1)
            elif 'today' in proposed_time.lower():
                start_time = datetime.now()
            else:
                # Parse time string
                start_time = datetime.strptime(proposed_time, '%I:%M %p')
                if start_time < datetime.now():
                    start_time += timedelta(days=1)
            
            # Create the meeting
            meeting = {
                'id': len(meetings) + 1,
                'subject': meeting['subject'],
                'start_time': start_time.isoformat(),
                'end_time': (start_time + timedelta(minutes=meeting['duration'])).isoformat(),
                'participants': meeting['participants'],
                'content': meeting['content'],
                'timezone': 'UTC',
                'created_at': datetime.now().isoformat()
            }
            
            meetings.append(meeting)
            del pending_meetings[meeting_id]
            
            # Send confirmation emails
            success, message = send_confirmation_email(meeting, meeting['participants'])
            if not success:
                print(f"Warning: {message}")
            
            if request.method == 'GET':
                return render_template('confirmation_success.html', meeting=meeting)
            return jsonify({
                'status': 'confirmed',
                'meeting': meeting
            })
        else:
            # Meeting rejected
            del pending_meetings[meeting_id]
            if request.method == 'GET':
                return render_template('confirmation_rejected.html')
            return jsonify({
                'status': 'rejected',
                'message': 'Meeting request rejected'
            })
            
    except Exception as e:
        if request.method == 'GET':
            return render_template('confirmation_error.html', error=str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting MCP Server...")
    print(f"API Key: {API_KEY}")
    print("Available endpoints:")
    print("- GET  / : Server status")
    print("- POST /context : Get meeting context")
    print("- GET  /meetings : List all meetings")
    print("- POST /meetings : Create a new meeting")
    print("- POST /process_email : Process an email and schedule a meeting")
    print("- POST /confirm_meeting/<meeting_id> : Confirm or reject a meeting")
    app.run(host='0.0.0.0', port=8000, debug=True) 