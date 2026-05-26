# Week 3 - Multi-Agent System with CrewAI + MCP

> **Goal:** Connect a multi-agent CrewAI system to the MCP server built in Week 2.
> Instead of Claude Desktop calling the tools - specialized AI agents call them programmatically.
>
> This README documents every question I wrestled with, the errors I hit, and what I learned.

---

## What I Built

A personal financial advisor powered by one AI agent with three MCP tools.
Ask any financial question in plain English - the agent decides which tool to call,
calls your MCP server, gets the result, and gives a comprehensive answer.

```
You type a question
        ↓
CrewAI financial_agent receives it
        ↓
Claude Haiku reads question + tool descriptions
        ↓
LLM decides which tool(s) to call
        ↓
_run() fires → ThreadPoolExecutor → asyncio → MCP server
        ↓
finance_mcp_server.py executes the math
        ↓
Result travels back up the chain
        ↓
Claude formulates final answer
        ↓
You see the result
```

---

## Architecture

```
financial_agents.py (CrewAI orchestration)
        ↓  BaseTool._run()
MCPTool parent class (ThreadPoolExecutor bridge)
        ↓  asyncio → stdio_client → ClientSession
finance_mcp_server.py (MCP server - Week 2)
        ↓  call_tool()
Python math functions (compound_interest, loan_emi, savings_goal)
```

**Stack:**
- CrewAI 1.14.5 - agent orchestration
- Claude Haiku (Anthropic API) - LLM brain
- MCP SDK - protocol bridge
- finance_mcp_server.py - Week 2 server reused unchanged

---

## Q1 - Why can't you import the MCP server directly?

An MCP server is designed to run as a **separate process** communicating through
stdio streams - not as a Python module you import.

If you tried `from finance_mcp_server import call_tool`, the async MCP handlers
would have no streams to listen on. The server is built to receive requests
through a specific channel (the MCP protocol), not direct function access.

```python
# This seems logical but won't work
from finance_mcp_server import call_tool
result = call_tool("loan_emi", {"loan_amount": 20000, ...})

# This is the correct way - go through the protocol
server_params = StdioServerParameters(
    command="/path/to/venv/bin/python",
    args=["/path/to/finance_mcp_server.py"]
)
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        result = await session.call_tool("loan_emi", {...})
```

The MCP server starts as a subprocess, communicates through stdin/stdout pipes,
and shuts down when the session ends. Every tool call goes through the protocol.

---

## Q2 - Sync vs Async - what's the difference?

**Synchronous** - each line waits for the previous to finish before moving on:

```python
def make_tea():
    boil_water()    # waits here until done
    add_teabag()    # then this
    pour_in_cup()   # then this
```

**Asynchronous** - when a line needs to wait (network call, file read, MCP response),
it yields control so other code can run. Comes back when the wait is done:

```python
async def make_tea():
    await boil_water()  # start boiling, do other things while waiting
    add_teabag()        # comes back when done
    pour_in_cup()
```

MCP uses async because it communicates over streams - it sends a request and waits
for a response from the server process. During that wait, async lets other things
run instead of freezing the entire program.

The `await` keyword means: "start this, but don't block everything else while waiting."

---

## Q3 - Why does ThreadPoolExecutor solve the event loop problem?

**The problem:**

```
CrewAI runs agents inside an existing async event loop
_run() is a sync function called from inside that loop
asyncio.run() cannot be called inside an already-running event loop
→ crashes with "Event loop is already running"
```

**The solution:**

```python
def _run(self, **kwargs) -> str:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(
            asyncio.run,
            self._call_mcp(kwargs)
        )
        return future.result()
```

`ThreadPoolExecutor` spawns a completely **new thread**. That new thread has
no existing event loop. `asyncio.run()` works perfectly in a fresh thread -
creates its own event loop, runs `_call_mcp`, gets the result, returns it
to the main thread.

```
Main thread (CrewAI event loop running)
    ↓
ThreadPoolExecutor spawns new thread
    ↓
New thread - no event loop exists
    ↓
asyncio.run() creates fresh event loop
    ↓
_call_mcp() runs: connects to MCP server, calls tool, gets result
    ↓
Result returned to main thread
    ↓
CrewAI agent receives result
```

