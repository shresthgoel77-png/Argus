import re
from enum import Enum

class BotIntent(Enum):
    ci_status = "ci_status"
    pr_summary = "pr_summary"
    repo_attention = "repo_attention"
    issue_explain = "issue_explain"
    unknown = "unknown"

def classify_intent(question_text: str, is_pull_request: bool) -> BotIntent:
    if not isinstance(question_text, str) or not question_text.strip():
        return BotIntent.unknown
        
    text = question_text.lower()
    
    def has_kw(kws):
        for kw in kws:
            if kw == "ci":
                if re.search(r'\bci\b', text):
                    return True
            elif kw in text:
                return True
        return False
        
    if has_kw(["summarize", "summary"]):
        if is_pull_request:
            return BotIntent.pr_summary
        return BotIntent.unknown
        
    if has_kw(["ci", "failing", "build", "pipeline", "workflow"]):
        return BotIntent.ci_status
        
    if has_kw(["attention", "what needs", "priorit"]):
        return BotIntent.repo_attention
        
    if has_kw(["explain"]):
        return BotIntent.issue_explain
        
    return BotIntent.unknown
