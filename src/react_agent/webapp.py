"""Custom FastAPI routes for LangGraph agent."""

from __future__ import annotations

import os
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from langchain_openai import ChatOpenAI

# Create FastAPI app
app = FastAPI(
    title="Real Estate AI Agent API",
    version="1.0.0",
    # Disable automatic OpenAPI schema generation to avoid conflicts
    openapi_url=None,
    docs_url=None,
    redoc_url=None
)


# System prompt for SMS generation
SMS_GENERATION_PROMPT = """You are a friendly connector helping introduce a loan officer to a potential buyer. Write a casual,
conversational SMS that facilitates the introduction in a natural way. Focus on making a warm connection rather than
listing specifications. Use the financial details to provide context, but present them naturally and conversationally
(e.g., "around the $500K range" or "checking out a place for about $500K").

Do NOT include:
- Sign-offs like "Best," "Regards," "Sincerely," "Thanks," etc.
- Placeholder text in brackets like [Your Name], [Agent Name], etc.
- Email signatures or closings
- Formal business language or overly structured formatting

This is a casual SMS introduction. Keep it friendly and conversational, like you're connecting two people you know.

Example: Hey Mike, wanted to connect you with John — they're checking out a place around the $500K range and could use
your input on loan options. Figured I'd make the intro so you two can chat directly.

Now, write the message using the details below:
- Buyer(s): {buyers}
- Loan Officer(s): {loan_officers}
- Price: {price}
- Down Payment: {down_payment}
- Loan Amount: {loan_amount}
- Monthly Payment: {monthly_payment}"""


@app.get("/custom/health")
async def health_check():
    """Health check endpoint for custom routes."""
    return {"status": "working", "service": "real-estate-ai-agent", "custom_routes": True}


@app.post("/custom/generate-sms")
async def generate_sms(request: Request):
    """
    Generate an SMS message to connect buyers with loan officers about a property.

    Expects JSON body with:
    - buyers: (Optional) String (e.g., "John") or list of objects with 'name' field (e.g., [{"name": "John"}])
    - loan_officers: (Optional) String (e.g., "Mike") or list of objects with 'name' field (e.g., [{"name": "Mike"}])
    - price: Property price string (e.g., "1000", "$1,000", "1k")
    - down_payment: Down payment amount string (e.g., "30000", "$30,000")
    - loan_amount: Loan amount string (e.g., "300000", "$300,000", "300 000")
    - monthly_payment: Monthly payment string (e.g., "3000", "$3,000")
    """
    try:
        # Parse request body as dict to avoid Pydantic issues
        body: Dict[str, Any] = await request.json()

        # Validate required fields (buyers and loan_officers are now optional)
        required_fields = ["price", "down_payment", "loan_amount", "monthly_payment"]
        missing_fields = [field for field in required_fields if field not in body]
        if missing_fields:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )

        # Extract data - handle both string and list formats, default to empty if not provided
        buyers = body.get("buyers", "")
        loan_officers = body.get("loan_officers", "")

        # Require at least one of buyers or loan_officers to be present
        if not buyers and not loan_officers:
            raise HTTPException(
                status_code=422,
                detail="At least one buyer or one loan officer is required"
            )

        # Format names - handle both string and list of objects
        if isinstance(buyers, str):
            buyers_str = buyers
        elif isinstance(buyers, list):
            buyers_str = ", ".join([
                buyer.get("name", "") if isinstance(buyer, dict) else str(buyer)
                for buyer in buyers
                if buyer
            ])
        else:
            buyers_str = str(buyers)

        if isinstance(loan_officers, str):
            loan_officers_str = loan_officers
        elif isinstance(loan_officers, list):
            loan_officers_str = ", ".join([
                lo.get("name", "") if isinstance(lo, dict) else str(lo)
                for lo in loan_officers
                if lo
            ])
        else:
            loan_officers_str = str(loan_officers)

        # Initialize OpenAI model
        model_name = os.getenv("OPENAI_MODEL", "gpt-4.1")
        llm = ChatOpenAI(
            model=model_name,
            temperature=0.9
        )

        # Format the prompt
        formatted_prompt = SMS_GENERATION_PROMPT.format(
            buyers=buyers_str,
            loan_officers=loan_officers_str,
            price=body["price"],
            down_payment=body["down_payment"],
            loan_amount=body["loan_amount"],
            monthly_payment=body["monthly_payment"]
        )

        # Generate the SMS message
        response = await llm.ainvoke(formatted_prompt, temperature=0.9)
        sms_message = response.content.strip()

        return {
            "message": sms_message,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate SMS: {str(e)}"
        )
