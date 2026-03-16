"""
Playwright Performance Testing Framework
Base class for all performance tests.
"""

import os
import asyncio
import time
import random
import uuid
from pathlib import Path
from playwright.async_api import async_playwright
from locust import User, task, events

from common_enhanced import (
    txn,
    nowdttm,
    timestamp,
    unique_user_string,
    generate_unique_id,
    load_config_from_file
)


class PerformanceFramework(User):
    """
    Base class for Playwright performance tests.

    Handles browser lifecycle, session persistence, transaction management,
    and tracing. Subclasses implement run_dynamic() with their test scenario.

    Usage:
        class MyTest(PerformanceFramework):
            async def run_dynamic(self):
                async with txn(self, "Login"):
                    await self.page.goto(self.base_url)
    """
    abstract = True

    # Configuration — overridden by environment variables
    base_url             = os.getenv("BASE_URL",            os.getenv("BASEURL", "https://example.com"))
    headless             = os.getenv("HEADLESS",            "true").lower() in ("true", "1", "yes")
    transaction_timeout  = int(os.getenv("TRANSACTION_TIMEOUT", os.getenv("TXNTIMEOUT", "10000")))
    enable_tracing       = os.getenv("ENABLE_TRACING",      os.getenv("PWTRACE", "false")).lower() in ("true", "1", "yes")
    ABORT_ITERATION_WHEN_TXN_FAILS = True

    # ------------------------------------------------------------------
    # Locust lifecycle
    # ------------------------------------------------------------------

    def on_start(self):
        asyncio.run(self._async_on_start())

    def on_stop(self):
        asyncio.run(self._async_on_stop())

    @task
    def run_test(self):
        asyncio.run(self._run_iteration())

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def _async_on_start(self):
        user_data_dir = Path(f"./user_data/user_{id(self)}")
        user_data_dir.mkdir(parents=True, exist_ok=True)
        self.user_data_dir = user_data_dir

        # Tracking state
        self.iteration                = 0
        self.currenttxn               = None
        self.currenttask              = None
        self.currentclass             = self.__class__.__name__
        self.currentscript            = os.path.basename(__file__)
        self.has_logged_in            = False
        self.iterationAllTxnPassed    = True
        self.error_screenshot_made    = False

        # Identity
        self.vuser_uuid               = str(uuid.uuid4())
        self.vuserid                  = id(self) % 10000
        self.startuporderid           = id(self)
        self.my_runner_client_id      = "standalone"
        self.iteration_start_timestamp = None

        # Browser
        self.pw      = await async_playwright().start()
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
        self.pprint(f"Browser initialized ({'headless' if self.headless else 'headed'})")

        if hasattr(self, 'user_init'):
            await self.user_init()

    async def _async_on_stop(self):
        self.pprint("Cleaning up session...")
        try:
            if hasattr(self, 'page')    and self.page:    await self.page.close()
            if hasattr(self, 'browser') and self.browser: await self.browser.close()
            if hasattr(self, 'pw')      and self.pw:      await self.pw.stop()
            self.pprint("Cleanup complete")
        except Exception as e:
            self.pprint(f"Cleanup error: {e}")

    # ------------------------------------------------------------------
    # Test iteration
    # ------------------------------------------------------------------

    async def _run_iteration(self):
        self.iteration += 1
        self.iteration_start_timestamp = nowdttm()
        self.iterationAllTxnPassed     = True
        self.error_screenshot_made     = False

        start_time = time.time()
        self.pprint(f"Starting iteration {self.iteration}")

        try:
            if self.enable_tracing:
                await self.page.context.tracing.start(screenshots=True, snapshots=True)

            await self.run_dynamic()

            if self.enable_tracing:
                trace_dir = os.getenv("TRACE_DIR", "./traces")
                Path(trace_dir).mkdir(parents=True, exist_ok=True)
                trace_path = f"{trace_dir}/user_{self.vuserid}_iter_{self.iteration}.zip"
                await self.page.context.tracing.stop(path=trace_path)

            status = "PASS" if self.iterationAllTxnPassed else "FAIL"
            self.pprint(f"{status} iteration {self.iteration} ({time.time() - start_time:.2f}s)")

        except Exception as e:
            self.pprint(f"FAIL iteration {self.iteration}: {type(e).__name__}: {str(e)[:100]}")

            if self.enable_tracing:
                trace_dir = os.getenv("TRACE_DIR", "./traces")
                Path(trace_dir).mkdir(parents=True, exist_ok=True)
                trace_path = f"{trace_dir}/user_{self.vuserid}_iter_{self.iteration}_FAILED.zip"
                try:
                    await self.page.context.tracing.stop(path=trace_path)
                except Exception:
                    pass
            raise

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    async def run_dynamic(self):
        """
        Implement this method with your test scenario.

        Example:
            async def run_dynamic(self):
                async with txn(self, "Login"):
                    await self.page.goto(self.base_url)
        """
        raise NotImplementedError("Subclass must implement run_dynamic()")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def pprint(self, msg: str):
        """Print with user context prefix."""
        print(f"[{timestamp()}] {unique_user_string(self)} | {msg}")

    def context(self) -> dict:
        """Return context dict for Locust event metadata."""
        return {
            "vuserid":   getattr(self, 'vuserid',   None),
            "iteration": getattr(self, 'iteration', None),
            "task":      getattr(self, 'currenttask', None),
            "txn":       getattr(self, 'currenttxn',  None),
            "class":     getattr(self, 'currentclass', None),
        }

    @property
    def unique_logon_username(self) -> str:
        """
        Returns a unique username for this virtual user.
        Built from TEST_USERNAME env var + zero-padded vuserid.
        e.g. testuser003
        """
        base = os.getenv("TEST_USERNAME", "testuser")
        return f"{base}{self.vuserid:03d}"

    def transaction(self, name: str, min_pace_ms: int = None, max_pace_ms: int = None):
        """Convenience wrapper around txn() context manager."""
        return txn(self, name=name, min_pace_ms=min_pace_ms, max_pace_ms=max_pace_ms)


# ---------------------------------------------------------------------------
# Event hooks
# ---------------------------------------------------------------------------

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n=== Performance Test Starting ===")
    print(f"Base URL:  {PerformanceFramework.base_url}")
    print(f"Headless:  {PerformanceFramework.headless}")
    print(f"Timeout:   {PerformanceFramework.transaction_timeout}ms")
    print(f"Tracing:   {PerformanceFramework.enable_tracing}")
    print("=" * 35 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n=== Performance Test Complete ===\n")
