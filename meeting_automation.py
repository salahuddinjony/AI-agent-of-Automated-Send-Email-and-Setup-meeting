import os
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import ollama
import re
from config import *
from calendar_service import GoogleCalendarService

class MeetingAutomation:
    def __init__(self):
        print("Initializing Meeting Automation...")
        print(f"Connecting to Ollama at {OLLAMA_API_URL}")
        self.ollama_client = ollama.Client(host=OLLAMA_API_URL)
        self.mcp_headers = {
            'Authorization': f'Bearer {MCP_API_KEY}',
            'Content-Type': 'application/json'
        }
        self.meeting_history = []
        self.calendar_service = GoogleCalendarService()
        print("Meeting Automation initialized successfully!")

    def validate_email_config(self):
        """Validate email configuration"""
        print("\nValidating email configuration:")
        print(f"SMTP Server: {SMTP_SERVER}")
        print(f"SMTP Port: {SMTP_PORT}")
        print(f"Email: {SMTP_EMAIL}")
        print(f"Password length: {len(SMTP_PASSWORD) if SMTP_PASSWORD else 0} characters")
        print(f"First and last character of password: {SMTP_PASSWORD[0]}...{SMTP_PASSWORD[-1]}")
        print(f"Password contains spaces: {'yes' if ' ' in SMTP_PASSWORD else 'no'}")
        
        if not SMTP_EMAIL or not SMTP_PASSWORD:
            raise ValueError("Email or password is missing in .env file")
        
        if '@' not in SMTP_EMAIL:
            raise ValueError("Invalid email format")
        
        if len(SMTP_PASSWORD) != 16:
            raise ValueError(f"App password should be exactly 16 characters (current length: {len(SMTP_PASSWORD)})")
            
        print("Email configuration validation completed")

    def test_smtp_connection(self):
        """Test SMTP connection without sending email"""
        print("\nTesting SMTP connection...")
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                print("1. Successfully connected to SMTP server")
                server.starttls()
                print("2. Successfully started TLS")
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                print("3. Successfully logged in")
                return True
        except Exception as e:
            print(f"SMTP test failed: {str(e)}")
            return False

    def get_context(self, topic, participants):
        """Get relevant context from MCP"""
        print(f"Getting context for topic: {topic}")
        context_prompt = {
            "topic": topic,
            "participants": participants,
            "history_length": MAX_HISTORY_LENGTH
        }
        
        try:
            response = requests.post(
                f"{MCP_API_URL}/context",
                headers=self.mcp_headers,
                json=context_prompt
            )
            
            if response.status_code == 200:
                context = response.json().get('context', '')
                print("Context retrieved successfully")
                return context
            else:
                print(f"Error getting context: {response.text}")
                return ''
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to MCP server: {str(e)}")
            return ''

    def generate_meeting_content(self, topic, participants):
        """Generate meeting content using Ollama AI with MCP context"""
        print(f"Generating meeting content for: {topic}")
        context = self.get_context(topic, participants)
        
        prompt = f"""
        Based on the following context:
        {context}
        
        Generate a professional meeting agenda for a meeting about {topic}.
        Include:
        1. Meeting objectives
        2. Key discussion points
        3. Expected outcomes
        4. Action items
        """
        
        try:
            response = self.ollama_client.generate(
                model=OLLAMA_MODEL,
                prompt=prompt
            )
            print("Meeting content generated successfully")
            return response['response']
        except Exception as e:
            print(f"Error generating meeting content: {str(e)}")
            return "Meeting agenda could not be generated. Please prepare manually."

    def schedule_meeting(self, subject, start_time, participants, duration=DEFAULT_MEETING_DURATION, is_recurring=False, recurrence_rule=''):
        """Schedule a meeting using MCP and Google Calendar"""
        print(f"Scheduling meeting: {subject}")
        end_time = start_time + timedelta(minutes=duration)
        
        # Generate meeting content using AI with context
        meeting_content = self.generate_meeting_content(subject, participants)
        
        # Create Google Calendar event with Meet link
        calendar_event = self.calendar_service.create_meeting(
            subject=subject,
            start_time=start_time,
            end_time=end_time,
            participants=participants,
            description=meeting_content,
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule
        )
        
        # Create meeting data for MCP
        meeting_data = {
            "subject": subject,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "participants": participants,
            "content": meeting_content,
            "timezone": DEFAULT_TIMEZONE,
            "meet_link": calendar_event['meetLink'],
            "calendar_link": calendar_event['htmlLink'],
            "is_recurring": is_recurring,
            "recurrence_rule": recurrence_rule
        }
        
        try:
            # Send to MCP
            response = requests.post(
                f"{MCP_API_URL}/meetings",
                headers=self.mcp_headers,
                json=meeting_data
            )
            
            if response.status_code == 200:
                meeting = response.json()
                self.meeting_history.append(meeting)
                print("Meeting scheduled successfully")
                return meeting
            else:
                print(f"Error scheduling meeting: {response.text}")
                raise Exception(f"Failed to schedule meeting: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to MCP server: {str(e)}")
            raise

    def send_meeting_confirmation(self, meeting, participants):
        """Send meeting confirmation email with Google Meet link"""
        print("\nPreparing to send meeting confirmation...")
        
        # Validate configuration first
        self.validate_email_config()
        
        # Test SMTP connection
        if not self.test_smtp_connection():
            raise Exception("Failed to establish SMTP connection")
        
        print(f"\nSending confirmation to: {participants}")
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Meeting Confirmation: {meeting['subject']}"
        msg['From'] = SMTP_EMAIL
        msg['To'] = ', '.join(participants)
        
        html = f"""
        <html>
            <body>
                <h2>Meeting Confirmation</h2>
                <p>Your meeting has been scheduled:</p>
                <ul>
                    <li>Subject: {meeting['subject']}</li>
                    <li>Start Time: {meeting['start_time']}</li>
                    <li>End Time: {meeting['end_time']}</li>
                    <li>Google Meet Link: <a href="{meeting['meet_link']}">{meeting['meet_link']}</a></li>
                    <li>Calendar Event: <a href="{meeting['calendar_link']}">View in Calendar</a></li>
                </ul>
                <h3>Agenda:</h3>
                <p>{meeting['content']}</p>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
                print("Email sent successfully!")
        except Exception as e:
            print("\nError sending email:")
            print(f"Type: {type(e).__name__}")
            print(f"Error: {str(e)}")
            raise

    def validate_email(self, email):
        """Validate email format and domain"""
        if not email:
            return False, "Email address is empty"
            
        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False, f"Invalid email format: {email}"
            
        # Check if it's a test email
        if email.endswith('@example.com'):
            return True, "Test email accepted"
            
        return True, "Email is valid"

    def validate_recipients(self, recipients):
        """Validate all recipient emails"""
        valid_recipients = []
        invalid_emails = []
        
        for email in recipients:
            is_valid, message = self.validate_email(email)
            if is_valid:
                valid_recipients.append(email)
            else:
                invalid_emails.append((email, message))
                
        return valid_recipients, invalid_emails

    def send_email(self, recipients, subject, content, generate_joke=False, joke_topic='', is_html=False):
        """Send an email with validation and error handling"""
        try:
            # Validate recipients first
            valid_recipients, invalid_emails = self.validate_recipients(recipients)
            
            if not valid_recipients:
                return False, "No valid recipients found"
                
            if invalid_emails:
                print("Warning: Some email addresses are invalid:")
                for email, message in invalid_emails:
                    print(f"- {email}: {message}")
            
            # Generate joke if requested
            if generate_joke:
                from llm_service import LLMService
                llm_service = LLMService()
                joke = llm_service.generate_joke(joke_topic)
                content = f"Here's a joke about {joke_topic}:\n\n{joke}\n\n{content}"
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = SMTP_EMAIL
            msg['To'] = ', '.join(valid_recipients)
            msg['Subject'] = subject
            
            # Add body
            if is_html:
                msg.attach(MIMEText(content, 'html'))
            else:
                msg.attach(MIMEText(content, 'plain'))
            
            # Send email
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
            
            return True, f"Email sent successfully to {', '.join(valid_recipients)}"
        except smtplib.SMTPRecipientsRefused as e:
            return False, f"Some recipients were refused: {str(e)}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except Exception as e:
            return False, f"Failed to send email: {str(e)}"

    def process_email(self, email_content):
        """Process an email and extract meeting details"""
        print("\nProcessing email for meeting details...")
        
        try:
            # Send email content to MCP for processing
            response = requests.post(
                f"{MCP_API_URL}/process_email",
                headers=self.mcp_headers,
                json={'email_content': email_content}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'pending_confirmation':
                    print("Meeting details extracted successfully")
                    print(f"Meeting ID: {result['meeting_id']}")
                    print(f"Subject: {result['meeting_details']['subject']}")
                    print(f"Proposed Time: {result['meeting_details']['proposed_time']}")
                    print(f"Participants: {', '.join(result['meeting_details']['participants'])}")
                    
                    # Send confirmation emails to participants
                    self.send_meeting_confirmation_request(
                        result['meeting_details'],
                        result['confirmation_link']
                    )
                    
                    return True, "Meeting request sent for confirmation"
                else:
                    return False, "Failed to process email"
            else:
                return False, f"Error processing email: {response.text}"
                
        except Exception as e:
            print(f"Error processing email: {str(e)}")
            return False, str(e)

    def send_meeting_confirmation_request(self, meeting_details, confirmation_link):
        """Send meeting confirmation request to participants with validation"""
        print("\nSending meeting confirmation requests...")
        
        try:
            # Validate recipients
            valid_recipients, invalid_emails = self.validate_recipients(meeting_details['participants'])
            
            if not valid_recipients:
                return False, "No valid recipients found for meeting confirmation"
                
            if invalid_emails:
                print("Warning: Some participants have invalid email addresses:")
                for email, message in invalid_emails:
                    print(f"- {email}: {message}")
            
            subject = f"Meeting Request: {meeting_details['subject']}"
            content = f"""
            <html>
                <body>
                    <h2>Meeting Request</h2>
                    <p>A meeting has been requested with the following details:</p>
                    
                    <ul>
                        <li><strong>Subject:</strong> {meeting_details['subject']}</li>
                        <li><strong>Proposed Time:</strong> {meeting_details['proposed_time']}</li>
                        <li><strong>Duration:</strong> {meeting_details['duration']} minutes</li>
                        <li><strong>Participants:</strong> {', '.join(valid_recipients)}</li>
                    </ul>
                    
                    <p>Please confirm or reject this meeting request by clicking one of the buttons below:</p>
                    
                    <div style="margin: 20px 0;">
                        <a href="{confirmation_link}?action=confirm" 
                           style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px;">
                            Confirm Meeting
                        </a>
                        <a href="{confirmation_link}?action=reject" 
                           style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Reject Meeting
                        </a>
                    </div>
                    
                    <p>Or copy and paste this link in your browser:</p>
                    <p style="word-break: break-all;">{confirmation_link}</p>
                    
                    <h3>Meeting Details:</h3>
                    <pre style="white-space: pre-wrap;">{meeting_details['content']}</pre>
                </body>
            </html>
            """
            
            # Send confirmation emails only to valid recipients
            success, message = self.send_email(
                recipients=valid_recipients,
                subject=subject,
                content=content,
                is_html=True
            )
            
            if not success:
                return False, f"Failed to send confirmation emails: {message}"
                
            return True, f"Confirmation requests sent successfully to {', '.join(valid_recipients)}"
            
        except Exception as e:
            return False, f"Error sending confirmation requests: {str(e)}"

    def confirm_meeting(self, meeting_id, confirm=True):
        """Confirm or reject a meeting request"""
        print(f"\n{'Confirming' if confirm else 'Rejecting'} meeting {meeting_id}...")
        
        try:
            response = requests.post(
                f"{MCP_API_URL}/confirm_meeting/{meeting_id}",
                headers=self.mcp_headers,
                json={'confirm': confirm}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'confirmed':
                    # Send final confirmation to participants
                    self.send_meeting_confirmation(result['meeting'], result['meeting']['participants'])
                    return True, "Meeting confirmed and notifications sent"
                else:
                    return True, "Meeting request rejected"
            else:
                return False, f"Error confirming meeting: {response.text}"
                
        except Exception as e:
            print(f"Error confirming meeting: {str(e)}")
            return False, str(e)

def main():
    print("Starting Meeting Automation System...")
    automation = MeetingAutomation()
    
    # Example meeting details
    subject = "Project Planning Meeting"
    start_time = datetime.now() + timedelta(days=1)  # Tomorrow
    participants = ["participant1@example.com", "participant2@example.com"]
    
    try:
        # Schedule meeting
        print("\nScheduling new meeting...")
        meeting = automation.schedule_meeting(subject, start_time, participants)
        
        # Send confirmation
        print("\nSending meeting confirmations...")
        automation.send_meeting_confirmation(meeting, participants)
        print("\nMeeting scheduled and confirmation sent successfully!")
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("Meeting automation failed. Please check the logs above for details.")

if __name__ == "__main__":
    main() 