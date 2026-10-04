from backend.automation.actions import execute_calendar_action


def apply_approved_action(user_id, action):
    """Final automation gate. Only confirmed UI actions should call this."""
    return execute_calendar_action(user_id, action)
