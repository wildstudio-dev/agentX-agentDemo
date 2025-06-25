from react_agent.tools.utils.file_handler import format_multimodal_message


# Tool function for LangGraph binding
async def document_analysis():
    """
    This function document is analysing the uploaded documents once requested.
    It needed request for analysis as an example: "Please analyse the attached file(s)."
    """
    return "Document analysis tool called"


# Internal function that actually processes the documents
async def process_document_analysis(state):
    """
    Internal function to process document analysis with state access.
    """
    messages_to_send = []
    document_message = state.messages[-2]
    # Check if this is the most recent user message with attachments
    if (hasattr(document_message, 'type') and document_message.type == "human" and
            hasattr(document_message, 'additional_kwargs') and
            document_message.additional_kwargs.get('attachments')):
        # Format as multimodal message
        multimodal_content = format_multimodal_message(
            document_message.content if hasattr(document_message, 'content') else str(document_message),
            document_message.additional_kwargs['attachments']
        )
        # TODO: Not sure if that role and content should be instead maybe type and text
        messages_to_send.append({
            "role": "user",
            "content": multimodal_content
        })
    return {"messages": messages_to_send}
