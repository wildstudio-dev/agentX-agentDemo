import logging

from openai import AsyncOpenAI

client = AsyncOpenAI()

async def aembed_texts(texts: list[str]) -> list[list[float]]:
    """Custom embedding function that must:
    1. Be async
    2. Accept a list of strings
    3. Return a list of float arrays (embeddings)
    """
    # logging.info("Embedding texts: %s", texts)
    logging.info("Embedding texts len: %s", texts)
    logging.info("Embedding texts len: %s", len(texts))
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [e.embedding for e in response.data]