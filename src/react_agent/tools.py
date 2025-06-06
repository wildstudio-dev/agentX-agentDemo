import logging
from enum import Enum
from typing import Any, Callable, List, Optional

import aiohttp


class LoanType(str, Enum):
    """Loan Type enumeration"""
    CONFORMING = "Conforming"
    NON_CONFORMING = "NonConforming"
    FHA = "FHA"
    VA = "VA"
    CONVENTIONAL = "Conventional"
    HELOC = "HELOC"
    USDA_RURAL_HOUSING = "USDARuralHousing"


class LoanPurpose(str, Enum):
    """Loan purpose enumeration"""
    PURCHASE = "Purchase"
    REFI_CASHOUT = "RefiCashout"
    REFI_RATE_TERM_LIMITED_CO = "RefiRateTermLimitedCO"
    FHA_STREAMLINE_REFI = "FHAStreamlineRefi"
    VA_RATE_REDUCTION = "VARateReduction"
    SIMPLE_REFINANCE = "SimpleRefinance"


class Occupancy(str, Enum):
    """Property occupancy type enumeration"""
    INVESTMENT_PROPERTY = "InvestmentProperty"
    PRIMARY_RESIDENCE = "PrimaryResidence"
    SECOND_HOME = "SecondHome"


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


class AmortizationType(str, Enum):
    """Loan amortization type enumeration"""
    FIXED = "Fixed"
    ARM = "ARM"
    BALLOON = "Balloon"


class LoanTerm(str, Enum):
    """Loan term enumeration"""
    ONE_YEAR = "OneYear"
    TWO_YEAR = "TwoYear"
    THREE_YEAR = "ThreeYear"
    FOUR_YEAR = "FourYear"
    FIVE_YEAR = "FiveYear"
    SIX_YEAR = "SixYear"
    SEVEN_YEAR = "SevenYear"
    EIGHT_YEAR = "EightYear"
    NINE_YEAR = "NineYear"
    TEN_YEAR = "TenYear"
    TWELVE_YEAR = "TwelveYear"
    FIFTEEN_YEAR = "FifteenYear"
    TWENTY_YEAR = "TwentyYear"
    TWENTY_FIVE_YEAR = "TwentyFiveYear"
    THIRTY_YEAR = "ThirtyYear"
    FORTY_YEAR = "FortyYear"


async def get_rate(
        price: int,
        city: str,
        address_line_1: str,
        postal_code: str,
        down_payment: int = 0,
        state: str = "UT",
        loan_type: LoanType = LoanType.CONFORMING,
        term: LoanTerm = LoanTerm.THIRTY_YEAR,
        amortization_type: AmortizationType = AmortizationType.FIXED,
        purpose: LoanPurpose = LoanPurpose.PURCHASE,
        fico_score: int = 720,
        occupancy: Occupancy = Occupancy.PRIMARY_RESIDENCE,
) -> Optional[dict[str, Any]]:
    """Find quote for a given property

    This function search for quotes related to a given client request for mortgage rates.
    It receives mandatory price, down_payment  city, address_line_1 and postal_code
    state, loan_type, term, amortization_type, purpose, occupancy and fico_score are optional parameters
    """
    url = "https://app.loanx.cc/api/rates"
    data = {
                "action": "getRateProducts",
                "channelId": "104065",
                "originatorId": "1555641",
                "price": price,
                "downPayment": price * 0.2 if down_payment == 0 else down_payment,
                "type": loan_type,
                "term": term,
                "amortizationType": amortization_type,
                "purpose": purpose,
                "agency": "NotSpecified",
                "ficoScore": fico_score,
                "occupancy": occupancy,
                "propertyType": "SingleFamily",
                "units": "OneUnit",
                "firstTimeHomeBuyer": True,
                "selfEmployed": True,
                "buydown": "None",
                "firstName": "Eric",
                "lastName": "Clemson",
                "countryOfCitizenship": "US",
                "residencyStatus": "CITIZEN",
                "address": {
                    "addressLine1": address_line_1,
                    "city": city,
                    "stateOrProvince": state,
                    "country": "US",
                    "postalCode": postal_code,
                },
                # what about those
                "dti": 0.69,
                "income": 7000
            }
    logging.info(f"get_rate: {data}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                return await response.json()
    except Exception as e:
        logging.info(f"catch {e}")
        return None


TOOLS: List[Callable[..., Any]] = [get_rate]