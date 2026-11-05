import time
from functools import lru_cache
from config import get_settings
from google import genai
from google.genai import types
from pydantic import BaseModel
from services.usage import record_call

@lru_cache
def get_client() -> genai.Client:
    return genai.Client(api_key = get_settings().google_api_key)

# Both functions use the client's async API (client.aio). The plain
# client.models.* calls are synchronous, so calling them from these async
# functions blocked the whole event loop for the length of the request —
# one user's In Terms generation stalled every other API request.

DEFAULT_MODEL = "gemini-3.5-flash-lite"

async def execute_query(
    prompt: str,
    schema: type[BaseModel],
    model: str = DEFAULT_MODEL,
) -> types.GenerateContentResponse:
    start = time.perf_counter()
    response = await get_client().aio.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": schema,
            # No tools are passed, so automatic function calling is unused —
            # disabling it also stops the SDK logging about it on every call.
            "automatic_function_calling": {"disable": True},
        },
    )

    usage = response.usage_metadata
    record_call(
        "llm",
        # The schema name doubles as a step label (ResearchPlan, FinalStory,
        # InTermsResult...), so cost breaks down by pipeline stage for free.
        schema.__name__,
        time.perf_counter() - start,
        input_tokens=(usage.prompt_token_count or 0) if usage else 0,
        # Thinking tokens are billed as output.
        output_tokens=(
            (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
            if usage else 0
        ),
    )

    return response

async def create_embedding(text: str) -> types.EmbedContentResponse:
    start = time.perf_counter()
    response = await get_client().aio.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config={
            "output_dimensionality": 768,
        },
    )
    record_call("embedding", "embed_dynamics", time.perf_counter() - start)

    return response
