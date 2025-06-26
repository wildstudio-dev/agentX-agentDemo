from react_agent.prompts import REPC_ANALYSIS_PROMPT

def is_repc(text):
    return "repc" in text.lower() or "real estate purchase contract" in text.lower()


def get_repc_message():
    return [{
        "type": "text",
        "text": f"{REPC_ANALYSIS_PROMPT}"
    }]


def has_custom_handling(text):
    # TODO: Extend with the special documents
    return is_repc(text)


def get_custom_messages(text):
    if is_repc(text):
        return get_repc_message()
    return []