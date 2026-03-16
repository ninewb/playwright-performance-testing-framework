"""
Enhanced Common Utilities
Integrated from original framework's common.py and common_sas.py
"""

import os
import asyncio
import random
import time
import re
import uuid
import string
import logging
import inspect
import traceback
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout, expect
from locust import events
from locust.env import Environment
from locust.exception import CatchResponseError

# Initialize logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress Playwright DEBUG if set
if "DEBUG" in os.environ:
    logger.info(f"Suppressing Playwright DEBUG={os.environ['DEBUG']}")
    os.environ.pop("DEBUG", None)


# ==================== Time & String Utilities ====================

def nowdttm() -> str:
    """Return current timestamp in milliseconds"""
    return str(int(time.time() * 1000))


def timestamp() -> str:
    """Return formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def generate_random_string(length: int = 8) -> str:
    """Generate random alphanumeric string"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def generate_unique_id() -> str:
    """Generate unique ID based on timestamp and random string"""
    rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=2))
    timestamp_suffix = str(int(time.time() * 1000))[-5:]
    return f"{rand_str}{timestamp_suffix}"


# ==================== Inspection Utilities ====================

def get_current_method_name() -> str:
    """Get the name of the calling method"""
    return inspect.stack()[1][3]


def get_parent_method_name() -> str:
    """Get the name of the parent method"""
    return inspect.stack()[2][3]


def get_my_py_file_name() -> str:
    """Get the name of the calling Python file"""
    return os.path.basename(inspect.stack()[1][1])


def get_parent_file_name() -> str:
    """Get the name of the parent Python file"""
    return os.path.basename(inspect.stack()[2][1])


def get_fn_stack() -> str:
    """Get formatted function call stack"""
    stack = "|"
    for record in inspect.stack():
        stack += "<" + record[3]
    return stack


# ==================== Configuration Loading ====================

def load_config_from_file(path: str = "./env.sh") -> Dict[str, Any]:
    """
    Load configuration from shell export file.
    
    Parses lines like: export KEY="value"
    Auto-converts types (bool, int, float, string)
    """
    config = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                # Match: export KEY="value" or export KEY=value
                match = re.match(r'export\s+(\w+)=(["\']?)(.*?)\2$', line.strip())
                if match:
                    key, _, value = match.groups()
                    
                    # Auto-convert types
                    if value.lower() in ("true", "false"):
                        value = value.lower() == "true"
                    else:
                        try:
                            if "." in value:
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            pass  # Keep as string
                    
                    config[key] = value
    
    return config


# ==================== User Context & Tracking ====================

def unique_user_string(user) -> str:
    """
    Generate unique identifier string for a user across the test run.
    Format: startupid.uuid.workerid.class.vuserid._.iteration.task.txn
    """
    try:
        startup_id = str(user.startuporderid)
    except:
        startup_id = "None"
    
    try:
        worker_id = str(user.my_runner_client_id)
    except:
        worker_id = "None"
    
    try:
        script = str(user.currentscript)
    except:
        script = "None"
    
    try:
        user_class = str(user.currentclass)
    except:
        user_class = "None"
    
    try:
        vuser_uuid = str(user.vuser_uuid)
    except:
        vuser_uuid = "None"
    
    try:
        vuser_id = f"vuser_{user.vuserid}"
    except:
        vuser_id = "None"
    
    try:
        iteration = f"iter_{user.iteration}"
    except:
        iteration = "None"
    
    try:
        task = str(user.currenttask)
    except:
        task = "None"
    
    try:
        txn = str(user.currenttxn)
    except:
        txn = "None"
    
    return f"{startup_id}.{vuser_uuid}.{worker_id}.{user_class}.{vuser_id}._.{iteration}.{task}.{txn}"


# ==================== Transaction Management ====================

