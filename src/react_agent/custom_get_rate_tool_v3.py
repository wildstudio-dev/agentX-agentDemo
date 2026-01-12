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
        loan_term_years: Term of the loan in years

    Returns:
        Current rate + 0.5% margin, or fallback rate if fetch fails
    """
    try:
        # If exact term not found, use the closest available term (15 or 30 years)
        # Terms closer to 15 (like 5, 10) use 15-year rate
        # Terms closer to 30 (like 20, 40, 50) use 30-year rate
        if loan_term_years < 20:
            closest_term = "15"
        else:
            closest_term = "30"
        logging.info(f"Closest Term {closest_term}")
        # Freddie mac has only 15 and 30 years
        years_to_rate = parse_freddie_mac_rates()
        latest_rate = years_to_rate.get(closest_term, None)
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


class SecondLienType(str, Enum):
    """Second lien payment type enumeration"""
    FULLY_AMORTIZED = "fully_amortized"
    INTEREST_ONLY = "interest_only"


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


def get_conventional_mi_rate(ltv) -> float:
    if ltv <= 0.80:
        return 0
    if ltv <= 0.85:
        return 0.0012
    elif ltv <= 0.90:
        return 0.0021
    elif ltv <= 0.95:
        return 0.0030
    elif ltv <= 0.97:
        return 0.0043
    else:
        # not proper but prefer not to block the logic
        return 0.0050


def get_fha_mi_rate(ltv, term, loan_amount) -> float:
    if term > 15:
        if loan_amount <= 726200:
            if ltv <= 0.95:
                return 0.005
            else:
                return 0.0055
        else:
            if ltv <= 0.95:
                return 0.007
            else:
                return 0.0075
    else:
        if loan_amount <= 726200:
            if ltv <= 0.90:
                return 0.0015
            else:
                return 0.004
        else:
            if ltv <= 0.78:
                return 0.0015
            elif 0.78 < ltv <= 0.90:
                return 0.004
            else:
                return 0.0065


def calculate_monthly_premium(interest, orig_mtg, p_i, upfront, mip, term_years=30):
    """Calculate monthly mortgage insurance premium using Encompass methodology.

    Per Encompass:
    1. MI is based off the base loan amount (without UFMIP)
    2. Calculate payment using base loan amount (not loan amount with UFMIP)
    3. Simulate paydown for 11 months (months 1-11)
    4. Take 12-month average (starting balance + 11 month-end balances)
    5. Calculate monthly MI = (avg_balance * mi_rate) / 12
    6. Round to 2 decimals at each step

    Args:
        interest: Annual interest rate (percentage, e.g., 6.5)
        orig_mtg: Base loan amount (without UFMIP)
        p_i: Monthly principal and interest payment (UNUSED - calculated from base loan amount)
        upfront: Upfront MIP factor (e.g., 0.0175 for 1.75%)
        mip: Annual MIP factor (e.g., 0.0055 for 0.55%)
        term_years: Loan term in years (default 30)

    Returns:
        Monthly mortgage insurance premium
    """
    try:
        logging.info(f"Calculating monthly premium using Encompass methodology for base loan ${orig_mtg:,.2f}...")

        # Calculate payment based on base loan amount (not including UFMIP)
        # This is critical - we use the base loan amount for both balance AND payment calculation
        monthly_rate = interest / 100 / 12
        term_months = term_years * 12

        if monthly_rate > 0:
            payment = (
                orig_mtg *
                (monthly_rate * (1 + monthly_rate) ** term_months)
                / ((1 + monthly_rate) ** term_months - 1)
            )
        else:
            payment = orig_mtg / term_months

        payment = round(payment, 2)
        logging.info(f"Payment for MI calculation (based on base loan): ${payment}")

        # Start with month 0 balance (base loan amount)
        balance = round(orig_mtg, 2)
        total_balance = balance  # Initialize with month 0 balance

        # Simulate 11 months of paydown (months 1-11)
        for month in range(1, 12):
            # Calculate interest for this month (rounded to 2 decimals)
            interest_payment = round(balance * monthly_rate, 2)

            # Calculate principal (rounded to 2 decimals)
            principal_payment = round(payment - interest_payment, 2)

            # Update balance (rounded to 2 decimals)
            balance = round(balance - principal_payment, 2)

            # Add to running total for average calculation
            total_balance += balance

            logging.debug(f"Month {month}: Interest=${interest_payment}, Principal=${principal_payment}, Balance=${balance}")

        # Calculate 12-month average (month 0 + months 1-11)
        avg_balance = round(total_balance / 12, 2)
        logging.info(f"12-month average balance: ${avg_balance:,.2f}")

        # Calculate monthly MI: (average balance * annual MI rate) / 12
        monthly_mi = round((avg_balance * mip) / 12, 2)

        logging.info(f"Monthly MI calculated: ${monthly_mi} (using {mip * 100:.2f}% annual rate)")
        return monthly_mi
    except Exception as e:
        logging.error(f"Error calculating monthly premium: {e}")
        return round((orig_mtg * mip) / 12, 2)  # Fallback calculation


def calculate_monthly_pi_payment(loan_amount: float, annual_rate: float, term_years: int) -> float:
    """Calculate monthly principal and interest payment.

    Args:
        loan_amount: The loan amount
        annual_rate: Annual interest rate as percentage
        term_years: Loan term in years

    Returns:
        Monthly P&I payment amount
    """
    monthly_rate = annual_rate / 12 / 100
    total_payments = term_years * 12

    if monthly_rate > 0:
        return (
            loan_amount *
            (monthly_rate * (1 + monthly_rate) ** total_payments)
            / ((1 + monthly_rate) ** total_payments - 1)
        )
    else:
        return loan_amount / total_payments


def calculate_buydown_scenarios(loan_amount: float, base_rate: float, term_years: int) -> dict:
    """Calculate temporary buydown scenarios (3/1, 2/1, 1/1) with subsidy costs.

    Args:
        loan_amount: The loan amount (first lien only, P&I basis)
        base_rate: The base annual interest rate as percentage
        term_years: Loan term in years

    Returns:
        Dictionary with buydown scenarios and subsidy calculations
    """
    # Calculate base (full rate) monthly P&I payment
    base_payment = calculate_monthly_pi_payment(loan_amount, base_rate, term_years)

    scenarios = {
        "standard": {
            "type": "Standard",
            "payment": base_payment,
            "rate": base_rate,
            "years": []
        }
    }

    # 3/1 Buydown: Year 1 = base - 3%, Year 2 = base - 2%, Year 3 = base - 1%, Year 4+ = base
    buydown_3_1_years = []
    total_subsidy_3_1 = 0
    for year, rate_reduction in [(1, 3.0), (2, 2.0), (3, 1.0)]:
        reduced_rate = base_rate - rate_reduction
        reduced_payment = calculate_monthly_pi_payment(loan_amount, reduced_rate, term_years)
        monthly_savings = base_payment - reduced_payment
        annual_subsidy = monthly_savings * 12
        total_subsidy_3_1 += annual_subsidy

        buydown_3_1_years.append({
            "year": year,
            "rate": reduced_rate,
            "payment": reduced_payment,
            "monthly_savings": monthly_savings,
            "annual_subsidy": annual_subsidy
        })

    scenarios["3_1"] = {
        "type": "3/1 Buydown",
        "years": buydown_3_1_years,
        "base_payment": base_payment,
        "base_rate": base_rate,
        "total_subsidy": total_subsidy_3_1
    }

    # 2/1 Buydown: Year 1 = base - 2%, Year 2 = base - 1%, Year 3+ = base
    buydown_2_1_years = []
    total_subsidy_2_1 = 0
    for year, rate_reduction in [(1, 2.0), (2, 1.0)]:
        reduced_rate = base_rate - rate_reduction
        reduced_payment = calculate_monthly_pi_payment(loan_amount, reduced_rate, term_years)
        monthly_savings = base_payment - reduced_payment
        annual_subsidy = monthly_savings * 12
        total_subsidy_2_1 += annual_subsidy

        buydown_2_1_years.append({
            "year": year,
            "rate": reduced_rate,
            "payment": reduced_payment,
            "monthly_savings": monthly_savings,
            "annual_subsidy": annual_subsidy
        })

    scenarios["2_1"] = {
        "type": "2/1 Buydown",
        "years": buydown_2_1_years,
        "base_payment": base_payment,
        "base_rate": base_rate,
        "total_subsidy": total_subsidy_2_1
    }

    # 1/1 Buydown: Year 1 = base - 1%, Year 2+ = base
    buydown_1_1_years = []
    total_subsidy_1_1 = 0
    for year, rate_reduction in [(1, 1.0)]:
        reduced_rate = base_rate - rate_reduction
        reduced_payment = calculate_monthly_pi_payment(loan_amount, reduced_rate, term_years)
        monthly_savings = base_payment - reduced_payment
        annual_subsidy = monthly_savings * 12
        total_subsidy_1_1 += annual_subsidy

        buydown_1_1_years.append({
            "year": year,
            "rate": reduced_rate,
            "payment": reduced_payment,
            "monthly_savings": monthly_savings,
            "annual_subsidy": annual_subsidy
        })

    scenarios["1_1"] = {
        "type": "1/1 Buydown",
        "years": buydown_1_1_years,
        "base_payment": base_payment,
        "base_rate": base_rate,
        "total_subsidy": total_subsidy_1_1
    }

    return scenarios


def format_buydown_output(scenarios: dict, home_price: float) -> str:
    """Format buydown scenarios into XML output string.

    Args:
        scenarios: Dictionary of buydown scenarios from calculate_buydown_scenarios
        home_price: Purchase price to calculate subsidy percentages

    Returns:
        Formatted XML string with buydown options
    """
    output = """
    <buydown-options>"""

    # Standard (no buydown)
    standard = scenarios["standard"]
    output += f"""
        <variant type="Standard">
            All Months: ${round(standard['payment'], 2):,} @ {round(standard['rate'], 3)}%
        </variant>"""

    # 3/1 Buydown
    scenario_3_1 = scenarios["3_1"]
    output += f"""

        <variant type="3/1 Buydown">"""
    for year_data in scenario_3_1["years"]:
        output += f"""
            Year {year_data['year']}: ${round(year_data['payment'], 2):,} @ {round(year_data['rate'], 3)}% (saves ${round(year_data['monthly_savings'], 2):,}/mo, ${round(year_data['annual_subsidy'], 2):,} annual subsidy)"""
    output += f"""
            Year 4+: ${round(scenario_3_1['base_payment'], 2):,} @ {round(scenario_3_1['base_rate'], 3)}%

            Total Upfront Subsidy: ${round(scenario_3_1['total_subsidy'], 2):,} ({(scenario_3_1['total_subsidy'] / home_price * 100):.2f}% of purchase price)
        </variant>"""

    # 2/1 Buydown
    scenario_2_1 = scenarios["2_1"]
    output += f"""

        <variant type="2/1 Buydown">"""
    for year_data in scenario_2_1["years"]:
        output += f"""
            Year {year_data['year']}: ${round(year_data['payment'], 2):,} @ {round(year_data['rate'], 3)}% (saves ${round(year_data['monthly_savings'], 2):,}/mo, ${round(year_data['annual_subsidy'], 2):,} annual subsidy)"""
    output += f"""
            Year 3+: ${round(scenario_2_1['base_payment'], 2):,} @ {round(scenario_2_1['base_rate'], 3)}%

            Total Upfront Subsidy: ${round(scenario_2_1['total_subsidy'], 2):,} ({(scenario_2_1['total_subsidy'] / home_price * 100):.2f}% of purchase price)
        </variant>"""

    # 1/1 Buydown
    scenario_1_1 = scenarios["1_1"]
    output += f"""

        <variant type="1/1 Buydown">"""
    for year_data in scenario_1_1["years"]:
        output += f"""
            Year {year_data['year']}: ${round(year_data['payment'], 2):,} @ {round(year_data['rate'], 3)}% (saves ${round(year_data['monthly_savings'], 2):,}/mo, ${round(year_data['annual_subsidy'], 2):,} annual subsidy)"""
    output += f"""
            Year 2+: ${round(scenario_1_1['base_payment'], 2):,} @ {round(scenario_1_1['base_rate'], 3)}%

            Total Upfront Subsidy: ${round(scenario_1_1['total_subsidy'], 2):,} ({(scenario_1_1['total_subsidy'] / home_price * 100):.2f}% of purchase price)
        </variant>"""

    output += """
    </buydown-options>

    <buydown-note>Subsidy amounts represent the upfront cost paid by seller, lender, or builder to reduce the buyer's interest rate during the initial years.</buydown-note>"""

    return output


