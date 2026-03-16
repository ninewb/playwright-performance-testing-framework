"""
Enhanced Example Tests with SAS Viya Integration
Demonstrates usage of common_enhanced utilities
"""

from framework import SimplifiedFramework
from common_enhanced import (
    sign_in,
    sign_out,
    viya_app_menu,
    fill_input_by_label,
    search_and_back,
    ViyaAuthClient,
    generate_unique_id,
)
import os
import random


class SASViyaLoginTest(SimplifiedFramework):
    """
    Basic SAS Viya login/logout test.
    Demonstrates session persistence and enhanced logging.
    """
    
    weight = 1
    
    # Test configuration
    test_username = os.getenv("TEST_USERNAME", "testuser")
    test_password = os.getenv("TEST_PASSWORD", "password123")
    
    async def test_scenario(self):
        """
        Test scenario: Login once, then perform actions repeatedly.
        """
        # Login only on first iteration
        if not self.has_logged_in:
            await self.perform_login()
        
        # Actions that repeat every iteration
        await self.navigate_to_app()
        await self.view_home()
    
    async def perform_login(self):
        """SAS Viya login using enhanced sign_in function"""
        self.currenttask = "Login"
        
        # Use enhanced sign_in from common_enhanced
        await sign_in(
            user=self,
            page=self.page,
            baseurl=self.base_url,
            username=self.test_username,
            password=self.test_password,
            timeout=self.transaction_timeout
        )
        
        self.has_logged_in = True
        self.pprint("Login complete")
    
    async def navigate_to_app(self):
        """Navigate to Visual Investigator application"""
        self.currenttask = "NavigateToApp"
        
        # Use enhanced viya_app_menu from common_enhanced
        await viya_app_menu(
            user=self,
            page=self.page,
            timeout=self.transaction_timeout
        )
    
    async def view_home(self):
        """View home tab"""
        self.currenttask = "ViewHome"
        
        async with self.transaction("ViewHomeTab"):
            await self.page.get_by_role("tab", name="Home").click()
            await self.page.wait_for_timeout(1000)


class SASViyaAlertWorkflow(SimplifiedFramework):
    """
    Advanced SAS Viya test demonstrating API integration.
    Fetches alerts via API and processes them via UI.
    """
    
    weight = 1
    
    # Configuration
    test_username = os.getenv("TEST_USERNAME", "testuser")
    test_password = os.getenv("TEST_PASSWORD", "password123")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    async def user_init(self):
        """
        Custom initialization - called after browser setup.
        Initialize API client for data fetching.
        """
        self.pprint("Initializing API client...")
        
        # Create Viya API client for fetching data
        self.api_client = ViyaAuthClient(
            baseurl=self.base_url,
            username=self.admin_username,
            password=self.admin_password
        )
        
        # Authenticate and get token
        self.api_client.get_bearer_token()
        self.pprint("API client initialized")
        
        # Fetch initial list of alerts
        self.alert_ids = []
    
    async def test_scenario(self):
        """
        Test scenario: Login, fetch alerts via API, process via UI.
        """
        # Login only on first iteration
        if not self.has_logged_in:
            await self.perform_login()
        
        # Fetch fresh alerts via API
        await self.fetch_alerts()
        
        # Process alerts via UI
        if self.alert_ids:
            await self.process_alert()
        else:
            self.pprint("No alerts available to process")
    
    async def perform_login(self):
        """Login to SAS Viya"""
        self.currenttask = "Login"
        
        await sign_in(
            user=self,
            page=self.page,
            baseurl=self.base_url,
            username=self.test_username,
            password=self.test_password,
            timeout=self.transaction_timeout
        )
        
        self.has_logged_in = True
    
    async def fetch_alerts(self):
        """Fetch available alerts via API"""
        self.currenttask = "FetchAlerts"
        
        async with self.transaction("FetchAlertsAPI"):
            self.alert_ids = await self.api_client.fetch_vi_entity(
                page=self.page,
                limit=100,
                entity="alertId"
            )
            self.pprint(f"Fetched {len(self.alert_ids)} alerts")
    
    async def process_alert(self):
        """Process a random alert via UI"""
        self.currenttask = "ProcessAlert"
        
        # Pick a random alert
        alert_id = random.choice(self.alert_ids)
        self.pprint(f"Processing alert: {alert_id}")
        
        # Navigate to Visual Investigator
        await viya_app_menu(
            user=self,
            page=self.page,
            timeout=self.transaction_timeout
        )
        
        # Search for the alert
        async with self.transaction("SearchAlert"):
            search_tab = self.page.get_by_label("Navigation tabs").get_by_text("Search")
            await search_tab.click()
            
            search_input = self.page.get_by_role("textbox", name="Search Input")
            await search_input.click()
            await search_input.fill(f"+_type:tm_alert +{alert_id}")
            await search_input.press("Enter")
            
            await self.page.wait_for_timeout(2000)
        
        # Open the alert
        async with self.transaction("OpenAlert"):
            await self.page.get_by_text(alert_id).first.dblclick()
            await self.page.wait_for_timeout(1000)
        
        # View alert details
        async with self.transaction("ViewAlertDetails"):
            await self.page.get_by_role("tab", name="Alert Details").click()
            await self.page.wait_for_timeout(500)


