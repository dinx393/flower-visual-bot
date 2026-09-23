from app.agent.contracts import ReviewDecision, ReviewFeedback


def may_publish(feedback: ReviewFeedback | None) -> bool:
    """Only an explicit employee approval can release a file to Google Drive."""
    return bool(feedback and feedback.decision is ReviewDecision.APPROVED)
