def parse_telegram_update(update: dict):
    """
    Parses an incoming Telegram webhook update.
    Returns a dictionary with message details or None if not a group message.
    """
    if "message" not in update:
        return None
        
    message = update["message"]
    text = message.get("text", "")
    
    if not text:
        return None # ignore photos, stickers, etc. for now
        
    msg_id = message.get("message_id")
    user = message.get("from", {})
    username = user.get("username") or user.get("first_name", "Anonymous")
    
    return {
        "telegram_msg_id": msg_id,
        "username": username,
        "text": text
    }
