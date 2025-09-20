# Daily Bread - Financial News Agent

## Description
Daily Bread is your personal macroeconomic advisor, designed to transform overwhelming market news into accessible insights. This agent processes the latest financial publications, categorizes articles, and provides comprehensive narrative analyses and summaries to keep you informed on global financial developments. It's perfect for busy professionals who need to stay updated without spending hours reading.

## Functionality

*   **Financial News Digest**: Provides narrative summaries and analyses of financial news across various categories.
*   **PDF Processing**: Automatically detects and processes new PDF financial publications, extracting text, splitting it into articles, and categorizing them into relevant market sectors.
*   **Market Category Analysis**: Generates comprehensive narrative reports on specific market categories, such as Stocks, Bonds, Commodities, Infrastructure, Real Estate, Energy, Inflation, and General Markets.
*   **Headline Retrieval**: Displays the latest headlines for any specified market category.
*   **Article Summarization**: Provides detailed, story-like summaries of individual articles based on their unique ID, or displays the full content for shorter pieces.
*   **Knowledge Base Management**: Maintains and updates an internal knowledge base and an external vector store with processed article content for efficient retrieval and analysis.

## Inputs

*   **User Messages (Text)**: Users interact by sending text queries to request market analysis (e.g., "What's happening with stocks?"), view headlines (e.g., "Show articles about inflation"), or read specific articles (e.g., "Read article 12"). Users can also ask for available categories or help.
*   **PDF Files**: New PDF documents containing financial publications can be placed in a designated `pdfs` directory for the agent to process.
*   **User Provided Metadata**: During PDF processing, the agent prompts the user to input the source name and publication date for each new PDF.

## Outputs

*   **Text Replies (Chat)**: The agent responds with welcome messages, market analyses, article headlines, article summaries, and instructions or error messages directly in the chat interface.
*   **Processed Data (Files)**: Extracted articles are saved as text files, categorized into respective folders within the agent's dataset.
*   **Vector Store Updates**: The agent updates an external vector store with new article content, enhancing its ability to perform relevant searches and generate informed summaries.

## Environment Variables

*   **`NEARAI_API_URL`**: Specifies the base URL for the NEAR AI Hub API, used for accessing AI services.
*   **`NEARAI_AUTH`**: Provides the authentication token or API key required to access the NEAR AI Hub.