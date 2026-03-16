# Framework Enhancement Summary

## Overview

The simplified framework has been enhanced with production-tested utilities from the original enterprise framework. This integration incorporates functions from common.py and common_sas.py, providing enterprise-grade capabilities while maintaining standalone deployment simplicity.

## Files Added

The enhancement includes three new core files:

1. common_enhanced.py - Enhanced utilities module (800+ lines)
2. example_enhanced.py - SAS Viya integration examples (4 test classes)
3. README_ENHANCED.md - Comprehensive technical documentation

## Enhancement Details

### 1. Enhanced Transaction Management

The framework now includes an advanced transaction context manager with the following capabilities:

Previous implementation:
```python
async with self.transaction("Login"):
    await self.page.click("#login")
```

Enhanced implementation:
```python
from common_enhanced import txn

async with txn(self, "Login"):
    await self.page.click("#login")
```

Features:
- Automatic timing measurement and metrics reporting
- HTTP header injection for distributed tracing
- Automatic error recovery with UI reset capability
- Configurable pacing between transactions
- Enhanced error logging and reporting

### 2. Context-Aware Logging

The framework provides structured logging with full execution context.

Previous implementation:
```python
print(f"[User {id(self)}] Login complete")
```

Enhanced implementation:
```python
self.pprint("Login complete")
```

Output format:
```
[2024-03-16 10:30:45.123] 1.abc123.standalone.MyTest.vuser_42._.iter_5.Login.Login | Login complete
```

Context elements included:
- Timestamp (millisecond precision)
- Startup order ID
- User UUID
- Worker ID
- User class name
- Virtual user ID
- Iteration number
- Current task identifier
- Current transaction name

### 3. SAS Viya Helper Functions

Pre-built functions for common SAS Viya operations:

```python
from common_enhanced import sign_in, sign_out, viya_app_menu

# Authentication
await sign_in(user=self, page=self.page, baseurl=self.base_url,
              username="user", password="pass", timeout=10000)

# Application navigation
await viya_app_menu(user=self, page=self.page, timeout=10000)

# Session termination
await sign_out(user=self, page=self.page, timeout=10000)
```

Available functions:
- sign_in: SAS Viya authentication workflow
- sign_out: Session termination workflow
- viya_app_menu: Navigate to Visual Investigator
- fill_input_by_label: Form field population
- search_and_back: Search execution and navigation

### 4. Viya API Client

REST API integration for data retrieval and validation:

```python
from common_enhanced import ViyaAuthClient

# Initialize client
client = ViyaAuthClient(
    baseurl="https://viya.example.com",
    username="admin",
    password="admin_pass"
)

# Authenticate (automatic token management)
client.get_bearer_token()

# Fetch data
users = await client.fetch_users(page=self.page, limit=500, prefix="test")
alerts = await client.fetch_vi_entity(page=self.page, limit=100, entity="alertId")
documents = await client.fetch_vi_document(page=self.page, limit=100, document="rr_report")
```

Capabilities:
- Bearer token authentication with automatic caching
- Token expiry management
- User retrieval from Identities API
- Visual Investigator entity fetching (alerts, actionable entities)
- Document retrieval (cases, reports, ACC documents)
- Support for both async (Playwright) and sync (requests) contexts

### 5. Utility Functions

Additional helper functions for test development:

```python
from common_enhanced import (
    generate_unique_id,      # Unique identifier generation
    generate_random_string,  # Random string generation
    nowdttm,                # Millisecond timestamp
    timestamp,              # Formatted timestamp
    load_config_from_file   # Shell file configuration loading
)

# Generate unique test data
case_id = f"CASE_{generate_unique_id()}"
await self.page.fill("#case-id", case_id)

# Timestamp management
self.pprint(f"Started at {timestamp()}")

# Configuration loading
config = load_config_from_file("./env.sh")
```

### 6. Enhanced Framework Base Class

The SimplifiedFramework base class has been enhanced with additional tracking and context management:

New attributes:
- vuserid: Virtual user identifier
- vuser_uuid: Unique user UUID
- currentclass: Test class name
- currenttask: Current task/phase identifier
- currenttxn: Current transaction name
- iterationAllTxnPassed: Transaction success flag
- iteration_start_timestamp: Iteration start time
- startuporderid: Startup order identifier
- my_runner_client_id: Runner client identifier

New methods:
- pprint(): Context-aware logging
- user_init(): Custom initialization hook
- context(): Event metadata dictionary

## Implementation Examples

### Example 1: Basic SAS Viya Authentication

```python
from framework import SimplifiedFramework
from common_enhanced import sign_in

class ViyaLoginTest(SimplifiedFramework):
    test_username = "testuser"
    test_password = "password"
    
    async def test_scenario(self):
        if not self.has_logged_in:
            await sign_in(
                user=self,
                page=self.page,
                baseurl=self.base_url,
                username=self.test_username,
                password=self.test_password,
                timeout=10000
            )
            self.has_logged_in = True
```

### Example 2: API and UI Integration

