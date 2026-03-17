#!/usr/bin/env python3
"""
Test Runner — local and Kubernetes modes.

Local:      python run_test.py aml_search.py -u 10 -r 1 -t 5m
Kubernetes: python run_test.py aml_search.py --kubernetes --environment staging --workers 3
              --tests-dir /path/to/py-playwright-tests
"""

import re
import sys
import os
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


def create_test_configmap(test_file: str, tests_dir: str, namespace: str):
    """
    Create py-pw-loc-configmap containing:
      - Framework files: framework.py, common_enhanced.py, utils.py
      - Test file: the specific test being run (resolved from tests_dir)

    Uses kubectl dry-run to generate the YAML then applies it,
    so existing configmaps are updated in-place.
    """
    repo_dir = Path(__file__).parent

    # Resolve test file path — try tests_dir first, then direct path
    test_name = Path(test_file).name
    candidates = [
        Path(tests_dir) / test_name,
        Path(tests_dir) / 'tests' / test_name,
        Path(test_file),
    ]
    test_path = next((p for p in candidates if p.exists()), None)
    if test_path is None:
        raise FileNotFoundError(
            f"Test file '{test_name}' not found. Searched: {[str(p) for p in candidates]}"
        )

    print(f"INFO: Building py-pw-loc-configmap from {test_path}")

    cmd = [
        'kubectl', '-n', namespace,
        'create', 'configmap', 'py-pw-loc-configmap',
        f'--from-file=framework.py={repo_dir / "framework.py"}',
        f'--from-file=common_enhanced.py={repo_dir / "common_enhanced.py"}',
        f'--from-file=utils.py={repo_dir / "utils.py"}',
        f'--from-file={test_name}={test_path}',
        '--dry-run=client', '-o', 'yaml',
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate configmap YAML:\n{result.stderr}")

    kubectl_apply(result.stdout, namespace)
    print(f"INFO: py-pw-loc-configmap applied ({test_name} + framework files)")


def run_kubernetes(args, config):
    """
    Fire-and-forget Kubernetes dispatch.
    Creates the configmap, applies the LocustTest CR and Collector Job,
    then exits. Everything else runs autonomously in the cluster.
    """
    template_dir = Path(args.template_dir)
    manifest_dir = Path(args.manifest_dir)

    test_name   = k8s_safe_name(args.testfile)
    timestamp   = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    namespace   = args.namespace
    environment = args.environment

    users       = int(config.get("USERS", "1"))
    spawn_rate  = float(config.get("SPAWN_RATE", "1"))
    run_time    = config.get("RUN_TIME", "5m")

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

    # 1. Build and apply configmap (framework files + test file)
    create_test_configmap(args.testfile, args.tests_dir, namespace)

    # 2. Apply LocustTest CR — operator creates master + worker pods
    locust_test_yaml = render_template(
        str(template_dir / 'locust-test.yaml'), substitutions
    )
    print(f"\nINFO: Applying LocustTest CR '{test_name}'...")
    kubectl_apply(locust_test_yaml, namespace)

    # 3. Apply Collector Job — watches for test completion, then uploads to blob
    collector_yaml = render_template(
        str(manifest_dir / 'collector-job.yaml'), substitutions
    )
    print(f"INFO: Applying Collector Job '{test_name}-collector'...")
    kubectl_apply(collector_yaml, namespace)

    # 4. Exit — pipeline is done, cluster handles the rest
    print(f"""
INFO: Test dispatched successfully.
  Test:        {test_name}
  Users:       {users}
  Duration:    {run_time}
  Environment: {environment}
  Namespace:   {namespace}

  Monitor pods:  kubectl -n {namespace} get pods
  Monitor job:   kubectl -n {namespace} get job {test_name}-collector
  Collector log: kubectl -n {namespace} logs job/{test_name}-collector -c upload
""")


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
  python run_test.py aml_search.py -u 10 -r 1 -t 5m

  # Kubernetes run (fire-and-forget)
  python run_test.py aml_search.py --kubernetes --environment staging \\
    --workers 3 --tests-dir /path/to/py-playwright-tests

  # Local with web UI
  python run_test.py aml_search.py --web-ui
        """
    )

    parser.add_argument("testfile", help="Test filename (e.g., aml_search.py)")

    # Common args
    parser.add_argument("-u", "--users",      type=int,   default=None)
    parser.add_argument("-r", "--spawn-rate", type=float, default=None)
    parser.add_argument("-t", "--run-time",   type=str,   default=None)
    parser.add_argument("--base-url",         type=str,   default=None)
    parser.add_argument("--config",           type=str,   default="config.json")
    parser.add_argument("--headless",         action="store_true")
    parser.add_argument("--headed",           action="store_true")

    # Local-only args
    parser.add_argument("--web-ui",   action="store_true")
    parser.add_argument("--web-port", type=int, default=8089)
    parser.add_argument("--csv",      type=str, default=None)
    parser.add_argument("--html",     type=str, default=None)

    # Kubernetes args
    parser.add_argument("-k", "--kubernetes",   action="store_true",  help="Dispatch test to Kubernetes (fire-and-forget)")
    parser.add_argument("--tests-dir",    type=str, default=".",          help="Path to checked-out py-playwright-tests repo")
    parser.add_argument("--namespace",    type=str, default="testing")
    parser.add_argument("--workers",      type=int, default=2)
    parser.add_argument("--environment",  type=str, default="dev")
    parser.add_argument("--acrname",      type=str, default=None)
    parser.add_argument("--graceful-exit",type=str, default="120s")
    parser.add_argument("--template-dir", type=str, default="templates")
    parser.add_argument("--manifest-dir", type=str, default="manifest")

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

    # -- Kubernetes mode (fire-and-forget) --
    if args.kubernetes:
        run_kubernetes(args, config)
        return

    # -- Local mode --
    test_file = Path(args.testfile)
    if not test_file.exists():
        # Try in tests_dir
        test_file = Path(args.tests_dir) / args.testfile
    if not test_file.exists():
        print(f"Error: Test file not found: {args.testfile}")
        sys.exit(1)

    users      = int(config.get("USERS", "1"))
    spawn_rate = float(config.get("SPAWN_RATE", "1"))
    locust_cmd = ["locust", "-f", str(test_file)]

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
        print("\nTest interrupted\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
