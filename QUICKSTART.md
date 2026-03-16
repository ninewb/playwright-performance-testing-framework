# Quick Start Guide

Get running in 5 minutes!

## Step 1: Install

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Step 2: Configure (1 minute)

Edit `config.json` with your application details:

```json
{
  "BASE_URL": "https://your-app.com",
  "TEST_USERNAME": "your_test_user",
  "TEST_PASSWORD": "your_password"
}
```

## Step 3: Run (30 seconds)

```bash
# Run the example test
python run_test.py example_test.py

# Or with custom settings
python run_test.py example_test.py -u 10 -r 2 -t 5m
```

## Step 4: View Results (1 minute)

Watch the live output:

```
Name                    # reqs  # fails  Avg    Min    Max    Median  req/s
----------------------------------------------------------------------------
Login                       10       0   245     198    312     234    0.20
Search                     120       2   156     89     423     142    2.40
View_Profile               120       0   198    145     289     187    2.40
```

## What Just Happened?

1. **10 virtual users** were spawned
2. Each user logged in **once** (session persisted)
3. Users repeatedly executed **search** and **profile viewing** actions
4. **Response times** were measured for each transaction
5. **Results** were aggregated and reported

## Next Steps

### Debug a Test (Visible Browser)

```bash
python run_test.py example_test.py --headed -u 1 -t 30s
```

### Use Web UI (Interactive)

```bash
python run_test.py example_test.py --web-ui
# Open http://localhost:8089 in your browser
```

### Save Results

```bash
python run_test.py example_test.py \
  --csv results/my_test \
  --html results/report.html
```

### Create Your Own Test

Copy `example_test.py` to `my_test.py` and modify:

```python
from framework import SimplifiedFramework

class MyTest(SimplifiedFramework):
    async def test_scenario(self):
        # Your test logic here
        if not self.has_logged_in:
            await self.login("user", "pass")
        
        await self.my_action()
    
    async def my_action(self):
        async with self.transaction("MyAction"):
            await self.page.goto(f"{self.base_url}/my-page")
```

Then run:

```bash
python run_test.py my_test.py
```

## Learn More

- Read the full [README.md](README.md) for detailed documentation
- Check out [example_test.py](example_test.py) for code examples
- Review [framework.py](framework.py) to understand the internals

## Common Issues

**"Browser not found"**
```bash
playwright install chromium
```

**"Connection refused"**
- Check BASE_URL in config.json
- Verify the application is running

**"Timeout errors"**
- Increase TRANSACTION_TIMEOUT in config.json
- Check network connectivity

## Tips

1. **Start with 1 user** to verify your test works
2. **Use headed mode** (`--headed`) for debugging
3. **Add pacing** to simulate realistic user behavior
4. **Monitor resources** (CPU, RAM) during tests
5. **Save traces** when debugging failures
