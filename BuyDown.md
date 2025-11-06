Buydown Payment Logic
An ideal “add on to AgentX” would be to display payment options for standard, 3/1, 2/1, and 1/1 temporary buydowns.
The AI retrieves the base rate from the Freddie Site, then calculates principal and interest (P&I) 
payments at reduced effective interest rates for the initial buydown years.
Calculation Logic
Use the base rate the payment, and temporary buydown payments.
For each buydown structure, apply the corresponding rate reductions:
3/1 Buydown: Year 1 = base – 3%, Year 2 = base – 2%, Year 3 = base – 1%, Year 4 + = base rate
2/1 Buydown: Year 1 = base – 2%, Year 2 = base – 1%, Year 3 + = base rate
1/1 Buydown: Year 1 = base – 1%, Year 2 + = base rate
Attached is a spreadsheet for comparative,

                3/1 BuyDown		2/1 Buydown		1/1 Buydown
Purchase Price	400000US$		400000US$		400000US$
Down	5%	    20000US$	   5%	20000US$	5%	20000US$
						
Loan amount		380 000 US$		380000US$       380000US$
						
Payment (Yr 1)	3,85%	1 781,47128251271 US$	4,85%	2005,23US$	5,85%	2241,78US$
Payment (Yr2)	4,85%	2 005,22894476964 US$	5,85%	2241,78US$	6,85%	2489,99US$
Payment (Yr3)	5,85%	2 241,77554988129 US$	6,85%	2489,96US$		
Payment (yr4-300)	6,85%	2489,96US$				