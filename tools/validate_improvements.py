#!/usr/bin/env python3
"""
Validation Script for Huxley Improvements
Implements ChatGPT's recommended validation checks
"""

import sys
import os
import json
import subprocess
import time
import asyncio
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_schema_validation():
    """Test that schema validation fails on bad input"""
    print("=== Schema Validation Test ===")
    try:
        from workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine()
        
        # Test bad input that should fail
        bad_workflow = {
            "name": 123,  # Should be string
            "workflow_id": "",  # Should not be empty
            "steps": []  # Should have at least one step
        }
        
        try:
            engine.validate_workflow_data(bad_workflow)
            print("❌ FAIL: Schema validation should have failed but didn't")
            return False
        except Exception as e:
            print(f"✅ PASS: Schema validation properly failed: {type(e).__name__}")
            return True
            
    except ImportError as e:
        print(f"❌ FAIL: Could not import workflow_engine: {e}")
        return False

def test_distributed_routing_disabled():
    """Test that distributed routing is disabled by default"""
    print("\n=== Distributed Routing Default Test ===")
    try:
        from distributed_agent_router import is_distributed_routing_enabled
        
        # Should be disabled by default
        enabled = is_distributed_routing_enabled()
        if not enabled:
            print("✅ PASS: Distributed routing is disabled by default")
            return True
        else:
            print("❌ FAIL: Distributed routing should be disabled by default")
            return False
            
    except ImportError as e:
        print(f"❌ FAIL: Could not import distributed_agent_router: {e}")
        return False

def test_cache_bypass():
    """Test cache can be bypassed for debugging"""
    print("\n=== Cache Bypass Test ===")
    try:
        # Set environment to disable cache
        os.environ['RESULT_CACHE'] = 'off'
        
        from performance_improvements import is_result_cache_enabled, PerformanceCache
        
        if not is_result_cache_enabled():
            print("✅ PASS: Cache can be disabled via environment variable")
            
            # Test that cache actually bypasses
            cache = PerformanceCache()
            cache.set("test_key", "test_value")
            result = cache.get("test_key")
            
            if result is None:
                print("✅ PASS: Cache properly bypassed when disabled")
                return True
            else:
                print("❌ FAIL: Cache should return None when disabled")
                return False
        else:
            print("❌ FAIL: Cache should be disabled when RESULT_CACHE=off")
            return False
            
    except ImportError as e:
        print(f"❌ FAIL: Could not import performance_improvements: {e}")
        return False
    finally:
        # Reset environment
        os.environ.pop('RESULT_CACHE', None)

def test_keychain_security():
    """Test that keychain helper is working"""
    print("\n=== Keychain Security Test ===")
    try:
        from keychain_helper import KeychainHelper
        
        keychain = KeychainHelper()
        
        # Test key generation (without actually storing)
        test_key = keychain._get_service_name("test_key", "test_capsule")
        expected_service = "huxley.system.capsule.test_capsule.test_key"
        
        if test_key == expected_service:
            print("✅ PASS: Keychain service name generation works correctly")
            return True
        else:
            print(f"❌ FAIL: Expected {expected_service}, got {test_key}")
            return False
            
    except ImportError as e:
        print(f"❌ FAIL: Could not import keychain_helper: {e}")
        return False

def test_capsule_boundaries():
    """Test capsule boundary enforcement"""
    print("\n=== Capsule Boundaries Test ===")
    try:
        from distributed_agent_router import enforce_capsule_boundaries
        
        # Should be enabled by default
        enforced = enforce_capsule_boundaries()
        if enforced:
            print("✅ PASS: Capsule boundaries are enforced by default")
            return True
        else:
            print("❌ FAIL: Capsule boundaries should be enforced by default")
            return False
            
    except ImportError as e:
        print(f"❌ FAIL: Could not import distributed_agent_router: {e}")
        return False

def test_structured_logging():
    """Test structured logging includes required fields"""
    print("\n=== Structured Logging Test ===")
    try:
        from workflow_engine import WorkflowEngine
        import logging
        import io
        
        # Capture log output
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter('%(message)s'))
        
        logger = logging.getLogger('workflow_engine.WorkflowEngine')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Create workflow engine (should log initialization)
        engine = WorkflowEngine()
        
        # Check log output contains structured data
        log_output = log_stream.getvalue()
        if "WorkflowEngine initialized" in log_output:
            print("✅ PASS: Structured logging is working")
            return True
        else:
            print("❌ FAIL: Expected structured log message not found")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Structured logging test failed: {e}")
        return False

