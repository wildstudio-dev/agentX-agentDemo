"""Handle file processing for multimodal AI models."""

import base64
import mimetypes
from typing import Dict, Any, List, Optional, Final
from pathlib import Path
import io
import logging
from react_agent.tools.utils.document_type_strategies import has_custom_handling, get_custom_messages
from react_agent.prompts import DEFAULT_SUMMARY_PROMPT

# Set up logging
logger = logging.getLogger(__name__)

DOCUMENT_HEADER_SIZE: Final = 500
DOCUMENT_IMAGE_LIMIT: Final = 500
LARGE_DOCUMENT_SIZE: Final = 15000
DOCUMENT_SIZE_LIMIT: Final = 30000

try:
    import pypdfium2 as pdfium

    PDF_SUPPORT = True
    logger.info("pypdfium2 loaded successfully - PDF support enabled")
except ImportError as e:
    PDF_SUPPORT = False
    logger.error(f"pypdfium2 not available: {e}. PDF processing will be limited.")
    print("Warning: pypdfium2 not available. PDF processing will be limited.")

# Try to import PyPDF2 as fallback for text extraction
try:
    import PyPDF2

    PYPDF2_SUPPORT = True
    logger.info("PyPDF2 loaded successfully - PDF text extraction available")
except ImportError:
    PYPDF2_SUPPORT = False
    logger.warning("PyPDF2 not available - PDF text extraction will be limited")


def get_token_count(text: str) -> float:
    return len(text) / 4


def process_image(content_type, attachment: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "type": "image_url",
        "image_url": {
            "url": f"data:{content_type};base64,{attachment.get('data', '')}"
        }
    }]


def process_large_document(pdf_data: str, filename: str, estimated_tokens: float) -> List[Dict[str, Any]]:
    logger.info("PDF too large for image conversion, using text extraction")
    extracted_text = extract_pdf_text(pdf_data)
    content_blocks = []
    if extracted_text:
        # Truncate if needed
        if len(extracted_text) > DOCUMENT_SIZE_LIMIT:
            extracted_text = extracted_text[
                             :DOCUMENT_SIZE_LIMIT] + "\n\n[Document truncated due to size limit]"
        if has_custom_handling(extracted_text[:DOCUMENT_HEADER_SIZE]):
            content_blocks.extend(get_custom_messages(extracted_text))
        else:
            content_blocks.append({
                "type": "text",
                "text": DEFAULT_SUMMARY_PROMPT
            })
        content_blocks.append({
            "type": "text",
            "text": f"=== PDF Content: {filename} (Text Extracted) ===\n\n{extracted_text}"
        })
    else:
        content_blocks.append({
                "type": "text",
                "text": DEFAULT_SUMMARY_PROMPT
            })
        content_blocks.extend(process_images(pdf_data, filename))
    return content_blocks


def process_images(pdf_data: str, filename: str):
    pdf_images = convert_pdf_to_images(pdf_data)
    content_blocks = []
    if pdf_images:
        # Add each page as an image
        for i, img_base64 in enumerate(pdf_images):
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            })
        content_blocks.append({
            "type": "text",
            "text": f"[PDF {filename} - {len(pdf_images)} pages shown as images above]"
        })
    else:
        content_blocks.append({
            "type": "text",
            "text": f"[PDF {filename} could not be processed - unable to extract text or convert to images]"
        })
    return content_blocks


def process_normal_document(pdf_data: str, filename: str):
    # Try text extraction first for smaller files too
    logger.info("Attempting PDF text extraction")
    extracted_text = extract_pdf_text(pdf_data)
    content_blocks = []
    if extracted_text and len(extracted_text) > DOCUMENT_IMAGE_LIMIT:  # If we got meaningful text
        if has_custom_handling(extracted_text[:DOCUMENT_HEADER_SIZE]):
            content_blocks.extend(get_custom_messages(extracted_text))
        else:
            content_blocks.append({
                "type": "text",
                "text": DEFAULT_SUMMARY_PROMPT
            })
        content_blocks.append({
            "type": "text",
            "text": f"=== PDF Content: {filename} ===\n\n{extracted_text}"
        })
    else:
        # Try image conversion as fallback
        content_blocks.extend(process_images(pdf_data, filename))

    return content_blocks


def process_text_documents(attachment: Dict[str, Any], filename: str):
    # Text files can be included directly
    content_blocks = []
    text_content = attachment.get("text", "")
    if not text_content and attachment.get("data"):
        # Decode base64 if text wasn't provided
        try:
            text_content = base64.b64decode(attachment["data"]).decode("utf-8")
        except Exception:
            # TODO: Not sure if its great option
            text_content = f"[Unable to decode {filename}]"
    if has_custom_handling(text_content[:DOCUMENT_HEADER_SIZE]):
        content_blocks.extend(get_custom_messages(text_content))
    else:
        content_blocks.append({
            "type": "text",
            "text": DEFAULT_SUMMARY_PROMPT
        })
    content_blocks.append({
        "type": "text",
        "text": f"=== FILE: {filename} ===\n\n{text_content}"
    })
    return content_blocks


