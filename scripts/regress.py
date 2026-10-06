from common import ROOT, bounded, finish
import unittest


def discover_suite(root=ROOT):
    loader = unittest.TestLoader()
    suite = loader.discover(str(root / 'tests'))
    if loader.errors or not suite.countTestCases():
        raise RuntimeError('current regression discovery failed')
    return suite


def validate_summary(payload, expected_tests):
    counts = ('tests', 'discovered_tests', 'failures', 'errors', 'skipped',
              'expected_failures', 'unexpected_successes')
    if (type(payload) is not dict
        or type(expected_tests) is not int or expected_tests <= 0
        or any(type(payload.get(field)) is not int for field in counts)
        or payload['tests'] != expected_tests
        or payload['discovered_tests'] != expected_tests
        or any(payload[field] != 0 for field in counts[2:])
        or payload.get('all_checks_passed') is not True):
        raise RuntimeError('current regression summary mismatch')


def main():
    bounded()
    suite = discover_suite()
    expected_tests = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    payload = dict(tests=result.testsRun, discovered_tests=expected_tests,
                   failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                   unexpected_successes=len(result.unexpectedSuccesses),
                   all_checks_passed=(result.wasSuccessful() and result.testsRun == expected_tests
                                      and not result.skipped and not result.expectedFailures
                                      and not result.unexpectedSuccesses))
    finish('regression.json', payload)
    validate_summary(payload, expected_tests)


if __name__ == '__main__':
    main()
