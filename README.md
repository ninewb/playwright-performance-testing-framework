# Playwright Performance Testing Framework

A streamlined, standalone performance testing framework combining **Playwright** for browser automation with **Locust** for load generation and metrics.

## Key Features

- **Session Persistence**: Browser sessions persist across test iterations (realistic user behavior)
- **Transaction Management**: Built-in transaction timing and reporting
- **Natural Pacing**: Configurable delays between actions to simulate real users
- **Multiple User Types**: Support for different user personas with varying workflows
- **Headless or Headed**: Run with visible browsers for debugging or headless for performance
- **Simple Configuration**: JSON-based config with environment variable overrides
- **Standalone Execution**: No Kubernetes or complex infrastructure required

## Requirements

- Python 3.8+
- pip

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Your Test

Edit `config.json`:

```json
{
  "BASE_URL": "https://your-app.com",
  "HEADLESS": "true",
  "TEST_USERNAME": "your_username",
  "TEST_PASSWORD": "your_password",
  "USERS": "10",
  "SPAWN_RATE": "1",
  "RUN_TIME": "5m"
}
```

### 3. Run the Example Test

```bash
# Simple run with defaults from config
python run_test.py example_test.py

# Custom parameters
python run_test.py example_test.py -u 20 -r 2 -t 10m

# With web UI (interactive)
python run_test.py example_test.py --web-ui

# Headed mode (visible browsers for debugging)
python run_test.py example_test.py --headed -u 1
```

## Creating Your Own Test

### Basic Structure

```python
from framework import SimplifiedFramework

class MyTest(SimplifiedFramework):
    """Your test class"""
    
    weight = 1  # Relative weight if using multiple user types
    
    async def test_scenario(self):
        """Main test flow - executed repeatedly"""
        
        # Login once per session
        if not self.has_logged_in:
            await self.perform_login()
        
        # Actions that repeat every iteration
        await self.action_1()
        await self.action_2()
    
    async def perform_login(self):
        """Login with transaction tracking"""
        async with self.transaction("Login"):
            await self.page.goto(f"{self.base_url}/login")
            await self.page.fill("#username", "user")
            await self.page.fill("#password", "pass")
            await self.page.click("button[type='submit']")
            await self.page.wait_for_url("**/dashboard")
        
        self.has_logged_in = True
    
    async def action_1(self):
        """Example action with natural pacing"""
        async with self.transaction("Search", min_pace_ms=1000, max_pace_ms=3000):
            await self.page.goto(f"{self.base_url}/search")
            await self.page.fill("input[name='q']", "test query")
            await self.page.click("button[type='submit']")
            await self.page.wait_for_selector(".results")
    
    async def action_2(self):
        """Another action"""
        async with self.transaction("View_Profile"):
            await self.page.goto(f"{self.base_url}/profile")
            await self.page.wait_for_load_state("networkidle")
```

### Transaction Context Manager

The `transaction()` context manager handles:
- Automatic timing measurement
- Success/failure reporting to Locust
- Optional pacing (delays between transactions)
- Exception handling

```python
# Basic transaction
async with self.transaction("Action_Name"):
    await self.page.click("#button")

# With pacing (1-3 second delay after completion)
async with self.transaction("Action_Name", min_pace_ms=1000, max_pace_ms=3000):
    await self.page.click("#button")
```

## Configuration Options

### Configuration File (`config.json`)

| Key | Description | Default |
|-----|-------------|---------|
| `BASE_URL` | Application URL | `https://example.com` |
| `HEADLESS` | Run browsers headless | `true` |
| `ENABLE_TRACING` | Save Playwright traces | `false` |
| `TRANSACTION_TIMEOUT` | Timeout for transactions (ms) | `10000` |
| `TEST_USERNAME` | Test user login | `testuser` |
| `TEST_PASSWORD` | Test user password | `password123` |
| `USERS` | Number of concurrent users | `10` |
| `SPAWN_RATE` | Users spawned per second | `1` |
| `RUN_TIME` | Test duration (e.g., 5m, 1h) | `5m` |
| `MIN_PACE_MS` | Minimum pacing delay (ms) | `1000` |
| `MAX_PACE_MS` | Maximum pacing delay (ms) | `3000` |

### Environment Variables

All config values can be overridden with environment variables:

```bash
export BASE_URL="https://staging.example.com"
export HEADLESS="false"
export USERS="50"

python run_test.py example_test.py
```

### Command-Line Arguments

```bash
# Override specific settings
python run_test.py example_test.py \
  --base-url https://staging.example.com \
  --users 50 \
  --spawn-rate 5 \
  --run-time 30m \
  --headless

# Save results
python run_test.py example_test.py \
  --csv results/test_run \
  --html results/report.html

# Interactive mode
python run_test.py example_test.py --web-ui --web-port 8089
```

## 📊 Understanding Results

### Locust Metrics

When you run a test, you'll see:

```
Name                              # reqs  # fails  Avg    Min    Max    Median  req/s
------------------------------------------------------------------------------------------
Login                                 10       0   245     198    312     234    0.20
Search                               120       2   156     89     423     142    2.40
View_Profile                         120       0   198    145     289     187    2.40
------------------------------------------------------------------------------------------
Aggregated                           250       2   178     89     423     165    5.00
```

