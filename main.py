def handle_conversation(user_message, conversation_context):
    """Handle the conversation with the user."""
    llm_service = LLMService()
    email_service = EmailService(EMAIL, PASSWORD)
    
    # Understand user intent
    intent_result = llm_service.understand_intent(user_message, conversation_context)
    
    if intent_result['intent'] == 'send_email':
        # Send email
        success, message = email_service.send_email(
            recipients=intent_result['recipients'],
            subject=intent_result['subject'],
            content=intent_result['content'],
            generate_joke=intent_result['generate_joke'],
            joke_topic=intent_result['joke_topic']
        )
        return message
    elif intent_result['intent'] == 'schedule_meeting':
        # Schedule meeting
        # ... existing meeting scheduling code ...
        pass
    else:
        return "I'm not sure what you'd like me to do. Please try again." 