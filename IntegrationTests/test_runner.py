import subprocess
from pathlib import Path
import os
import sys
import pytest
import yaml
import conftest as vars

def debug(message):
    """
    Take a string as a mesasage and output if DEBUG is true
    """
    if vars.DEBUG is True:
        print(message)


def debugList(messageList, prefix="", postfix=""):
    """
    Take a list of messages and output if DEBUG is true, with a prefix and a postfix
    """
    if vars.DEBUG is True:
        for message in messageList:
            print(prefix + str(message) + postfix)


def locateTests(path, testFiles):
    """
    Locate all test files that exist in the given directory
    Ignore any tests which are in the ignoredTests directory
    Return a list of paths to the test files
    """
    # To ID a file will be opened and at the top there should be a comment which starts with VM:
    for file in Path(path).glob("*.som"):
        # Check if the file is in the ignored tests (Check via path, multiple tests named test.som)
        with open(file, "r") as f:
            contents = f.read()
            if "VM" in contents:
                testFiles.append(file)

    return testFiles


def readDirectory(path, testFiles):
    """
    Recursively read all sub directories
    Path is the directory we are currently in
    testFiles is the list of test files we are building up
    """
    for directory in Path(path).iterdir():
        if directory.is_dir():
            readDirectory(directory, testFiles)
        else:
            continue

    locateTests(path, testFiles)


def assembleTestDictionary(testFiles):
    """
    Assemble a dictionary of
    name: the name of the test file
    stdout/stderr: the expected output of the test
    """
    tests = []
    for file in testFiles:
        testDict = parseTestFile(file)
        if testDict is None:
            continue
        tests.append(testDict)

    return tests


def parseTestFile(testFile):
    """
    parse the test file to extract the important information
    """
    testDict = {"name": testFile, "stdout": [], "stderr": [], "customCP": "NaN"}
    with open(testFile, "r") as f:
        contents = f.read()
        comment = contents.split('"')[1]

        # Make sure if using a custom test classpath that it is above
        # Stdout and Stderr
        if "customCP" in comment:
            commentLines = comment.split("\n")
            for line in commentLines:
                if "customCP" in line:
                    testDict["customCP"] = line.split("customCP:")[1].strip()
                    continue

        if "stdout" in comment:
            stdOut = comment.split("stdout:")[1]
            if "stderr" in stdOut:
                stdErrInx = stdOut.index("stderr:")
                stdOut = stdOut[:stdErrInx]
            stdOut = stdOut.replace("...", "")
            stdOutL = stdOut.split("\n")
            stdOutL = [line.strip() for line in stdOutL if line.strip()]
            testDict["stdout"] = stdOutL

        if "stderr" in comment:
            stdErr = comment.split("stderr:")[1]
            if "stdout" in stdErr:
                stdOutInx = stdErr.index("stdout:")
                stdErr = stdErr[:stdOutInx]
            stdErr = stdErr.replace("...", "")
            stdErrL = stdErr.split("\n")
            stdErrL = [line.strip() for line in stdErrL if line.strip()]
            testDict["stderr"] = stdErrL

        testTuple = (
            testDict["name"],
            testDict["stdout"],
            testDict["stderr"],
            testDict["customCP"],
        )

    return testTuple


def checkOut(result, expstd, experr, errorMessage):
    """
    check if the output of the test matches the expected output
    result: The object returned by subprocess.run
    expstd: The expected standard output
    experr: The expected standard error output
    errorMessage: The pregenerated error message to be used in case of failure
    Returns: Boolean indicating if result matches expected output
    """

    # Tests borrowed from lang_tests and stderr and atdout will not directly match that of all SOMs
    # Order of the output is important

    stdout = result.stdout.splitlines()
    stderr = result.stderr.splitlines()

    # Check if each line in stdout and stderr is in the expected output
    for line in expstd:
        if not any(line in out_line for out_line in stdout):
            return False
        if line in stdout:
            stdout.remove(line)
        if line in stderr:
            stderr.remove(line)

    for line in experr:
        if not any(line in err_line for err_line in stderr):
            return False
        if line in stdout:
            stdout.remove(line)
        if line in stderr:
            stderr.remove(line)

    # If we made it this far then the test passed
    return True

# Code below here runs before pytest finds it's methods

location = os.path.relpath(os.path.dirname(__file__) + "/Tests")

# Work out settings for the application (They are labelled REQUIRED or OPTIONAL)
if "DEBUG" in os.environ: # OPTIONAL
    vars.DEBUG = os.environ["DEBUG"].lower() == "true"

if "CLASSPATH" not in os.environ: # REQUIRED
    sys.exit("Please set the CLASSPATH environment variable")

if "EXECUTABLE" not in os.environ: # REQUIRED
    sys.exit("Please set the EXECUTABLE environment variable")

