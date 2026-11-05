from schemas.rss import RSSResult
from schemas.research import ResearchExecutionSteps, ResearchDecision, ResearchPlan, ResearchQuestionAssessment, ResearchResult
from services.search import search_web
from services.google import execute_query

# Each search costs a Tavily credit and re-sends all evidence so far to the
# next LLM step. Measured: the agent used every search it was given (it never
# declared itself done early), so this cap is the main cost lever.
MAX_SEARCHES = 2

async def research_article(article: RSSResult) -> ResearchExecutionSteps:
    plan = await create_research_plan(article)
    step = ResearchExecutionSteps(
        article=article,
        questions = plan.questions
    )

    for _ in range(MAX_SEARCHES):
        decision = await get_next_search(step)

        if decision.done:
            break

        query = decision.query.strip().lower()

        if query in (previous.strip().lower() for previous in step.searches):
            break

        results = await search_web(decision.query)

        step.searches.append(decision.query)
        step.sources.extend(results)

        assessment = await assess_research_question(decision.question, step)

        if assessment.answered:
            step.answered_questions.append(decision.question)

        # print(step)

    return step
    # return await synthesize_search(step)


async def create_research_plan(article: RSSResult) -> ResearchPlan:
    prompt = f"""
                You are planning research for a news story.

                Your goal is to identify the key factual questions that must
                be answered before an editor can accurately explain this story.

                ARTICLE:
                Title: {article.title}
                Source: {article.source}
                Summary: {article.summary}

                Generate 3-6 specific research questions.

                Focus on:
                - what happened
                - important factual details
                - relevant context
                - what happens next
                - information necessary for a reader to understand why the story matters

                Do not write the story.
                Do not answer the questions.
                Only identify the questions that need to be researched.
                """
    response = await execute_query(prompt, ResearchPlan)
    return ResearchPlan.model_validate_json(response.text)

async def get_next_search(step: ResearchExecutionSteps) -> ResearchDecision:
    prompt = await build_research_prompt(step)
    response = await execute_query(prompt, ResearchDecision)
    return ResearchDecision.model_validate_json(response.text)

async def build_research_prompt(step: ResearchExecutionSteps) -> str:
    questions = '\n'.join(f"- {question}" for question in step.questions)
    previous_searches = '\n'.join(f"- {search}" for search in step.searches)
    previous_sources = '\n'.join(f"- {source.source.title}: {source.content}" for source in step.sources)
    answered_questions = '\n'.join(f"- {answered_question}" for answered_question in step.answered_questions)

    return f"""
            You are a news research agent.

            Your job is to gather reliable evidence needed to answer
            the research questions for a news story.

            ARTICLE:
            Title: {step.article.title}
            Source: {step.article.source}

            RESEARCH QUESTIONS:
            {questions}

            QUESTIONS ALREADY ANSWERED:
            {answered_questions or "None"}

            PREVIOUS SEARCHES:
            {previous_searches or "None"}

            EVIDENCE FOUND:
            {previous_sources or "None"}

            Choose the single most important unanswered research question.

            Generate ONE precise search query designed to find reliable
            information that helps answer that question.

            If all important questions have sufficient evidence,
            mark the research as complete.

            Do not choose a question that is already answered.
            Do not repeat previous searches.
            Do not invent information.
            Prefer primary and reputable sources.
            """

async def assess_research_question(question: str, step: ResearchExecutionSteps) -> ResearchQuestionAssessment:
     prompt = f"""
                You are evaluating evidence collected for a news research task.

                ARTICLE:
                Title: {step.article.title}
                Summary: {step.article.summary}

                RESEARCH QUESTION:
                {question}

                EVIDENCE:
                {step.sources}

                Determine whether the evidence collected so far is sufficient
                to answer the research question accurately.

                Be conservative. If the evidence is incomplete, ambiguous,
                contradictory, or only indirectly relevant, mark the question
                as unanswered.

                Return:
                - answered: true or false
                - reasoning: a brief explanation

                Do not invent facts.
                """
     response = await execute_query(prompt, ResearchQuestionAssessment)
     return ResearchQuestionAssessment.model_validate_json(response.text)

async def synthesize_search(step: ResearchExecutionSteps) -> ResearchResult:
    questions = '\n'.join(f"- {question}" for question in step.questions)
    previous_sources = '\n'.join(f"- {source.source.title}: {source.content}" for source in step.sources)
    answered_questions = '\n'.join(f"- {answered_question}" for answered_question in step.answered_questions)
    prompt = f"""
                You are a news research synthesizer.

                Your job is to summarize the reliable information discovered
                during the research process into a structured research result.

                ARTICLE:
                Title: {step.article.title}
                Summary: {step.article.summary}

                RESEARCH QUESTIONS:
                {questions}

                ANSWERED QUESTIONS:
                {answered_questions}

                EVIDENCE:
                {previous_sources}

                Extract:

                FACTS:
                Concrete factual claims that are directly supported by the
                evidence.

                CONTEXT:
                Background information that helps a reader understand the
                facts and why the story matters.

                SOURCES:
                Include the sources that directly support the facts or
                context you extracted.

                Rules:
                - Only include information supported by the evidence.
                - Do not invent or infer facts.
                - Do not include unsupported speculation.
                - Prefer information supported by reputable or primary sources.
                - Keep facts concise and specific.
                - Do not write the final news story.
                - Do not include a source merely because it appeared in search results. Include it only if you actually used information from that source in the resulting facts or context.
                - Do not include irrelevant facts simply because they appeared in a source.
                """
    response = await execute_query(prompt, ResearchResult)
    return ResearchResult.model_validate_json(response.text)