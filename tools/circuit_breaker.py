#!/usr/bin/env python3
"""
Lightweight Circuit Breaker - Prevent cascade failures in Huxley
Implements circuit breaker pattern with jittered backoff for external calls
"""

import time
import random
import logging
import threading
from typing import Callable, Any, Optional, Dict, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import functools
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, reject calls
    HALF_OPEN = "half_open" # Testing recovery

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5                    # Failures before opening
    success_threshold: int = 2                    # Successes to close from half-open
    timeout_seconds: float = 60.0                 # Time before trying half-open
    max_timeout_seconds: float = 600.0           # Maximum timeout (10 minutes)
    backoff_multiplier: float = 2.0             # Exponential backoff multiplier
    jitter_factor: float = 0.1                  # Jitter factor (10%)
    monitor_window_size: int = 100              # Size of failure monitoring window

@dataclass
class CallResult:
    """Result of a circuit breaker protected call"""
    success: bool
    value: Any = None
    exception: Optional[Exception] = None
    execution_time_ms: float = 0
    circuit_state: CircuitState = CircuitState.CLOSED

class CircuitBreakerError(Exception):
    """Circuit breaker specific error"""
    def __init__(self, message: str, circuit_state: CircuitState, last_failure: Optional[Exception] = None):
        super().__init__(message)
        self.circuit_state = circuit_state
        self.last_failure = last_failure

class CircuitBreaker:
    """Lightweight circuit breaker implementation"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_failure = None
        self.next_attempt_time = None
        self.current_timeout = self.config.timeout_seconds
        
        # Monitoring
        self.recent_calls = deque(maxlen=self.config.monitor_window_size)
        self.total_calls = 0
        self.total_failures = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
    def _calculate_next_attempt_time(self) -> datetime:
        """Calculate next attempt time with exponential backoff and jitter"""
        # Exponential backoff
        timeout = min(self.current_timeout, self.config.max_timeout_seconds)
        
        # Add jitter to prevent thundering herd
        jitter = timeout * self.config.jitter_factor * (2 * random.random() - 1)
        final_timeout = max(1, timeout + jitter)
        
        # Update timeout for next failure
        self.current_timeout = min(
            self.current_timeout * self.config.backoff_multiplier,
            self.config.max_timeout_seconds
        )
        
        return datetime.now() + timedelta(seconds=final_timeout)
    
    def _should_attempt_call(self) -> bool:
        """Check if call should be attempted based on current state"""
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.HALF_OPEN:
            return True
            
        if self.state == CircuitState.OPEN:
            if self.next_attempt_time and datetime.now() >= self.next_attempt_time:
                # Transition to half-open
                with self.lock:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                return True
            else:
                return False
        
        return False
    
    def _record_success(self, execution_time_ms: float):
        """Record a successful call"""
        with self.lock:
            self.recent_calls.append({'success': True, 'time': time.time(), 'duration_ms': execution_time_ms})
            self.total_calls += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    # Transition to closed
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.current_timeout = self.config.timeout_seconds  # Reset timeout
                    logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED (recovered)")
            
            elif self.state == CircuitState.OPEN:
                # This shouldn't happen, but handle gracefully
                self.state = CircuitState.HALF_OPEN
                self.success_count = 1
    
    def _record_failure(self, exception: Exception, execution_time_ms: float):
        """Record a failed call"""
        with self.lock:
            self.recent_calls.append({'success': False, 'time': time.time(), 'duration_ms': execution_time_ms})
            self.total_calls += 1
            self.total_failures += 1
            self.last_failure = exception
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    # Transition to open
                    self.state = CircuitState.OPEN
                    self.next_attempt_time = self._calculate_next_attempt_time()
                    logger.warning(f"Circuit breaker '{self.name}' transitioning to OPEN after {self.failure_count} failures")
            
            elif self.state == CircuitState.HALF_OPEN:
                # Failure in half-open, go back to open
                self.state = CircuitState.OPEN
                self.next_attempt_time = self._calculate_next_attempt_time()
                logger.warning(f"Circuit breaker '{self.name}' transitioning back to OPEN (half-open test failed)")
    
    def call(self, func: Callable, *args, **kwargs) -> CallResult:
        """Execute a function with circuit breaker protection"""
        if not self._should_attempt_call():
            return CallResult(
                success=False,
                exception=CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN",
                    self.state,
                    self.last_failure
                ),
                circuit_state=self.state
            )
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time_ms = (time.time() - start_time) * 1000
            
            self._record_success(execution_time_ms)
            
            return CallResult(
                success=True,
                value=result,
                execution_time_ms=execution_time_ms,
                circuit_state=self.state
            )
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self._record_failure(e, execution_time_ms)
            
            return CallResult(
                success=False,
                exception=e,
                execution_time_ms=execution_time_ms,
                circuit_state=self.state
            )
    
    async def async_call(self, func: Callable, *args, **kwargs) -> CallResult:
        """Execute an async function with circuit breaker protection"""
        if not self._should_attempt_call():
            return CallResult(
                success=False,
                exception=CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN",
                    self.state,
                    self.last_failure
                ),
                circuit_state=self.state
            )
        
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            self._record_success(execution_time_ms)
            
            return CallResult(
                success=True,
                value=result,
                execution_time_ms=execution_time_ms,
                circuit_state=self.state
            )
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self._record_failure(e, execution_time_ms)
            
            return CallResult(
                success=False,
                exception=e,
                execution_time_ms=execution_time_ms,
                circuit_state=self.state
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        with self.lock:
            recent_window_seconds = 60  # Last minute
            current_time = time.time()
            
            recent_successes = sum(
                1 for call in self.recent_calls 
                if call['success'] and (current_time - call['time']) <= recent_window_seconds
            )
            
            recent_failures = sum(
                1 for call in self.recent_calls 
                if not call['success'] and (current_time - call['time']) <= recent_window_seconds
            )
            
            recent_avg_duration = 0
            if self.recent_calls:
                recent_durations = [call['duration_ms'] for call in self.recent_calls if (current_time - call['time']) <= recent_window_seconds]
                if recent_durations:
                    recent_avg_duration = sum(recent_durations) / len(recent_durations)
            
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_calls": self.total_calls,
                "total_failures": self.total_failures,
                "success_rate": (self.total_calls - self.total_failures) / max(self.total_calls, 1),
                "recent_successes": recent_successes,
                "recent_failures": recent_failures,
                "recent_avg_duration_ms": recent_avg_duration,
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
                "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None,
                "current_timeout_seconds": self.current_timeout
            }

# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()

def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """Get or create a circuit breaker by name"""
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, config)
        return _circuit_breakers[name]

def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator to wrap functions with circuit breaker protection"""
    def decorator(func):
        cb = get_circuit_breaker(name, config)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = cb.call(func, *args, **kwargs)
            if result.success:
                return result.value
            else:
                raise result.exception
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await cb.async_call(func, *args, **kwargs)
            if result.success:
                return result.value
            else:
                raise result.exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator

def get_all_circuit_breaker_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all circuit breakers"""
    with _registry_lock:
        return {name: cb.get_stats() for name, cb in _circuit_breakers.items()}

# Convenience function for Huxley-specific configurations
def get_builder_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get circuit breaker with Huxley-optimized configuration"""
    config = CircuitBreakerConfig(
        failure_threshold=3,        # Fail after 3 attempts
        success_threshold=2,        # Recover after 2 successes
        timeout_seconds=30.0,       # 30 second initial timeout
        max_timeout_seconds=300.0,  # Max 5 minute timeout
        backoff_multiplier=1.5,     # Gentle exponential backoff
        jitter_factor=0.2          # 20% jitter
    )
    
    return get_circuit_breaker(f"builder_{service_name}", config)

# Example usage functions for common Huxley services
def safe_rag_call(func: Callable, *args, **kwargs) -> Any:
    """Make a safe call to RAG service with circuit breaker"""
    cb = get_builder_circuit_breaker("rag_service")
    result = cb.call(func, *args, **kwargs)
    
    if result.success:
        return result.value
    else:
        raise result.exception

def safe_mcp_call(server_name: str, func: Callable, *args, **kwargs) -> Any:
    """Make a safe call to MCP server with circuit breaker"""
    cb = get_builder_circuit_breaker(f"mcp_{server_name}")
    result = cb.call(func, *args, **kwargs)
    
    if result.success:
        return result.value
    else:
        raise result.exception

def main():
    """CLI interface for circuit breaker management"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Circuit Breaker Management")
    parser.add_argument("--stats", action="store_true", help="Show circuit breaker statistics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--test", help="Test a circuit breaker with specified name")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = get_all_circuit_breaker_stats()
        
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            if not stats:
                print("No circuit breakers found")
                return
            
            print("Circuit Breaker Statistics")
            print("=" * 50)
            
            for name, cb_stats in stats.items():
                state_emoji = {
                    "closed": "✅",
                    "open": "❌", 
                    "half_open": "🟡"
                }
                
                print(f"\n{state_emoji.get(cb_stats['state'], '?')} {name} ({cb_stats['state'].upper()})")
                print(f"  Total Calls: {cb_stats['total_calls']}")
                print(f"  Success Rate: {cb_stats['success_rate']:.2%}")
                print(f"  Recent: {cb_stats['recent_successes']} successes, {cb_stats['recent_failures']} failures")
                
                if cb_stats['recent_avg_duration_ms'] > 0:
                    print(f"  Avg Duration: {cb_stats['recent_avg_duration_ms']:.1f}ms")
                
                if cb_stats['last_failure_time']:
                    print(f"  Last Failure: {cb_stats['last_failure_time']}")
                
                if cb_stats['next_attempt_time']:
                    print(f"  Next Attempt: {cb_stats['next_attempt_time']}")
    
    elif args.test:
        # Test circuit breaker
        def test_function():
            import time
            time.sleep(0.1)
            # Randomly fail for testing
            if random.random() < 0.3:
                raise Exception("Test failure")
            return "Success"
        
        cb = get_circuit_breaker(args.test)
        
        print(f"Testing circuit breaker: {args.test}")
        for i in range(10):
            result = cb.call(test_function)
            status = "✅" if result.success else "❌"
            print(f"{status} Call {i+1}: {result.value if result.success else result.exception}")
            time.sleep(0.5)
        
        print(f"\nFinal stats: {cb.get_stats()}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()