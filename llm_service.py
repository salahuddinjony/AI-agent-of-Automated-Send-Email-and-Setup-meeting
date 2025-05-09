import os
from datetime import datetime, timedelta
import ollama
from config import *

class LLMService:
    def __init__(self):
        print("Initializing LLM Service...")
        self.ollama_client = ollama.Client(host=OLLAMA_API_URL)
        self.known_contacts = {
            'salah': 'salahuddin0758@gmail.com',
            'abdullah': 'aamcse@gmail.com',
            'sallu': 'salauddin0758@gmail.com',
            # Add more contacts as needed
        }
        print("LLM Service initialized successfully!")

    def parse_time(self, time_str):
        """Parse time from natural language"""
        print(f"Parsing time: {time_str}")  # Debug print
        current_date = datetime.now()
        
        # Handle "tomorrow"
        if 'tomorrow' in time_str.lower():
            current_date += timedelta(days=1)
            time_parts = time_str.lower().replace('tomorrow', '').strip()
        # Handle "today"
        elif 'today' in time_str.lower():
            time_parts = time_str.lower().replace('today', '').strip()
        else:
            time_parts = time_str

        # Normalize time format
        time_parts = time_parts.upper().strip()
        
        # Handle AM/PM times
        if 'AM' in time_parts or 'PM' in time_parts:
            try:
                # Try parsing with colon
                time = datetime.strptime(time_parts, '%I:%M %p').time()
                print(f"Parsed time with colon: {time}")  # Debug print
                return datetime.combine(current_date.date(), time)
            except ValueError:
                try:
                    # Try parsing without colon
                    time = datetime.strptime(time_parts, '%I %p').time()
                    print(f"Parsed time without colon: {time}")  # Debug print
                    return datetime.combine(current_date.date(), time)
                except ValueError:
                    try:
                        # Try parsing with space between time and AM/PM
                        time = datetime.strptime(time_parts, '%I%M %p').time()
                        print(f"Parsed time with space: {time}")  # Debug print
                        return datetime.combine(current_date.date(), time)
                    except ValueError:
                        print(f"Failed to parse time: {time_parts}")  # Debug print
                        return None

        print(f"Time string does not contain AM/PM: {time_parts}")  # Debug print
        return None

    def parse_duration(self, duration_str):
        """Parse duration from natural language"""
        duration_str = duration_str.lower()
        if 'm' in duration_str or 'min' in duration_str:
            try:
                return int(''.join(filter(str.isdigit, duration_str)))
            except ValueError:
                return 30  # default duration
        elif 'h' in duration_str or 'hour' in duration_str:
            try:
                hours = int(''.join(filter(str.isdigit, duration_str)))
                return hours * 60
            except ValueError:
                return 60  # default duration
        return 30  # default duration

    def resolve_contact(self, name):
        """Resolve contact name to email"""
        name = name.lower()
        if '@' in name:  # Already an email
            return name
        return self.known_contacts.get(name)

    def understand_intent(self, message, context=None):
        """Understand user intent using LLM"""
        print(f"\nProcessing message: {message}")
        print(f"Current context: {context}")  # Debug print
        
        # Build conversation history for context
        conversation_context = ""
        if context and 'conversation_history' in context:
            for msg in context['conversation_history']:
                role = "User" if msg['role'] == 'user' else "Assistant"
                conversation_context += f"{role}: {msg['content']}\n"
        
        system_prompt = f"""You are an AI assistant that helps understand meeting and email related requests.
        Current conversation context:
        {conversation_context}
        
        Extract the following information from the user's message and return it in a structured format:
        {{
            "intent": "schedule_meeting" or "send_email",
            "time": "extracted time (e.g., '2:00 PM tomorrow' or '10:00 AM today')",
            "duration": "duration in minutes (e.g., '30' or '60')",
            "recipients": ["list of recipients"],
            "subject": "meeting subject or email subject",
            "content": "email content if applicable",
            "generate_joke": true/false,
            "joke_topic": "topic for the joke if applicable",
            "is_recurring": true/false,
            "recurrence_rule": "recurrence rule if applicable (e.g., 'FREQ=WEEKLY;BYDAY=FR;UNTIL=20240430T235959Z' for weekly Friday meetings in April)"
        }}
        
        Consider the conversation context when extracting information. For example:
        - If the user is responding to a question about recipients, extract the recipient information
        - If the user is responding to a question about subject, extract the subject information
        - If the user is responding to a question about content, extract the content information
        - If the user wants to send a joke, set generate_joke to true and extract the joke topic
        - If the user wants to schedule a recurring meeting, set is_recurring to true and extract the recurrence rule
        
        Example 1:
        User: "schedule a meeting tomorrow at 2pm with salahuddin0758@gmail.com"
        Response: {{
            "intent": "schedule_meeting",
            "time": "2:00 PM tomorrow",
            "duration": "30",
            "recipients": ["salahuddin0758@gmail.com"],
            "subject": "Meeting",
            "content": "",
            "generate_joke": false,
            "joke_topic": "",
            "is_recurring": false,
            "recurrence_rule": ""
        }}
        
        Example 2:
        User: "set up a meeting every friday in apr to salauddin0758@gmail.com"
        Response: {{
            "intent": "schedule_meeting",
            "time": "10:00 AM this Friday",
            "duration": "30",
            "recipients": ["salahuddin0758@gmail.com"],
            "subject": "Weekly Meeting",
            "content": "",
            "generate_joke": false,
            "joke_topic": "",
            "is_recurring": true,
            "recurrence_rule": "FREQ=WEEKLY;BYDAY=FR;UNTIL=20240430T235959Z"
        }}
        """

        try:
            print(f"Using Ollama model: {OLLAMA_MODEL}")
            response = self.ollama_client.generate(
                model=OLLAMA_MODEL,
                prompt=f"{system_prompt}\n\nUser message: {message}\nResponse:"
            )
            print(f"Ollama response: {response['response']}")
            
            # Process the LLM response to extract structured information
            result = self._process_llm_response(response['response'], message)
            print(f"Processed result: {result}")
            return result
        except Exception as e:
            print(f"Error in LLM understanding: {str(e)}")
            print(f"Error type: {type(e)}")
            return None

    def _process_llm_response(self, llm_response, original_message):
        """Process LLM response and extract structured information"""
        import json
        import re

        # Default structure for the response
        result = {
            'intent': None,
            'time': None,
            'duration': 30,  # default duration in minutes
            'recipients': [],
            'subject': '',
            'content': '',
            'generate_joke': False,
            'joke_topic': '',
            'is_recurring': False,
            'recurrence_rule': ''
        }

        try:
            # Clean up the response
            llm_response = llm_response.strip()
            
            # Remove any markdown code block markers and comments
            llm_response = re.sub(r'```json\n|\n```', '', llm_response)
            llm_response = re.sub(r'//.*$', '', llm_response, flags=re.MULTILINE)
            
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Clean up the JSON string
                json_str = json_str.replace('\n', ' ').replace('\r', '')
                # Fix common JSON formatting issues
                json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
                
                # Parse the JSON
                parsed = json.loads(json_str)
                
                # Map the parsed values to our result structure
                result['intent'] = parsed.get('intent')
                result['time'] = parsed.get('time')
                result['duration'] = parsed.get('duration', 30)
                result['recipients'] = parsed.get('recipients', [])
                result['subject'] = parsed.get('subject', '')
                result['content'] = parsed.get('content', '')
                result['generate_joke'] = parsed.get('generate_joke', False)
                result['joke_topic'] = parsed.get('joke_topic', '')
                result['is_recurring'] = parsed.get('is_recurring', False)
                result['recurrence_rule'] = parsed.get('recurrence_rule', '')

                # Convert string recipients to list if needed
                if isinstance(result['recipients'], str):
                    result['recipients'] = [result['recipients']]

                # Convert duration to integer if it's a string
                if isinstance(result['duration'], str):
                    try:
                        result['duration'] = int(result['duration'])
                    except ValueError:
                        result['duration'] = 30

                # Parse time if it's a string
                if isinstance(result['time'], str) and result['time']:
                    result['time'] = self.parse_time(result['time'])

                # Resolve contact names to emails
                resolved_recipients = []
                for recipient in result['recipients']:
                    email = self.resolve_contact(recipient)
                    if email:
                        resolved_recipients.append(email)
                result['recipients'] = resolved_recipients

        except Exception as e:
            print(f"Error parsing LLM response: {str(e)}")
            print(f"Raw response: {llm_response}")
            # Fall back to basic intent detection if JSON parsing fails
            if any(word in original_message.lower() for word in ['meeting', 'schedule', 'set up']):
                result['intent'] = 'schedule_meeting'
            elif any(word in original_message.lower() for word in ['email', 'send', 'message']):
                result['intent'] = 'send_email'
            elif any(word in original_message.lower() for word in ['help', 'what can you do']):
                result['intent'] = 'help'

        return result 

    def generate_joke(self, topic="computer"):
        """Generate a joke about a specific topic using LLM"""
        print(f"Generating joke about: {topic}")
        
        joke_prompt = f"""Generate a funny joke about {topic}. 
        The joke should be clean, professional, and suitable for a work environment.
        Return only the joke text, no additional formatting or explanation."""
        
        try:
            response = self.ollama_client.generate(
                model=OLLAMA_MODEL,
                prompt=joke_prompt
            )
            joke = response['response'].strip()
            print(f"Generated joke: {joke}")
            return joke
        except Exception as e:
            print(f"Error generating joke: {str(e)}")
            return f"Here's a classic computer joke: Why do programmers prefer dark mode? Because light attracts bugs!" 