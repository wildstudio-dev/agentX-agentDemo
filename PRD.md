Overview
Enhancements to the payment tool to handle second liens / subordinate financing 
scenarios. This is a future enhancement, not immediately required.

Key Enhancement Areas
1. DPA / Second-Lien Scenario #1 - Fully Amortized Seconds
2. Piggyback / MI-Avoidance Scenario #2 - Interest-Only Seconds
3. Required User Inputs
4. Example Agent Prompts to Support

Why This Matters
Second liens are common in real-world scenarios for down payment assistance and avoiding PMI. This enhancement would make the payment tool more complete and provide agents with realistic payment comparisons when subordinate financing is involved.

Payment Tool Enhancement – Handling Second Liens
1. Description
First off, great work on the current payment tool — so powerful.  
Here is a something to ponder for future versions, second liens, or also called subordinate financing.   It is not a necessity.
Second liens are common in the below 2 scenarios :

1. Down Payment Assistance (DPA) programs (e.g., CALFA, Utah Housing Corp, etc.).
2. Piggyback or MI-Avoidance loans, where a borrower uses a second lien to lower the first-lien LTV or stay out of jumbo territory.

This update will make the tool more complete and give agents realistic payment comparisons when subordinate financing is involved.
2. DPA / Second-Lien Scenario #1 – Fully Amortized Seconds
Use case: Down payment assistance or closing cost coverage programs like Utah Housing or CAFA.
- Typical first lien: FHA (96.5% LTV)
- Typical second lien: Around 3.5% of the purchase price (sometimes higher if it covers closing costs)
- Combined LTV (CLTV): Can exceed 100% (e.g., 96.5 / 101.9) – to cover closing cost
- Amortization: Fully amortized, 30-year term
- Interest rate assumption: Roughly 1.0% higher than the first-lien rate
3. Piggyback / MI-Avoidance Scenario #2 – Interest-Only Seconds
Use case: Borrower uses a second lien to:
- Avoid mortgage insurance (e.g., 80/10/10 structure)
- Stay within conforming limits and avoid jumbo pricing
- Loan structure example: 80% first lien, 10% second lien, 10% down payment
- Amortization: Interest-only, but sometimes this is fully amortized – this is something the user should be able to change.
- Rate assumption: About 1.0% higher than the first-lien rate
4. User Inputs
It would be great if the user could input:
-Second Lien Amount: Either a dollar amount or % of the purchase price
-Second Lien Type, Fully amortized, or Interest Only,   
5. Example Agent Prompts for the AI
To help ensure the AI interprets these scenarios correctly, here are some examples of natural-language prompts real estate agents might use when testing or demonstrating the tool:
1. “Can you tell me the payment for a $600,000 purchase with an 80% first and a 15% second that is interest only?”
2. “I have a borrower who wants to purchase a $435,000 home using Utah Housing, and the seller will pay the closing costs, so the second only needs to be 3.5%.”
3. “What’s the total payment if a borrower does an 80/10/10 conventional with a 7% first and 8% second?”
4. “Show me what the payment difference would be between a standard FHA loan and using a Utah Housing DPA program.”
5. “If my borrower takes out a $500,000 loan with a $50,000 interest-only second, what’s the total monthly payment at 7% and 8% respectively?”