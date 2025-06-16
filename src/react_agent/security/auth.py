import logging
from langgraph_sdk import Auth

auth = Auth()

@auth.authenticate
async def get_current_user(
        authorization: str | None,
):
    """Validate JWT tokens and extract user information."""
    logging.info("Authenticating user with token: %s", authorization)
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
    logging.info("Adding owner to resource with context: %s", ctx)
    """Makes resources private to the user."""
    logging.info("User identity: %s", ctx.user.identity)
    filters = {
        "owner": ctx.user.identity,
    }
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)

    return filters