**Key Metrics:**
- **# reqs**: Total requests (transactions)
- **# fails**: Failed transactions
- **Avg/Min/Max/Median**: Response times (ms)
- **req/s**: Throughput (transactions per second)

### Playwright Traces

Enable tracing for debugging:

```json
{
  "ENABLE_TRACING": "true"
}
```

Traces are saved to `./traces/` and can be viewed with:

```bash
playwright show-trace traces/user_12345_iter_1.zip
```

## Architecture

### Session Persistence

Unlike basic Locust tests, this framework maintains **persistent browser sessions**:

1. **First iteration**: User logs in, session is established
2. **Subsequent iterations**: Same session is reused
3. **Result**: Realistic user behavior without repeated login overhead

### Transaction Flow

```
Iteration 1:
  - Login (once) → Session persists
  - Action 1
  - Action 2

Iteration 2:
  - (No login - session active)
  - Action 1
  - Action 2

Iteration 3:
  - (No login - session active)
  - Action 1
  - Action 2
```

### Multiple User Types

Create different user personas:

```python
class RegularUser(SimplifiedFramework):
    weight = 3  # 75% of traffic
    # ... regular user workflow

class AdminUser(SimplifiedFramework):
    weight = 1  # 25% of traffic
    # ... admin workflow
```

## Debugging

### Visible Browsers

Run with `--headed` to see what's happening:

```bash
python run_test.py example_test.py --headed -u 1 -t 30s
```

### Enable Tracing

Set in config or environment:

```bash
export ENABLE_TRACING="true"
python run_test.py example_test.py
```

### Verbose Logging

Add print statements in your test:

```python
async def my_action(self):
    print(f"[User {id(self)}] Starting action...")
    async with self.transaction("MyAction"):
        # your code
    print(f"[User {id(self)}] Action completed")
```

## Scaling Strategies

### Local Machine

```bash
# Conservative
python run_test.py example_test.py -u 10 -r 1

# Moderate
python run_test.py example_test.py -u 50 -r 5

# Aggressive (watch your CPU/RAM!)
python run_test.py example_test.py -u 100 -r 10
```

### Cloud VM

For large-scale tests, run on a cloud VM:

```bash
# Example: AWS EC2 c5.4xlarge (16 vCPU, 32 GB RAM)
python run_test.py example_test.py -u 500 -r 50 -t 1h --headless
```

## Comparison to Original Framework

| Feature | Original | Simplified |
|---------|----------|------------|
| **Infrastructure** | Kubernetes required | Standalone |
| **Deployment** | Complex (operator, CRDs, pods) | Simple (pip install) |
| **Session Persistence** | ✓ | ✓ |
| **Transaction Management** | ✓ | ✓ |
| **Multiple User Types** | ✓ | ✓ |
| **Distributed Workers** | ✓ | ✗ (single machine) |
| **Auto-scaling** | ✓ | ✗ |
| **Learning Curve** | High | Low |

## Best Practices

### 1. Start Small

Begin with 1 user to verify your test works:

```bash
python run_test.py my_test.py --headed -u 1 -t 30s
```

### 2. Use Realistic Pacing

Don't hammer the server - add delays:

```python
async with self.transaction("Action", min_pace_ms=2000, max_pace_ms=5000):
    # your action
```

### 3. Handle Errors Gracefully

Use try/except for non-critical steps:

```python
async with self.transaction("Main_Action"):
    await self.page.click("#important")
    
    # Optional action - don't fail the whole test
    try:
        await self.page.click("#optional", timeout=2000)
    except:
        print("Optional element not found, continuing...")
```

### 4. Monitor Resources

Watch CPU, RAM, and network during tests:

```bash
# Linux/Mac
htop
# Windows
Task Manager
```

### 5. Warm Up Period

Use spawn rate to gradually ramp up:

```bash
# Spawn 100 users over 100 seconds (1/sec)
python run_test.py my_test.py -u 100 -r 1 -t 10m
```

## Troubleshooting

### "Browser not found"

```bash
playwright install chromium
```

### "Module not found: framework"

Make sure you're running from the framework directory:

```bash
cd simplified_framework
python run_test.py example_test.py
```

### High CPU usage

Reduce concurrent users or use headless mode:

```bash
python run_test.py example_test.py --headless -u 10
```

### Timeout errors

Increase transaction timeout:

```json
{
  "TRANSACTION_TIMEOUT": "30000"
}
```

## Example Use Cases

1. **Login Flow Performance**: Measure authentication response times
2. **Search Functionality**: Test search performance under load
3. **Dashboard Loading**: Measure time to interactive for complex UIs
4. **Form Submissions**: Test form handling and validation performance
5. **Multi-Step Workflows**: Measure end-to-end business process performance

## Resources

- [Locust Documentation](https://docs.locust.io/)
- [Playwright Documentation](https://playwright.dev/)
- [Performance Testing Best Practices](https://playwright.dev/docs/best-practices)