import subprocess
import sys


def run_tests():
    """Запуск тестов через subprocess"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/tests_tasks_api.py",
            "-v",
            "--tb=short"
        ], capture_output=True, text=True)

        print("STDOUT:")
        print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        print(f"Return code: {result.returncode}")
        return result.returncode

    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


if __name__ == "__main__":
    print("🚀 Запуск тестов TODO List API...")
    exit_code = run_tests()
    sys.exit(exit_code)