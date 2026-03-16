#!/usr/bin/env python3
"""
Test Runner — local and Kubernetes modes.
Local:      python run_test.py tests/aml_search.py -u 10 -r 1 -t 5m
Kubernetes: python run_test.py tests/aml_search.py --kubernetes --environment staging --workers 3
"""

import re
import sys
import os
import time
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils import Config, parse_duration


# ---------------------------------------------------------------------------
# Kubernetes helpers
# ---------------------------------------------------------------------------

def k8s_safe_name(test_file: str) -> str:
    name = Path(test_file).stem.lower()
    name = re.sub(r'[._]', '-', name)
    name = re.sub(r'[^a-z0-9-]', '', name)
    return name


def render_template(template_path: str, substitutions: dict) -> str:
    content = Path(template_path).read_text()
    for key, val in substitutions.items():
        content = content.replace(f'%%{key}%%', str(val))
    return content


def kubectl_apply(yaml_content: str, namespace: str):
    result = subprocess.run(
        ['kubectl', '-n', namespace, 'apply', '-f', '-'],
        input=yaml_content, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"kubectl apply failed:\n{result.stderr}")
    print(result.stdout.strip())


def wait_for_locust_completion(test_name: str, namespace: str, timeout: int = 7200) -> bool:
    """
    Wait for all locust master/worker pods to finish.
    Phase 1 — wait up to 5 min for pods to appear.
    Phase 2 — wait up to timeout for all pods to reach a terminal state.
    """
    deadline = time.time() + timeout

    print(f"INFO: Waiting for test pods to appear (test={test_name})...")
    pods_appeared = False
    while time.time() < deadline:
        r = subprocess.run(
            ['kubectl', '-n', namespace, 'get', 'pods',
             '-l', 'locust.io/role', '--no-headers'],
            capture_output=True, text=True
        )
        lines = [l for l in r.stdout.strip().splitlines() if l and test_name in l]
        if lines:
            pods_appeared = True
            print(f"INFO: Test pods detected ({len(lines)} pod(s)). Waiting for completion...")
            break
        time.sleep(5)

    if not pods_appeared:
        print("ERROR: Timed out waiting for test pods to appear.")
        return False

    terminal = {'Completed', 'Succeeded', 'Error', 'CrashLoopBackOff', 'OOMKilled'}
    while time.time() < deadline:
        r = subprocess.run(
            ['kubectl', '-n', namespace, 'get', 'pods',
             '-l', 'locust.io/role', '--no-headers'],
            capture_output=True, text=True
        )
        lines = [l for l in r.stdout.strip().splitlines() if l and test_name in l]
        if not lines:
            print("INFO: All test pods have terminated.")
            return True
        still_running = [l for l in lines if not any(t in l for t in terminal)]
        if not still_running:
            print("INFO: All test pods reached terminal state.")
            return True
        statuses = ', '.join(l.split()[2] for l in lines if len(l.split()) > 2)
        print(f"INFO: Pods still running — {statuses}")
        time.sleep(10)

    print("ERROR: Timed out waiting for test completion.")
    return False


def wait_for_job(job_name: str, namespace: str, timeout: int = 600) -> bool:
    print(f"INFO: Waiting for collector job '{job_name}' to complete...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ['kubectl', '-n', namespace, 'get', 'job', job_name,
             '-o', 'jsonpath={.status.conditions[?(@.type=="Complete")].status}'],
            capture_output=True, text=True
        )
        if r.stdout.strip() == 'True':
            print(f"INFO: Collector job '{job_name}' completed successfully.")
            return True
        r_fail = subprocess.run(
            ['kubectl', '-n', namespace, 'get', 'job', job_name,
             '-o', 'jsonpath={.status.conditions[?(@.type=="Failed")].status}'],
            capture_output=True, text=True
        )
        if r_fail.stdout.strip() == 'True':
            print(f"ERROR: Collector job '{job_name}' failed.")
            return False
        time.sleep(10)
    print(f"ERROR: Timed out waiting for collector job '{job_name}'.")
    return False


