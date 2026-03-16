"""
Simplified Playwright Performance Testing Framework
Maintains session persistence and transaction management without K8s complexity
"""

import os
import asyncio
import time
import random
from pathlib import Path
from playwright.async_api import async_playwright
from locust import User, task, events
from contextlib import asynccontextmanager


class SimplifiedFramework(User):
    """
    Base class for Playwright performance tests.
    Handles browser lifecycle, session persistence, and transaction management.
    """
    abstract = True
    
    # Default configuration (can be overridden)
    base_url = os.getenv("BASE_URL", "https://example.com")
    headless = os.getenv("HEADLESS", "true").lower() in ["true", "1", "yes"]
    transaction_timeout = int(os.getenv("TRANSACTION_TIMEOUT", "10000"))
    enable_tracing = os.getenv("ENABLE_TRACING", "false").lower() in ["true", "1", "yes"]
    
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
    
    async def _async_on_start(self):
        """Initialize browser and persistent session"""
        # Create unique user data directory for session persistence
        user_data_dir = Path(f"./user_data/user_{id(self)}")
        user_data_dir.mkdir(parents=True, exist_ok=True)
        self.user_data_dir = user_data_dir
        
        # Initialize tracking variables
        self.iteration = 0
        self.current_transaction = None
        self.has_logged_in = False
        
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
        
        print(f"[User {id(self)}] Browser initialized in {'headless' if self.headless else 'headed'} mode")
    
    async def _async_on_stop(self):
        """Cleanup browser and session"""
        print(f"[User {id(self)}] Cleaning up session...")
        try:
            if hasattr(self, 'page') and self.page:
                await self.page.close()
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
            if hasattr(self, 'pw') and self.pw:
                await self.pw.stop()
        except Exception as e:
            print(f"[User {id(self)}] Cleanup error: {e}")
    
    async def _run_performance_test(self):
        """Execute the test iteration"""
        self.iteration += 1
        start_time = time.time()
        
        try:
            if self.enable_tracing:
                await self.page.context.tracing.start(screenshots=True, snapshots=True)
            
            # Call the user-defined test logic
            await self.test_scenario()
            
            if self.enable_tracing:
                trace_path = f"./traces/user_{id(self)}_iter_{self.iteration}.zip"
                Path("./traces").mkdir(exist_ok=True)
                await self.page.context.tracing.stop(path=trace_path)
            
            print(f"[User {id(self)}] Iteration {self.iteration} completed in {time.time() - start_time:.2f}s")
        
        except Exception as e:
            print(f"[User {id(self)}] Iteration {self.iteration} failed: {e}")
            if self.enable_tracing:
                trace_path = f"./traces/user_{id(self)}_iter_{self.iteration}_FAILED.zip"
                Path("./traces").mkdir(exist_ok=True)
                await self.page.context.tracing.stop(path=trace_path)
            raise
    
    async def test_scenario(self):
        """
        Override this method with your test scenario.
        This is where you define the user journey.
        """
        raise NotImplementedError("Subclass must implement test_scenario()")
    
    @asynccontextmanager
    async def transaction(self, name: str, min_pace_ms: int = None, max_pace_ms: int = None):
        """
        Context manager for measuring and reporting transactions.
        
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
        self.current_transaction = name
        start_time = time.time()
        start_perf = time.perf_counter()
        
        try:
            yield  # Execute the transaction code
            
            # Fire success event to Locust
            response_time = (time.perf_counter() - start_perf) * 1000
            self.environment.events.request.fire(
                request_type="transaction",
                name=name,
                response_time=response_time,
                response_length=0,
                exception=None,
            )
            
        except Exception as e:
            # Fire failure event to Locust
            self.environment.events.request.fire(
                request_type="transaction",
                name=name,
                response_time=None,
                response_length=0,
                exception=e,
            )
            raise
        
        finally:
            self.current_transaction = None
            
            # Apply pacing if specified
            if min_pace_ms is not None and max_pace_ms is not None:
                delay = random.randint(min_pace_ms, max_pace_ms) / 1000
                await asyncio.sleep(delay)
            
            # Small stability buffer
            await asyncio.sleep(0.1)
    
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
        print(f"[User {id(self)}] Logged in as {username}")
    
    async def logout(self):
        """
        Example logout helper method.
        Override this with your application-specific logout logic.
        """
        async with self.transaction("Logout"):
            await self.page.goto(f"{self.base_url}/logout")
            await self.page.wait_for_load_state("networkidle")
        
        self.has_logged_in = False
        print(f"[User {id(self)}] Logged out")


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
