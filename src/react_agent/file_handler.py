"""Handle file processing for multimodal AI models."""

import base64
import mimetypes
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import tempfile
import os
import io
import re
import logging

# Set up logging
logger = logging.getLogger(__name__)

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


def is_real_estate_document(filename: str, content: str = "") -> Tuple[bool, str]:
    """
    Detect if a document is real estate related and identify its type.
    
    Args:
        filename: Name of the file
        content: Text content of the file (if available)
        
    Returns:
        Tuple of (is_real_estate_doc, document_type)
    """
    filename_lower = filename.lower()
    content_lower = content.lower() if content else ""
    
    # Common real estate document patterns
    doc_patterns = {
        "listing": ["listing", "mls", "property listing", "for sale"],
        "purchase_agreement": ["purchase agreement", "sales contract", "offer to purchase", "purchase and sale"],
        "loan_estimate": ["loan estimate", "le ", "closing disclosure", "cd "],
        "appraisal": ["appraisal", "property valuation", "appraised value"],
        "inspection": ["inspection report", "property inspection", "home inspection"],
        "title": ["title report", "title insurance", "preliminary title"],
        "disclosure": ["disclosure", "property disclosure", "seller disclosure"],
        "hoa": ["hoa", "homeowners association", "condo association"],
        "lease": ["lease agreement", "rental agreement", "lease contract"],
        "mortgage": ["mortgage", "deed of trust", "promissory note"]
    }
    
    # Check filename and content for patterns
    for doc_type, patterns in doc_patterns.items():
        for pattern in patterns:
            if pattern in filename_lower or (content and pattern in content_lower):
                return True, doc_type
    
    # Check for real estate keywords in content
    if content:
        re_keywords = ["property", "real estate", "square feet", "bedrooms", "bathrooms", 
                      "listing price", "purchase price", "closing date", "escrow"]
        keyword_count = sum(1 for keyword in re_keywords if keyword in content_lower)
        if keyword_count >= 3:
            return True, "real_estate_document"
    
    return False, ""


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
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{attachment.get('data', '')}"
                }
            })
            
        elif content_type == "application/pdf":
            # Log attachment info
            logger.info(f"Processing PDF attachment: {filename}")
            pdf_data = attachment.get('data', '')
            
            if not pdf_data:
                logger.error(f"No data found for PDF attachment: {filename}")
                content_blocks.append({
                    "type": "text",
                    "text": f"=== PDF ERROR: {filename} - No data provided ===\n\nThe PDF file appears to be empty or data was not transmitted correctly."
                })
            else:
                # PDFs need to be converted to images for GPT-4
                pdf_images = convert_pdf_to_images(pdf_data)
                
                if pdf_images:
                    # Add each page as an image
                    for i, img_base64 in enumerate(pdf_images):
                        content_blocks.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
                            }
                        })
                    # Add a text note about the PDF
                    # Check if filename suggests real estate document
                    is_re_doc, doc_type = is_real_estate_document(filename)
                    if is_re_doc:
                        content_blocks.append({
                            "type": "text",
                            "text": f"=== {doc_type.replace('_', ' ').title().upper()} PDF: {filename} ({len(pdf_images)} pages) ===\n\nAnalyze the real estate document shown in the images above and provide a structured summary including:\n• Document type and purpose\n• Key property details (address, price, type, size)\n• Financial information (loan amounts, payments, rates)\n• Important dates and deadlines\n• Critical terms or action items for the agent"
                        })
                    else:
                        content_blocks.append({
                            "type": "text",
                            "text": f"=== PDF: {filename} ({len(pdf_images)} pages shown above) ==="
                        })
                else:
                    # Try text extraction as fallback
                    logger.info("PDF image conversion failed, attempting text extraction")
                    extracted_text = extract_pdf_text(pdf_data)
                    
                    if extracted_text:
                        # We got text, use it
                        is_re_doc, doc_type = is_real_estate_document(filename, extracted_text)
                        
                        if is_re_doc:
                            content_blocks.append({
                                "type": "text",
                                "text": f"=== {doc_type.replace('_', ' ').title().upper()} PDF: {filename} (TEXT ONLY) ===\n\nNote: PDF visual elements could not be processed. Showing extracted text only.\n\n{extracted_text}\n\n---\nAnalyze this real estate document and provide a structured summary including:\n• Document type and purpose\n• Key property details (address, price, type, size)\n• Financial information (loan amounts, payments, rates)\n• Important dates and deadlines\n• Critical terms or action items for the agent"
                            })
                        else:
                            content_blocks.append({
                                "type": "text",
                                "text": f"=== PDF: {filename} (TEXT ONLY) ===\n\nNote: PDF visual elements could not be processed. Showing extracted text only.\n\n{extracted_text}"
                            })
                    else:
                        # Provide detailed error information
                        error_msg = f"=== PDF ERROR: {filename} ===\n\n"
                        if not PDF_SUPPORT and not PYPDF2_SUPPORT:
                            error_msg += "PDF processing is not available. Neither pypdfium2 nor PyPDF2 are installed.\n"
                            error_msg += "Please install one of them with:\n"
                            error_msg += "• pip install pypdfium2 (recommended for image conversion)\n"
                            error_msg += "• pip install PyPDF2 (for text extraction)\n\n"
                        else:
                            error_msg += "Unable to process PDF. Possible reasons:\n"
                            error_msg += "• The PDF data may be corrupted or invalid\n"
                            error_msg += "• The base64 encoding may be incorrect\n"
                            error_msg += "• The PDF may be password protected\n"
                            error_msg += "• The PDF may contain only images without text\n\n"
                        
                        error_msg += f"File size: {attachment.get('size', 'unknown')} bytes\n"
                        error_msg += "Please check the logs for more detailed error information."
                        
                        content_blocks.append({
                            "type": "text",
                            "text": error_msg
                        })
            
        elif content_type.startswith("text/") or content_type in ["application/json", "text/csv"]:
            # Text files can be included directly
            text_content = attachment.get("text", "")
            if not text_content and attachment.get("data"):
                # Decode base64 if text wasn't provided
                try:
                    text_content = base64.b64decode(attachment["data"]).decode("utf-8")
                except Exception:
                    text_content = f"[Unable to decode {filename}]"
                    
            # Check if it's a real estate document
            is_re_doc, doc_type = is_real_estate_document(filename, text_content)
            
            if is_re_doc:
                content_blocks.append({
                    "type": "text", 
                    "text": f"=== {doc_type.replace('_', ' ').title().upper()}: {filename} ===\n\n{text_content}\n\n---\nAnalyze this real estate document above and provide a structured summary including:\n• Document type and purpose\n• Key property details (address, price, type, size)\n• Financial information (loan amounts, payments, rates)\n• Important dates and deadlines\n• Critical terms or action items for the agent"
                })
            else:
                content_blocks.append({
                    "type": "text", 
                    "text": f"=== FILE: {filename} ===\n\n{text_content}"
                })
            
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


def convert_pdf_to_images(pdf_data: str, max_pages: int = 5) -> List[str]:
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
                
                # Render page at 150 DPI (scale = 150/72)
                scale = 150 / 72
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