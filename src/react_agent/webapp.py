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
SMS_GENERATION_PROMPT = """You are a real estate agent. Write a concise SMS to facilitate a connection between a loan officer(s) and a buyer(s) about a property. Use a friendly, professional tone, and include the price, down payment, loan amount, and monthly payment if available. Address both parties by name and make it clear the loan officer(s) should reach out to the buyer(s).

Do NOT include:
- Sign-offs like "Best," "Regards," "Sincerely," "Thanks," etc.
- Placeholder text in brackets like [Your Name], [Agent Name], etc.
- Email signatures or closings

This is an SMS text message. End the message naturally after conveying the information.

Example:
Hey Mike, please connect with John about a property. These are the rough numbers — Price $500k, Down 20%, Loan $300k, Monthly Payment $2,937. They're ready to talk rates.

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
    return {"status": "healthy", "service": "real-estate-ai-agent", "custom_routes": True}


@app.post("/custom/generate-sms")
async def generate_sms(request: Request):
    """
    Generate an SMS message to connect buyers with loan officers about a property.

    Expects JSON body with:
    - buyers: String (e.g., "John") or list of objects with 'name' field (e.g., [{"name": "John"}])
    - loan_officers: String (e.g., "Mike") or list of objects with 'name' field (e.g., [{"name": "Mike"}])
    - price: Property price string (e.g., "1000", "$1,000", "1k")
    - down_payment: Down payment amount string (e.g., "30000", "$30,000")
    - loan_amount: Loan amount string (e.g., "300000", "$300,000", "300 000")
    - monthly_payment: Monthly payment string (e.g., "3000", "$3,000")
    """
    try:
        # Parse request body as dict to avoid Pydantic issues
        body: Dict[str, Any] = await request.json()

        # Validate required fields
        required_fields = ["buyers", "loan_officers", "price", "down_payment", "loan_amount", "monthly_payment"]
        missing_fields = [field for field in required_fields if field not in body]
        if missing_fields:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )

        # Extract data - handle both string and list formats
        buyers = body.get("buyers", [])
        loan_officers = body.get("loan_officers", [])

        if not buyers or not loan_officers:
            raise HTTPException(
                status_code=422,
                detail="At least one buyer and one loan officer required"
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
        model_name = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        llm = ChatOpenAI(model=model_name)

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
        response = await llm.ainvoke(formatted_prompt)
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


@app.get("/custom/info")
async def custom_info():
    """Information about custom routes."""
    return {
        "service": "Real Estate AI Agent - Custom Routes",
        "version": "1.0.0",
        "endpoints": {
            "health": "/custom/health (GET)",
            "generate_sms": "/custom/generate-sms (POST)",
            "info": "/custom/info (GET)"
        }
    }