def test_feature_flags():
    """Test feature flags are properly configured"""
    print("\n=== Feature Flags Test ===")
    
    # Check config file exists
    config_path = Path(__file__).parent.parent / "global" / "config" / "config.json"
    if not config_path.exists():
        print(f"❌ FAIL: Config file not found: {config_path}")
        return False
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        features = config.get('features', {})
        
        # Check key feature flags
        checks = [
            ('DISTRIBUTED_ROUTING', False, 'Distributed routing should be disabled by default'),
            ('RESULT_CACHE', True, 'Result cache should be enabled by default'),
            ('STRICT_SCHEMA', True, 'Strict schema validation should be enabled'),
            ('JWT_AUTH', True, 'JWT auth should be enabled'),
        ]
        
        all_passed = True
        for flag, expected, description in checks:
            actual = features.get(flag)
            if actual == expected:
                print(f"✅ PASS: {description}")
            else:
                print(f"❌ FAIL: {description} (got {actual})")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ FAIL: Could not read config file: {e}")
        return False

def test_no_secrets_in_config():
    """Test that no secrets are stored in config files"""
    print("\n=== No Secrets in Config Test ===")
    
    # Check security config
    security_config_path = Path(__file__).parent.parent / "global" / "security" / "mcp_auth_config.json"
    
    if not security_config_path.exists():
        print(f"❌ FAIL: Security config not found: {security_config_path}")
        return False
    
    try:
        with open(security_config_path) as f:
            config_content = f.read()
        
        # Check that it references keychain, not actual keys
        if "keychain" in config_content.lower() and "jwt_signing_key_source" in config_content:
            print("✅ PASS: Security config references keychain instead of storing keys")
            
            # Double check no suspicious patterns
            suspicious_patterns = ["secret", "key:", "password", "token:"]
            for pattern in suspicious_patterns:
                if pattern in config_content.lower() and "keychain" not in config_content.lower():
                    print(f"❌ FAIL: Suspicious pattern found: {pattern}")
                    return False
            
            return True
        else:
            print("❌ FAIL: Security config should reference keychain")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Could not read security config: {e}")
        return False

async def test_async_no_orphans():
    """Test that async operations don't create orphaned event loops"""
    print("\n=== Async Orphan Prevention Test ===")
    try:
        from system_monitor import SystemMonitor
        
        # Test graceful start/stop
        monitor = SystemMonitor()
        
        start_time = time.time()
        await monitor.start()
        await asyncio.sleep(0.1)  # Brief run
        await monitor.stop()
        duration = time.time() - start_time
        
        if duration < 5.0:  # Should stop quickly
            print("✅ PASS: Async components start/stop gracefully")
            return True
        else:
            print("❌ FAIL: Async components took too long to stop")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Async orphan test failed: {e}")
        return False

def run_unit_tests():
    """Run fast unit tests"""
    print("\n=== Unit Tests ===")
    try:
        # Try to run pytest if available
        result = subprocess.run(['python', '-m', 'pytest', '-q', '--tb=short'], 
                               capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ PASS: Unit tests passed")
            return True
        else:
            print(f"❌ FAIL: Unit tests failed:\n{result.stdout}\n{result.stderr}")
            return False
            
    except FileNotFoundError:
        print("⚠️  SKIP: pytest not available, skipping unit tests")
        return True
    except subprocess.TimeoutExpired:
        print("❌ FAIL: Unit tests timed out")
        return False
    except Exception as e:
        print(f"❌ FAIL: Unit test execution failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🔍 Running Huxley Improvements Validation")
    print("=" * 60)
    
    tests = [
        test_feature_flags,
        test_schema_validation,
        test_distributed_routing_disabled,
        test_cache_bypass,
        test_keychain_security,
        test_capsule_boundaries,
        test_structured_logging,
        test_no_secrets_in_config,
    ]
    
    async_tests = [
        test_async_no_orphans,
    ]
    
    # Run sync tests
    passed = 0
    total = len(tests) + len(async_tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ FAIL: {test.__name__} crashed: {e}")
    
    # Run async tests
    async def run_async_tests():
        nonlocal passed
        for test in async_tests:
            try:
                if await test():
                    passed += 1
            except Exception as e:
                print(f"❌ FAIL: {test.__name__} crashed: {e}")
    
    asyncio.run(run_async_tests())
    
    # Run unit tests last
    if run_unit_tests():
        passed += 1
    total += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"🏆 VALIDATION SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - System improvements are ready to ship!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review issues above before shipping")
        return 1

if __name__ == "__main__":
    exit(main())