def run_kubernetes(args, config):
    """Orchestrate the full Kubernetes test flow."""
    template_dir = Path(args.template_dir)
    manifest_dir = Path(args.manifest_dir)

    test_name   = k8s_safe_name(args.testfile)
    timestamp   = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    namespace   = args.namespace
    environment = args.environment

    users       = int(config.get("USERS", "1"))
    spawn_rate  = float(config.get("SPAWN_RATE", "1"))
    run_time    = config.get("RUN_TIME", "5m")
    base_url    = config.get("BASE_URL", "")

    locust_file = Path(args.testfile).name
    acr_name    = args.acrname or config.get("ACRNAME", "")
    acr_base    = acr_name.replace('.azurecr.io', '')

    substitutions = {
        'NAMESPACE':       namespace,
        'LOCUSTTESTNAME':  test_name,
        'LOCUSTFILE':      locust_file,
        'ACRNAME':         acr_name,
        'ACR_BASENAME':    acr_base,
        'NLOCUSTUSERS':    users,
        'SPAWNRATE_ups':   spawn_rate,
        'RUNTIME_s':       run_time,
        'GRACEFUL_EXIT_s': args.graceful_exit,
        'WORKERREPLICAS':  args.workers,
        'TESTNAME':        test_name,
        'ENVIRONMENT':     environment,
        'TIMESTAMP':       timestamp,
    }

    # Apply LocustTest CR
    locust_test_yaml = render_template(
        str(template_dir / 'locust-test.yaml'), substitutions
    )
    print(f"\nINFO: Applying LocustTest CR for '{test_name}'...")
    kubectl_apply(locust_test_yaml, namespace)

    # Wait for test to complete
    completed = wait_for_locust_completion(test_name, namespace, timeout=int(args.test_timeout))
    if not completed:
        print("ERROR: Test did not complete within the timeout. Check pod logs for details.")
        sys.exit(1)

    # Apply collector job
    collector_yaml = render_template(
        str(manifest_dir / 'collector-job.yaml'), substitutions
    )
    print(f"\nINFO: Applying collector job for '{test_name}'...")
    kubectl_apply(collector_yaml, namespace)

    job_name = f"{test_name}-collector"
    success = wait_for_job(job_name, namespace, timeout=600)
    if not success:
        print("ERROR: Collector job did not complete. Check job logs:")
        print(f"  kubectl -n {namespace} logs job/{job_name} -c upload")
        sys.exit(1)

    # Print blob URL from job logs
    r = subprocess.run(
        ['kubectl', '-n', namespace, 'logs', f'job/{job_name}', '-c', 'upload'],
        capture_output=True, text=True
    )
    for line in r.stdout.splitlines():
        if line.startswith('BLOB_URL='):
            print(f"\nINFO: Results available at: {line.split('=', 1)[1]}\n")
            break


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Playwright Performance Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local run
  python run_test.py tests/aml_search.py -u 10 -r 1 -t 5m

  # Kubernetes run
  python run_test.py tests/aml_search.py --kubernetes --environment staging --workers 3

  # Local with web UI
  python run_test.py tests/aml_search.py --web-ui
        """
    )

    parser.add_argument("testfile", help="Test file path (e.g., tests/aml_search.py)")

    # Common args
    parser.add_argument("-u", "--users",      type=int,   default=None, help="Number of concurrent users")
    parser.add_argument("-r", "--spawn-rate", type=float, default=None, help="User spawn rate per second")
    parser.add_argument("-t", "--run-time",   type=str,   default=None, help="Test duration (e.g., 30s, 5m, 1h)")
    parser.add_argument("--base-url",         type=str,   default=None, help="Base URL (overrides config)")
    parser.add_argument("--config",           type=str,   default="config.json", help="Config file path")
    parser.add_argument("--headless",         action="store_true", help="Run browsers headless")
    parser.add_argument("--headed",           action="store_true", help="Run browsers headed")

    # Local-only args
    parser.add_argument("--web-ui",   action="store_true", help="Launch Locust web UI")
    parser.add_argument("--web-port", type=int, default=8089, help="Web UI port")
    parser.add_argument("--csv",      type=str, default=None, help="CSV output prefix")
    parser.add_argument("--html",     type=str, default=None, help="HTML report output file")

    # Kubernetes args
    parser.add_argument("-k", "--kubernetes",   action="store_true", help="Run test in Kubernetes via Locust Operator")
    parser.add_argument("--namespace",    type=str, default="testing",     help="Kubernetes namespace")
    parser.add_argument("--workers",      type=int, default=2,             help="Number of Locust worker replicas")
    parser.add_argument("--environment",  type=str, default="dev",         help="Environment name (dev/staging/prod)")
    parser.add_argument("--acrname",      type=str, default=None,          help="ACR registry hostname (e.g. myacr.azurecr.io)")
    parser.add_argument("--graceful-exit",type=str, default="120s",        help="Locust graceful stop timeout")
    parser.add_argument("--test-timeout", type=int, default=7200,          help="Max seconds to wait for test completion")
    parser.add_argument("--template-dir", type=str, default="templates",   help="Path to Locust CR templates")
    parser.add_argument("--manifest-dir", type=str, default="manifest",    help="Path to K8s manifest templates")

    args = parser.parse_args()

    # Load and apply config overrides
    config = Config(args.config)
    if args.users      is not None: config.config["USERS"]      = str(args.users)
    if args.spawn_rate is not None: config.config["SPAWN_RATE"] = str(args.spawn_rate)
    if args.run_time   is not None: config.config["RUN_TIME"]   = args.run_time
    if args.base_url   is not None: config.config["BASE_URL"]   = args.base_url
    if args.headless:               config.config["HEADLESS"]   = "true"
    if args.headed:                 config.config["HEADLESS"]   = "false"

    config.export_to_env()
    config.display()

    if not Path(args.testfile).exists():
        print(f"Error: Test file not found: {args.testfile}")
        sys.exit(1)

    # -- Kubernetes mode --
    if args.kubernetes:
        run_kubernetes(args, config)
        return

    # -- Local mode --
    users      = int(config.get("USERS", "1"))
    spawn_rate = float(config.get("SPAWN_RATE", "1"))

    locust_cmd = ["locust", "-f", str(args.testfile)]

    if args.web_ui:
        locust_cmd.extend(["--web-host", "0.0.0.0", "--web-port", str(args.web_port)])
        print(f"\nStarting Locust Web UI at http://localhost:{args.web_port}\n")
    else:
        run_time = config.get("RUN_TIME", "5m")
        locust_cmd.extend(["--headless", "-u", str(users), "-r", str(spawn_rate), "-t", run_time])
        if args.csv:  locust_cmd.extend(["--csv",  args.csv])
        if args.html: locust_cmd.extend(["--html", args.html])
        print(f"\nStarting test: {users} users, spawn rate {spawn_rate}/s, duration {run_time}\n")

    try:
        subprocess.run(locust_cmd, check=True)
        print("\nTest completed successfully\n")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"\nTest failed with error code {e.returncode}\n")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\nTest interrupted by user\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
