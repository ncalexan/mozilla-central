# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import unicode_literals

import os
import time

from StringIO import StringIO
import unittest

from mozunit import main

from mozbuild.backend.android import AndroidPackageMakefileFragment
from mozbuild.backend.configenvironment import ConfigEnvironment
from mozbuild.backend.recursivemake import RecursiveMakeBackend
from mozbuild.frontend.emitter import TreeMetadataEmitter
from mozbuild.frontend.reader import BuildReader
from mozbuild.frontend.android import AndroidPackageData

from mozbuild.test.backend.common import BackendTester


class TestAndroidPackageMakefileFragment(unittest.TestCase):
    def setUp(self):
        self.package = AndroidPackageData(input_base='input/', output_base='output/')

        self.package.add_resources('output/dir1/test1a.xml')
        self.package.add_resources('output/dir1/test1b.xml')
        self.package.add_resources('output/dir2/test2.xml')

        self.package.add_preprocessed_resources('output/dir3/test1.xml')
        self.package.add_preprocessed_resources('output/dir3/test2.xml')
        self.package.add_preprocessed_resources('output/dir4/test3.xml')

        self.package.add_external_resource(src='input/dir5/test1.xml',
                                           dst='output/dir6/test2.xml')
        self.package.add_external_resource(src='input/dir5/test1.xml',
                                           dst='output/dir7/test3.xml')

        self.fragment = AndroidPackageMakefileFragment(self.package)

    REGULAR = '''
INSTALL_output-dir1_FILES += input/dir1/test1a.xml
INSTALL_output-dir1_FILES += input/dir1/test1b.xml
INSTALL_output-dir1_DEST := output/dir1
INSTALL_TARGETS += INSTALL_output-dir1
INSTALL_output-dir2_FILES += input/dir2/test2.xml
INSTALL_output-dir2_DEST := output/dir2
INSTALL_TARGETS += INSTALL_output-dir2
'''

    PREPROCESSED = '''
output-dir3 += input/dir3/test1.xml.in
output-dir3 += input/dir3/test2.xml.in
output-dir3_PATH := output/dir3
PP_TARGETS += output-dir3
output-dir4 += input/dir4/test3.xml.in
output-dir4_PATH := output/dir4
PP_TARGETS += output-dir4
'''

    EXTERNAL = '''
output/dir6/test2.xml: $(topsrcdir)/input/dir5/test1.xml
\t$(NSINSTALL) -D $(dir $@)
\tcp "$^" "$@"
output/dir7/test3.xml: $(topsrcdir)/input/dir5/test1.xml
\t$(NSINSTALL) -D $(dir $@)
\tcp "$^" "$@"
'''

    RESOURCE_LIST = '''
ANDROID_PACKAGE_RESOURCES += output/dir1/test1a.xml
ANDROID_PACKAGE_RESOURCES += output/dir1/test1b.xml
ANDROID_PACKAGE_RESOURCES += output/dir2/test2.xml
ANDROID_PACKAGE_RESOURCES += output/dir3/test1.xml
ANDROID_PACKAGE_RESOURCES += output/dir3/test2.xml
ANDROID_PACKAGE_RESOURCES += output/dir4/test3.xml
ANDROID_PACKAGE_RESOURCES += output/dir6/test2.xml
ANDROID_PACKAGE_RESOURCES += output/dir7/test3.xml
'''

    GARBAGE = '''
GARBAGE += output/dir3/test1.xml
GARBAGE += output/dir3/test2.xml
GARBAGE += output/dir4/test3.xml
GARBAGE += output/dir6/test2.xml
GARBAGE += output/dir7/test3.xml
'''

    def assertLinesEqual(self, actual, expected):
        actual_lines = [ line for line in actual.split('\n') if line ]
        expected_lines = [ line for line in expected.split('\n') if line ]
        self.assertEquals(actual_lines, expected_lines)

    def test_preprocessed(self):
        s = StringIO()
        self.fragment._write_preprocessed_resources(s)
        self.assertLinesEqual(s.getvalue(), self.PREPROCESSED)

    def test_external(self):
        s = StringIO()
        self.fragment._write_external_resources(s)
        self.assertLinesEqual(s.getvalue(), self.EXTERNAL)

    def test_regular(self):
        s = StringIO()
        self.fragment._write_internal_resources(s)
        self.assertLinesEqual(s.getvalue(), self.REGULAR)

    def test_resource_list(self):
        s = StringIO()
        self.fragment._write_resource_list(s)
        self.assertLinesEqual(s.getvalue(), self.RESOURCE_LIST)

    def test_garbage(self):
        s = StringIO()
        self.fragment._write_garbage(s)
        self.assertLinesEqual(s.getvalue(), self.GARBAGE)

    def test_write(self):
        s = StringIO()
        self.fragment.write(s)
        v = s.getvalue()

        self.assertTrue(self.PREPROCESSED in v)
        self.assertTrue(self.EXTERNAL in v)
        self.assertTrue(self.REGULAR in v)
        self.assertTrue(self.GARBAGE in v)
        self.assertTrue(self.RESOURCE_LIST in v)

if __name__ == '__main__':
    main()
