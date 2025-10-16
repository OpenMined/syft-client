#!/usr/bin/env python3
"""
Local notebook test runner with automated input handling.
Tests notebooks with real Gmail accounts before CI integration.

Usage:
    python ci/run_notebook_local.py --test e2e-sales
    python ci/run_notebook_local.py --test e2e-wildchat
    python ci/run_notebook_local.py --test all
"""

import argparse
import sys
from pathlib import Path
import time
import json
from datetime import datetime


class NotebookTestRunner:
    def __init__(self, do_email="test1@openmined.org", ds_email="test2@openmined.org"):
        self.do_email = do_email
        self.ds_email = ds_email
        self.test_results = []
        self.output_dir = Path("test_outputs") / datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_notebook(self, notebook_path, inputs, timeout=600):
        """
        Run a single notebook with automated inputs by modifying in memory.

        Args:
            notebook_path: Path to the notebook file
            inputs: List of input strings to provide
            timeout: Execution timeout in seconds
        """
        import nbformat
        from nbconvert.preprocessors import ExecutePreprocessor

        notebook_path = Path(notebook_path)
        print(f"\n{'=' * 80}")
        print(f"Running: {notebook_path.name}")
        print(f"Inputs: {inputs}")
        print(f"{'=' * 80}\n")

        # Prepare output path
        output_name = f"{notebook_path.stem}_executed.ipynb"
        output_path = self.output_dir / notebook_path.parent.name / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()

        try:
            # Read the notebook
            with open(notebook_path, "r") as f:
                nb = nbformat.read(f, as_version=4)

            # Replace input() calls with hardcoded values in memory
            input_counter = 0
            for cell in nb.cells:
                if cell.cell_type == "code":
                    source = cell.source
                    # Replace input() calls with actual values
                    while "input(" in source and input_counter < len(inputs):
                        # Find input() calls and replace with the actual value
                        import re

                        # Match patterns like: variable = input("prompt")
                        pattern = r"(\w+)\s*=\s*input\([^)]*\)"
                        match = re.search(pattern, source)
                        if match:
                            var_name = match.group(1)
                            replacement = f'{var_name} = "{inputs[input_counter]}"  # input() replaced'
                            source = re.sub(pattern, replacement, source, count=1)
                            input_counter += 1
                        else:
                            break
                    cell.source = source

            # Execute the modified notebook
            ep = ExecutePreprocessor(timeout=timeout, kernel_name="python3")
            ep.preprocess(nb, {"metadata": {"path": str(notebook_path.parent)}})

            # Save the executed notebook
            with open(output_path, "w") as f:
                nbformat.write(nb, f)

            elapsed = time.time() - start_time
            print(f"✅ SUCCESS: {notebook_path.name} ({elapsed:.1f}s)")
            print(f"Output saved to: {output_path}")
            self.test_results.append(
                {
                    "notebook": str(notebook_path),
                    "status": "SUCCESS",
                    "elapsed": elapsed,
                    "output": str(output_path),
                }
            )
            return True

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            print(f"❌ FAILED: {notebook_path.name} ({elapsed:.1f}s)")
            print(f"Error: {error_msg[:500]}")  # Limit error message length
            self.test_results.append(
                {
                    "notebook": str(notebook_path),
                    "status": "FAILED",
                    "elapsed": elapsed,
                    "error": error_msg,
                }
            )
            return False

    def test_e2e_sales(self):
        """Test E2E sales dataset workflow"""
        print("\n🧪 Testing E2E Sales Workflow...")

        # Step 1: DO sets up dataset
        success_do = self.run_notebook(
            "test_notebooks/e2e-demo/Beach_DO_Notebook.ipynb",
            inputs=[self.do_email, self.ds_email],
            timeout=300,
        )

        if not success_do:
            print("⚠️  DO notebook failed, skipping DS notebook")
            return False

        print("\n⏳ Waiting 10 seconds for sync...")
        time.sleep(10)

        # Step 2: DS submits job
        success_ds = self.run_notebook(
            "test_notebooks/e2e-demo/Beach_DS_Notebook.ipynb",
            inputs=[self.ds_email, self.do_email],
            timeout=300,
        )

        return success_do and success_ds

    def test_e2e_wildchat(self):
        """Test E2E wildchat dataset workflow"""
        print("\n🧪 Testing E2E Wildchat Workflow...")

        # Step 1: DO sets up dataset
        success_do = self.run_notebook(
            "test_notebooks/e2e-demo-wildchat/Beach_DO_Notebook.ipynb",
            inputs=[self.do_email, self.ds_email],
            timeout=300,
        )

        if not success_do:
            print("⚠️  DO notebook failed, skipping DS notebook")
            return False

        print("\n⏳ Waiting 10 seconds for sync...")
        time.sleep(10)

        # Step 2: DS submits job
        success_ds = self.run_notebook(
            "test_notebooks/e2e-demo-wildchat/Beach_DS_Notebook.ipynb",
            inputs=[self.ds_email, self.do_email],
            timeout=300,
        )

        return success_do and success_ds

    def test_login(self):
        """Test basic login functionality"""
        print("\n🧪 Testing Login...")

        return self.run_notebook(
            "test_notebooks/Syft Job Login.ipynb", inputs=[], timeout=120
        )

    def test_sync(self):
        """Test sync functionality"""
        print("\n🧪 Testing Sync...")

        return self.run_notebook(
            "test_notebooks/Test Sync.ipynb", inputs=[], timeout=300
        )

    def test_serve(self):
        """Test syft-serve functionality"""
        print("\n🧪 Testing Serve...")

        return self.run_notebook(
            "test_notebooks/test_serve.ipynb", inputs=[], timeout=180
        )

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80 + "\n")

        passed = sum(1 for r in self.test_results if r["status"] == "SUCCESS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAILED")
        errors = sum(1 for r in self.test_results if r["status"] == "ERROR")
        timeouts = sum(1 for r in self.test_results if r["status"] == "TIMEOUT")
        total = len(self.test_results)

        print(f"Total: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"💥 Errors: {errors}")
        print(f"⏱️  Timeouts: {timeouts}")
        print()

        for result in self.test_results:
            status_icon = {
                "SUCCESS": "✅",
                "FAILED": "❌",
                "ERROR": "💥",
                "TIMEOUT": "⏱️",
            }.get(result["status"], "❓")

            notebook_name = Path(result["notebook"]).name
            print(f"{status_icon} {notebook_name:<50} {result['elapsed']:>6.1f}s")

        # Save results to JSON
        results_file = self.output_dir / "test_results.json"
        with open(results_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "do_email": self.do_email,
                    "ds_email": self.ds_email,
                    "summary": {
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "errors": errors,
                        "timeouts": timeouts,
                    },
                    "results": self.test_results,
                },
                f,
                indent=2,
            )

        print(f"\nResults saved to: {results_file}")
        print(f"Outputs saved to: {self.output_dir}")

        return passed == total


