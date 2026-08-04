from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import asyncio
import httpx # Required to catch the specific HTTPStatusError

#from location import find_coordinate
from pydantic import BaseModel, Field

load_dotenv()

    
model = ChatGoogleGenerativeAI(
    model='gemini-2.5-flash', 
    temperature=0.1,
    max_tokens=1000,
)

system_prompt = (
    "You are the 'CostWise' AI, a trip budget specialist. "
    "1. TOOLS: Sequentially lookup 3 best match flights, then 3 best match hotels, "
    "and finally all best and popular local activities/tours for the destination with their charges." # New Requirement
    "2. BUDGET MODES: Tailor all results (flights, hotels, activities) to 'Low', 'Medium', or 'High'. "
    "3. CURRENCY: Use convert_currency_tool for all prices if requested. "
    "4. OUTPUT: Provide a detailed breakdown (Flights, Hotels, Activities) and 'Estimated Grand Total' in a Markdown table."
    "5. NOTE: Do not provide any addational information or facts."
)

class CurrencyArgs(BaseModel):
    from_currency : str = Field(description="The source currency code (e.g. 'USD')")
    to_currency : str = Field(description="The target currency code (e.g. 'IND')")
    amount : float = Field(description="The numneric amount to convert")

# Define a retry decorator for HTTPStatusError
@retry(
    stop=stop_after_attempt(5), # Try up to 5 times
    wait=wait_fixed(2),         # Wait 2 seconds between retries
    retry=retry_if_exception_type(httpx.HTTPStatusError) # Only retry on HTTPStatusError
)

async def get_mcp_tools_with_retry(client: MultiServerMCPClient):
    return await client.get_tools()

@retry(
    stop=stop_after_attempt(5), # Try up to 5 times
    wait=wait_fixed(2),         # Wait 2 seconds between retries
    retry=retry_if_exception_type(httpx.HTTPStatusError) # Only retry on HTTPStatusError
)
async def invoke_mcp_tool_with_retry(tool_instance, payload):
    return await tool_instance.ainvoke(payload)

async def main(from_city: str | None, to_city: str | None, no_of_people: str | None, no_of_rooms: str | None, check_in: str | None, check_out: str | None, budget: str | None, currency: str | None) -> str | None:
    """Generate the budget of the trip according to our input using MCP servers and LLM model.

    Args:
        from_city (str): Departure City of the trip
        to_city (str): Destination City of the trip
        no_of_people (str): Number of People in the trip
        no_of_rooms (str): Number of Rooms required in Hotel
        check_in (str): Check In Date
        check_out (str): Check Out Date
        budget (str): Mode of the Budget
        currency (str): Target Curreny

    Returns:
        str: Response from the LLM model according to our input
    """
    query = (
           f"I need a full budget for a trip from {from_city} to {to_city}." 
           f"Logistics: {no_of_people} persons, {no_of_rooms} rooms. Check-in: {check_in}, Check-out: {check_out}."
           f"Budget Mode: '{budget}'"
           f"Currency: Convert all USD prices to {currency}."
           "Output: Provide a markdown table with a detailed breakdown of flights, hotels and all the activities followed by an 'Estimated Grand Total' in INR."
           )
    try:
        # tool with the help of MCP 
        # kiwi MCP server for getting the information about flight
        flight_client = MultiServerMCPClient(
            {
                "flight-search":{
                    "transport": "streamable_http",
                    "url": "https://mcp.kiwi.com"
                }
            }
        )

        # 1stay MCP server to get the hotel details.
        hotel_client = MultiServerMCPClient(
            {
                "gondola": {
                    "transport": "streamable_http",
                    "url": "https://mcp.gondola.ai/mcp"
                }
            }
        )

        currency_client = MultiServerMCPClient(
            {
                "frankfurther":{
                    "transport": "streamable_http",
                    "url": "https://mcp.frankfurter.dev/"
                }
            }
        )

        search_client = MultiServerMCPClient(
            {
            "web-search": {
                "transport": "streamable_http",                     # or "streamable_http"
                "url": "https://search.parallel.ai/mcp", # Cloud endpoint URL
                "headers": {}                            # Empty dictionary because it's free/keyless!
            }
        }
        )

        # getting the flight search tool from kiwi mcp server
        flight_tools_list = await get_mcp_tools_with_retry(flight_client)
        flight_search_tool = flight_tools_list[0]

        # getting the hotel search tool from 1stay mcp server
        hotel_tools_list = await get_mcp_tools_with_retry(hotel_client)
        hotel_search_tool = hotel_tools_list[0]

        # getting current currency tool from frankfuther mcp server.
        currency_tools_list = await get_mcp_tools_with_retry(currency_client)
        convert_currency_tool = currency_tools_list[1]

        # getting web search tool from web-serach mcp server.
        search_tools_list = await get_mcp_tools_with_retry(search_client)
        web_search_tool = search_tools_list[0] # Assuming web_search_list contains at least one tool

        @tool(args_schema=CurrencyArgs)
        async def convert_currency(from_currency: str, to_currency: str, amount: float):
            """Use this tool to convert amounts between different currencies."""
            payload = {
                "from": from_currency,
                "to": to_currency,
                "amount": amount
            }
            return await invoke_mcp_tool_with_retry(convert_currency_tool, payload)
        
        all_tools = [flight_search_tool, hotel_search_tool, convert_currency, web_search_tool]

        agent = create_agent(
            model=model,
            system_prompt=system_prompt,
            tools=all_tools,
        )

        response = await agent.ainvoke(
            {"messages": [HumanMessage(content=query)]}
        )

        #print(f"[SYSTEM] {response}")
        print("-"*50)
        # Get the raw content from the last message
        last_message_content = response["messages"][-1].content
        
        # FIX: Check if the content is wrapped in a list/dict structure
        if isinstance(last_message_content, list) and len(last_message_content) > 0:
            # Safely grab the text key from the first content block dictionary
            first_block = last_message_content[0]
            if isinstance(first_block, dict) and "text" in first_block:
                return first_block["text"]
                
        # Fallback if it's already a standard string or in an unexpected format
        return str(last_message_content)
    
    except Exception as e:
        return f"Some error occur! Detail : {str(e)}"
"""
if __name__ == "__main__":
    result = asyncio.run(main=main())
    print(result)"""