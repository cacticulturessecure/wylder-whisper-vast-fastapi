# test_client.py
import requests
import time
import logging
from datetime import datetime
import sys
import json
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('test-client')

class TunnelTester:
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
    
    def check_health(self) -> Dict[str, Any]:
        """Check if the server is healthy"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def test_echo(self, message: str) -> Dict[str, Any]:
        """Send a test message and get echo response"""
        try:
            data = {
                "content": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            response = self.session.post(
                f"{self.base_url}/echo",
                json=data,
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Echo test failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def run_tests(self, num_tests: int = 5, delay: float = 1.0):
        """Run a series of tests"""
        logger.info(f"Starting test sequence ({num_tests} tests)")
        
        # Initial health check
        health = self.check_health()
        if health.get("status") != "healthy":
            logger.error("Initial health check failed")
            return False

        successful = 0
        failed = 0

        for i in range(num_tests):
            logger.info(f"Running test {i+1}/{num_tests}")
            
            result = self.test_echo(f"Test message {i+1}")
            if result.get("status") == "success":
                successful += 1
                logger.info(f"Test {i+1} successful")
            else:
                failed += 1
                logger.error(f"Test {i+1} failed")

            if i < num_tests - 1:
                time.sleep(delay)

        logger.info(f"Test sequence complete. Success: {successful}, Failed: {failed}")
        return successful, failed

if __name__ == "__main__":
    num_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    tester = TunnelTester()
    successful, failed = tester.run_tests(num_tests)
    
    sys.exit(1 if failed > 0 else 0)