@asynccontextmanager
async def txn(user, name: str = "unnamed", request_type: str = "event", 
              min_pace_ms: Optional[int] = None, max_pace_ms: Optional[int] = None):
    """
    Context manager for transaction timing and reporting.
    
    Features:
    - Automatic timing measurement
    - Success/failure reporting to Locust
    - Optional pacing delays
    - HTTP header injection for tracing
    - Error recovery with UI reset
    
    Args:
        user: User object (must have environment, page, etc.)
        name: Transaction name for reporting
        request_type: Type for Locust metrics
        min_pace_ms: Minimum pacing delay after transaction (milliseconds)
        max_pace_ms: Maximum pacing delay after transaction (milliseconds)
    
    Usage:
        async with txn(user, "Login"):
            await user.page.goto("/login")
            await user.page.fill("#username", "user")
            await user.page.click("#submit")
    """
    user.currenttxn = name
    start_time = time.time()
    
    # Initialize required attributes if missing
    if not hasattr(user, 'iteration_start_timestamp'):
        user.iteration_start_timestamp = None
    if not hasattr(user, 'vuserid'):
        user.vuserid = None
    if not hasattr(user, 'currentclass'):
        user.currentclass = None
    if not hasattr(user, 'currenttask'):
        user.currenttask = None
    if not hasattr(user, 'ABORT_ITERATION_WHEN_TXN_FAILS'):
        user.ABORT_ITERATION_WHEN_TXN_FAILS = True
    if not hasattr(user, 'iterationAllTxnPassed'):
        user.iterationAllTxnPassed = True
    if not hasattr(user, 'error_screenshot_made'):
        user.error_screenshot_made = False
    
    # Add tracing headers if page is available
    if hasattr(user, 'page') and user.page:
        try:
            await user.page.set_extra_http_headers({
                'step': str(user.currenttxn),
                'user': str(f"vuser{user.vuserid}"),
                'script': str(f"{user.currentclass}_{user.currenttask}"),
                'timestamp': str(user.iteration_start_timestamp),
                'steptimestamp': str(int(start_time * 1000000)),
            })
        except Exception as e:
            logger.debug(f"Could not set extra headers: {e}")
    
    start_perf_counter = time.perf_counter()
    
    try:
        yield  # Execute transaction code
        
        # Fire success event to Locust
        response_time = (time.perf_counter() - start_perf_counter) * 1000
        user.environment.events.request.fire(
            request_type=request_type,
            name=name,
            start_time=start_time,
            response_time=response_time,
            response_length=0,
            url=user.page.url if hasattr(user, 'page') and user.page else None,
            exception=None,
        )
        
        if hasattr(user, 'pprint'):
            user.pprint(f"✓ {name} ({response_time:.0f}ms)")
        
    except Exception as e:
        # Transaction failed
        user.iterationAllTxnPassed = False
        
        if hasattr(user, 'pprint'):
            user.pprint(f"✗ {name} failed: {type(e).__name__}")
        
        # Attempt UI reset for recovery
        if hasattr(user, 'page') and user.page and hasattr(user, 'base_url'):
            try:
                await reset_screen(user, user.page, user.base_url)
                if hasattr(user, 'pprint'):
                    user.pprint("UI reset performed after failure")
            except Exception as reset_err:
                logger.debug(f"Reset attempt failed: {reset_err}")
        
        # Format error for Locust
        try:
            error_msg = re.sub("=======*", "", getattr(e, "message", str(e)))
            error_msg = error_msg.replace("\n", "").replace(" logs ", " ")[:500]
            error = CatchResponseError(error_msg)
        except:
            error = e
        
        # Fire failure event
        user.environment.events.request.fire(
            request_type=request_type,
            name=name,
            start_time=start_time,
            response_time=None,
            response_length=0,
            url=user.page.url if hasattr(user, 'page') and user.page else None,
            exception=error,
        )
        
        if user.ABORT_ITERATION_WHEN_TXN_FAILS:
            raise
    
    finally:
        # Apply pacing if specified
        if min_pace_ms is not None and max_pace_ms is not None:
            delay = random.randint(min_pace_ms, max_pace_ms)
            if hasattr(user, 'pprint'):
                user.pprint(f"⏱ Pacing {delay}ms")
            await asyncio.sleep(delay / 1000)
        
        # Small stability buffer
        await asyncio.sleep(0.1)
        user.currenttxn = None