class SASViyaReportWorkflow(SimplifiedFramework):
    """
    SAS Viya report processing workflow.
    Demonstrates document fetching and editing.
    """
    
    weight = 1
    
    test_username = os.getenv("TEST_USERNAME", "testuser")
    test_password = os.getenv("TEST_PASSWORD", "password123")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    async def user_init(self):
        """Initialize API client"""
        self.pprint("Initializing API client...")
        
        self.api_client = ViyaAuthClient(
            baseurl=self.base_url,
            username=self.admin_username,
            password=self.admin_password
        )
        
        self.api_client.get_bearer_token()
        self.report_ids = []
    
    async def test_scenario(self):
        """
        Test scenario: Fetch reports via API, open and edit via UI.
        """
        if not self.has_logged_in:
            await self.perform_login()
        
        await self.fetch_reports()
        
        if self.report_ids:
            await self.process_report()
        else:
            self.pprint("No reports available")
    
    async def perform_login(self):
        """Login to SAS Viya"""
        self.currenttask = "Login"
        
        await sign_in(
            user=self,
            page=self.page,
            baseurl=self.base_url,
            username=self.test_username,
            password=self.test_password,
            timeout=self.transaction_timeout
        )
        
        self.has_logged_in = True
    
    async def fetch_reports(self):
        """Fetch available reports via API"""
        self.currenttask = "FetchReports"
        
        async with self.transaction("FetchReportsAPI"):
            self.report_ids = await self.api_client.fetch_vi_document(
                page=self.page,
                limit=100,
                document="rr_report"
            )
            self.pprint(f"Fetched {len(self.report_ids)} reports")
    
    async def process_report(self):
        """Open and view a report"""
        self.currenttask = "ProcessReport"
        
        report_id = random.choice(self.report_ids)
        self.pprint(f"Processing report: {report_id}")
        
        # Navigate to VI
        await viya_app_menu(
            user=self,
            page=self.page,
            timeout=self.transaction_timeout
        )
        
        # Search for report
        async with self.transaction("SearchReport"):
            await self.page.get_by_label("Navigation tabs").get_by_text("Search").click()
            
            search_input = self.page.get_by_role("textbox", name="Search Input")
            await search_input.click()
            await search_input.fill(f"+_type:rr_report +{report_id}")
            await search_input.press("Enter")
            
            await self.page.wait_for_timeout(2000)
        
        # Open report
        async with self.transaction("OpenReport"):
            await self.page.get_by_text(report_id).first.dblclick()
            await self.page.wait_for_timeout(1000)
        
        # View report details
        async with self.transaction("ViewReportDetails"):
            await self.page.get_by_role("tab", name="Report Details").click()
            await self.page.wait_for_timeout(500)
        
        # Edit a field with unique value
        async with self.transaction("EditReportField"):
            await self.page.get_by_role("button", name="Edit").click()
            
            # Generate unique value
            unique_value = f"Test_{generate_unique_id()}"
            
            # Fill a field (adjust selector for your application)
            # Example: await self.page.get_by_role("textbox", name="Notes").fill(unique_value)
            await self.page.wait_for_timeout(500)
            
            self.pprint(f"Updated field with: {unique_value}")


class GenericWorkflow(SimplifiedFramework):
    """
    Generic workflow using enhanced utilities.
    Works with any web application.
    """
    
    weight = 1
    
    test_username = os.getenv("TEST_USERNAME", "testuser")
    test_password = os.getenv("TEST_PASSWORD", "password123")
    
    async def test_scenario(self):
        """
        Generic test flow demonstrating enhanced features.
        """
        if not self.has_logged_in:
            await self.perform_login()
        
        await self.search_items()
        await self.view_dashboard()
        await self.update_profile()
    
    async def perform_login(self):
        """Generic login with enhanced logging"""
        self.currenttask = "Login"
        
        async with self.transaction("Navigate_to_Login"):
            await self.page.goto(f"{self.base_url}/login")
            await self.page.wait_for_selector("#username", timeout=self.transaction_timeout)
        
        async with self.transaction("Fill_Credentials"):
            await self.page.fill("#username", self.test_username)
            await self.page.fill("#password", self.test_password)
        
        async with self.transaction("Submit_Login"):
            await self.page.click("button[type='submit']")
            await self.page.wait_for_url("**/dashboard", timeout=self.transaction_timeout)
        
        self.has_logged_in = True
        self.pprint("Login successful")
    
    async def search_items(self):
        """Search with pacing"""
        self.currenttask = "Search"
        
        async with self.transaction("Navigate_to_Search"):
            await self.page.goto(f"{self.base_url}/search")
            await self.page.wait_for_selector("input[name='query']")
        
        # Generate unique search query
        unique_query = f"test_{generate_unique_id()}"
        
        async with self.transaction("Perform_Search", min_pace_ms=1000, max_pace_ms=3000):
            await self.page.fill("input[name='query']", unique_query)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_selector(".search-results")
        
        self.pprint(f"Searched for: {unique_query}")
    
    async def view_dashboard(self):
        """View dashboard"""
        self.currenttask = "Dashboard"
        
        async with self.transaction("Load_Dashboard"):
            await self.page.goto(f"{self.base_url}/dashboard")
            await self.page.wait_for_load_state("networkidle")
    
    async def update_profile(self):
        """Update profile with unique data"""
        self.currenttask = "UpdateProfile"
        
        async with self.transaction("Navigate_to_Profile"):
            await self.page.goto(f"{self.base_url}/profile")
            await self.page.wait_for_selector("input[name='bio']")
        
        # Generate unique bio
        unique_bio = f"Bio updated at {generate_unique_id()}"
        
        async with self.transaction("Update_Profile_Info"):
            await self.page.fill("input[name='bio']", unique_bio)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_selector(".success-message", timeout=5000)
            
            self.pprint(f"Profile updated: {unique_bio}")
