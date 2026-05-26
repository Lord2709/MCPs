# Week 2 - Building an MCP Server from Scratch

> **Goal:** Understand MCP as a protocol by building a server from scratch - not just using one.
> 
> This README documents the actual questions I wrestled with while building this,
> and the answers I arrived at through code. Use it to learn, revise, or follow along.

---

## What problem does MCP solve?

MCP creates a standardized protocol to define tools, such that any LLM accessing them
gets exactly the same structured result every time.

Without MCP, every developer invented their own format for exposing tools to LLMs.
A tool server built by one person wouldn't work with an orchestrator built by someone else.

With MCP, the rules are fixed:
- Want to advertise tools? → implement `list_tools()`
- Want to receive a tool call? → implement `call_tool()`
- Want to return a result? → return `TextContent`

Any LLM, any framework, any orchestrator - same protocol, every time.

---

## Q1 - What is an MCP server exactly?

An MCP server is a separate process - not a library you import, not a function you call.
It sits between the LLM and your actual tools. The LLM never talks to a user directly.
Instead it talks to the MCP server, which exposes what tools are available and executes
them when called.

```
User → Claude/Orchestrator → MCP Server → Your Python functions
```

The MCP server is always one layer behind the user. It never sees the user directly.

**The skeleton - a server that starts and waits:**

```python
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Give the server a name
app = Server("personal-finance")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

Run this and it starts silently. That silence is correct - it is waiting for a client
(Claude Desktop or your own orchestrator) to connect.

---

## Q2 - What are read_stream and write_stream?

They are the input and output channels of the MCP server - not separate files,
not separate programs. Think of them as two pipes through which the server
communicates with whoever connects to it.

```
Client (Claude Desktop)         MCP Server
───────────────────────         ──────────
write ────────────────────────→ read_stream
                                (server reads requests here)

read  ←──────────────────────── write_stream
                                (server writes responses here)
```

When the client asks "what tools do you have?" - that request arrives through
`read_stream`. When the server responds with the tool list - it goes out through
`write_stream`.

This is called **stdio transport** - two programs on the same computer talking
through stdin and stdout pipes. No network required.

---

## Q3 - Why is list_tools() a function, not a static list?

A static list is the same for everyone, always. A function runs fresh every time
a client connects - which means it can return different tools based on context.

**Static list - same tools for everyone:**
```python
# Hardcoded upfront - cannot change at runtime
tools = [
    {"name": "compound_interest"},
    {"name": "loan_emi"}
]
```

**list_tools() as a function - dynamic:**
```python
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    # Runs fresh every time a client connects
    # Could check user role, environment, availability
    # Returns only the tools relevant right now
    return [
        types.Tool(
            name="compound_interest",
            description="Calculate the future value of an investment.",
            inputSchema={ ... }
        ),
        types.Tool(
            name="loan_emi",
            description="Calculate the monthly EMI for a loan.",
            inputSchema={ ... }
        )
    ]
```

A function lets you add restrictions, check conditions, or load tools from a config -
things a hardcoded list can never do.

---

## Q4 - What is a schema and why does it matter?

A schema is a contract - a defined structure that data must follow.

When the LLM calls a tool, it generates the arguments as JSON text. Without a schema,
the LLM might send wrong field names, wrong types, or missing values. With a schema,
the LLM reads the contract before generating anything - and knows exactly what to produce.

```
Without schema:
LLM might send: { "number1": 15, "number2": 27 }
Tool expects:   { "a": 15, "b": 27 }
Result:         tool breaks - wrong key names

With schema:
Schema says: required fields are a and b, both numbers
LLM sends:  { "a": 15, "b": 27 }
Result:     tool works every time
```

**inputSchema in practice:**

```python
inputSchema={
    "type": "object",
    "properties": {
        "principal": {
            "type": "number",
            "description": "The initial amount of money invested."
        },
        "monthly_contribution": {
            "type": "number",
            "description": "The amount added to the investment every month."
        },
        "annual_rate": {
            "type": "number",
            "description": "The annual interest rate as a percentage e.g. 8 for 8%."
        },
        "years": {
            "type": "number",
            "description": "The number of years the money is invested for."
        }
    },
    "required": ["principal", "monthly_contribution", "annual_rate", "years"]
}
```

Three parts every schema needs:
- `type: object` - the whole thing is a dictionary
- `properties` - describes each individual field
- `required` - lists fields that cannot be missing

---

## Q5 - Why does call_tool() return TextContent instead of a plain value?

If tools returned raw Python values - int, float, string, list - the client would
receive a different type every time and have to guess how to handle it.

TextContent wraps every result in the same structure, every time, no matter which
tool ran or what it returned:

```python
# Without wrapping - unpredictable
return 42              # int
return "42"            # string
return [42]            # list
return {"value": 42}   # dict