The analogy: the main kitchen is busy. You need a stove but all are taken.
Solution: go to a separate kitchen, cook there, bring the result back.
ThreadPoolExecutor is the separate kitchen.

---

## Q4 - One agent with 3 tools vs 3 agents with 1 tool each

**3 agents, 1 tool each (what I built first):**

```python
ci_agent   = Agent(tools=[CompoundInterestCalculator()])
loan_agent = Agent(tools=[LoanEMICalculator()])
goal_agent = Agent(tools=[SavingsGoalCalculator()])

# Always runs all 3 regardless of question
crew = Crew(agents=[ci_agent, loan_agent, goal_agent],
            tasks=[ci_task, loan_task, goal_task])
```

```
Problem: user asks about a loan
         → compound interest agent runs anyway (unnecessary)
         → savings goal agent runs anyway (unnecessary)
         3x cost, 3x time, 2 irrelevant answers
```

**1 agent, 3 tools (the better approach):**

```python
financial_agent = Agent(
    tools=[CompoundInterestCalculator(),
           LoanEMICalculator(),
           SavingsGoalCalculator()]
)
```

```
User asks about a loan → only loan_emi tool called
User asks complex question → agent calls multiple tools automatically
LLM decides what's needed at runtime
```

| | 3 agents 1 tool | 1 agent 3 tools |
|---|---|---|
| Who decides what runs | You (hardcoded) | LLM (runtime) |
| Unnecessary tool calls | Always | Never |
| Multi-tool questions | Hard | Natural |
| Best for | Truly independent workflows | Same domain, related tools |

**Use 3 separate agents when:**
- Each agent has many tools in its own domain
- Agents pass results to each other (researcher → writer → reviewer)
- Tasks need genuinely different expertise and reasoning styles
- You want agents to run in parallel

**Use 1 agent with multiple tools when:**
- All tools serve the same domain
- No agent needs another agent's output
- You want the LLM to decide dynamically

---

## Q5 - How does the LLM decide which tool to call?

The LLM reads the tool `name` and `description` exactly like it reads any other text,
then matches them against the user's question.

```python
# The LLM reads this:
types.Tool(
    name="loan_emi",
    description="Calculate the monthly EMI for a loan. 
                 Use when user asks about loan payments, 
                 mortgage, or monthly installments."
)

# User asks: "What is my monthly mortgage payment?"
# LLM matches: "mortgage payment" → loan_emi description
# LLM calls: loan_emi tool
```

**This is why description quality matters:**

```python
# Vague - LLM might pick wrong tool
description="does loan stuff"

# Clear - LLM picks correctly every time
description="Calculate the monthly EMI for a loan. 
             Use when user asks about loan payments, 
             mortgage, or monthly installments."
```

The tool description is not documentation for humans - it's an instruction to the LLM.
Write it as if you're telling the LLM exactly when and how to use the tool.

---

## Q6 - When would you use 3 separate agents?

3 separate agents makes sense when tasks are genuinely different in nature:

```
Research Agent   → 10 web search tools, browses the web
Writing Agent    → 3 document tools, creates reports
Review Agent     → 5 analysis tools, checks quality

Each has a different job
Each passes output to the next
Each needs focused context for its domain
```

Our finance example was overkill for 3 agents because:

```
All 3 tools serve the same domain (finance)
No agent uses another agent's output
Each agent only had 1 tool - no real specialization
Tasks were independent, not collaborative
```

The rule of thumb:
```
Same domain, LLM decides → 1 agent, multiple tools
Different domains, sequential pipeline → multiple agents
Complex task needing debate/review → AutoGen group chat
```

---

## The Errors That Taught Me The Most

**Error 1 - cache_breakpoint (Groq + CrewAI incompatibility)**

```
GroqException: property 'cache_breakpoint' is unsupported
```

CrewAI 1.14.5's new experimental agent executor adds a `cache_breakpoint`
parameter to system messages. Groq doesn't support it.