def process_attachments_for_multimodal(attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process file attachments for multimodal model input.
    
    Args:
        attachments: List of attachment dictionaries with file data
        
    Returns:
        List of formatted content blocks for multimodal messages
    """
    content_blocks = []

    for attachment in attachments:
        filename = attachment.get("filename", "")
        content_type = attachment.get("content_type", "")

        # Handle different file types
        if content_type.startswith("image/"):
            # Images can be sent directly as base64
            # NOTE: Cannot determine document type on image
            content_blocks.extend(process_image(content_type, attachment))

        elif content_type == "application/pdf":
            # Log attachment info
            logger.info(f"Processing PDF attachment: {filename}")
            pdf_data = attachment.get('data', '')

            if not pdf_data:
                logger.error(f"No data found for PDF attachment: {filename}")
                content_blocks.append({
                    "type": "text",
                    "text": f"[PDF file {filename} could not be processed - no data]"
                })
            else:
                # TODO: Not sure this make sense
                estimated_tokens = get_token_count(pdf_data)
                logger.info(f"PDF {filename} estimated tokens: {estimated_tokens}")

                if estimated_tokens > LARGE_DOCUMENT_SIZE:  # Use text extraction for large files
                    content_blocks.extend(process_large_document(pdf_data, filename, estimated_tokens))
                else:
                    content_blocks.extend(process_normal_document(pdf_data, filename))

        elif content_type.startswith("text/") or content_type in ["application/json", "text/csv"]:
            content_blocks.extend(process_text_documents(attachment, filename))

        else:
            # Unsupported file type
            content_blocks.append({
                "type": "text",
                "text": f"=== UNSUPPORTED FILE: {filename} ({content_type}) ==="
            })

    return content_blocks


def format_multimodal_message(text: str, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format a message with text and attachments for multimodal model input.
    
    Args:
        text: The text message from the user
        attachments: List of file attachments
        
    Returns:
        Formatted content array for multimodal message
    """
    content = []

    # Add the text message first
    if text:
        content.append({
            "type": "text",
            "text": text
        })

    # Process and add attachments
    if attachments:
        attachment_content = process_attachments_for_multimodal(attachments)
        content.extend(attachment_content)

    return content


def convert_pdf_to_images(pdf_data: str, max_pages: int = 3) -> List[str]:
    """
    Convert PDF to images for GPT-4 processing using pypdfium2.
    
    Args:
        pdf_data: Base64 encoded PDF data
        max_pages: Maximum number of pages to convert (default 5)
        
    Returns:
        List of base64 encoded images
    """
    if not PDF_SUPPORT:
        logger.error("PDF to image conversion not available. Please install pypdfium2.")
        print("PDF to image conversion not available. Please install pypdfium2.")
        return []

    if not pdf_data:
        logger.error("No PDF data provided")
        return []

    try:
        # Log the size of the base64 data
        logger.info(f"Processing PDF with base64 data size: {len(pdf_data)} characters")

        # Decode base64 PDF data
        pdf_bytes = base64.b64decode(pdf_data)
        logger.info(f"Decoded PDF size: {len(pdf_bytes)} bytes")

        # Load PDF with pypdfium2
        pdf = pdfium.PdfDocument(pdf_bytes)
        total_pages = len(pdf)
        logger.info(f"PDF loaded successfully with {total_pages} pages")

        # Limit number of pages
        n_pages = min(total_pages, max_pages)
        logger.info(f"Converting {n_pages} pages (max: {max_pages})")

        # Convert pages to images
        base64_images = []
        for page_num in range(n_pages):
            try:
                page = pdf[page_num]

                # Render page at 100 DPI (scale = 100/72) to reduce size
                scale = 100 / 72
                bitmap = page.render(scale=scale)

                # Convert to PIL Image
                pil_image = bitmap.to_pil()

                # Convert PIL image to base64
                img_buffer = io.BytesIO()
                pil_image.save(img_buffer, format='PNG')
                img_buffer.seek(0)

                # Encode to base64
                img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
                base64_images.append(img_base64)
                logger.debug(f"Successfully converted page {page_num + 1}")

            except Exception as page_error:
                logger.error(f"Error converting page {page_num + 1}: {page_error}")
                # Continue with other pages even if one fails

        # Close the PDF
        pdf.close()

        logger.info(f"Successfully converted {len(base64_images)} pages to images")
        return base64_images

    except base64.binascii.Error as e:
        logger.error(f"Invalid base64 data for PDF: {e}")
        print(f"Error: PDF data is not valid base64 encoding")
        return []
    except Exception as e:
        logger.error(f"Error converting PDF to images: {type(e).__name__}: {e}")
        print(f"Error converting PDF to images: {e}")
        return []


def extract_pdf_text(pdf_data: str) -> Optional[str]:
    """
    Extract text from PDF using PyPDF2 as a fallback.
    
    Args:
        pdf_data: Base64 encoded PDF data
        
    Returns:
        Extracted text or None if extraction fails
    """
    if not PYPDF2_SUPPORT:
        return None

    try:
        # Decode base64 PDF data
        pdf_bytes = base64.b64decode(pdf_data)
        pdf_file = io.BytesIO(pdf_bytes)

        # Extract text using PyPDF2
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_content = []

        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            if text.strip():
                text_content.append(f"--- Page {page_num + 1} ---\n{text}")

        return "\n\n".join(text_content) if text_content else None



    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return None


def prepare_file_from_path(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Prepare a file from disk for multimodal processing.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Attachment dictionary with file data
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None

        # Detect content type
        content_type, _ = mimetypes.guess_type(str(path))
        if not content_type:
            content_type = "application/octet-stream"

        # Read file content
        if content_type.startswith("text/") or content_type in ["application/json", "text/csv"]:
            with open(path, "r", encoding="utf-8") as f:
                text_content = f.read()
                return {
                    "filename": path.name,
                    "content_type": content_type,
                    "size": path.stat().st_size,
                    "text": text_content
                }
        else:
            # Binary files - encode as base64
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
                return {
                    "filename": path.name,
                    "content_type": content_type,
                    "size": path.stat().st_size,
                    "data": data
                }

    except Exception as e:
        print(f"Error preparing file {file_path}: {e}")
        return None
