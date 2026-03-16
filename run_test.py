#!/usr/bin/env python3
"""
Simple Test Runner
Execute performance tests with minimal setup
"""

import sys
import os
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import Config, parse_duration


def main():
    parser = argparse.ArgumentParser(
        description="Run Playwright Performance Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with 10 users for 5 minutes
  python run_test.py example_test.py -u 10 -r 1 -t 5m
  
  # Run headless with custom config
  python run_test.py example_test.py --headless --config my_config.json
  
  # Run with web UI
  python run_test.py example_test.py --web-ui
        """
    )
    
    parser.add_argument(
        "testfile",
        help="Python file containing test classes (e.g., example_test.py)"
    )
    parser.add_argument(
        "-u", "--users",
        type=int,
        default=None,
        help="Number of concurrent users (default: from config)"
    )
    parser.add_argument(
        "-r", "--spawn-rate",
        type=float,
        default=None,
        help="User spawn rate per second (default: from config)"
    )
    parser.add_argument(
        "-t", "--run-time",
        type=str,
        default=None,
        help="Test duration (e.g., 30s, 5m, 1h) (default: from config)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browsers in headless mode"
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browsers in headed mode (visible)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config file (default: config.json)"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Base URL for testing (overrides config)"
    )
    parser.add_argument(
        "--web-ui",
        action="store_true",
        help="Launch Locust web UI (default: headless mode)"
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8089,
        help="Port for web UI (default: 8089)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Save results to CSV with this prefix"
    )
    parser.add_argument(
        "--html",
        type=str,
        default=None,
        help="Save HTML report to this file"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config(args.config)
    
    # Override config with command-line arguments
    if args.users is not None:
        config.config["USERS"] = str(args.users)
    
    if args.spawn_rate is not None:
        config.config["SPAWN_RATE"] = str(args.spawn_rate)
    
    if args.run_time is not None:
        config.config["RUN_TIME"] = args.run_time
    
    if args.base_url is not None:
        config.config["BASE_URL"] = args.base_url
    
    if args.headless:
        config.config["HEADLESS"] = "true"
    
    if args.headed:
        config.config["HEADLESS"] = "false"
    
    # Export configuration to environment
    config.export_to_env()
    config.display()
    
    # Verify test file exists
    test_file = Path(args.testfile)
    if not test_file.exists():
        print(f"Error: Test file not found: {args.testfile}")
        sys.exit(1)
    
    # Build Locust command
    locust_cmd = [
        "locust",
        "-f", str(test_file),
    ]
    
    # Add user count and spawn rate
    users = int(config.get("USERS", "1"))
    spawn_rate = float(config.get("SPAWN_RATE", "1"))
    
    if args.web_ui:
        # Web UI mode
        locust_cmd.extend([
            "--web-host", "0.0.0.0",
            "--web-port", str(args.web_port),
        ])
        print(f"\n🌐 Starting Locust Web UI at http://localhost:{args.web_port}\n")
    else:
        # Headless mode
        run_time = config.get("RUN_TIME", "5m")
        
        locust_cmd.extend([
            "--headless",
            "-u", str(users),
            "-r", str(spawn_rate),
            "-t", run_time,
        ])
        
        # Add CSV output if requested
        if args.csv:
            locust_cmd.extend(["--csv", args.csv])
        
        # Add HTML report if requested
        if args.html:
            locust_cmd.extend(["--html", args.html])
        
        print(f"\n🚀 Starting test: {users} users, spawn rate {spawn_rate}/s, duration {run_time}\n")
    
    # Execute Locust
    import subprocess
    try:
        result = subprocess.run(locust_cmd, check=True)
        print("\n✓ Test completed successfully\n")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Test failed with error code {e.returncode}\n")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