Fix: switch to Anthropic API (Claude Haiku). CrewAI and Anthropic work
natively together - no compatibility issues.

Lesson: when a framework and a provider conflict, switching providers
is often faster than debugging the framework internals.

---

**Error 2 - SyntaxError on venv/bin/python**

```
SyntaxError: Non-UTF-8 code starting with '\xcf' 
in file /Users/sahil/.../venv/bin/python
```

I accidentally set `server_path` to the Python binary instead of the script:

```python
# Wrong - server_path pointed to the binary
server_path: str = "/path/to/venv/bin/python"
command="python"

# Correct - server_path is the script, command is the binary
server_path: str = "/path/to/finance_mcp_server.py"
command="/path/to/venv/bin/python"
```

Lesson: `command` = the Python interpreter, `args/server_path` = the script to run.
Same as Claude Desktop config - always use full venv Python path, not system Python.

---

**Error 3 - Event loop conflict**

```
RuntimeError: This event loop is already running
```

Calling `asyncio.run()` inside CrewAI's async execution context fails because
an event loop already exists. Fix: `ThreadPoolExecutor` runs the async code
in a fresh thread with its own clean event loop.

Lesson: async and sync worlds don't mix directly. When you need to call async
code from sync code that's already inside an event loop - use a new thread.

---

## Final Code Structure

```python
# Parent class - MCP connection logic lives here once
class MCPTool(BaseTool):
    name: str = ""
    description: str = ""
    server_path: str = "/path/to/finance_mcp_server.py"

    async def _call_mcp(self, arguments: dict) -> str:
        server_params = StdioServerParameters(
            command="/path/to/venv/bin/python",
            args=[self.server_path]
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self.name, arguments)
                return result.content[0].text

    def _run(self, **kwargs) -> str:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, self._call_mcp(kwargs))
            return future.result()

# Child classes - just name, description, typed parameters
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

# One agent - all three tools
financial_agent = Agent(
    role="Personal Financial Advisor",
    goal="Answer any financial question using the right calculation tool",
    backstory="Expert financial advisor with investment, loan, and savings tools",
    tools=[CompoundInterestCalculator(), LoanEMICalculator(), SavingsGoalCalculator()],
    llm=llm
)

# Dynamic task - user provides the question
user_question = input("Ask your financial question: ")
financial_task = Task(
    description=user_question,
    agent=financial_agent,
    expected_output="Detailed financial answer with all relevant numbers"
)

crew = Crew(agents=[financial_agent], tasks=[financial_task],
            process=Process.sequential, verbose=True)
result = crew.kickoff()
```

---

## Test Results

**Single tool question:**
```
Question: "What is the EMI on a $20,000 loan at 7% for 5 years?"
Tool called: loan_emi
Result: Monthly EMI: $396.02 ✅
```

**Multi-tool question (agent called two tools automatically):**
```
Question: "I want to buy a house in 5 years. I have $10k saved 
           and can save $800/month. I'll need a $300k mortgage 
           at 6.5% for 30 years. Full picture please."

Tools called automatically:
    compound_interest → savings projection
    loan_emi          → mortgage calculation

Combined into one comprehensive answer - no manual orchestration needed ✅
```

---

## What I Wish I Knew Earlier

- **MCP server is a process, not a module.** I kept thinking I could just import it.
  The protocol exists specifically because it runs separately - that's the whole point.

- **The LLM is making real decisions.** It's not pattern matching keywords.
  It reads tool descriptions like instructions and reasons about which fits.
  Better descriptions genuinely produce better tool selection.

- **One agent with multiple tools is often better than multiple agents.**
  Three agents felt more "multi-agent" but was actually less intelligent.
  One agent with all tools let the LLM reason across the full toolset.

- **Every error told me something architectural.**
  cache_breakpoint → provider compatibility matters
  venv/bin/python syntax error → path confusion between interpreter and script
  event loop conflict → sync/async worlds need explicit bridging

- **ThreadPoolExecutor is the standard pattern for calling async from sync.**
  Once you understand why it works - new thread, fresh event loop -
  you'll use it confidently whenever you hit this problem.