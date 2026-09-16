import pytest
from app.bot.mention_parser import extract_mention

def test_extract_mention_simple():
    assert extract_mention("@repomedic what is the status?") == "what is the status?"
    assert extract_mention("hey @repomedic, help me") == "help me"

def test_extract_mention_punctuation():
    assert extract_mention("@repomedic: tell me") == "tell me"
    assert extract_mention("@repomedic. yes") == "yes"

def test_extract_mention_no_mention():
    assert extract_mention("hello world") is None

def test_extract_mention_mid_word():
    assert extract_mention("john@repomedic.com") is None
    assert extract_mention("my@repomedic") is None
    assert extract_mention("@repomedic2 is bad") is None
    assert extract_mention("Check out @repomedic-test") is None

def test_extract_mention_in_code_block():
    body = "```\n@repomedic do this\n```"
    assert extract_mention(body) is None

    body_inline = "type `@repomedic do this` in chat"
    assert extract_mention(body_inline) is None

def test_extract_mention_in_quote():
    body = "> @repomedic do this\nNo thanks"
    assert extract_mention(body) is None
