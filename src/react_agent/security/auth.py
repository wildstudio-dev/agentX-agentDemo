import logging
from langgraph_sdk import Auth

auth = Auth()

@auth.authenticate
async def get_current_user(
        authorization: str | None,
):
    """Validate JWT tokens and extract user information."""
    logging.info("Authenticating user with token: %s", authorization)
    # https://langchain-ai.github.io/langgraph/concepts/auth/?utm_source=chatgpt.com#authentication
    assert authorization
    scheme, token = authorization.split()
    assert scheme.lower() == "bearer"

    try:
        if token:
            logging.info("Token found")
        else:
            raise ValueError("Invalid token")
        
        return {
            "identity": token,
        }
    except Exception as e:
        raise Auth.exceptions.HTTPException(status_code=401, detail=str(e))


@auth.on
async def add_owner(
    ctx: Auth.types.AuthContext,
    value: dict
    ):
    logging.info("Adding owner to resource with context: %s %s", ctx)
    """Makes resources private to the user."""
    # User id is set in the authentication is a good practice but we need to add the filtering
    # here as well
    # But when needed we should do it manually
    # https://langchain-ai.github.io/langgraph/concepts/auth/?utm_source=chatgpt.com#authorization
    filters = {
        "owner": ctx.user.identity,
    }
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)

    return filters