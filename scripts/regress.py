from common import *
import unittest
bounded()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
finish('regression.json',dict(tests=result.testsRun,failures=len(result.failures),
                             errors=len(result.errors),all_checks_passed=result.wasSuccessful()))
if not result.wasSuccessful():raise SystemExit(1)
