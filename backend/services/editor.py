import json

from schemas.research import ResearchResult
from schemas.outputs import FinalStory
from services.google import execute_query

async def edit_story(research: ResearchResult) -> FinalStory:
    prompt = f"""
        You are the editor for a short-form news platform designed for
        Gen Z readers who want to understand what is happening quickly.

        Your job is to turn the provided research into a concise,
        engaging news story.

        RESEARCH:
        {research}

        This is a short-form card, not an article — every field below has a
        hard character limit, so write tightly from the start rather than
        composing a longer version and trimming it.

        Write:

        HEADLINE:
        A clear, interesting headline that tells the reader what the
        story is about. Maximum 60 characters.

        SUMMARY:
        One sentence that explains the story at a glance.
        A reader should understand the basic situation from this alone.
        Maximum 110 characters.

        KEY POINTS:
        3-5 short bullet points containing the most important facts.
        Each point should be concise and easy to scan. Maximum 90
        characters each.

        SOURCES:
        Include only the sources that you actually used.

        STYLE:
        - Be concise.
        - Prioritize clarity over completeness.
        - Assume the reader has little or no prior knowledge of the story.
        - Use plain, conversational language.
        - Make the important information immediately obvious.
        - Avoid unnecessary background information.
        - Do not write a traditional long-form news article.
        - Do not use excessive slang, memes, emojis, or forced Gen-Z language.
        - Do not sacrifice accuracy for entertainment.

        ACCURACY:
        - Use ONLY information contained in the research.
        - Do not introduce new facts.
        - Do not speculate.
        - Do not make predictions unless they are explicitly supported
        by the research.
        - Do not present opinions as facts.
        - Every factual claim must be supported by the provided research.
        """
    response = await execute_query(prompt, FinalStory)
    # model_construct, not model_validate_json: the schema's max_length
    # constraints are sent to Gemini as real generation limits and usually
    # keep output in budget, but it's not a 100% guarantee. Skipping
    # re-validation here means an occasional few-characters-over response
    # still comes through instead of hard-failing the whole request.
    return FinalStory.model_construct(**json.loads(response.text))