"""
Request/Response Domain Model

Defines data structures related to proxy requests and responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ProxyRequest:
    """
    Proxy Request Data Class
    
    Encapsulates request information sent by the client.
    """
    
    # Request Path (e.g., /v1/chat/completions)
    path: str
    # HTTP Method
    method: str
    # Request Headers
    headers: dict[str, str]
    # Request Body
    body: dict[str, Any]
    # Protocol Type (openai / anthropic)
    protocol: str
    # API Key ID
    api_key_id: int
    # API Key Name
    api_key_name: str
    # Trace ID
    trace_id: str
    # Request Time
    request_time: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def requested_model(self) -> Optional[str]:
        """Get requested model name"""
        return self.body.get("model")
    
    @property
    def is_stream(self) -> bool:
        """Is stream request"""
        return self.body.get("stream", False)


@dataclass
class ProxyResponse:
    """
    Proxy Response Data Class
    
    Encapsulates forwarded response information.
    """
    
    # HTTP Status Code
    status_code: int
    # Response Headers
    headers: dict[str, str]
    # Response Body (Non-stream)
    body: Any
    # Target Model Name
    target_model: str
    # Provider ID
    provider_id: int
    # Provider Name
    provider_name: str
    # Retry Count
    retry_count: int = 0
    # First Byte Delay (ms)
    first_byte_delay_ms: Optional[int] = None
    # Total Time (ms)
    total_time_ms: Optional[int] = None
    # Input Token Count
    input_tokens: Optional[int] = None
    # Output Token Count
    output_tokens: Optional[int] = None
    # Error Info
    error_info: Optional[str] = None
    # Success Status
    success: bool = True
    
    @property
    def is_error(self) -> bool:
        """Is error response"""
        return not self.success or self.status_code >= 400


@dataclass
class CandidateProvider:
    """
    Candidate Provider Data Class
    
    Candidate provider information output after rule engine matching.
    """
    
    # Provider ID
    provider_id: int
    # Provider Name
    provider_name: str
    # Provider Base URL
    base_url: str
    # Provider Protocol
    protocol: str
    # Provider API Key
    api_key: Optional[str]
    # Target Model Name (Actual model corresponding to this provider)
    target_model: str
    # Priority
    priority: int = 0
    # Weight
    weight: int = 1