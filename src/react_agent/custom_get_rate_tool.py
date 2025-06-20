import re
from enum import Enum
from typing import Union

# https://singlefamily.fanniemae.com/originating-underwriting/loan-limits
CONVENTIONAL_LOAN_LIMITS = [806500, 1032650, 1248150, 1551250]

# https://www.fha.com/lending_limits_state?state=UTAH
FHA_LOAN_LIMITS = [629050, 805300, 973400, 1209750]

LOAN_LIMITS = {
    "conventional": CONVENTIONAL_LOAN_LIMITS,
    "fha": FHA_LOAN_LIMITS
}


def parse_currency_amount(value: Union[str, int, float]) -> float:
    """Parse various currency input formats into a float.
    
    Handles formats like:
    - 20000, 20,000, $20,000
    - "20k", "20K", "20 thousand"
    - "20 grand", "20 down"
    - Percentages like "20%" (returns as decimal)
    """
    if isinstance(value, (int, float)):
        return float(value)
    
    if not isinstance(value, str):
        raise ValueError(f"Cannot parse currency amount from {type(value)}")
    
    # Clean up the string
    value = value.strip().lower()
    
    # Handle percentage inputs
    if '%' in value:
        num = re.findall(r'[\d.]+', value)[0] if re.findall(r'[\d.]+', value) else '0'
        return float(num) / 100.0
    
    # Remove common currency symbols and words
    value = re.sub(r'[$,]', '', value)
    value = re.sub(r'\b(dollars?|bucks?|down|payment)\b', '', value)
    
    # Handle shorthand notations
    multiplier = 1
    if re.search(r'\b(k|thousand|grand)\b', value):
        multiplier = 1000
        value = re.sub(r'\b(k|thousand|grand)\b', '', value)
    elif re.search(r'\b(m|million|mil)\b', value):
        multiplier = 1000000
        value = re.sub(r'\b(m|million|mil)\b', '', value)
    
    # Handle case where suffixes are directly attached to numbers (e.g., "20k", "1.5m")
    k_match = re.search(r'(\d+(?:\.\d+)?)k\b', value)
    if k_match:
        return float(k_match.group(1)) * 1000
    
    m_match = re.search(r'(\d+(?:\.\d+)?)m\b', value)
    if m_match:
        return float(m_match.group(1)) * 1000000
    
    # Extract the numeric part
    numbers = re.findall(r'[\d.]+', value.strip())
    if not numbers:
        raise ValueError(f"No numeric value found in: {value}")
    
    return float(numbers[0]) * multiplier


class LoanType(Enum):
    CONVENTIONAL = "conventional"
    FHA = "fha"


