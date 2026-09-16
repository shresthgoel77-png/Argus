import pytest
from app.bot.question_parser import classify_intent, BotIntent

def test_classify_pr_summary():
    assert classify_intent("can you summarize this PR?", True) == BotIntent.pr_summary
    assert classify_intent("give me a summary please", True) == BotIntent.pr_summary

def test_classify_pr_summary_downgrades_on_issue():
    assert classify_intent("can you summarize this PR?", False) == BotIntent.unknown

def test_classify_ci_status():
    assert classify_intent("why is CI failing?", True) == BotIntent.ci_status
    assert classify_intent("check the build", False) == BotIntent.ci_status
    assert classify_intent("workflow status", True) == BotIntent.ci_status

def test_classify_repo_attention():
    assert classify_intent("what needs attention?", False) == BotIntent.repo_attention
    assert classify_intent("what is the top priority?", True) == BotIntent.repo_attention

def test_classify_issue_explain():
    assert classify_intent("please explain the issue", False) == BotIntent.issue_explain
    assert classify_intent("explain this code", True) == BotIntent.issue_explain
    
def test_classify_unknown():
    assert classify_intent("hello there", True) == BotIntent.unknown
    assert classify_intent("do some magic", False) == BotIntent.unknown

def test_ci_keyword_boundary():
    # 'ci' shouldn't match mid-word like 'decision'
    assert classify_intent("what is the decision?", True) == BotIntent.unknown