# With TextContent - always the same shape
return [types.TextContent(type="text", text="...")]
```

The client reads the `type` field and always knows what it's getting.
Works on the 1st call and the 100th call - consistent structure every time.

**call_tool() for compound interest:**

```python
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "compound_interest":
        principal             = arguments["principal"]
        monthly_contribution  = arguments["monthly_contribution"]
        annual_rate           = arguments["annual_rate"]
        years                 = arguments["years"]

        monthly_rate     = annual_rate / 100 / 12
        months           = years * 12

        fv_principal     = principal * (1 + monthly_rate) ** months
        fv_contributions = monthly_contribution * (((1 + monthly_rate) ** months - 1) / monthly_rate)

        total            = fv_principal + fv_contributions
        total_invested   = principal + (monthly_contribution * months)
        interest_earned  = total - total_invested

        return [types.TextContent(
            type="text",
            text=f"Total Invested: ${total_invested:,.2f}\n"
                 f"Interest Earned: ${interest_earned:,.2f}\n"
                 f"Final Value: ${total:,.2f}"
        )]
```

---

## Q6 - Who starts the MCP server?

It depends on who the client is:

```
Claude Desktop    → starts your server automatically
                    reads the config file on startup
                    spawns your Python file as a subprocess
                    you never run it manually

Your own client   → you can start it manually in a separate terminal
                    OR use stdio_client() which spawns it for you
```

**Claude Desktop config file:**

```json
{
    "mcpServers": {
        "personal-finance": {
            "command": "/path/to/venv/bin/python",
            "args": [
                "/path/to/week2/finance_mcp_server.py"
            ]
        }
    }
}
```

Two fields that matter:
- `command` - which Python to use (must be your venv Python so mcp package is installed)
- `args` - full absolute path to your server file

When Claude Desktop opens, it reads this config, runs the command, and your server
starts automatically. When you quit Claude Desktop, the server process stops.

---

## Q7 - How does the LLM know which tool to call?

The LLM knows because you tell it - every single API call sends the full tool list
as part of the request. The LLM reads the tool name, description, and schema exactly
like it reads any other text, and uses that to decide which tool fits the user's request.

```
User: "What is my monthly payment on a $20,000 loan at 7% for 5 years?"

LLM reads available tools:
  - compound_interest: "Calculate the future value of an investment..."
  - loan_emi:          "Calculate the monthly EMI for a loan..."  ← matches
  - savings_goal:      "How many months to reach a savings goal..."

LLM thinks: user wants a loan payment → loan_emi is the right tool
LLM calls:  loan_emi({ loan_amount: 20000, annual_rate: 7, years: 5 })
```

**This is why descriptions matter so much.**

```python
# Vague - LLM might pick wrong tool
description="does loan stuff"

# Clear - LLM picks correctly every time
description="Calculate the monthly EMI for a loan. 
             Use when the user asks about loan payments, 
             mortgage, or monthly installments."
```

Better description = better tool selection. The LLM reads it like instructions.

---

## Final Code - finance_mcp_server.py

```python
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

