# tests/sample_test_failure.py
import sys
import datetime

print(f"Sample Test (Failure) started at {datetime.datetime.now()}")
print("This test simulates a failed operation.", file=sys.stderr)
# Simulate some work then an error
print("Working on something critical...", file=sys.stdout)
print("Oh no, an error occurred!", file=sys.stderr)
sys.exit(1) # Explicitly exit with failure code
