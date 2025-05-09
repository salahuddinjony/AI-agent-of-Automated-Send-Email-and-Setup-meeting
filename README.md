# Automated Meeting Setup System with MCP

This project automates the process of scheduling meetings and sending email confirmations using Model Context Protocol (MCP) and Ollama AI.

## Features

- Automated meeting scheduling with context awareness
- AI-generated meeting agendas using Ollama with MCP context
- Email confirmations with meeting details
- Meeting history tracking and context management
- Smart agenda generation based on previous meetings

## Prerequisites

- Python 3.8 or higher
- MCP server running (or accessible via network)
- Ollama running locally (or accessible via network)
- Required Python packages (listed in requirements.txt)
- SMTP email account for notifications

## Setup

1. Clone this repository
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following variables:
   ```
   MCP_API_URL=http://localhost:8000
   MCP_API_KEY=your_mcp_api_key
   OLLAMA_API_URL=http://localhost:11434
   OLLAMA_MODEL=llama2
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_EMAIL=your.email@gmail.com
   SMTP_PASSWORD=your_app_password
   ```

4. Make sure both MCP and Ollama services are running and accessible

## Usage

1. Run the main script:
   ```bash
   python meeting_automation.py
   ```

2. The script will:
   - Get relevant context from MCP based on meeting topic and participants
   - Generate an AI-powered agenda using the context
   - Schedule the meeting through MCP
   - Send confirmation emails to all participants
   - Store meeting history for future context

## Customization

You can modify the following in `config.py`:
- Default meeting duration
- Timezone settings
- Context window size
- Maximum history length
- Email templates
- AI model settings

## Security Notes

- Never commit your `.env` file to version control
- Keep your MCP API key and email credentials secure
- Use appropriate security measures for your MCP server
- Consider using environment-specific API keys

## Troubleshooting

If you encounter issues:
1. Verify your MCP server is running and accessible
2. Check if Ollama is running and accessible
3. Ensure all required packages are installed
4. Verify your SMTP credentials
5. Check your network connectivity
6. Review MCP server logs for any errors 