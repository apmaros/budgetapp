from dataclasses import dataclass
from app.util import current_time_sec


@dataclass
class MonzoToken:
    access_token: str
    client_id: str
    expires_in_sec: int
    refresh_token: str
    token_type: str
    user_id: str
    account_id: str
    created_at_sec: str = current_time_sec()
