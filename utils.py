"""
Configuration and Utility Functions
"""

import os
import json
from typing import Dict, Any


class Config:
    """
    Simple configuration management.
    Loads from environment variables and optional config.json file.
    """
    
    def __init__(self, config_file: str = "config.json"):
        self.config = {}
        self.load_defaults()
        
        # Load from config file if it exists
        if os.path.exists(config_file):
            self.load_from_file(config_file)
        
        # Environment variables override everything
        self.load_from_env()
    
    def load_defaults(self):
        """Set default configuration values"""
        self.config = {
            # Application settings
            "BASE_URL": "https://example.com",
            "HEADLESS": "true",
            "ENABLE_TRACING": "false",
            
            # Test settings
            "TRANSACTION_TIMEOUT": "10000",
            "TEST_USERNAME": "testuser",
            "TEST_PASSWORD": "password123",
            
            # Locust settings
            "USERS": "10",
            "SPAWN_RATE": "1",
            "RUN_TIME": "5m",
            
            # Performance settings
            "MIN_PACE_MS": "1000",
            "MAX_PACE_MS": "3000",
        }
    
    def load_from_file(self, filepath: str):
        """Load configuration from JSON file"""
        try:
            with open(filepath, 'r') as f:
                file_config = json.load(f)
                self.config.update(file_config)
            print(f"✓ Loaded configuration from {filepath}")
        except Exception as e:
            print(f"⚠ Warning: Could not load {filepath}: {e}")
    
    def load_from_env(self):
        """Load configuration from environment variables"""
        for key in self.config.keys():
            env_value = os.getenv(key)
            if env_value is not None:
                self.config[key] = env_value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def export_to_env(self):
        """Export all configuration to environment variables"""
        for key, value in self.config.items():
            os.environ[key] = str(value)
    
    def display(self):
        """Display current configuration"""
        print("\n" + "=" * 50)
        print("CONFIGURATION")
        print("=" * 50)
        for key, value in sorted(self.config.items()):
            # Mask passwords in output
            display_value = "***" if "PASSWORD" in key.upper() else value
            print(f"{key:25s} = {display_value}")
        print("=" * 50 + "\n")


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.2f}h"


def parse_duration(duration_str: str) -> int:
    """
    Parse duration string to seconds.
    Supports: 30s, 5m, 2h, 120
    """
    duration_str = str(duration_str).strip().lower()
    
    if duration_str.endswith('s'):
        return int(duration_str[:-1])
    elif duration_str.endswith('m'):
        return int(duration_str[:-1]) * 60
    elif duration_str.endswith('h'):
        return int(duration_str[:-1]) * 3600
    else:
        return int(duration_str)  # Assume seconds


def generate_test_data(template: str, index: int) -> str:
    """
    Generate test data with index-based variation.
    
    Example:
        generate_test_data("user_{index}@test.com", 5)
        # Returns: "user_5@test.com"
    """
    return template.replace("{index}", str(index))


class PerformanceStats:
    """Simple performance statistics tracker"""
    
    def __init__(self):
        self.transactions = {}
    
    def record(self, name: str, response_time: float, success: bool = True):
        """Record a transaction"""
        if name not in self.transactions:
            self.transactions[name] = {
                "count": 0,
                "success": 0,
                "failed": 0,
                "total_time": 0,
                "min": float('inf'),
                "max": 0,
            }
        
        stats = self.transactions[name]
        stats["count"] += 1
        
        if success:
            stats["success"] += 1
            stats["total_time"] += response_time
            stats["min"] = min(stats["min"], response_time)
            stats["max"] = max(stats["max"], response_time)
        else:
            stats["failed"] += 1
    
    def get_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for a transaction"""
        if name not in self.transactions:
            return {}
        
        stats = self.transactions[name]
        avg = stats["total_time"] / stats["success"] if stats["success"] > 0 else 0
        
        return {
            "name": name,
            "count": stats["count"],
            "success": stats["success"],
            "failed": stats["failed"],
            "avg_ms": round(avg, 2),
            "min_ms": round(stats["min"], 2) if stats["min"] != float('inf') else 0,
            "max_ms": round(stats["max"], 2),
            "success_rate": round(stats["success"] / stats["count"] * 100, 2) if stats["count"] > 0 else 0,
        }
    
    def summary(self):
        """Print summary of all transactions"""
        print("\n" + "=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        print(f"{'Transaction':<30} {'Count':>8} {'Success':>8} {'Failed':>8} {'Avg (ms)':>10} {'Min':>8} {'Max':>8}")
        print("-" * 80)
        
        for name in sorted(self.transactions.keys()):
            stats = self.get_stats(name)
            print(
                f"{stats['name']:<30} "
                f"{stats['count']:>8} "
                f"{stats['success']:>8} "
                f"{stats['failed']:>8} "
                f"{stats['avg_ms']:>10.2f} "
                f"{stats['min_ms']:>8.2f} "
                f"{stats['max_ms']:>8.2f}"
            )
        
        print("=" * 80 + "\n")


# Global configuration instance
config = Config()
