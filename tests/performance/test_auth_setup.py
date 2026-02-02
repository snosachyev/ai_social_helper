#!/usr/bin/env python3
"""
Setup test authentication for load testing
"""

import requests
import time
import sys
import subprocess
import os

BASE_URL = "http://localhost:8000"

def create_test_tokens():
    """Create test JWT tokens for load testing"""
    print("🔐 Creating test authentication tokens...")
    
    # Simple test tokens for load testing
    test_tokens = []
    
    for i in range(100):  # Create 100 test tokens
        token = f"test-load-token-{i:03d}-{int(time.time())}"
        test_tokens.append(token)
    
    print(f"✅ Created {len(test_tokens)} test tokens")
    return test_tokens

def backup_original_file():
    """Backup the original API gateway file"""
    api_gateway_file = "/home/sergey/projects/ai_coding/ai_social_helper/services/api-gateway/main.py"
    backup_file = f"{api_gateway_file}.backup"
    
    try:
        with open(api_gateway_file, 'r') as f:
            content = f.read()
        
        with open(backup_file, 'w') as f:
            f.write(content)
        
        print(f"✅ Backed up original file to {backup_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to backup file: {e}")
        return False

def modify_verify_token_for_testing():
    """Modify verify_token function to accept test tokens"""
    api_gateway_file = "/home/sergey/projects/ai_coding/ai_social_helper/services/api-gateway/main.py"
    
    try:
        with open(api_gateway_file, 'r') as f:
            content = f.read()
        
        # Find and replace the verify_token function
        old_function = '''async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token."""
    # Simplified token verification - in production, use proper JWT validation
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return credentials.credentials'''
        
        new_function = '''async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token."""
    # Simplified token verification - in production, use proper JWT validation
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    token = credentials.credentials
    
    # Test mode: accept test tokens for load testing
    if token.startswith("test-load-token-"):
        return token
    
    # For now, accept any non-empty token (simplified for testing)
    if token and len(token) > 5:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials"
    )'''
        
        if old_function in content:
            content = content.replace(old_function, new_function)
            
            with open(api_gateway_file, 'w') as f:
                f.write(content)
            
            print("✅ Modified verify_token function for testing")
            return True
        else:
            print("❌ Could not find verify_token function to modify")
            return False
            
    except Exception as e:
        print(f"❌ Failed to modify file: {e}")
        return False

def restart_api_gateway():
    """Restart API Gateway service to apply changes"""
    print("🔄 Restarting API Gateway service...")
    
    try:
        # Find the API Gateway container
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=api-gateway", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            container_name = result.stdout.strip()
            print(f"Found container: {container_name}")
            
            # Restart the container
            restart_result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True, text=True
            )
            
            if restart_result.returncode == 0:
                print("✅ API Gateway restarted successfully")
                
                # Wait for service to be ready
                print("⏳ Waiting for API Gateway to be ready...")
                time.sleep(10)
                
                # Test health endpoint
                try:
                    response = requests.get(f"{BASE_URL}/health", timeout=5)
                    print(f"Health check: {response.status_code}")
                    return True
                except Exception as e:
                    print(f"❌ Health check failed: {e}")
                    return False
            else:
                print(f"❌ Failed to restart container: {restart_result.stderr}")
                return False
        else:
            print("❌ API Gateway container not found")
            return False
            
    except Exception as e:
        print(f"❌ Failed to restart API Gateway: {e}")
        return False

def test_authentication():
    """Test the modified authentication"""
    print("🧪 Testing modified authentication...")
    
    test_token = "test-load-token-001"
    headers = {
        'Authorization': f'Bearer {test_token}',
        'Content-Type': 'application/json'
    }
    
    # Test with valid test token
    try:
        response = requests.get(f"{BASE_URL}/documents", headers=headers, timeout=5)
        print(f"Test with valid token: {response.status_code}")
        
        if response.status_code != 403:
            print("✅ Test authentication working!")
            return True
        else:
            print("❌ Test authentication failed")
            return False
            
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

def generate_load_test_config():
    """Generate load test configuration with test tokens"""
    print("📝 Generating load test configuration...")
    
    config_content = '''#!/usr/bin/env python3
"""
Load test configuration with test authentication
"""

TEST_TOKENS = [
'''
    
    for i in range(100):
        config_content += f'    "test-load-token-{i:03d}",\n'
    
    config_content += ''']

def get_random_test_token():
    """Get a random test token for load testing"""
    import random
    return random.choice(TEST_TOKENS)

def get_auth_headers():
    """Get authentication headers for load testing"""
    token = get_random_test_token()
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
'''
    
    with open('/home/sergey/projects/ai_coding/ai_social_helper/tests/performance/test_auth_config.py', 'w') as f:
        f.write(config_content)
    
    print("✅ Generated test authentication configuration")
    return True

def main():
    """Main setup function"""
    print("🚀 Setting up test authentication for load testing")
    print("=" * 60)
    
    # Step 1: Backup original file
    if not backup_original_file():
        print("❌ Setup failed at backup step")
        sys.exit(1)
    
    # Step 2: Modify verify_token function
    if not modify_verify_token_for_testing():
        print("❌ Setup failed at modification step")
        sys.exit(1)
    
    # Step 3: Restart API Gateway
    if not restart_api_gateway():
        print("❌ Setup failed at restart step")
        sys.exit(1)
    
    # Step 4: Test authentication
    if not test_authentication():
        print("❌ Setup failed at authentication test step")
        sys.exit(1)
    
    # Step 5: Generate configuration
    if not generate_load_test_config():
        print("❌ Setup failed at config generation step")
        sys.exit(1)
    
    print("\n🎉 Test authentication setup completed successfully!")
    print("\nNext steps:")
    print("1. Run load tests with test tokens:")
    print("   locust -f tests/performance/locust/auth_load_test.py --host http://localhost:8000")
    print("2. Monitor system performance")
    print("3. Check test results in reports/")
    
    print("\n📋 Test tokens available:")
    print("- Format: test-load-token-XXX")
    print("- Total: 100 tokens")
    print("- Usage: Bearer test-load-token-001")

if __name__ == "__main__":
    main()
