import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Step 1 — create the server and give it a name
app = Server("personal-finance")

# Step 2 — define the entry point
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name= "compound_interest",
            description= "Calculate the future value of an investment based on compound interest.",
            inputSchema= {
                        "type": "object",
                        "properties": {
                            "principal": {"type": "number", "description": "The initial amount of money invested."},
                            "monthly_contribution": {"type": "number", "description": "The amount of money added to the investment every month."},
                            "annual_rate": {"type": "number", "description": "The annual interest rate in percentage."},
                            "years": {"type": "number", "description": "The number of years the money is invested for."}
                        },
                        "required": ["principal", "monthly_contribution", "annual_rate", "years"]
                    }
        ),
        types.Tool(
            name= "loan_emi",
            description= "Calculate the monthly EMI for a loan.",
            inputSchema= {
                        "type": "object",
                        "properties": {
                            "loan_amount": {"type": "number", "description": "The principal loan amount."},
                            "annual_rate": {"type": "number", "description": "The  interest rate in percentage."},
                            "years": {"type": "number", "description": "The total number of yearly payments."}
                        },
                        "required": ["loan_amount", "annual_rate", "years"]
                    }
        ),
        types.Tool(
            name= "savings_goal",
            description= "How many months to reach a goal.",
            inputSchema= {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "number", "description": "The target savings goal."},
                            "monthly_saving": {"type": "number", "description": "The amount saved."},
                            "annual_rate": {"type": "number", "description": "The annual interest rate in percentage."},
                            "current_savings": {"type": "number", "description": "The current amount of savings."}
                        },
                        "required": ["goal", "monthly_saving", "annual_rate", "current_savings"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "compound_interest":
        principal = arguments["principal"]
        monthly_contribution = arguments["monthly_contribution"]
        annual_rate = arguments["annual_rate"]
        years = arguments['years']
        
        monthly_rate = annual_rate / 100 / 12
        months = years * 12
        
        fv_principal = principal * (1 + monthly_rate) ** months
        fv_contributions = monthly_contribution * (((1 + monthly_rate) ** months - 1) / monthly_rate)
        
        total = fv_principal + fv_contributions
        total_invested = principal + (monthly_contribution * months)
        interest_earned = total - total_invested

        return [types.TextContent(
            type="text",
            text=f"Total Invested: ${total_invested:,.2f}\nInterest Earned: ${interest_earned:,.2f}\nFinal Value: ${total:,.2f}"
        )]
    elif name == "loan_emi":
        P = arguments["loan_amount"]
        r = arguments["annual_rate"] / 100 / 12
        n = arguments["years"] * 12

        emi = (P * r * (1 + r) ** n) / ((1 + r) ** n - 1)
        
        total_paid = emi * n
        total_interest = total_paid - P

        return [types.TextContent(
            type="text",
            text=f"Monthly EMI: ${emi:,.2f}\nTotal Amount Paid: ${total_paid:,.2f}\nTotal Interest Paid: ${total_interest:,.2f}"
        )]
    elif name == "savings_goal":
        goal = arguments["goal"]
        monthly_saving = arguments["monthly_saving"]
        annual_rate = arguments["annual_rate"]
        current_savings = arguments["current_savings"]

        monthly_rate = annual_rate / 100 / 12
        months = 0

        while current_savings < goal:
            current_savings += monthly_saving
            current_savings *= (1 + monthly_rate)
            months += 1

        years = months // 12
        remaining_months = months % 12

        return [types.TextContent(
            type="text",
            text=f"Time to reach goal: {years} years and {remaining_months} months"
        )]

if __name__ == "__main__":
    asyncio.run(main())