async def reset_screen(user, page: Page, baseurl: str, timeout: int = 10000):
    """
    Attempt to recover UI by navigating to base URL.
    
    Args:
        user: User object
        page: Playwright page
        baseurl: Base URL to navigate to
        timeout: Timeout in milliseconds
    """
    try:
        if hasattr(user, 'pprint'):
            user.pprint("Attempting UI reset...")
        
        await page.goto(baseurl, timeout=timeout, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        if hasattr(user, 'pprint'):
            user.pprint("UI reset complete")
    
    except Exception as e:
        logger.warning(f"UI reset failed: {e}")
        raise


# ==================== SAS-Specific Functions ====================

async def sign_in(user, page: Page, baseurl: str, username: str, password: str, timeout: int = 10000):
    """
    Sign in to SAS Viya.
    
    Args:
        user: User object (for transaction tracking)
        page: Playwright page
        baseurl: Base URL
        username: Login username
        password: Login password
        timeout: Timeout in milliseconds
    """
    if hasattr(user, 'pprint'):
        user.pprint(f"Logging in as {username}")
    
    async with txn(user, "LaunchUrl"):
        await page.goto(f"{baseurl}/SASLogon/login")
        await expect(page.get_by_role("button", name="Sign in")).to_be_visible(timeout=timeout)
    
    async with txn(user, "TypeCredentials"):
        await page.get_by_role("textbox", name="User ID:").fill(username)
        await page.get_by_role("textbox", name="Password:").fill(password)
    
    async with txn(user, "Login"):
        async with page.expect_navigation(url=re.compile(r"SASLanding"), timeout=timeout):
            await page.get_by_role("button", name="Sign in").click()
        await expect(page.get_by_text("Welcome to SAS")).to_be_visible(timeout=timeout)
    
    if hasattr(user, 'pprint'):
        user.pprint(f"Login complete for {username}")


async def sign_out(user, page: Page, timeout: int = 10000):
    """
    Sign out from SAS Viya.
    
    Args:
        user: User object
        page: Playwright page
        timeout: Timeout in milliseconds
    """
    async with txn(user, "SignOutMenu"):
        await page.get_by_role("button", name=re.compile(r"Application options$", re.I)).click()
    
    async with txn(user, "SignOut"):
        await expect(page.get_by_text("Sign out")).to_be_visible(timeout=timeout)
        await page.get_by_role("menuitem", name="Sign out").click()
        await expect(page.get_by_role("heading", name="You have signed out.")).to_be_visible(timeout=timeout)


async def viya_app_menu(user, page: Page, timeout: int = 10000):
    """
    Open Applications menu and navigate to 'Investigate and Search Data'.
    Handles both home-page and internal-page DOM variants.
    
    Args:
        user: User object
        page: Playwright page
        timeout: Timeout in milliseconds
    """
    if hasattr(user, 'pprint'):
        user.pprint("Attempting to open Applications menu...")
    
    app_switcher = page.get_by_test_id("LandingAppRootBanner-appSwitcher")
    alt_switcher = page.get_by_role("button", name="Applications menu")
    
    try:
        if await app_switcher.count() > 0:
            # Landing page layout
            if hasattr(user, 'pprint'):
                user.pprint("Detected Landing page layout...")
            
            async with txn(user, "ClickonApplicationMenu"):
                await app_switcher.click()
                menu_item = page.get_by_test_id(
                    "LandingAppRootBanner-appSwitcherMenu-menuList-2-item-0"
                ).locator("div").filter(has_text="Investigate and Search Data")
                await expect(menu_item).to_be_visible(timeout=timeout)
            
            async with txn(user, "ClickonInvestigateSearch"):
                await menu_item.click()
                home_button = page.get_by_role("tab", name="Home")
                await expect(home_button).to_be_visible(timeout=timeout)
                await page.evaluate("window.scrollTo(0, 0)")
                if hasattr(user, 'pprint'):
                    user.pprint("Navigated to Visual Investigator home")
        
        elif await alt_switcher.count() > 0:
            # Internal page layout
            if hasattr(user, 'pprint'):
                user.pprint("Detected internal page layout...")
            
            async with txn(user, "ClickonApplicationMenu"):
                await alt_switcher.click()
                await expect(page.get_by_text("Investigate and Search Data")).to_be_visible(timeout=timeout)
            
            async with txn(user, "ClickonInvestigateSearch"):
                await page.get_by_text("Investigate and Search Data").click()
                home_button = page.get_by_role("tab", name="Home")
                await expect(home_button).to_be_visible(timeout=timeout)
                await page.evaluate("window.scrollTo(0, 0)")
                if hasattr(user, 'pprint'):
                    user.pprint("Navigated to Visual Investigator home")
        
        else:
            raise Exception("Could not find any Applications menu variant")
    
    except Exception as e:
        if hasattr(user, 'pprint'):
            user.pprint(f"viya_app_menu failed: {e}")
        raise


async def fill_input_by_label(page: Page, label: str, value: str, timeout: int = 1000):
    """Fill input field by label"""
    await page.get_by_label(label, exact=True).click()
    await page.get_by_label(label, exact=True).fill(value)
    await page.wait_for_timeout(timeout)


async def search_and_back(page: Page, search_label: str, timeout: int = 10000):
    """Execute search and return to home"""
    await page.get_by_label(search_label).get_by_role("button", name="Search").click()
    await expect(page.locator("button", has_text="Back to search")).to_be_visible(timeout=timeout)
    await page.locator("button", has_text="Back to search").click()
    await page.get_by_text("Home", exact=True).click()
    await page.get_by_role("button", name="Reset").click()
    await page.wait_for_timeout(1000)


# ==================== Viya API Client ====================

class ViyaAuthClient:
    """
    Authentication and API client for SAS Viya.
    Handles bearer token management and common API operations.
    """
    
    def __init__(self, baseurl: str, username: str, password: str):
        """
        Initialize Viya API client.
        
        Args:
            baseurl: Base URL for Viya (e.g., https://viya.example.com)
            username: Admin username
            password: Admin password
        """
        self.baseurl = baseurl.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.token_expiry = 0
    
    def get_bearer_token(self):
        """
        Obtain bearer token from SAS Logon service.
        Token is cached and reused until expiry.
        """
        # Check if we have a valid token
        if self.token and time.time() < self.token_expiry:
            logger.debug("Using cached bearer token")
            return self.token
        
        url = f"{self.baseurl}/SASLogon/oauth/token"
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = requests.post(
                url,
                data=data,
                auth=("sas.tkmtrn", ""),
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self.token_expiry = time.time() + expires_in - 60  # 60s buffer
                
                logger.info("Successfully obtained bearer token")
                return self.token
            else:
                logger.error(f"Failed to obtain token ({response.status_code}): {response.text}")
                raise RuntimeError("Failed to authenticate to Viya")
        
        except Exception as e:
            logger.error(f"Error obtaining bearer token: {e}")
            raise
    
    async def fetch_users(self, page: Optional[Page] = None, limit: int = 500, prefix: str = "test") -> List[str]:
        """
        Fetch users from Viya Identities API.
        
        Args:
            page: Optional Playwright page (for async context)
            limit: Maximum users to fetch
            prefix: Filter users by ID prefix
        
        Returns:
            List of user IDs
        """
        if not self.token:
            self.get_bearer_token()
        
        url = f"{self.baseurl}/identities/users?start=0&limit={limit}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        try:
            if page is not None:
                # Use Playwright async request
                response = await page.context.request.get(url, headers=headers, timeout=30000)
                status = response.status
                data = await response.json()
            else:
                # Use requests library
                response = requests.get(url, headers=headers, verify=False, timeout=30)
                status = response.status_code
                data = response.json()
            
            if status != 200:
                logger.error(f"Non-OK response ({status}) fetching users")
                return []
            
            items = data.get("items", [])
            user_ids = [
                user.get("id", "")
                for user in items
                if user.get("id", "").startswith(prefix)
            ]
            
            logger.info(f"Fetched {len(user_ids)} users with prefix '{prefix}'")
            return user_ids
        
        except Exception as e:
            logger.error(f"Error fetching users: {e}")
            return []
    
    async def fetch_vi_entity(self, page: Page, limit: int = 250, entity: str = "alertId") -> List[str]:
        """
        Fetch Visual Investigator entities (alerts, actionable entities).
        
        Args:
            page: Playwright page (required for async requests)
            limit: Maximum entities to fetch
            entity: Entity field to extract (alertId, actionableEntityId, actionableEntityLabel)
        
        Returns:
            List of entity IDs/values
        """
        url = f"{self.baseurl}/svi-alert/alerts?start=0&limit={limit}"
        url += "&filter=and(eq(queueId,'tm_alert_queue'),eq(alertStatusId,'ACTIVE'))"
        
        try:
            response = await page.context.request.get(
                url,
                headers={"Accept": "application/json"},
                timeout=30000
            )
            
            if not response.ok:
                logger.error(f"Non-OK response ({response.status}) fetching entities")
                if response.status == 401:
                    logger.error("Unauthorized - session may be invalid")
                return []
            
            data = await response.json()
            items = data.get("items", [])
            
            if not items:
                logger.warning(f"No items found in response")
                return []
            
            entity_ids = [
                str(item.get(entity))
                for item in items
                if (
                    item.get(entity) is not None
                    and item.get("alertStatusId") == "ACTIVE"
                    and item.get("assignedUserId") is None
                )
            ]
            
            logger.info(f"Fetched {len(entity_ids)} active unassigned entities")
            return entity_ids
        
        except Exception as e:
            logger.error(f"Error fetching entities: {e}")
            return []
    
    async def fetch_vi_document(self, page: Page, limit: int = 250, document: str = "tm_cases") -> List[str]:
        """
        Fetch Visual Investigator documents.
        
        Args:
            page: Playwright page
            limit: Maximum documents to fetch
            document: Document type (tm_cases, rr_report, ACC, etc.)
        
        Returns:
            List of document IDs
        """
        url = f"{self.baseurl}/svi-datahub/documents/{document}?start=0&limit={limit}"
        
        try:
            response = await page.context.request.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Accept-Item": "application/json"
                },
                timeout=30000
            )
            
            if not response.ok:
                logger.error(f"Non-OK response ({response.status}) fetching documents")
                if response.status == 401:
                    logger.error("Unauthorized - session may be invalid")
                return []
            
            data = await response.json()
            items = data.get("items") if isinstance(data, dict) else data
            
            if not items or not isinstance(items, list):
                logger.warning(f"No items found in document response")
                return []
            
            doc_ids = [
                str(item.get("id"))
                for item in items
                if item.get("id") is not None
            ]
            
            logger.info(f"Fetched {len(doc_ids)} document IDs from {document}")
            return doc_ids
        
        except Exception as e:
            logger.error(f"Error fetching documents: {e}")
            return []


# ==================== Event Hooks ====================

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize global state when Locust starts"""
    logger.info("=" * 60)
    logger.info("Enhanced Framework Initialized")
    logger.info("=" * 60)
