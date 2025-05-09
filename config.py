import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MCP Configuration
MCP_API_URL = os.getenv('MCP_API_URL', 'http://localhost:8000')
MCP_API_KEY = os.getenv('MCP_API_KEY')

# Ollama Configuration
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
OLLAMA_MODEL = 'mistral'  # Hardcoded to use mistral model

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Meeting Configuration
DEFAULT_MEETING_DURATION = 60  # minutes
DEFAULT_TIMEZONE = 'UTC'

# Context Configuration
CONTEXT_WINDOW_SIZE = 2048  # tokens
MAX_HISTORY_LENGTH = 10  # number of previous meetings to consider 