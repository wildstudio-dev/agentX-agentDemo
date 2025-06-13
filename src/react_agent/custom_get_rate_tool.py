from enum import Enum

# https://singlefamily.fanniemae.com/originating-underwriting/loan-limits
CONVENTIONAL_LOAN_LIMITS = [806500, 1032650, 1248150, 1551250]

# https://www.fha.com/lending_limits_state?state=UTAH
FHA_LOAN_LIMITS = [629050, 805300, 973400, 1209750]

LOAN_LIMITS = {
    "conventional": CONVENTIONAL_LOAN_LIMITS,
    "fha": FHA_LOAN_LIMITS
}


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
    """This function estimates monthly payments for a conventional loan. It requires either a home price or a loan amount, and calculates the monthly payment based on the provided parameters.
    Args:
        home_price (float): The price of the home. If not provided, it will be calculated based on the loan amount and a default down payment.
        loan_type (LoanType): The type of loan, either 'conventional' or 'fha'. Defaults to 'conventional'.
        units (int): The number of units in the property. Defaults to 1.
        down_payment (float): The down payment amount. If not provided, it defaults to 20% of the home price.
        annual_interest_rate (float): The annual interest rate as a percentage. Defaults to 7.5%.
        loan_term_years (int): The term of the loan in years. Defaults to 30 years.
        loan_amount (float): The amount of the loan. If not provided, it will be calculated based on the home price and down payment.
        annual_property_tax (float): The annual property tax amount. If not provided, it defaults to 0.65% of the home price.
        annual_home_insurance (float): The annual home insurance amount. If not provided, it defaults to 0.2% of the home price.
        fico_score (int): The FICO score of the borrower. Defaults to 760.
    """

    if home_price is None and loan_amount is None:
        return {
            "error": "Either home_price or loan_amount must be provided."
        }

    # Validate loan type
    if not isinstance(loan_type, LoanType):
        try:
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