def calculate_second_lien_payment(second_lien_amount: float,
                                  second_lien_rate: float,
                                  second_lien_type: SecondLienType,
                                  second_lien_term_years: int = 30) -> float:
    """Calculate monthly payment for second lien.

    Args:
        second_lien_amount: The second lien loan amount
        second_lien_rate: Annual interest rate as percentage
        second_lien_type: Either fully_amortized or interest_only
        second_lien_term_years: Term in years (for fully amortized)

    Returns:
        Monthly payment amount
    """
    if second_lien_type == SecondLienType.INTEREST_ONLY:
        # Interest-only: monthly payment = (amount × annual rate) / 12
        return (second_lien_amount * second_lien_rate / 100) / 12
    else:
        # Fully amortized: use standard amortization formula
        monthly_rate = second_lien_rate / 12 / 100
        total_payments = second_lien_term_years * 12

        if monthly_rate > 0:
            return (
                second_lien_amount *
                (monthly_rate * (1 + monthly_rate) ** total_payments)
                / ((1 + monthly_rate) ** total_payments - 1)
            )
        else:
            return second_lien_amount / total_payments


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
        homeowners_association_fee: int = 0,
        second_lien_amount: Optional[Union[str, int, float]] = None,
        second_lien_type: Optional[Union[SecondLienType, str]] = SecondLienType.INTEREST_ONLY,
        second_lien_rate: Optional[float] = None,
        second_lien_term_years: int = 30
):
    """Calculate monthly mortgage payments with detailed breakdown, including support for second liens/subordinate financing.

    This is my primary tool for helping real estate professionals get instant payment quotes with current market rates,
    including scenarios with down payment assistance (DPA) programs and piggyback loans for MI avoidance.

    Args:
        home_price: The purchase price of the home. Accepts various formats like "$500,000", "500k", "500 thousand".
        loan_type: The type of loan: 'conventional', 'fha', 'va', 'jumbo'. Defaults to 'conventional'.
        units: The number of units in the property. Defaults to 1.
        down_payment: The down payment amount. Accepts formats like "20,000", "20k", "20 grand", or percentages like "20%".
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
        second_lien_amount: Amount of second lien/subordinate financing/down payment assistance (DPA). Can be dollar amount or percentage (e.g., "10%" or "50000").
        second_lien_type: Type of second lien: 'fully_amortized' or 'interest_only'. Defaults to 'interest_only'.
        second_lien_rate: Annual interest rate for second lien. Defaults to first lien rate + 1.0%.
        second_lien_term_years: Term for fully amortized second liens. Defaults to 30 years.
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

        # Handle second lien amount - could be percentage or dollar amount
        second_lien_is_percentage = False
        if second_lien_amount is not None:
            if isinstance(second_lien_amount, str) and '%' in second_lien_amount:
                second_lien_is_percentage = True
            second_lien_amount = parse_currency_amount(second_lien_amount)
            # If it's a percentage and home_price is known, convert to dollar amount
            if second_lien_is_percentage and home_price is not None:
                second_lien_amount = home_price * second_lien_amount
                second_lien_is_percentage = False  # Mark as converted to prevent double conversion

        if annual_property_tax is not None:
            annual_property_tax = parse_currency_amount(annual_property_tax)
        if annual_home_insurance is not None:
            annual_home_insurance = parse_currency_amount(annual_home_insurance)
        if ltv is not None:
            ltv = parse_currency_amount(ltv) if isinstance(ltv, str) else float(ltv)
    except ValueError as e:
        return f"Invalid input format: {str(e)}. Please provide numbers in formats like '500000', '$500,000', '500k', '20%', or '500 thousand'."

    if home_price is None and loan_amount is None:
        return "Either home_price or loan_amount must be provided."

    # Validate and normalize loan type
    if not isinstance(loan_type, LoanType):
        try:
            loan_type = validate_normalize_loan_type(loan_type)
        except ValueError:
            return "Invalid loan type. Must be 'conventional', 'fha', 'va', 'jumbo'"

    # Validate and normalize second lien type
    if second_lien_type is not None and isinstance(second_lien_type, str):
        second_lien_type_lower = second_lien_type.lower().strip()
        if second_lien_type_lower in ['fully_amortized', 'fully amortized', 'amortized', 'amortizing']:
            second_lien_type = SecondLienType.FULLY_AMORTIZED
        elif second_lien_type_lower in ['interest_only', 'interest only', 'io']:
            second_lien_type = SecondLienType.INTEREST_ONLY
        else:
            try:
                second_lien_type = SecondLienType(second_lien_type_lower)
            except ValueError:
                return "Invalid second lien type. Must be 'fully_amortized' or 'interest_only'"

    # Default to interest_only if not specified
    if second_lien_type is None and second_lien_amount is not None:
        second_lien_type = SecondLienType.INTEREST_ONLY

    # Determine home price if not provided
    if home_price is None:
        if down_payment is None:
            down_payment = loan_amount * 0.25  # Assume 20% down if not specified
        home_price = loan_amount + down_payment
        # Convert second lien percentage to dollars now that we have home_price
        if second_lien_amount is not None and second_lien_is_percentage:
            second_lien_amount = home_price * second_lien_amount

    # Handle LTV input
    if ltv is not None:
        if ltv > 1:
            ltv = ltv / 100  # Convert percentage to decimal
        loan_amount = home_price * ltv
        # Adjust down payment to account for first lien and any second lien
        if second_lien_amount is not None:
            down_payment = home_price - loan_amount - second_lien_amount
        else:
            down_payment = home_price - loan_amount

    # Set loan-type specific defaults
    if down_payment is None:
        if loan_type == LoanType.FHA:
            down_payment = home_price * 0.035  # 3.5% for FHA
        elif loan_type == LoanType.VA:
            down_payment = 0  # VA allows 0% down
        else:
            down_payment = home_price * 0.20  # 20% for conventional/jumbo

        # Adjust down payment if second lien is present
        if second_lien_amount is not None:
            down_payment = max(0, down_payment - second_lien_amount)

    # Calculate loan amount
    if loan_amount is None:
        if second_lien_amount is not None:
            # First lien = home price - down payment - second lien
            loan_amount = home_price - down_payment - second_lien_amount
        else:
            loan_amount = home_price - down_payment

    # Validate that down payment isn't negative
    if down_payment < 0:
        return "Invalid loan structure: down payment cannot be negative. Please check your second lien amount and down payment inputs."

    # Determine if loan should be jumbo
    if loan_type == LoanType.CONVENTIONAL and loan_amount > LOAN_LIMITS["conventional"][units - 1]:
        loan_type = LoanType.JUMBO

    # Validate loan limits (only for first lien)
    if loan_type in [LoanType.CONVENTIONAL, LoanType.FHA]:
        if loan_amount > LOAN_LIMITS[loan_type.value][units - 1]:
            return  f"First lien amount ${loan_amount:,.2f} exceeds {loan_type.value} limit of ${LOAN_LIMITS[loan_type.value][units - 1]:,.2f} for {units} unit(s)."

    # Calculate LTV (first lien only) and CLTV (combined)
    calculated_ltv = round(loan_amount / home_price, 3) if home_price > 0 else 0

    if second_lien_amount is not None and second_lien_amount > 0:
        calculated_cltv = round((loan_amount + second_lien_amount) / home_price, 3) if home_price > 0 else 0
    else:
        calculated_cltv = calculated_ltv

    # Validate CLTV doesn't exceed reasonable limits
    if calculated_cltv > 1.05:  # 105% CLTV max
        return f"Combined LTV of {calculated_cltv:.1%} exceeds maximum allowable CLTV of 105%. This structure may not be feasible."

    # Validate LTV limits for first lien
    if loan_type == LoanType.CONVENTIONAL and calculated_ltv > 0.95:
        if calculated_ltv > 0.965:
            return f"First lien LTV of {calculated_ltv:.1%} exceeds conventional loan limit of 95%. Consider FHA loan."
        else:
            loan_type = LoanType.FHA
    elif loan_type == LoanType.FHA and calculated_ltv > 0.965:
        return f"First lien LTV of {calculated_ltv:.1%} exceeds FHA loan limit of 96.5%."

    # Get interest rate
    if annual_interest_rate is None:
        annual_interest_rate = fetch_freddie_mac_rate(loan_type.value, loan_term_years)

    # Set second lien rate (default: first lien rate + 1.0%)
    if second_lien_amount is not None and second_lien_amount > 0:
        if second_lien_rate is None:
            second_lien_rate = annual_interest_rate + 1.0

    # Handle FHA upfront MIP
    fha_upfront_mip = 0
    base_loan_amount = loan_amount
    if loan_type == LoanType.FHA:
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

    # Calculate monthly payment components for FIRST LIEN
    monthly_interest_rate = annual_interest_rate / 12 / 100
    total_payments = loan_term_years * 12

    # Monthly principal and interest for first lien
    if monthly_interest_rate > 0:
        monthly_principal_interest = (
                loan_amount *
                (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments)
                / ((1 + monthly_interest_rate) ** total_payments - 1)
        )
    else:
        monthly_principal_interest = loan_amount / total_payments

    # Calculate mortgage insurance (only if first lien LTV > 80% for conventional, always for FHA)
    monthly_mi = 0.0
    mi_rate = 0.0

    # For conventional loans with second lien: if first lien LTV <= 80%, no MI needed
    # This is the key benefit of piggyback loans (e.g., 80/10/10)
    if loan_type == LoanType.CONVENTIONAL:
        # Only charge MI if first lien LTV > 80%
        if calculated_ltv > 0.80:
            mi_rate = get_conventional_mi_rate(calculated_ltv)
            monthly_mi = (loan_amount * mi_rate) / 12
    elif loan_type == LoanType.FHA:
        # FHA always requires MIP regardless of second lien
        mi_rate = get_fha_mi_rate(calculated_ltv, loan_term_years, base_loan_amount)
        monthly_mi = calculate_monthly_premium(
            annual_interest_rate, base_loan_amount, monthly_principal_interest, 0.0175, mi_rate, loan_term_years
        )

    # Calculate SECOND LIEN payment if present
    monthly_second_lien_payment = 0.0
    if second_lien_amount is not None and second_lien_amount > 0:
        monthly_second_lien_payment = calculate_second_lien_payment(
            second_lien_amount,
            second_lien_rate,
            second_lien_type,
            second_lien_term_years
        )

    # Monthly property tax and insurance
    monthly_tax = annual_property_tax / 12
    monthly_insurance = annual_home_insurance / 12

    # Total monthly payment
    total_monthly_payment = (
            monthly_principal_interest +
            monthly_second_lien_payment +
            monthly_tax +
            monthly_insurance +
            monthly_mi +
            homeowners_association_fee
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

    # Build result string
    result = f"""
