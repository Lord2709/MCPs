import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

tools = [
    {
        "type": "function",
        "function": {
            "name": "add_numbers",
            "description": "Add two numbers together. Only accepts plain numbers, not expressions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "A plain number"},
                    "b": {"type": "number", "description": "A plain number"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multiply_numbers",
            "description": "Multiply two numbers. Only accepts plain numbers, not expressions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "A plain number"},
                    "b": {"type": "number", "description": "A plain number"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "subtract_numbers",
            "description": "Subtract two numbers. Only accepts plain numbers, not expressions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "A plain number"},
                    "b": {"type": "number", "description": "A plain number"}
                },
                "required": ["a", "b"]
            }
        }
    }
]

def add_numbers(a, b):
    return a + b

def multiply_numbers(a, b):
    return a * b

def subtract_numbers(a, b):
    return a - b

def run_agent(user_message):
    messages = [
        {
            "role": "system",
            "content": """You are a calculator assistant.
IMPORTANT RULES:
- Call only ONE tool at a time
- Wait for the result before calling the next tool
- Never pass a function call as an argument to another function
- Only pass plain numbers as arguments
- Break multi-step problems into sequential single tool calls"""
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    print(f"\n USER: {user_message}")
    print("─" * 40)

    while True:
        # import json
        # print("JSON Before API Call:", json.dumps({
        #     "messages": messages,
        #     "tools": tools
        # }, indent=2))

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message

        print(f" LLM DECIDED: {message.content}")

        if message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f" LLM DECIDED: call {tool_name} with {tool_args}")

                for key, val in tool_args.items():
                    if not isinstance(val, (int, float)):
                        raise ValueError(f"Expected number for {key}, got {type(val)}: {val}")

                if tool_name == "add_numbers":
                    result = add_numbers(**tool_args)
                elif tool_name == "multiply_numbers":
                    result = multiply_numbers(**tool_args)
                elif tool_name == "subtract_numbers":
                    result = subtract_numbers(**tool_args)
                else:
                    result = f"Unknown tool: {tool_name}"

                print(f" TOOL RESULT: {result}")

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })

        else:
            print(f"\n FINAL ANSWER: {message.content}")
            return message.content

run_agent("What is 15 + 27, whole multiplied by 3, and subtract by 10?")