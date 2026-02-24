# LLM Provider (vertex_ai or anthropic)
LLM_PROVIDER=vertex_ai

# Vertex AI (for production)
GOOGLE_CLOUD_PROJECT=ai-innov-474401
GOOGLE_CLOUD_LOCATION=asia-southeast1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json

# Tavily
TAVILY_API_KEY=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

# Gamma (optional for MVP)
GAMMA_API_KEY=sk-gamma-hflkS65h5JJG9DdnjwJaMonFYPyOXxBQanAfWdbg4\

# Storage
UPLOAD_DIR=./uploads

# State Persistence
STATE_STORAGE=memory  # memory, sqlite, or postgres

# Model Selection (for Vertex AI)
# Options: gemini-2.0-flash-exp (fastest, latest), gemini-1.5-pro-002 (most capable), gemini-1.5-flash-002 (balanced)
VERTEX_MODEL_NAME=gemini-2.5-flash