```python
from framework import SimplifiedFramework
from common_enhanced import sign_in, ViyaAuthClient
import random

class AlertProcessingTest(SimplifiedFramework):
    
    async def user_init(self):
        """Initialize API client once per user"""
        self.api_client = ViyaAuthClient(
            baseurl=self.base_url,
            username=self.admin_username,
            password=self.admin_password
        )
        self.api_client.get_bearer_token()
    
    async def test_scenario(self):
        # Authenticate once per session
        if not self.has_logged_in:
            await sign_in(self, self.page, self.base_url, 
                         self.test_username, self.test_password)
            self.has_logged_in = True
        
        # Retrieve data via API
        alerts = await self.api_client.fetch_vi_entity(
            page=self.page,
            entity="alertId"
        )
        
        # Process via UI
        if alerts:
            alert = random.choice(alerts)
            await self.process_alert_ui(alert)
```

### Example 3: Unique Test Data Generation

```python
from framework import SimplifiedFramework
from common_enhanced import generate_unique_id

class DataEntryTest(SimplifiedFramework):
    
    async def test_scenario(self):
        # Generate unique identifier
        unique_name = f"Test_{generate_unique_id()}"
        
        async with self.transaction("CreateRecord"):
            await self.page.fill("#name", unique_name)
            await self.page.click("#submit")
        
        self.pprint(f"Created record: {unique_name}")
```

## Usage Instructions

### Running Basic Tests

Existing tests remain compatible:

```bash
python run_test.py example_test.py
```

### Running Enhanced Tests

Execute SAS Viya integration examples:

```bash
# Configure environment
export BASE_URL="https://viya.example.com"
export TEST_USERNAME="testuser"
export ADMIN_USERNAME="admin"

# Execute tests
python run_test.py example_enhanced.py -u 10 -t 5m
```

### Creating Custom Tests

Copy template from example_enhanced.py:

```bash
cp example_enhanced.py custom_test.py
# Modify custom_test.py as needed
python run_test.py custom_test.py
```

## Performance Comparison

### Basic Framework Output

```
Name                    # reqs  # fails  Avg    Min    Max
------------------------------------------------------------
Login                       10       0   245     198    312
Search                     120       2   156     89     423
```

### Enhanced Framework Output

```
[2024-03-16 10:30:45.123] 1.abc.standalone.Test.vuser_1._.iter_1.Login.LaunchUrl | LaunchUrl (245ms)
[2024-03-16 10:30:45.456] 1.abc.standalone.Test.vuser_1._.iter_1.Login.Login | Logged in as testuser
[2024-03-16 10:30:46.789] 1.abc.standalone.Test.vuser_1._.iter_1.FetchAlerts.API | FetchAlertsAPI (312ms)
[2024-03-16 10:30:46.823] 1.abc.standalone.Test.vuser_1._.iter_1.FetchAlerts.API | Found 45 alerts

Name                    # reqs  # fails  Avg    Min    Max
------------------------------------------------------------
LaunchUrl                   10       0   245     198    312
Login                       10       0   412     356    498
FetchAlertsAPI              10       0   312     287    356
SearchAlert                120       0   156     89     234
OpenAlert                  120       0   198    145     289
```

## Migration Approach

### Option 1: No Changes Required

All existing tests remain functional without modification.

### Option 2: Incremental Enhancement

Add enhanced features gradually:

```python
from framework import SimplifiedFramework

class ExistingTest(SimplifiedFramework):
    async def test_scenario(self):
        async with self.transaction("Login"):
            await self.page.click("#login")
            self.pprint("Login complete")  # Add enhanced logging
```

### Option 3: Full Enhancement

Implement all enhanced features:

```python
from framework import SimplifiedFramework
from common_enhanced import sign_in, ViyaAuthClient

class EnhancedTest(SimplifiedFramework):
    async def user_init(self):
        self.api_client = ViyaAuthClient(...)
    
    async def test_scenario(self):
        if not self.has_logged_in:
            await sign_in(self, self.page, self.base_url, "user", "pass")
            self.has_logged_in = True
        
        data = await self.api_client.fetch_vi_entity(...)
```

## Test Execution Examples

### SAS Viya Login Performance Testing
```bash
python run_test.py example_enhanced.py -u 50 -t 10m
```

### Alert Processing at Scale
```bash
python run_test.py example_enhanced.py -u 20 -t 30m --csv results/alerts
```

### Report Generation Testing
```bash
python run_test.py example_enhanced.py -u 10 -t 15m --html results/report.html
```

### Mixed Workload Testing
```bash
python run_test.py example_enhanced.py -u 30 -t 1h
```

## Debugging Capabilities

### Visual Debugging

```bash
python run_test.py example_enhanced.py --headed -u 1 -t 30s
```

### Playwright Tracing

Configuration:
```json
{
  "ENABLE_TRACING": "true"
}
```

View traces:
```bash
playwright show-trace traces/user_42_iter_1.zip
```

### API Debug Logging

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Feature Summary

| Component | Basic Framework | Enhanced Framework |
|-----------|----------------|-------------------|
| Logging | Simple print statements | Context-aware structured logging |
| Transactions | Basic timing | Enhanced with recovery and tracing |
| SAS Viya Support | Manual implementation | Built-in helper functions |
| API Access | Not available | Full REST client with authentication |
| Data Generation | Manual implementation | Utility functions provided |
| Error Recovery | Not available | Automatic UI reset |
| Tracing | Basic | HTTP header injection |
| User Tracking | Simple ID | UUID, vuserid, context tracking |
| Configuration | JSON only | JSON and shell file support |

## Documentation Resources

1. ENHANCEMENTS.md - This document
2. README_ENHANCED.md - Complete technical documentation
3. example_enhanced.py - Working code examples
4. common_enhanced.py - Function reference (inline documentation)

All enhancements maintain backward compatibility with existing tests.