<rate-calculation>
    <payment>${round(total_monthly_payment, 2):,}</payment>

    <breakdown>"""

    # First lien breakdown
    result += f"""
        First Lien Payment: ${round(monthly_principal_interest, 2):,}"""

    # Second lien breakdown if present
    if second_lien_amount is not None and second_lien_amount > 0:
        second_lien_type_display = "Interest-Only" if second_lien_type == SecondLienType.INTEREST_ONLY else "Fully Amortized"
        result += f"""
        Second Lien Payment: ${round(monthly_second_lien_payment, 2):,} ({second_lien_type_display})"""

    result += f"""
        Property Taxes: ${round(monthly_tax, 2):,} (${round(annual_property_tax, 2):,} annually at {property_tax_rate:.2f}%)
        Insurance: ${round(monthly_insurance, 2):,} (${round(annual_home_insurance, 2):,} annually)"""

    if homeowners_association_fee and homeowners_association_fee > 0:
        result += f"""
        HOA Fees: ${round(homeowners_association_fee, 2):,}"""

    if monthly_mi > 0:
        mi_type = "PMI" if loan_type == LoanType.CONVENTIONAL else "MIP"
        result += f"""
        {mi_type}: ${round(monthly_mi, 2):,} (at {mi_rate * 100:.2f}% annually)"""
    elif loan_type == LoanType.CONVENTIONAL and calculated_ltv > 0.80 and second_lien_amount is not None:
        # Note that MI was avoided due to second lien
        result += f"""
        PMI: $0 (avoided with second lien - first lien LTV at {calculated_ltv:.1%})"""

    va_text = ""
    if loan_type == LoanType.VA:
        va_text += f"VA Funding Fee: ${round(va_funding_fee, 2):,} ({'First-time' if va_first_time else 'Subsequent'} use)"
        if va_exempt:
            va_text += " - EXEMPT"

    # Format down payment percentage
    down_payment_percent = (down_payment / home_price) * 100
    if down_payment_percent == int(down_payment_percent):
        down_payment_percent_str = f"{int(down_payment_percent)}%"
    else:
        down_payment_percent_str = f"{down_payment_percent:.2f}%"

    result += f"""
    </breakdown>

    <loan-details>
        Purchase Price: ${round(home_price, 2):,}
        Down Payment: ${round(down_payment, 2):,} ({down_payment_percent_str})

        First Lien Details:
        • Amount: ${round(loan_amount, 2):,}
        • Interest Rate: {round(annual_interest_rate, 3)}%
        • Term: {loan_term_years} years
        • Type: {loan_type_display}
        • LTV: {calculated_ltv:.1%}"""

    # Second lien details if present
    if second_lien_amount is not None and second_lien_amount > 0:
        second_lien_percent = (second_lien_amount / home_price) * 100
        if second_lien_percent == int(second_lien_percent):
            second_lien_percent_str = f"{int(second_lien_percent)}%"
        else:
            second_lien_percent_str = f"{second_lien_percent:.2f}%"

        second_lien_type_display = "Interest-Only" if second_lien_type == SecondLienType.INTEREST_ONLY else f"Fully Amortized ({second_lien_term_years} years)"

        result += f"""

        Second Lien Details:
        • Amount: ${round(second_lien_amount, 2):,} ({second_lien_percent_str} of purchase price)
        • Interest Rate: {round(second_lien_rate, 3)}%
        • Type: {second_lien_type_display}

        Combined LTV (CLTV): {calculated_cltv:.1%}"""
    else:
        # No second lien, so show LTV in main details
        pass

    if va_text:
        result += f"""
        {va_text}"""

    result += f"""
    </loan-details>"""

    # Only show assumptions for Conventional loans with LTV > 80% and MI
    if loan_type == LoanType.CONVENTIONAL and calculated_ltv > 0.80 and monthly_mi > 0:
        result += f"""

    <assumptions>
        MI Calculation Assumptions:
        • Credit Score: {fico_score}
        • Occupancy: {occupancy_display[occupancy] if occupancy else "Primary Residence"}
        • Property Type: {property_type_display[property_type] if property_type else "Single Family"}
        • PMI Rate: {mi_rate * 100:.2f}% per year (Estimate)
    </assumptions>"""

    # Calculate and add buydown scenarios
    # Use base_loan_amount for FHA (without upfront MIP), otherwise use the loan_amount without fees
    buydown_loan_amount = base_loan_amount if loan_type == LoanType.FHA else (loan_amount - va_funding_fee if loan_type == LoanType.VA else loan_amount)
    buydown_scenarios = calculate_buydown_scenarios(buydown_loan_amount, annual_interest_rate, loan_term_years)
    result += format_buydown_output(buydown_scenarios, home_price)

    # Collect all applicable disclaimers
    disclaimers = []

    # Complex property disclaimer
    if units != 1 or occupancy != Occupancy.PRIMARY_RESIDENCE or property_type != PropertyType.SINGLE_FAMILY:
        disclaimers.append("These adjustments add complexity to the rate. For a reliable quote and full details, connect with a licensed LoanX loan officer.")

    # Second lien disclaimer
    if second_lien_amount is not None and second_lien_amount > 0:
        disclaimers.append("Second lien calculations are estimates. Actual rates and terms may vary by lender. Consult with a licensed loan officer for accurate quotes on subordinate financing.")

    # MI Disclaimer for High LTV Conventional Loans
    if loan_type == LoanType.CONVENTIONAL and calculated_ltv > 0.80 and monthly_mi > 0:
        disclaimers.append("This loan requires Private Mortgage Insurance (PMI) due to LTV exceeding 80%. PMI can typically be removed once you reach 20% equity through payments or appreciation. Contact your lender for PMI removal requirements.")

    # Output disclaimers if any exist
    if disclaimers:
        result += """

    <disclaimer>"""
        for disclaimer in disclaimers:
            result += f"""
        • {disclaimer}"""
        result += """
    </disclaimer>"""

    result += """
</rate-calculation>
    """

    return result
