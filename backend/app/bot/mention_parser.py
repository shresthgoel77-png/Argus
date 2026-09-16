import re
from app.core.config import settings

def extract_mention(comment_body: str) -> str | None:
    """
    Extracts the text following a bot mention in a comment, if present.
    Returns None if the comment doesn't mention the bot.
    """
    if not comment_body:
        return None

    # Remove markdown blockquotes
    lines = comment_body.split('\n')
    unquoted_lines = [line for line in lines if not line.lstrip().startswith('>')]
    unquoted_body = '\n'.join(unquoted_lines)

    # Remove multi-line code blocks
    no_multi_code = re.sub(r'```.*?```', '', unquoted_body, flags=re.DOTALL)
    
    # Remove inline code blocks
    clean_body = re.sub(r'`[^`]*`', '', no_multi_code)

    handle = settings.bot_mention_handle.lower()
    escaped_handle = re.escape(handle)
    
    # The pattern looks for:
    # 1. Start of string or whitespace (?:^|\s)
    # 2. The handle (case-insensitive)
    # 3. Negative lookahead for word characters/hyphens to avoid mid-word matches
    # 4. Optional punctuation immediately following the handle
    # 5. Capture everything after as the command
    pattern = r'(?:^|\s)' + escaped_handle + r'(?![a-zA-Z0-9_\-])(?:[:,\.\s]*)(.*)'
    
    match = re.search(pattern, clean_body, flags=re.IGNORECASE | re.DOTALL)
    if match:
        extracted = match.group(1).lstrip()
        return extracted
        
    return None