def get_rate(
        home_price=None,
        loan_type=LoanType.CONVENTIONAL,
        units=1,
        down_payment=None,
        annual_interest_rate=7.5,
        loan_term_years=30,
        loan_amount=None,
        annual_property_tax=None,
        annual_home_insurance=None,
        fico_score=760
):
    """Calculate monthly mortgage payments with detailed breakdown. This is my primary tool for helping real estate professionals get instant rate quotes. I can handle flexible input formats and provide comprehensive payment analysis.
    
    Args:
        home_price (Union[str, int, float]): The price of the home. Accepts various formats like "$500,000", "500k", "500 thousand".
        loan_type (LoanType): The type of loan, either 'conventional' or 'fha'. Defaults to 'conventional'.
        units (int): The number of units in the property. Defaults to 1.
        down_payment (Union[str, int, float]): The down payment amount. Accepts formats like "20,000", "20k", "20 grand".
        annual_interest_rate (float): The annual interest rate as a percentage. Defaults to 7.5%.
        loan_term_years (int): The term of the loan in years. Defaults to 30 years.
        loan_amount (Union[str, int, float]): The amount of the loan. Accepts various formats.
        annual_property_tax (Union[str, int, float]): The annual property tax amount.
        annual_home_insurance (Union[str, int, float]): The annual home insurance amount.
        fico_score (int): The FICO score of the borrower. Defaults to 760.
    """

    # Parse input values with error handling
    try:
        if home_price is not None:
            home_price = parse_currency_amount(home_price)
        if loan_amount is not None:
            loan_amount = parse_currency_amount(loan_amount)
        if down_payment is not None:
            down_payment = parse_currency_amount(down_payment)
        if annual_property_tax is not None:
            annual_property_tax = parse_currency_amount(annual_property_tax)
        if annual_home_insurance is not None:
            annual_home_insurance = parse_currency_amount(annual_home_insurance)
    except ValueError as e:
        return {
            "error": f"Invalid input format: {str(e)}. Please provide numbers in formats like '500000', '$500,000', '500k', or '500 thousand'."
        }

    if home_price is None and loan_amount is None:
        return {
            "error": "Either home_price or loan_amount must be provided."
        }

    # Validate and normalize loan type
    if not isinstance(loan_type, LoanType):
        try:
            # Handle string inputs with flexible matching
            if isinstance(loan_type, str):
                loan_type_lower = loan_type.lower().strip()
                if loan_type_lower in ['conventional', 'conv', 'conforming']:
                    loan_type = LoanType.CONVENTIONAL
                elif loan_type_lower in ['fha']:
                    loan_type = LoanType.FHA
                else:
                    loan_type = LoanType(loan_type)
            else:
                loan_type = LoanType(loan_type)
        except ValueError:
            return {
                "error": "Invalid loan type. Must be 'conventional' or 'fha'."
            }

    if home_price is None:
        home_price = loan_amount + (loan_amount * 0.2)

    # Set default down payment (20% of home price) if not provided
    if down_payment is None:
        down_payment = home_price * 0.2

    # Set default property tax (0.65% of home price) if not provided
    if annual_property_tax is None:
        annual_property_tax = home_price * 0.0065
    # Ensure annual_property_tax is at least 0.65% of home price

    # Set default home insurance (0.2% of home price) if not provided
    if annual_home_insurance is None:
        annual_home_insurance = home_price * 0.002

    # Calculate loan amount and LTV
    loan_amount = home_price - down_payment

    if loan_amount > LOAN_LIMITS[loan_type.value][units - 1]:
        return {
            "error": "Loan amount exceeds limit for the selected loan type and unit count."
        }

    ltv = loan_amount / home_price

    if ltv > 0.95 and loan_type == LoanType.CONVENTIONAL:
        return {
            "error": "Loan-to-value ratio exceeds 95%. Conventional loans require a maximum LTV of 95%."
        }

    monthly_interest_rate = annual_interest_rate / 12 / 100
    total_payments = loan_term_years * 12

    # Monthly principal and interest using amortization formula
    if monthly_interest_rate > 0:
        monthly_principal_interest = (
                loan_amount *
                (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments)
                / ((1 + monthly_interest_rate) ** total_payments - 1)
        )
    else:
        monthly_principal_interest = loan_amount / total_payments

    # MIP (Mortgage Insurance Premium) is required for FHA loans, but not for conventional loans
    mip = 0.0

    if loan_type == LoanType.FHA:
        # For FHA loans, MIP is typically 0.85% annually
        mip = (loan_amount * 0.0085) / 12

    # Monthly property tax and insurance
    monthly_tax = annual_property_tax / 12
    monthly_insurance = annual_home_insurance / 12

    # Total monthly payment
    total_monthly_payment = (
            monthly_principal_interest + monthly_tax + monthly_insurance + mip
    )

    return f"""
        <rate-calculation>
            <rate>{round(annual_interest_rate, 3)}%</rate>
            <payment>${round(total_monthly_payment, 2)}</payment>
        
            <breakdown>
                Principal & Interest: ${round(monthly_principal_interest, 2)}
                Property Taxes: ${round(monthly_tax, 2)}
                Insurance: ${round(monthly_insurance, 2)}
                Mortgage Insurance Premium: ${round(mip, 2)}
            </breakdown>
        
            <assumptions>
            • Credit Score (FICO Score): ${fico_score}
            • Down Payment: ${round(down_payment, 2)}
            • Loan Type: {loan_type.value == LoanType.CONVENTIONAL.value and "Conventional" or "FHA"}
            • Property Type: Primary Residence
            • Loan Amount: ${round(loan_amount, 2)}
            </assumptions>
        </rate-calculation>
    """
