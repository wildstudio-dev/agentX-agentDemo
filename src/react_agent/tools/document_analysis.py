import base64
import mimetypes
from urllib.parse import urlparse
import os

import requests
from react_agent.tools.utils.file_handler import format_multimodal_message


# Tool function for LangGraph binding
async def document_analysis():
    """
    This function document is analysing the uploaded documents once requested.
    It needed request for analysis as an example: "Please analyse the attached file(s)."
    """
    return "Document analysis tool called"


def download_file_as_base64(url):
    """
    Download a file from URL and return as base64-encoded object

    Args:
        url (str): URL to download file from

    Returns:
        dict: Object with filename, content_type, and data (base64)
    """
    try:
        # Download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Get filename from URL or Content-Disposition header
        filename = None
        if 'content-disposition' in response.headers:
            content_disposition = response.headers['content-disposition']
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')

        if not filename:
            # Extract filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = "downloaded_file"

        # Get content type
        content_type = response.headers.get('content-type')
        if not content_type:
            # Guess content type from filename
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'

        # Encode file content as base64
        file_data = base64.b64encode(response.content).decode('utf-8')

        # Create the object
        file_object = {
            'filename': filename,
            'content_type': content_type,
            'data': file_data
        }

        return file_object

    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        return None
    except Exception as e:
        print(f"Error processing file: {e}")
        return None


async def process_document_analysis(state):
    """
    Internal function to process document analysis with state access.
    """
    messages_to_send = []
    document_message = state.messages[-2]
    # Check if this is the most recent user message with attachments
    if (hasattr(document_message, 'type') and document_message.type == "human" and
            hasattr(document_message, 'additional_kwargs') and
            document_message.additional_kwargs.get('fileLink')):
        # Format as multimodal message
        attachments = [
            download_file_as_base64(document_message.additional_kwargs['fileLink'])
        ]
        multimodal_content = format_multimodal_message(
            document_message.content if hasattr(document_message, 'content') else str(document_message),
            attachments
        )
        # TODO: Not sure if that role and content should be instead maybe type and text
        messages_to_send.append({
            "role": "user",
            "content": multimodal_content
        })
    return {"messages": messages_to_send}
