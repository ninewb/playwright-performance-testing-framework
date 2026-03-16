"""
Simplified Playwright Performance Testing Framework
Maintains session persistence and transaction management without K8s complexity

Enhanced with common utilities from original framework
"""

import os
import asyncio
import time
import random
import uuid
from pathlib import Path
from playwright.async_api import async_playwright
from locust import User, task, events
from contextlib import asynccontextmanager

# Import enhanced common utilities
from common_enhanced import (
    txn,
    nowdttm,
    timestamp,
    unique_user_string,
    generate_unique_id,
    load_config_from_file
)


class SimplifiedFramework(User):
    """
    Base class for Playwright performance tests.
    Handles browser lifecycle, session persistence, and transaction management.
    
    Enhanced Features:
    - Session persistence across iterations
    - Transaction-based performance measurement
    - User ID tracking and context
    - Enhanced logging with pprint
    - Configuration from env files
    - Error recovery with UI reset
    """
    abstract = True
    
    # Default configuration (can be overridden)
    base_url = os.getenv("BASE_URL", "https://example.com")
    headless = os.getenv("HEADLESS", "true").lower() in ["true", "1", "yes"]
    transaction_timeout = int(os.getenv("TRANSACTION_TIMEOUT", "10000"))
    enable_tracing = os.getenv("ENABLE_TRACING", "false").lower() in ["true", "1", "yes"]
    
    # Enhanced tracking
    ABORT_ITERATION_WHEN_TXN_FAILS = True
    
    def on_start(self):
        """Synchronous wrapper for async initialization"""
        asyncio.run(self._async_on_start())
    
    def on_stop(self):
        """Synchronous wrapper for async cleanup"""
        asyncio.run(self._async_on_stop())
    
    @task
    def run_test(self):
        """Main test execution wrapper"""
        asyncio.run(self._run_performance_test())
    
    def pprint(self, msg: str):
        """
        Enhanced print with context information.
        Includes user ID, iteration, task, and transaction info.
        """
        context = unique_user_string(self)
        print(f"[{timestamp()}] {context} | {msg}")
    
    async def _async_on_start(self):
        """Initialize browser and persistent session with enhanced tracking"""
        # Create unique user data directory for session persistence
        user_data_dir = Path(f"./user_data/user_{id(self)}")
        user_data_dir.mkdir(parents=True, exist_ok=True)
        self.user_data_dir = user_data_dir
        
        # Initialize enhanced tracking variables
        self.iteration = 0
        self.currenttxn = None
        self.currenttask = None
        self.currentclass = self.__class__.__name__
        self.currentscript = os.path.basename(__file__)
        self.has_logged_in = False
        
        # User identification
        self.vuser_uuid = str(uuid.uuid4())
        self.vuserid = id(self) % 10000  # Simple ID for standalone mode
        self.startuporderid = id(self)
        self.my_runner_client_id = "standalone"
        
        # Iteration tracking
        self.iteration_start_timestamp = None
        self.iterationAllTxnPassed = True
        self.error_screenshot_made = False
        
        # Launch persistent browser context
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=self.headless,
            ignore_https_errors=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
            ],
        )
        self.page = await self.browser.new_page()
        
        self.pprint(f"Browser initialized in {'headless' if self.headless else 'headed'} mode")
        
        # Call user-defined initialization if available
        if hasattr(self, 'user_init'):
            await self.user_init()
    
    async def _async_on_stop(self):
        """Cleanup browser and session"""
        self.pprint("Cleaning up session...")
        try:
            if hasattr(self, 'page') and self.page:
                await self.page.close()
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
            if hasattr(self, 'pw') and self.pw:
                await self.pw.stop()
            self.pprint("Cleanup complete")
        except Exception as e:
            self.pprint(f"Cleanup error: {e}")
    
    async def _run_performance_test(self):
        """Execute the test iteration with enhanced tracking"""
        self.iteration += 1
        self.iteration_start_timestamp = nowdttm()
        self.iterationAllTxnPassed = True
        self.error_screenshot_made = False
        
        start_time = time.time()
        self.pprint(f"Starting iteration {self.iteration}")
        
        try:
            if self.enable_tracing:
                await self.page.context.tracing.start(screenshots=True, snapshots=True)
            
            # Call the user-defined test logic
            await self.test_scenario()
            
            if self.enable_tracing:
                trace_dir = os.getenv("TRACE_DIR", "./traces")
                Path(trace_dir).mkdir(parents=True, exist_ok=True)
                trace_path = f"{trace_dir}/user_{self.vuserid}_iter_{self.iteration}.zip"
                await self.page.context.tracing.stop(path=trace_path)
            
            duration = time.time() - start_time
            status = "✓" if self.iterationAllTxnPassed else "✗"
            self.pprint(f"{status} Iteration {self.iteration} completed in {duration:.2f}s")
        
        except Exception as e:
            self.pprint(f"✗ Iteration {self.iteration} failed: {type(e).__name__}: {str(e)[:100]}")
            
            if self.enable_tracing:
                trace_dir = os.getenv("TRACE_DIR", "./traces")
                Path(trace_dir).mkdir(parents=True, exist_ok=True)
                trace_path = f"{trace_dir}/user_{self.vuserid}_iter_{self.iteration}_FAILED.zip"
                try:
                    await self.page.context.tracing.stop(path=trace_path)
                except:
                    pass
            
            raise
    
    async def test_scenario(self):
        """
        Override this method with your test scenario.
        This is where you define the user journey.
        """
        raise NotImplementedError("Subclass must implement test_scenario()")
    
    def context(self) -> dict:
        """
        Return context dictionary for Locust event metadata.
        """
        return {
            "vuserid": getattr(self, 'vuserid', None),
            "iteration": getattr(self, 'iteration', None),
            "task": getattr(self, 'currenttask', None),
            "txn": getattr(self, 'currenttxn', None),
            "class": getattr(self, 'currentclass', None),
        }
    
    # Helper method to use enhanced txn function
    def transaction(self, name: str, min_pace_ms: int = None, max_pace_ms: int = None):
        """
        Context manager for measuring and reporting transactions.
        Uses enhanced txn from common_enhanced module.
        
        Usage:
            async with self.transaction("Login"):
                await self.page.goto("/login")
                await self.page.fill("#username", "user")
                await self.page.click("#submit")
        
        Args:
            name: Transaction name
            min_pace_ms: Minimum pacing delay after transaction (milliseconds)
            max_pace_ms: Maximum pacing delay after transaction (milliseconds)
        """
        return txn(self, name=name, min_pace_ms=min_pace_ms, max_pace_ms=max_pace_ms)
    
    async def login(self, username: str, password: str):
        """
        Example login helper method.
        Override this with your application-specific login logic.
        """
        async with self.transaction("Login"):
            await self.page.goto(f"{self.base_url}/login")
            await self.page.fill("#username", username)
            await self.page.fill("#password", password)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_load_state("networkidle")
        
        self.has_logged_in = True
        self.pprint(f"Logged in as {username}")
    
    async def logout(self):
        """
        Example logout helper method.
        Override this with your application-specific logout logic.
        """
        async with self.transaction("Logout"):
            await self.page.goto(f"{self.base_url}/logout")
            await self.page.wait_for_load_state("networkidle")
        
        self.has_logged_in = False
        self.pprint("Logged out")


# Event hooks for custom metrics or logging
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("\n=== Performance Test Starting ===")
    print(f"Base URL: {SimplifiedFramework.base_url}")
    print(f"Headless: {SimplifiedFramework.headless}")
    print(f"Transaction Timeout: {SimplifiedFramework.transaction_timeout}ms")
    print("=" * 35 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops"""
    print("\n=== Performance Test Complete ===\n")
