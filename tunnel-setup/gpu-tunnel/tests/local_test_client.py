# local_test_client.py
import requests
import time
from datetime import datetime
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('test-client')

def run_tests(num_tests=1):
    """Run a series of test requests"""
    url = "http://localhost:8000"
    
    # Test health endpoint
    logger.info("Testing health endpoint...")
    try:
        response = requests.get(f"{url}/health")
        if response.status_code == 200:
            logger.info(f"Health check successful: {response.json()}")
        else:
            logger.error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return False

    # Run test messages
    successful = 0
    for i in range(num_tests):
        try:
            test_data = {
                "message": f"Test message {i+1}",
                "timestamp": datetime.now(datetime.UTC).isoformat()
            }
            
            logger.info(f"Sending test {i+1}/{num_tests}")
            logger.info(f"Data: {test_data}")
            
            response = requests.post(
                f"{url}/test",
                json=test_data
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Test {i+1} successful:")
                logger.info(f"  Status: {result['status']}")
                logger.info(f"  Received: {result['received']}")
                logger.info(f"  Server time: {result['server_time']}")
                successful += 1
            else:
                logger.error(f"Test {i+1} failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Error in test {i+1}: {str(e)}")
            
        if i < num_tests - 1:
            time.sleep(1)
    
    logger.info(f"Tests completed: {successful}/{num_tests} successful")
    return successful == num_tests

if __name__ == "__main__":
    num_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    success = run_tests(num_tests)
    sys.exit(0 if success else 1)
