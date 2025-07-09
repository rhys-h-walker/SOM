"""
Defines variables that are required for a report to be generated.
"""

import os

# Report Generate Logic
tests_failed_unexpectedly = []
tests_passed_unexpectedly = []
tests_passed = 0  # pylint: disable=invalid-name
tests_failed = 0  # pylint: disable=invalid-name
total_tests = 0  # pylint: disable=invalid-name
tests_skipped = 0  # pylint: disable=invalid-name

# Lists containing references to each exception test
known_failures = []
failing_as_unspecified = []
unsupported = []
do_not_run = []

# Environment variables
DEBUG = False
CLASSPATH = ""
EXECUTABLE = ""
GENERATE_REPORT_LOCATION = ""
TEST_EXCEPTIONS = ""
GENERATE_REPORT = False


# Log data
def pytest_runtest_logreport(report):
    """
    Increment the counters for what action was performed
    """
    # Global required here to access counters
    # Not ideal but without the counters wouldn't work
    global total_tests, tests_passed, tests_failed, tests_skipped  # pylint: disable=global-statement
    if report.when == "call":  # only count test function execution, not setup/teardown
        total_tests += 1
        if report.passed:
            tests_passed += 1
        elif report.failed:
            tests_failed += 1
        elif report.skipped:
            tests_skipped += 1


# Run after all tests completed, Generate a report of failing and passing tests
def pytest_sessionfinish():
    """
    Generate report based on test run
    """
    print("Running this method")
    if GENERATE_REPORT:
        os.makedirs(GENERATE_REPORT_LOCATION, exist_ok=True)

        # Generate a report_message to save
        report_message = f"""
Pytest Completed with {tests_passed}/{total_tests} passing:

Test_total: {total_tests}  ** This includes those that we expect to fail **
Tests_passed: {tests_passed} ** This includes those that we expect to fail **
Tests_failed: {tests_failed}
Tests_skipped: {tests_skipped}

Tests that passed unexpectedly:
{'\n'.join(f"{test}" for test in tests_passed_unexpectedly)}

Tests that failed unexpectedly:
{'\n'.join(f"{test}" for test in tests_failed_unexpectedly)}

## ENVIRONMENT VARIABLES USED ##

Executable: {EXECUTABLE}
Classpath: {CLASSPATH}
Test Exceptions: {TEST_EXCEPTIONS}
Debug: {DEBUG}
Generage Report: {GENERATE_REPORT_LOCATION}

## TAGGED TESTS FILE ##

Known_failures:
{'\n'.join(f"{test}" for test in known_failures)}

Failing_as_unspecified:
{'\n'.join(f"{test}" for test in failing_as_unspecified)}

Unsupported:
{'\n'.join(f"{test}" for test in unsupported)}

Do_not_run:
{'\n'.join(f"{test}" for test in do_not_run)}
"""
        print(f"Report location {GENERATE_REPORT_LOCATION}/report.txt")
        with open(f"{GENERATE_REPORT_LOCATION}/report.txt", "w", encoding="utf-8") as f:
            f.write(report_message)
            f.close()
