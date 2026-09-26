from typing import Optional
from pydantic import BaseModel, ConfigDict


class OnrampSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    destinationAddress: str
    appUserId: Optional[str] = None

    @property
    def destination_address(self) -> str:
        return self.destinationAddress

    @property
    def app_user_id(self) -> Optional[str]:
        return self.appUserId


class OnrampSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sessionToken: Optional[str] = None
    sessionId: Optional[str] = None
    widgetUrl: str
    destinationWallet: str
    expiresAt: Optional[str] = None
    traceId: Optional[str] = None

    def __init__(
        self,
        widget_url: Optional[str] = None,
        destination_wallet: Optional[str] = None,
        session_token: Optional[str] = None,
        session_id: Optional[str] = None,
        expires_at: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            widgetUrl=widget_url if widget_url is not None else kwargs.get("widgetUrl", ""),
            destinationWallet=destination_wallet if destination_wallet is not None else kwargs.get("destinationWallet", ""),
            sessionToken=session_token if session_token is not None else kwargs.get("sessionToken"),
            sessionId=session_id if session_id is not None else kwargs.get("sessionId"),
            expiresAt=expires_at if expires_at is not None else kwargs.get("expiresAt"),
            traceId=trace_id if trace_id is not None else kwargs.get("traceId"),
        )
