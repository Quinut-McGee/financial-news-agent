import re
from nearai.agents.environment import Environment
from functions.pdf_processor import check_and_process_new_pdfs
from functions.category_manager import show_category_headlines, generate_category_summary
from functions.summarizer import summarize_specific_article

async def run(env: Environment):
    """Main entry point for the agent."""
    try:
        messages = env.list_messages()
        is_first_message = len(messages) <= 1
        
        # For first interaction, give welcome and process PDFs if needed
        if is_first_message:
            env.add_reply("Welcome to Daily Bread - your personal macroeconomic advisor. Ask me what is the latest on inflation, stocks, bonds, commodities, infrastructure, real estate, energy, or general news, and we'll go from there!")
            
            # Process any new PDFs
            pdf_processed = check_and_process_new_pdfs(env)
            if pdf_processed:
                env.add_reply("\nI've analyzed the latest financial publications and updated my knowledge base.")
                from vector.vector_store import vector_store
                await vector_store.update_store()
        
        # Define available categories
        categories = {
            "stocks": "Stocks",
            "bonds": "Bonds",
            "commodities": "Commodities",
            "infrastructure": "Infrastructure",
            "real estate": "Real Estate",
            "energy": "Energy",
            "inflation": "Inflation",
            "general": "General"
        }
        
        # Process user input for subsequent messages
        if not is_first_message:
            query = messages[-1]["content"].lower()
            
            # Check for article read request
            article_match = re.search(r'read article (\d+)', query)
            if article_match:
                article_id = int(article_match.group(1))
                await summarize_specific_article(env, article_id)
                return
            
            # Check for headlines request - FIXED REGEX HERE
            headlines_match = re.search(r'show articles about (.+)', query)
            if headlines_match:
                category = headlines_match.group(1).strip().lower()
                # Handle multi-word categories like "real estate"
                if category in categories:
                    show_category_headlines(env, category)
                    return
            
            # Check if user is asking about available categories
            if any(word in query for word in ["categories", "options", "what can you", "help"]):
                response = """As your macroeconomic advisor, I can provide analysis on:

- **Stocks**: Equity market trends, major movers, and sector performance
- **Bonds**: Fixed income markets, yield curves, and credit conditions
- **Commodities**: Raw materials pricing, supply/demand dynamics, and futures
- **Infrastructure**: Public works, development projects, and construction activity
- **Real Estate**: Housing markets, commercial property, and mortgage trends
- **Energy**: Oil, gas, renewables, and energy policy developments
- **Inflation**: Price trends, monetary policy, and purchasing power analysis
- **General Markets**: Broad financial and economic concepts

You can:
1. Request market analysis (e.g., "What's happening with stocks?")
2. View headlines in a category (e.g., "Show articles about inflation")
3. Read specific articles by ID (e.g., "Read article 12")

What financial insights would you like today?"""
                env.add_reply(response)
                return
            
            # Try to match query to a category
            matched_category = None
            for key, value in categories.items():
                if key in query:
                    matched_category = value  # Use the value for summary generation
                    break
            
            if matched_category:
                await generate_category_summary(env, matched_category)
            else:
                env.add_reply("I can provide macroeconomic analysis on: Stocks, Bonds, Commodities, Infrastructure, Real Estate, Energy, Inflation, or general financial concepts. Which market would you like insights on?")
    
    except Exception as e:
        env.add_reply(f"I encountered an unexpected issue: {str(e)}")
        env.add_reply("How can I assist with your financial analysis today?")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run(env))