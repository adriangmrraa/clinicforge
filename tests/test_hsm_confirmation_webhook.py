import re
from pathlib import Path

def test_confirm_buttons_synonyms():
    # Read orchestrator_service/routes/chat_webhooks.py and extract _CONFIRM_BUTTONS content
    webhook_file = Path(__file__).parent.parent / "orchestrator_service" / "routes" / "chat_webhooks.py"
    content = webhook_file.read_text(encoding="utf-8")
    
    # Locate _CONFIRM_BUTTONS block
    match = re.search(r"_CONFIRM_BUTTONS\s*=\s*\{([^}]+)\}", content)
    assert match is not None, "Could not locate _CONFIRM_BUTTONS in chat_webhooks.py"
    
    buttons_text = match.group(1)
    
    # Extract all single/double quoted strings inside _CONFIRM_BUTTONS block
    buttons = set(re.findall(r'"([^"]+)"|\'([^\']+)\'', buttons_text))
    # Flatten the tuple results from findall
    buttons = {b for t in buttons for b in t if b}
    
    expected_synonyms = {
        "conservo", "asisto", "voy", "acepto", "confirmo",
        "conservo ✅", "asisto ✅", "voy ✅", "acepto ✅", "confirmo ✅",
        "sí, voy", "si, voy", "sí, asisto", "si, asisto", "si, confirmo", "sí, confirmo"
    }
    
    for syn in expected_synonyms:
        assert syn.lower() in buttons, f"Synonym '{syn}' missing from _CONFIRM_BUTTONS"
