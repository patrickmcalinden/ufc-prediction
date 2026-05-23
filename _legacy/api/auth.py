import os
from fastapi import Header, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(x_api_key: str = Security(api_key_header)):
    expected = os.getenv("BET_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="API key not configured on server")
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
