import os
import asyncio
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from langchain_groq import ChatGroq
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

llm = LLM(
    model="claude-haiku-4-5-20251001",
    api_key=os.environ["ANTHROPIC_API_KEY"]
)

# Parent class — holds server path and connection logic
class MCPTool(BaseTool):
    name: str = ""
    description: str = ""
    server_path: str = "/Users/sahil/Documents/GitHub/MCPs/Week2/finance_mcp_server.py"
    async def _call_mcp(self, arguments: dict) -> str:
        server_params = StdioServerParameters(
            command="/Users/sahil/Documents/GitHub/MCPs/venv/bin/python",
            args=[self.server_path]
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self.name, arguments)
                return result.content[0].text
    
    def _run(self, **kwargs) -> str:
        # Run async code in a completely separate thread
        # with its own fresh event loop
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                self._call_mcp(kwargs)
            )
            return future.result()


# Child classes — just name, description, and parameters
class CompoundInterestCalculator(MCPTool):
    name: str = "compound_interest"
    description: str = "Calculate the future value of an investment."
    
    def _run(self, principal: float, monthly_contribution: float,
             annual_rate: float, years: float) -> str:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                self._call_mcp({
                    "principal": principal,
                    "monthly_contribution": monthly_contribution,
                    "annual_rate": annual_rate,
                    "years": years
                })
            )
            return future.result()


class LoanEMICalculator(MCPTool):
    name: str = "loan_emi"
    description: str = "Calculate the monthly EMI for a loan."
    
    def _run(self, loan_amount: float, annual_rate: float, years: float) -> str:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                self._call_mcp({
                    "loan_amount": loan_amount,
                    "annual_rate": annual_rate,
                    "years": years
                })
            )
            return future.result()


class SavingsGoalCalculator(MCPTool):
    name: str = "savings_goal"
    description: str = "Calculate how long to reach a savings goal."
    
    def _run(self, goal: float, monthly_saving: float,
             annual_rate: float, current_savings: float) -> str:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                self._call_mcp({
                    "goal": goal,
                    "monthly_saving": monthly_saving,
                    "annual_rate": annual_rate,
                    "current_savings": current_savings
                })
            )
            return future.result()
    
# Agents
ci_agent = Agent(
    role="Compound Interest Calculator",
    goal="Calculate the future value of an investment based on compound interest.",
    backstory="You are a helpful assistant that calculates the future value of an investment based on compound interest. You can take into account the initial principal, monthly contributions, annual interest rate, and the number of years the money is invested for.",
    tools=[CompoundInterestCalculator()],
    llm=llm
)

loan_agent = Agent(
    role="Loan Specialist",
    goal="Calculate loan EMI accurately",
    backstory="You are a financial expert specializing in loans",
    tools=[LoanEMICalculator()],
    llm=llm
)

goal_agent = Agent(
    role="Savings Goal Planner",
    goal="Calculate how long it will take to reach a savings goal",
    backstory="You are a financial planner who helps users determine how long it will take to reach their savings goals based on their monthly savings, current savings, and expected annual interest rate.",
    tools=[SavingsGoalCalculator()],
    llm=llm
)

# Tasks
ci_task = Task(
    description="Calculate the future value of investing $1,000 upfront with $500 monthly contributions at 8% annual interest for 10 years.",
    agent=ci_agent,
    expected_output="Total invested, interest earned, and final value in dollars"
)

loan_task = Task(
    description="Calculate the monthly EMI for a $20,000 loan at 7% annual interest for 5 years.",
    agent=loan_agent,
    expected_output="Monthly EMI, total amount paid, and total interest paid in dollars"
)

goal_task = Task(
    description="I have $2,000 saved already and save $500 per month at 6% annual interest. How long to reach $20,000?",
    agent=goal_agent,
    expected_output="Time required in years and months to reach the savings goal"
)

crew = Crew(
    agents=[ci_agent, loan_agent, goal_agent],
    tasks=[ci_task, loan_task, goal_task],
    process=Process.sequential,
    verbose=True
)

result = crew.kickoff()
print(result)