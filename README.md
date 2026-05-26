# MCP & Agent Learning Journey

Building real AI agent projects from scratch to understand 
MCP, multi-agent orchestration, and A2A systems.

## Week 1 - Orchestrator Loop from Scratch
**Goal:** Understand how an agent loop works before using any framework.

Built a raw Python orchestrator using only the Groq API. 
No LangChain. No CrewAI. Every line written and understood manually.

**What I learned:**
- The orchestrator is just a Python while loop
- LLMs return JSON strings - json.loads converts them to dicts
- Tool descriptions are instructions the LLM reads as text
- Context window fills up - messages list must be managed

**Files:**
- `calculator_agent.py` - multi-tool agent with add, multiply, subtract

---

## Week 2 - Building an MCP Server from Scratch
**Goal:** Understand MCP as a protocol by building a server, not just using one.

Built a personal finance MCP server with 3 tools. 
Connected to Claude Desktop. Claude calls my Python functions live.

**What I learned:**
- MCP server is a separate process, not a library
- list_tools() advertises what the server can do
- call_tool() executes functions and returns structured TextContent
- Claude Desktop spawns the server automatically via config
- Tool descriptions are contracts between the LLM and your code

**Tools built:**
- `compound_interest` - future value of an investment
- `loan_emi` - monthly loan payment calculator  
- `savings_goal` - time to reach a savings target

**Files:**
- `finance_mcp_server.py`

---

## Week 3 - Coming Soon
Multi-agent system with CrewAI where each agent uses MCP tools.

---

## Stack
- Python 3.13
- Groq API (Llama 3.3 70B)
- MCP SDK
- Claude Desktop
