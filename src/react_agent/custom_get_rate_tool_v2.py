import os

import re
import requests
from enum import Enum
from typing import Union, Optional
from bs4 import BeautifulSoup
import logging

# Loan limits for different loan types
CONVENTIONAL_LOAN_LIMITS = [806500, 1032650, 1248150, 1551250]
FHA_LOAN_LIMITS = [629050, 805300, 973400, 1209750]

LOAN_LIMITS = {
    "conventional": CONVENTIONAL_LOAN_LIMITS,
    "fha": FHA_LOAN_LIMITS,
    "jumbo": [float('inf')] * 4,  # No upper limit for jumbo
    "va": [float('inf')] * 4,  # VA loans have no conforming limits
}

VA_FUNDING_FEES = {
    "first_time": {
        "no_down": 0.0215,
        "5_percent_down": 0.015,
        "10_percent_down": 0.0125
    },
    "subsequent": {
        "no_down": 0.033,
        "5_percent_down": 0.0150,
        "10_percent_down": 0.0125
    }
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


def parse_freddie_mac_rates():
    url = os.getenv("FREDDIE_MAC_PMMS_URL", "https://www.freddiemac.com/pmms/pmms_archives")
    response = requests.get(url, timeout=10)

    soup = BeautifulSoup(response.text, 'html.parser')
    tds = soup.find_all("td", class_="large-text-center")
    years_to_rate = {
        "30": 7.0,
        "15": 7.0
    }
    found_rate = {
        "30": False,
        "15": False
    }
    for td in tds:
        text = td.text.strip()
        if "30‑Yr" in td.text.strip() and not found_rate["30"]:
            parts = text.split(" ")
            logging.info(f"Found 30-Year rate: {text}")
            for part in parts:
                if part.endswith("%"):
                    latest_rate = part.strip('%')
                    logging.info(f"Latest 30-Year rate: {latest_rate}")
                    found_rate["30"] = True
                    years_to_rate["30"] = float(latest_rate)
        if "15‑Yr" in td.text.strip() and not found_rate["15"]:
            parts = text.split(" ")
            logging.info(f"Found 15-Year rate: {text}")
            for part in parts:
                if part.endswith("%"):
                    logging.info(f"Found percentage part: {part}")
                    latest_rate = part.strip('%')
                    found_rate["15"] = True
                    years_to_rate["15"] = float(latest_rate)
        if found_rate["30"] and found_rate["15"]:
            logging.info("Both 30-Year and 15-Year rates found, breaking loop.")
            break
    return years_to_rate


def fetch_freddie_mac_rate(loan_type: str, loan_term_years: int) -> float:
    """Fetch current Freddie Mac PMMS rate and add 0.5% margin.
    
    Args:
        loan_type: Type of loan to get rate for
        
    Returns:
        Current rate + 0.5% margin, or fallback rate if fetch fails
    """
    try:
        years_to_rate = parse_freddie_mac_rates()
        latest_rate = years_to_rate.get(str(loan_term_years), None)
        if latest_rate is not None:
            base_rate = float(latest_rate)
            logging.info(f"Freddie Mac rate for {loan_term_years}-Yr: {base_rate}%")
            return base_rate + 0.5  # Add 0.5% margin
        logging.info(f"Freddie Mac rate not found for {loan_term_years}-Yr, using fallback.")

    except Exception as e:
        # Fallback to reasonable rate if API fails
        logging.error(f"Failed to fetch Freddie Mac rate: {e}")

    # Fallback rates by loan type
    fallback_rates = {
        "conventional": 7.5,
        "fha": 7.5,
        "va": 7.5,
        "jumbo": 7.5
    }

    return fallback_rates.get(loan_type, 7.5)


class LoanType(Enum):
    CONVENTIONAL = "conventional"
    FHA = "fha"
    VA = "va"
    JUMBO = "jumbo"


class Occupancy(str, Enum):
    """Property occupancy type enumeration"""
    INVESTMENT_PROPERTY = "InvestmentProperty"
    PRIMARY_RESIDENCE = "PrimaryResidence"
    SECOND_HOME = "SecondHome"


occupancy_display = {
    Occupancy.INVESTMENT_PROPERTY: "Investment Property",
    Occupancy.PRIMARY_RESIDENCE: "Primary Residence",
    Occupancy.SECOND_HOME: "Second Home"
}


class PropertyType(str, Enum):
    """Property type enumeration"""
    SINGLE_FAMILY = "SingleFamily"
    CONDO = "Condo"
    MANUFACTURED_DOUBLE_WIDE = "ManufacturedDoubleWide"
    CONDOTEL = "Condotel"
    MODULAR = "Modular"
    PUD = "PUD"
    TIMESHARE = "Timeshare"
    MANUFACTURED_SINGLE_WIDE = "ManufacturedSingleWide"
    COOP = "Coop"
    NON_WARRANTABLE_CONDO = "NonWarrantableCondo"
    TOWNHOUSE = "Townhouse"
    DETACHED_CONDO = "DetachedCondo"


property_type_display = {
    PropertyType.SINGLE_FAMILY: "Single Family",
    PropertyType.CONDO: "Condo",
    PropertyType.MANUFACTURED_DOUBLE_WIDE: "Manufactured Double Wide",
    PropertyType.CONDOTEL: "Condotel",
    PropertyType.MODULAR: "Modular",
    PropertyType.PUD: "PUD",
    PropertyType.TIMESHARE: "Timeshare",
    PropertyType.MANUFACTURED_SINGLE_WIDE: "Manufactured Single Wide",
    PropertyType.COOP: "Coop",
    PropertyType.NON_WARRANTABLE_CONDO: "Non-Warrantable Condo",
    PropertyType.TOWNHOUSE: "Townhouse",
    PropertyType.DETACHED_CONDO: "Detached Condo",
}


def calculate_va_funding_fee(loan_amount: float, down_payment: float,
                             is_first_time: bool = True, is_exempt: bool = False) -> float:
    """Calculate VA funding fee based on down payment and usage.
    
    Args:
        loan_amount: The loan amount
        down_payment: Down payment amount
        is_first_time: Whether this is first-time VA loan usage
        is_exempt: Whether veteran is exempt from funding fee
        
    Returns:
        Funding fee amount
    """
    if is_exempt:
        return 0.0

    home_price = loan_amount + down_payment
    down_payment_percent = down_payment / home_price if home_price > 0 else 0

    fee_type = "first_time" if is_first_time else "subsequent"

    if down_payment_percent >= 0.10:
        fee_rate = VA_FUNDING_FEES[fee_type]["10_percent_down"]
    elif down_payment_percent >= 0.05:
        fee_rate = VA_FUNDING_FEES[fee_type]["5_percent_down"]
    else:
        fee_rate = VA_FUNDING_FEES[fee_type]["no_down"]

    return loan_amount * fee_rate


def validate_normalize_loan_type(loan_type):
    if isinstance(loan_type, str):
        loan_type_lower = loan_type.lower().strip()
        if loan_type_lower in ['conventional', 'conv', 'conforming']:
            loan_type = LoanType.CONVENTIONAL
        elif loan_type_lower in ['fha']:
            loan_type = LoanType.FHA
        elif loan_type_lower in ['va', 'veteran', 'veterans']:
            loan_type = LoanType.VA
        elif loan_type_lower in ['jumbo']:
            loan_type = LoanType.JUMBO
        else:
            loan_type = LoanType(loan_type)

    else:
        loan_type = LoanType(loan_type)
    return loan_type


def get_rate(
        home_price: Optional[Union[str, int, float]] = None,
        loan_type: Union[LoanType, str] = LoanType.CONVENTIONAL,
        units: int = 1,
        down_payment: Optional[Union[str, int, float]] = None,
        annual_interest_rate: Optional[float] = None,
        loan_term_years: int = 30,
        loan_amount: Optional[Union[str, int, float]] = None,
        annual_property_tax: Optional[Union[str, int, float]] = None,
        annual_home_insurance: Optional[Union[str, int, float]] = None,
        fico_score: int = 760,
        va_first_time: bool = True,
        va_exempt: bool = False,
        ltv: Optional[Union[str, float]] = None,
        occupancy: Optional[Occupancy] = Occupancy.PRIMARY_RESIDENCE,
        property_type: Optional[PropertyType] = PropertyType.SINGLE_FAMILY,
        homeowners_association_fee: int = 0
):
    """Calculate monthly mortgage payments with detailed breakdown. This is my primary tool for helping real estate professionals get instant payment quotes with current market rates.
    
    Args:
        home_price: The purchase price of the home. Accepts various formats like "$500,000", "500k", "500 thousand".
        loan_type: The type of loan: 'conventional', 'fha', 'va', 'jumbo'. Defaults to 'conventional'.
        units: The number of units in the property. Defaults to 1.
        down_payment: The down payment amount. Accepts formats like "20,000", "20k", "20 grand".
        annual_interest_rate: The annual interest rate as a percentage. If not provided, fetches current Freddie Mac rate + 0.5%.
        loan_term_years: The term of the loan in years. Defaults to 30 years.
        loan_amount: The amount of the loan. Accepts various formats.
        annual_property_tax: The annual property tax amount.
        annual_home_insurance: The annual home insurance amount.
        fico_score: The FICO score of the borrower. Defaults to 760.
        va_first_time: For VA loans, whether this is first-time usage. Defaults to True.
        va_exempt: For VA loans, whether veteran is exempt from funding fee. Defaults to False.
        ltv: Loan-to-value ratio. Can be used instead of down payment.
        occupancy: Property occupancy type. Defaults to Primary Residence.
        property_type: Property type. Defaults to Single Family.
        homeowners_association_fee: Monthly HOA (Homeowners Association Fee) fee. Defaults to 0.
    """

    # Parse input values with error handling
    try:
        if home_price is not None:
            home_price = parse_currency_amount(home_price)
        if loan_amount is not None:
            loan_amount = parse_currency_amount(loan_amount)

        # Handle down payment - could be percentage or dollar amount
        down_payment_is_percentage = False
        if down_payment is not None:
            if isinstance(down_payment, str) and '%' in down_payment:
                down_payment_is_percentage = True
            down_payment = parse_currency_amount(down_payment)
            # If it's a percentage and home_price is known, convert to dollar amount
            if down_payment_is_percentage and home_price is not None:
                down_payment = home_price * down_payment

        if annual_property_tax is not None:
            annual_property_tax = parse_currency_amount(annual_property_tax)
        if annual_home_insurance is not None:
            annual_home_insurance = parse_currency_amount(annual_home_insurance)
        if ltv is not None:
            ltv = parse_currency_amount(ltv) if isinstance(ltv, str) else float(ltv)
    except ValueError as e:
        return {
            "error": f"Invalid input format: {str(e)}. Please provide numbers in formats like '500000', '$500,000', '500k', '20%', or '500 thousand'."
        }

    if home_price is None and loan_amount is None:
        return {
            "error": "Either home_price or loan_amount must be provided."
        }

    # Validate and normalize loan type
    if not isinstance(loan_type, LoanType):
        try:
            loan_type = validate_normalize_loan_type(loan_type)
        except ValueError:
            return {
                "error": "Invalid loan type. Must be 'conventional', 'fha', 'va', 'jumbo'"
            }

    # Determine home price if not provided
    if home_price is None:
        if down_payment is None:
            down_payment = loan_amount * 0.25  # Assume 20% down if not specified
        home_price = loan_amount + down_payment

    # Handle LTV input
    if ltv is not None:
        if ltv > 1:
            ltv = ltv / 100  # Convert percentage to decimal
        loan_amount = home_price * ltv
        down_payment = home_price - loan_amount

    # Set loan-type specific defaults
    if down_payment is None:
        if loan_type == LoanType.FHA:
            down_payment = home_price * 0.035  # 3.5% for FHA
        elif loan_type == LoanType.VA:
            down_payment = 0  # VA allows 0% down
        else:
            down_payment = home_price * 0.20  # 20% for conventional/jumbo

    # Calculate loan amount
    if loan_amount is None:
        loan_amount = home_price - down_payment

    # Determine if loan should be jumbo
    if loan_type == LoanType.CONVENTIONAL and loan_amount > LOAN_LIMITS["conventional"][units - 1]:
        loan_type = LoanType.JUMBO

    # Validate loan limits
    if loan_type in [LoanType.CONVENTIONAL, LoanType.FHA]:
        if loan_amount > LOAN_LIMITS[loan_type.value][units - 1]:
            return {
                "error": f"Loan amount ${loan_amount:,.2f} exceeds {loan_type.value} limit of ${LOAN_LIMITS[loan_type.value][units - 1]:,.2f} for {units} unit(s)."
            }

    # Calculate LTV
    calculated_ltv = loan_amount / home_price if home_price > 0 else 0

    # Validate LTV limits
    if loan_type == LoanType.CONVENTIONAL and calculated_ltv > 0.95:
        if calculated_ltv > 0.965:
            return {
                "error": f"LTV of {calculated_ltv:.1%} exceeds conventional loan limit of 95%. Consider FHA loan."
            }
        else:
            loan_type = LoanType.FHA
    elif loan_type == LoanType.FHA and calculated_ltv > 0.965:
        return {
            "error": f"LTV of {calculated_ltv:.1%} exceeds FHA loan limit of 96.5%."
        }

    # Get interest rate
    if annual_interest_rate is None:
        annual_interest_rate = fetch_freddie_mac_rate(loan_type.value, loan_term_years)

    # Handle FHA upfront MIP
    fha_upfront_mip = 0
    if loan_type == LoanType.FHA:
        base_loan_amount = loan_amount
        fha_upfront_mip = base_loan_amount * 0.0175  # 1.75% upfront MIP
        loan_amount = base_loan_amount + fha_upfront_mip  # Add upfront MIP to loan amount

    # Handle VA funding fee
    va_funding_fee = 0
    if loan_type == LoanType.VA:
        va_funding_fee = calculate_va_funding_fee(loan_amount, down_payment, va_first_time, va_exempt)
        loan_amount += va_funding_fee  # Add funding fee to loan amount

    # Set default property tax and insurance
    if annual_property_tax is None:
        annual_property_tax = home_price * 0.0065  # 0.65% default
    if annual_home_insurance is None:
        annual_home_insurance = home_price * 0.002  # 0.2% default

    # Calculate monthly payment components
    monthly_interest_rate = annual_interest_rate / 12 / 100
    total_payments = loan_term_years * 12

    # Monthly principal and interest
    if monthly_interest_rate > 0:
        monthly_principal_interest = (
                loan_amount *
                (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments)
                / ((1 + monthly_interest_rate) ** total_payments - 1)
        )
    else:
        monthly_principal_interest = loan_amount / total_payments

    # Calculate mortgage insurance
    monthly_mi = 0.0
    if loan_type == LoanType.CONVENTIONAL and calculated_ltv > 0.80:
        # PMI for conventional loans over 80% LTV
        monthly_mi = (loan_amount * 0.005) / 12  # 0.5% annually
    elif loan_type == LoanType.FHA:
        # Monthly MIP for FHA loans (0.55% annually)
        monthly_mi = (loan_amount * 0.0055) / 12

    # Monthly property tax and insurance
    monthly_tax = annual_property_tax / 12
    monthly_insurance = annual_home_insurance / 12

    # Total monthly payment
    total_monthly_payment = (
            monthly_principal_interest + monthly_tax + monthly_insurance + monthly_mi
    )

    # Calculate property tax rate
    property_tax_rate = (annual_property_tax / home_price) * 100 if home_price > 0 else 0

    # Prepare loan type display name
    loan_type_display = {
        LoanType.CONVENTIONAL: "Conventional",
        LoanType.FHA: "FHA",
        LoanType.VA: "VA",
        LoanType.JUMBO: "Jumbo",
    }[loan_type]

    result = f"""
<rate-calculation>
    <payment>${round(total_monthly_payment, 2):,}</payment>
    
    <breakdown>
        Principal & Interest: ${round(monthly_principal_interest, 2):,}
        Property Taxes: ${round(monthly_tax, 2):,} (${round(annual_property_tax, 2):,} annually at {property_tax_rate:.2f}%)
        Insurance: ${round(monthly_insurance, 2):,} (${round(annual_home_insurance, 2):,} annually)
        """

    if homeowners_association_fee and homeowners_association_fee > 0:
        result += f"\n        HOA Fees: ${round(homeowners_association_fee, 2):,}"

    if monthly_mi > 0:
        mi_type = "PMI" if loan_type == LoanType.CONVENTIONAL else "MIP"
        result += f"\n        {mi_type}: ${round(monthly_mi, 2):,}"

    va_text = ""
    if loan_type == LoanType.VA:
        va_text += f"VA Funding Fee: ${round(va_funding_fee, 2):,} ({'First-time' if va_first_time else 'Subsequent'} use)"
        if va_exempt:
            va_text += " - EXEMPT"

    result += f"""
    </breakdown>
    
    <loan-details>
        Purchase Price: ${round(home_price, 2):,}
        Down Payment: ${round(down_payment, 2):,} ({(down_payment / home_price) * 100:.1f}%)
        Loan Amount: ${round(loan_amount, 2):,}
        Loan-to-Value (LTV): {calculated_ltv:.1%}
        Interest Rate: {round(annual_interest_rate, 3)}%
        {va_text if loan_type == LoanType.VA else ""}
        Loan Type: {loan_type_display}
        Loan Term: {loan_term_years} years
    </loan-details>
    
    <assumptions>
        • Credit Score (FICO): {fico_score}
        • Occupancy: {occupancy_display[occupancy] if occupancy else "Primary Residence"}
        • Property Type: {property_type_display[property_type] if property_type else "Single Family"}
        • Units: {units}"""

    if loan_type == LoanType.FHA and fha_upfront_mip > 0:
        result += f"\n        • FHA Upfront MIP: ${round(fha_upfront_mip, 2):,} (financed)"

    result += """
    </assumptions>
    """
    if units is not 1 or occupancy is not Occupancy.PRIMARY_RESIDENCE or property_type is not PropertyType.SINGLE_FAMILY:
        result += """<disclaimer> This rate and payment estimate is generated using AI and is intended for illustrative purposes only.
        It does not constitute a loan offer, pre-qualification, or commitment to lend. The estimated rate is based on the
        Freddie Mac Primary Mortgage Market Survey® (PMMS®) average for the applicable loan type during the week of the
        request, plus an assumed margin of 0.50%. Actual rates and terms may vary based on a variety of factors,
        including credit profile, property type, loan amount, down payment, and market conditions. All borrowers must
        complete a full loan application and receive official loan disclosures before relying on any figures for
        decision-making. Please contact a licensed loan officer for a personalized quote and full details visiting
        the LoanX IOS application https://apps.apple.com/us/app/loanx-ai/id6743818733
        </disclaimer>
        """

    result += """
        </rate-calculation>
    """

    return result
