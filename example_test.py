"""
Example Performance Test
Demonstrates how to use the Simplified Framework
"""

from framework import SimplifiedFramework
import os


class ExampleTest(SimplifiedFramework):
    """
    Example test scenario demonstrating session persistence
    and transaction-based performance measurement.
    """
    
    # Locust weight (higher = more users of this type)
    weight = 1
    
    # Test-specific configuration
    test_username = os.getenv("TEST_USERNAME", "testuser")
    test_password = os.getenv("TEST_PASSWORD", "password123")
    
    async def test_scenario(self):
        """
        Define the user journey to be executed.
        
        This is called repeatedly by Locust for each iteration.
        The browser session persists across iterations, so you only
        need to log in once.
        """
        
        # Login only on first iteration
        if not self.has_logged_in:
            await self.perform_login()
        
        # Main test flow - executes every iteration
        await self.search_items()
        await self.view_dashboard()
        await self.update_profile()
    
    async def perform_login(self):
        """Login sequence with transaction tracking"""
        
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
        print(f"[User {id(self)}] Successfully logged in")
    
    async def search_items(self):
        """Search functionality with natural pacing"""
        
        async with self.transaction("Navigate_to_Search"):
            await self.page.goto(f"{self.base_url}/search")
            await self.page.wait_for_selector("input[name='query']")
        
        # Transaction with custom pacing (1-3 seconds after completion)
        async with self.transaction("Perform_Search", min_pace_ms=1000, max_pace_ms=3000):
            await self.page.fill("input[name='query']", f"test query {self.iteration}")
            await self.page.click("button[type='submit']")
            await self.page.wait_for_selector(".search-results")
        
        async with self.transaction("View_Search_Results"):
            # Simulate user reading results
            results = await self.page.query_selector_all(".result-item")
            print(f"[User {id(self)}] Found {len(results)} search results")
    
    async def view_dashboard(self):
        """Dashboard viewing with wait times"""
        
        async with self.transaction("Load_Dashboard"):
            await self.page.goto(f"{self.base_url}/dashboard")
            await self.page.wait_for_load_state("networkidle")
        
        async with self.transaction("Interact_with_Dashboard"):
            # Example: click through tabs or widgets
            tabs = await self.page.query_selector_all(".dashboard-tab")
            if tabs:
                await tabs[0].click()
                await self.page.wait_for_timeout(500)  # Small wait for animation
    
    async def update_profile(self):
        """Profile update sequence"""
        
        async with self.transaction("Navigate_to_Profile"):
            await self.page.goto(f"{self.base_url}/profile")
            await self.page.wait_for_selector("input[name='bio']")
        
        async with self.transaction("Update_Profile_Info"):
            # Simulate updating user profile
            import random
            await self.page.fill("input[name='bio']", f"Updated bio - iteration {self.iteration}")
            await self.page.click("button[type='submit']")
            
            # Wait for success message
            await self.page.wait_for_selector(".success-message", timeout=5000)
            print(f"[User {id(self)}] Profile updated successfully")


class AdminWorkflow(SimplifiedFramework):
    """
    Example of a second user type with different behavior.
    
    Demonstrates how to create multiple user personas with different
    weights and workflows in the same test.
    """
    
    weight = 1  # Equal weight to ExampleTest
    
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    async def test_scenario(self):
        """Admin-specific test flow"""
        
        if not self.has_logged_in:
            await self.admin_login()
        
        await self.view_admin_dashboard()
        await self.manage_users()
    
    async def admin_login(self):
        """Admin login sequence"""
        async with self.transaction("Admin_Login"):
            await self.page.goto(f"{self.base_url}/admin/login")
            await self.page.fill("#username", self.admin_username)
            await self.page.fill("#password", self.admin_password)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_url("**/admin/dashboard")
        
        self.has_logged_in = True
    
    async def view_admin_dashboard(self):
        """View admin dashboard"""
        async with self.transaction("Load_Admin_Dashboard"):
            await self.page.goto(f"{self.base_url}/admin/dashboard")
            await self.page.wait_for_load_state("networkidle")
    
    async def manage_users(self):
        """User management actions"""
        async with self.transaction("View_User_List"):
            await self.page.goto(f"{self.base_url}/admin/users")
            await self.page.wait_for_selector(".user-table")
        
        async with self.transaction("Search_Users"):
            await self.page.fill("input[name='search']", "test")
            await self.page.click("button.search")
            await self.page.wait_for_timeout(1000)
