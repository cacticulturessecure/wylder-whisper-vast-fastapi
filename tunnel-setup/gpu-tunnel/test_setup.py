# test_setup.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import asyncio
import logging
from datetime import datetime
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tunnel_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('tunnel-test')

# Server Configuration
class Settings:
    HOST = "127.0.0.1"
    PORT = 8000
    DEBUG = True

settings = Settings()

# FastAPI Setup
app = FastAPI(title="Tunnel Test API")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Models
class TestMessage(BaseModel):
    content: str
    timestamp: str = None

class TestResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    echo: str = None

# API Endpoints
@app.get("/")
async def root():
    return {"status": "running", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "tunnel-test"
    }

@app.post("/echo")
async def echo_message(message: TestMessage):
    logger.info(f"Received message: {message.content}")
    return TestResponse(
        status="success",
        message="Message received",
        timestamp=datetime.utcnow().isoformat(),
        echo=message.content
    )

# Main execution
if __name__ == "__main__":
    try:
        logger.info(f"Starting test server on {settings.HOST}:{settings.PORT}")
        uvicorn.run(
            "test_setup:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)