def main():
    parser = argparse.ArgumentParser(description="Run notebook tests locally")
    parser.add_argument(
        "--test",
        choices=["e2e-sales", "e2e-wildchat", "login", "sync", "serve", "all"],
        default="e2e-sales",
        help="Test to run",
    )
    parser.add_argument(
        "--do-email", default="test1@openmined.org", help="Data Owner email"
    )
    parser.add_argument(
        "--ds-email", default="test2@openmined.org", help="Data Scientist email"
    )

    args = parser.parse_args()

    runner = NotebookTestRunner(do_email=args.do_email, ds_email=args.ds_email)

    print(f"""
╔════════════════════════════════════════════════════════════════╗
║              Notebook Local Test Runner                       ║
╚════════════════════════════════════════════════════════════════╝

Data Owner:     {args.do_email}
Data Scientist: {args.ds_email}
Test Suite:     {args.test}
""")

    success = True

    if args.test == "all":
        # Run all tests
        success &= runner.test_login()
        success &= runner.test_serve()
        success &= runner.test_e2e_sales()
        success &= runner.test_e2e_wildchat()
        success &= runner.test_sync()
    elif args.test == "e2e-sales":
        success = runner.test_e2e_sales()
    elif args.test == "e2e-wildchat":
        success = runner.test_e2e_wildchat()
    elif args.test == "login":
        success = runner.test_login()
    elif args.test == "sync":
        success = runner.test_sync()
    elif args.test == "serve":
        success = runner.test_serve()

    runner.print_summary()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
