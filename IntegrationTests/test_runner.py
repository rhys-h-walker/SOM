"""
This is the SOM integration test runner file. Pytest automatically discovers
this file and will find all .som test files in the below directories.
"""

import subprocess
from pathlib import Path
import os
import sys
import pytest
import yaml
import conftest as external_vars


def debug(message):
    """
    Take a string as a mesasage and output if DEBUG is true
    """
    if external_vars.DEBUG is True:
        print(message)


def debug_list(message_list, prefix="", postfix=""):
    """
    Take a list of messages and output if DEBUG is true, with a prefix and a postfix
    """
    if external_vars.DEBUG is True:
        for message in message_list:
            print(prefix + str(message) + postfix)


def locate_tests(path, test_files):
    """
    Locate all test files that exist in the given directory
    Ignore any tests which are in the ignoredTests directory
    Return a list of paths to the test files
    """
    # To ID a file will be opened and at the top there should be a comment which starts with VM:
    for file_path in Path(path).glob("*.som"):
        # Check if the file is in the ignored tests (Check via path, multiple tests named test.som)
        with open(file_path, "r", encoding="utf-8") as f:
            contents = f.read()
            if "VM" in contents:
                test_files.append(file_path)

    return test_files


def read_directory(path, test_files):
    """
    Recursively read all sub directories
    Path is the directory we are currently in
    testFiles is the list of test files we are building up
    """
    for directory in Path(path).iterdir():
        if directory.is_dir():
            read_directory(directory, test_files)
        else:
            continue

    locate_tests(path, test_files)


def assemble_test_dictionary(test_files):
    """
    Assemble a dictionary of
    name: the name of the test file
    stdout/stderr: the expected output of the test
    """
    tests = []
    for file_path in test_files:
        test_dict = parse_test_file(file_path)
        if test_dict is None:
            continue
        tests.append(test_dict)

    return tests


def parse_test_file(test_file):
    """
    parse the test file to extract the important information
    """
    test_info_dict = {"name": test_file, "stdout": [], "stderr": [], "customCP": "NaN"}
    with open(test_file, "r", encoding="utf-8") as open_file:
        contents = open_file.read()
        comment = contents.split('"')[1]

        # Make sure if using a custom test classpath that it is above
        # Stdout and Stderr
        if "custom_classpath" in comment:
            comment_lines = comment.split("\n")
            for line in comment_lines:
                if "custom_classpath" in line:
                    test_info_dict["customCP"] = line.split("custom_classpath:")[1].strip()
                    continue

        if "stdout" in comment:
            std_out = comment.split("stdout:")[1]
            if "stderr" in std_out:
                std_err_inx = std_out.index("stderr:")
                std_out = std_out[:std_err_inx]
            std_out = std_out.replace("...", "")
            std_err_l = std_out.split("\n")
            std_err_l = [line.strip() for line in std_err_l if line.strip()]
            test_info_dict["stdout"] = std_err_l

        if "stderr" in comment:
            std_err = comment.split("stderr:")[1]
            if "stdout" in std_err:
                std_out_inx = std_err.index("stdout:")
                std_err = std_err[:std_out_inx]
            std_err = std_err.replace("...", "")
            std_err_l = std_err.split("\n")
            std_err_l = [line.strip() for line in std_err_l if line.strip()]
            test_info_dict["stderr"] = std_err_l

        test_tuple = (
            test_info_dict["name"],
            test_info_dict["stdout"],
            test_info_dict["stderr"],
            test_info_dict["customCP"],
        )

    return test_tuple


def check_out(test_outputs, expected_std_out, expected_std_err):
    """
    check if the output of the test matches the expected output
    result: The object returned by subprocess.run
    expstd: The expected standard output
    experr: The expected standard error output
    Returns: Boolean indicating if result matches expected output

    note: This method does not directly error, just checks conditions
    """

    # Tests borrowed from lang_tests and stderr and atdout will not directly match that of all SOMs
    # Order of the output is important

    std_out = test_outputs.stdout.splitlines()
    std_err = test_outputs.stderr.splitlines()

    # Check if each line in stdout and stderr is in the expected output
    for line in expected_std_out:
        if not any(line in out_line for out_line in std_out):
            return False
        if line in std_out:
            std_out.remove(line)
        if line in std_err:
            std_err.remove(line)

    for line in expected_std_err:
        if not any(line in err_line for err_line in std_err):
            return False
        if line in std_out:
            std_out.remove(line)
        if line in std_err:
            std_err.remove(line)

    # If we made it this far then the test passed
    return True


# Code below here runs before pytest finds it's methods

location = os.path.relpath(os.path.dirname(__file__) + "/Tests")

# Work out settings for the application (They are labelled REQUIRED or OPTIONAL)
if "DEBUG" in os.environ:  # OPTIONAL
    external_vars.DEBUG = os.environ["DEBUG"].lower() == "true"

if "CLASSPATH" not in os.environ:  # REQUIRED
    sys.exit("Please set the CLASSPATH environment variable")

if "EXECUTABLE" not in os.environ:  # REQUIRED
    sys.exit("Please set the EXECUTABLE environment variable")