app = Server("personal-finance")

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
            name="compound_interest",
            description="Calculate the future value of an investment based on compound interest.",
            inputSchema={
                "type": "object",
                "properties": {
                    "principal":             {"type": "number", "description": "The initial amount of money invested."},
                    "monthly_contribution":  {"type": "number", "description": "The amount added every month."},
                    "annual_rate":           {"type": "number", "description": "Annual interest rate as percentage."},
                    "years":                 {"type": "number", "description": "Number of years invested."}
                },
                "required": ["principal", "monthly_contribution", "annual_rate", "years"]
            }
        ),
        types.Tool(
            name="loan_emi",
            description="Calculate the monthly EMI for a loan.",
            inputSchema={
                "type": "object",
                "properties": {
                    "loan_amount":  {"type": "number", "description": "The principal loan amount."},
                    "annual_rate":  {"type": "number", "description": "Annual interest rate as percentage."},
                    "years":        {"type": "number", "description": "Loan duration in years."}
                },
                "required": ["loan_amount", "annual_rate", "years"]
            }
        ),
        types.Tool(
            name="savings_goal",
            description="Calculate how many months to reach a savings goal.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal":             {"type": "number", "description": "The target savings amount."},
                    "monthly_saving":   {"type": "number", "description": "Amount saved per month."},
                    "annual_rate":      {"type": "number", "description": "Annual interest rate as percentage."},
                    "current_savings":  {"type": "number", "description": "Amount already saved."}
                },
                "required": ["goal", "monthly_saving", "annual_rate", "current_savings"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "compound_interest":
        principal            = arguments["principal"]
        monthly_contribution = arguments["monthly_contribution"]
        annual_rate          = arguments["annual_rate"]
        years                = arguments["years"]

        monthly_rate     = annual_rate / 100 / 12
        months           = years * 12
        fv_principal     = principal * (1 + monthly_rate) ** months
        fv_contributions = monthly_contribution * (((1 + monthly_rate) ** months - 1) / monthly_rate)
        total            = fv_principal + fv_contributions
        total_invested   = principal + (monthly_contribution * months)
        interest_earned  = total - total_invested

        return [types.TextContent(
            type="text",
            text=f"Total Invested: ${total_invested:,.2f}\n"
                 f"Interest Earned: ${interest_earned:,.2f}\n"
                 f"Final Value: ${total:,.2f}"
        )]

    elif name == "loan_emi":
        P = arguments["loan_amount"]
        r = arguments["annual_rate"] / 100 / 12
        n = arguments["years"] * 12

        emi            = (P * r * (1 + r) ** n) / ((1 + r) ** n - 1)
        total_paid     = emi * n
        total_interest = total_paid - P

        return [types.TextContent(
            type="text",
            text=f"Monthly EMI: ${emi:,.2f}\n"
                 f"Total Amount Paid: ${total_paid:,.2f}\n"
                 f"Total Interest Paid: ${total_interest:,.2f}"
        )]

    elif name == "savings_goal":
        goal             = arguments["goal"]
        monthly_saving   = arguments["monthly_saving"]
        annual_rate      = arguments["annual_rate"]
        current_savings  = arguments["current_savings"]
        monthly_rate     = annual_rate / 100 / 12
        months           = 0

        while current_savings < goal:
            current_savings += monthly_saving
            current_savings *= (1 + monthly_rate)
            months          += 1

        years             = months // 12
        remaining_months  = months % 12

        return [types.TextContent(
            type="text",
            text=f"Time to reach goal: {years} years and {remaining_months} months"
        )]

if __name__ == "__main__":
    asyncio.run(main())
```

---

## What I wish I knew earlier

- **The server is a separate process, not a function.**
  I kept thinking of it like a Python module I'd import.
  It's actually a program that runs independently and waits for connections.

- **Silence means it's working.**
  When you run the server and nothing prints - that's correct.
  It's waiting for a client. An error would print something. Silence is success.

- **Tool descriptions are instructions to the LLM, not documentation for humans.**
  Write them as if you're telling the LLM exactly when and how to use the tool.
  Vague descriptions = wrong tool selected = broken agent.

- **Claude Desktop manages the server lifecycle for you.**
  You don't run the server manually. Claude reads the config, spawns your Python
  file as a subprocess, and kills it when you quit. The config path must be exact -
  full absolute path, venv Python, not system Python.

- **inputSchema and TextContent are both contracts.**
  Schema is a contract on what goes IN to your tool.
  TextContent is a contract on what comes OUT.
  Both exist to make behavior predictable across every single call.

---

## Test Results

| Question asked in Claude Desktop | Tool called | Result |
|---|---|---|
| "$1000 + $500/month at 8% for 10 years?" | compound_interest | Final Value: $92,473.35 |
| "$20,000 loan at 7% for 5 years?" | loan_emi | Monthly EMI: $396.02 |
| "$2000 saved, $500/month at 6%, goal $20,000?" | savings_goal | 2 years and 9 months |

---

*Part of a weekly learning series - building MCP and multi-agent AI systems from scratch.*  
*Week 1: Raw orchestrator loop | Week 2: MCP Server | Week 3: Multi-agent with CrewAI (coming soon)*
