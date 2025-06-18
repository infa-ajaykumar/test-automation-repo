# tests/sample_test_success.py
import sys
import datetime

print(f"Sample Test (Success) started at {datetime.datetime.now()}")
print("This test simulates a successful operation.")
# Simulate some work
for i in range(3):
    print(f"Working... step {i+1}")
print("Test completed successfully.")
sys.exit(0) # Explicitly exit with success code
