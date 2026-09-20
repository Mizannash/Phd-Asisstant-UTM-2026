# Centralized Configuration

# For CrewAI (uses LiteLLM which expects the gemini/ prefix)
CREWAI_PRIMARY_MODEL = "gemini/gemini-3.6-flash"
CREWAI_FALLBACK_MODEL = "gemini/gemini-3.5-flash-lite"

# For LangChain (ChatGoogleGenerativeAI) and direct REST API calls
LANGCHAIN_PRIMARY_MODEL = "gemini-3.6-flash"
