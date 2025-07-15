import logging
from google import genai
from google.genai import types

client = genai.Client()

# from openai import AsyncOpenAI
# client = AsyncOpenAI()

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Custom embedding function that must:
    1. Be async
    2. Accept a list of strings
    3. Return a list of float arrays (embeddings)
    """
    logging.info("Embedding texts len: %s", len(texts))
    # response = await client.embeddings.create(
    #     model="text-embedding-3-small",
    #     input=texts
    # )
    # return [e.embedding for e in response.data]

    response = client.models.embed_content(
        model="gemini-embedding-exp-03-07",
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=1536
        )
    )
    print(response)
    # print(len(response)
    return [e.values for e in response.embeddings]