if "TEST_EXCEPTIONS" in os.environ:  # OPTIONAL
    external_vars.TEST_EXCEPTIONS = os.environ["TEST_EXCEPTIONS"]

if "GENERATE_REPORT" in os.environ:  # OPTIONAL
    # Value is the location
    # Its prescense in env variables signifies intent to save
    external_vars.GENERATE_REPORT_LOCATION = os.environ["GENERATE_REPORT"]
    external_vars.GENERATE_REPORT = True

external_vars.CLASSPATH = os.environ["CLASSPATH"]
external_vars.EXECUTABLE = os.environ["EXECUTABLE"]

debug(
    f"""
\n\nWelcome to SOM Integration Testing
\nDEBUG is set to: {external_vars.DEBUG}
CLASSPATH is set to: {external_vars.CLASSPATH}
EXECUTABLE is set to: {external_vars.EXECUTABLE}
TEST_EXCEPTIONS is set to: {external_vars.TEST_EXCEPTIONS}
GENERATE_REPORT is set to: {external_vars.GENERATE_REPORT}
GENERATE_REPORT_LOCATION is set to: {external_vars.GENERATE_REPORT_LOCATION}
"""
)

debug("Opening test_tags")
if external_vars.TEST_EXCEPTIONS:
    with open(f"{external_vars.TEST_EXCEPTIONS}", "r", encoding="utf-8") as file:
        yamlFile = yaml.safe_load(file)
        external_vars.known_failures = yamlFile["known_failures"]
        external_vars.failing_as_unspecified = yamlFile["failing_as_unspecified"]
        external_vars.unsupported = yamlFile["unsupported"]
        # Tests here do not fail at a SOM level but at a python level
        external_vars.do_not_run = yamlFile["do_not_run"]

debug_list(external_vars.known_failures, prefix="Failure expected from: ")
debug_list(
    external_vars.failing_as_unspecified,
    prefix="Failure expected through undefined behaviour: ",
)
debug_list(
    external_vars.unsupported, prefix="Test that fails through unsupported bahaviour: "
)
debug_list(
    external_vars.do_not_run,
    prefix="Test that will not run through python breaking logic: ",
)

testFiles = []
read_directory(location, testFiles)
TESTS_LIST = assemble_test_dictionary(testFiles)


@pytest.mark.parametrize(
    "name,stdout,stderr,custom_classpath",
    TESTS_LIST,
    ids=[str(test_args[0]) for test_args in TESTS_LIST],
)
def tests_runner(name, stdout, stderr, custom_classpath):
    """
    Take an array of dictionaries with test file names and expected output
    Run all of the tests and check the output
    Cleanup the build directory if required
    """

    # Check if a test shoudld not be ran
    if str(name) in external_vars.do_not_run:
        debug(f"Not running test {name}")
        pytest.skip("Test included in do_not_run")

    if custom_classpath != "NaN":
        debug(f"Using custom classpath: {custom_classpath}")
        command = f"{external_vars.EXECUTABLE} -cp {custom_classpath} {name}"
    else:
        command = f"{external_vars.EXECUTABLE} -cp {external_vars.CLASSPATH} {name}"

    debug(f"Running test: {name}")

    result = subprocess.run(
        command, capture_output=True, text=True, shell=True, check=False
    )

    # Produce potential error messages now and then run assertion
    error_message = f"""
Test failed for: {name}
Expected stdout: {stdout}
Given stdout   : {result.stdout}
Expected stderr: {stderr}
Given stderr   : {result.stderr}
Command used   : {command}
"""

    if result.returncode != 0:
        error_message += f"Command failed with return code: {result.returncode}\n"

    test_pass_bool = check_out(result, stdout, stderr)

    # Check if we have any unexpectedly passing tests
    if (
        str(name) in external_vars.known_failures and test_pass_bool
    ):  # Test passed when it is not expected tp
        external_vars.tests_passed_unexpectedly.append(name)
        assert False, f"Test {name} is in known_failures but passed"
    elif (
        str(name) in external_vars.known_failures and test_pass_bool is False
    ):  # Test failed as expected
        assert True

    if (
        str(name) in external_vars.failing_as_unspecified and test_pass_bool
    ):  # Test passed when it is not expected tp
        external_vars.tests_passed_unexpectedly.append(name)
        assert False, f"Test {name} is in failing_as_unspecified but passed"
    elif (
        str(name) in external_vars.failing_as_unspecified and test_pass_bool is False
    ):  # Test failed as expected
        assert True

    if (
        str(name) in external_vars.unsupported and test_pass_bool
    ):  # Test passed when it is not expected tp
        external_vars.tests_passed_unexpectedly.append(name)
        assert False, f"Test {name} is in unsupported but passed"
    elif (
        str(name) in external_vars.unsupported and test_pass_bool is False
    ):  # Test failed as expected
        assert True

    if (
        str(name) not in external_vars.unsupported
        and str(name) not in external_vars.known_failures
        and str(name) not in external_vars.failing_as_unspecified
    ):
        if not test_pass_bool:
            external_vars.tests_failed_unexpectedly.append(name)
        assert (
            test_pass_bool
        ), f"Error on test, {name} expected to pass: {error_message}"
