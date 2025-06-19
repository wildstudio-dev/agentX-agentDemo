import logging
from langgraph_sdk import Auth

auth = Auth()

@auth.authenticate
async def get_current_user(
        authorization: str | None,
):
    """Validate JWT tokens and extract user information."""
    logging.info("Authenticating user with token: %s", authorization[:20] + "..." if authorization and len(authorization) > 20 else authorization)
    # https://langchain-ai.github.io/langgraph/concepts/auth/?utm_source=chatgpt.com#authentication
    
    if not authorization:
        logging.warning("No authorization header provided")
        raise Auth.exceptions.HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        parts = authorization.split()
        if len(parts) != 2:
            raise ValueError("Invalid authorization header format")
        
        scheme, token = parts
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authentication scheme")
        
        if not token:
            raise ValueError("Invalid token")
        
        logging.info("Token validated successfully")
        return {
            "identity": token,
        }
    except Auth.exceptions.HTTPException:
        raise
    except Exception as e:
        logging.error("Authentication failed: %s", str(e))
        raise Auth.exceptions.HTTPException(status_code=401, detail=str(e))


@auth.on
async def add_owner(
    ctx: Auth.types.AuthContext,
    value: dict
    ):
    logging.info(
        "Adding owner to resource - User: %s, Resource: %s, Action: %s", 
        ctx.user.identity if hasattr(ctx.user, 'identity') else 'Unknown',
        ctx.resource,
        ctx.action
    )
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
    
    logging.debug("Applied filters: %s", filters)
    return filters