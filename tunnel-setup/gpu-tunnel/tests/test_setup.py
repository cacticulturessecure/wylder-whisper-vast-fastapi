# Update test_setup.py on GPU server
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import uvicorn
import logging

# Add this class for message structure
class TestMessage(BaseModel):
    message: str
    timestamp: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "tunnel-test"
    }

@app.post("/test")  # Changed to POST and added proper response
async def test_endpoint(message: TestMessage):
    return {
        "status": "success",
        "received": message.message,
        "server_time": datetime.utcnow().isoformat(),
        "client_time": message.timestamp
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