if "TEST_EXCEPTIONS" in os.environ: # OPTIONAL
    vars.TEST_EXCEPTIONS = os.environ["TEST_EXCEPTIONS"]

vars.GENERATE_REPORT = False
if "GENERATE_REPORT" in os.environ: # OPTIONAL
    # Value is the location
    # Its prescense in env variables signifies intent to save
    vars.GENERATE_REPORT_LOCATION = os.environ["GENERATE_REPORT"]
    vars.GENERATE_REPORT = True

vars.CLASSPATH = os.environ["CLASSPATH"]
vars.EXECUTABLE = os.environ["EXECUTABLE"]

debug(
    f"""
\n\nWelcome to SOM Integration Testing
\nDEBUG is set to: {vars.DEBUG}
CLASSPATH is set to: {vars.CLASSPATH}
EXECUTABLE is set to: {vars.EXECUTABLE}
TEST_EXCEPTIONS is set to: {vars.TEST_EXCEPTIONS}
GENERATE_REPORT is set to: {vars.GENERATE_REPORT}
GENERATE_REPORT_LOCATION is set to: {vars.GENERATE_REPORT_LOCATION}
"""
)

debug(f"Opening test_tags")
if vars.TEST_EXCEPTIONS:
    with open(f"{vars.TEST_EXCEPTIONS}", "r") as f:
        yamlFile = yaml.safe_load(f)
        vars.known_failures = (yamlFile["known_failures"])
        vars.failing_as_unspecified = (yamlFile["failing_as_unspecified"])
        vars.unsupported = (yamlFile["unsupported"])
        vars.do_not_run = yamlFile["do_not_run"] # Tests here do not fail at a SOM level but at a python level (e.g. Invalud UTF-8 characters)

debugList(vars.known_failures, prefix="Failure expected from: ")
debugList(vars.failing_as_unspecified, prefix="Failure expected through undefined behaviour: ")
debugList(vars.unsupported, prefix="Test that fails through unsupported bahaviour: ")
debugList(vars.do_not_run, prefix="Test that will not run through python breaking logic: ")

testFiles = []
readDirectory(location, testFiles)
TESTS_LIST = assembleTestDictionary(testFiles)

@pytest.mark.parametrize(
    "name,stdout,stderr,customCP",
    TESTS_LIST,
    ids=[str(test_args[0]) for test_args in TESTS_LIST],
)
def tests_runner(name, stdout, stderr, customCP):
    """
    Take an array of dictionaries with test file names and expected output
    Run all of the tests and check the output
    Cleanup the build directory if required
    """

    # Check if a test shoudld not be ran
    if (str(name) in vars.do_not_run):
        debug(f"Not running test {name}")
        pytest.skip("Test included in do_not_run")

    if customCP != "NaN":
        debug(f"Using custom classpath: {customCP}")
        command = f"{vars.EXECUTABLE} -cp {customCP} {name}"
    else:
        command = f"{vars.EXECUTABLE} -cp {vars.CLASSPATH} {name}"

    debug(f"Running test: {name}")

    result = subprocess.run(command, capture_output=True, text=True, shell=True)

    # Produce potential error messages now and then run assertion
    errMsg = f"""
Test failed for: {name}
Expected stdout: {stdout}
Given stdout   : {result.stdout}
Expected stderr: {stderr}
Given stderr   : {result.stderr}
Command used   : {command}
"""

    if result.returncode != 0:
        errMsg += f"Command failed with return code: {result.returncode}\n"

    # SOM level errors will be raised in stdout only SOM++ errors are in stderr (Most tests are for SOM level errors)
    testPassed = checkOut(result, stdout, stderr, errMsg)

    # Check if we have any unexpectedly passing tests
    if (str(name) in vars.known_failures and testPassed): # Test passed when it is not expected tp
        vars.passedUnexpectedly.append(name)
        assert(False), f"Test {name} is in known_failures but passed"
    elif (str(name) in vars.known_failures and testPassed is False): # Test failed as expected
        assert(True)

    if (str(name) in vars.failing_as_unspecified and testPassed): # Test passed when it is not expected tp
        vars.passedUnexpectedly.append(name)
        assert(False), f"Test {name} is in failing_as_unspecified but passed"
    elif (str(name) in vars.failing_as_unspecified and testPassed is False): # Test failed as expected
        assert(True)

    if (str(name) in vars.unsupported and testPassed): # Test passed when it is not expected tp
        vars.passedUnexpectedly.append(name)
        assert(False), f"Test {name} is in unsupported but passed"
    elif (str(name) in vars.unsupported and testPassed is False): # Test failed as expected
        assert(True)

    if (str(name) not in vars.unsupported and str(name) not in vars.known_failures and str(name) not in vars.failing_as_unspecified):
        if (not testPassed):
            vars.failedUnexpectedly.append(name)
        assert(testPassed), f"Error on test, {name} expected to pass: {errMsg}"
