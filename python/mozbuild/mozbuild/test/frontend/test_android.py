# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest

from mozunit import main

from mozbuild.frontend.android import (
    AndroidPackageData,
)


class TestAndroidPackageData(unittest.TestCase):
    def test_attributes(self):
        r"""Unrecognized attributes cannot be written."""

        package = AndroidPackageData()

        # Unknown attributes raise.
        def _test(p):
            return p.attribute_that_does_not_exist
        self.assertRaises(AttributeError, _test, package)

        # Known attributes are okay.
        self.assertFalse(package.resources)

    def test_resource_bases(self):
        r"""Setting `input_base` and `output_base` has effect."""

        package = AndroidPackageData(input_base='input/',
                                     output_base='output/')

        package.add_resources('output/xml/test.xml')
        package.add_preprocessed_resources('output/xml/pre.xml')

        resources = {
            'output/xml/test.xml': 'input/xml/test.xml',
        }
        self.assertEquals(package.resources, resources)

        preprocessed_resources = {
            'output/xml/pre.xml': 'input/xml/pre.xml.in',
        }
        self.assertEquals(package.preprocessed_resources, preprocessed_resources)

    def test_resources(self):
        r"""Adding resources of different types accumulates and
        translates paths."""

        package = AndroidPackageData()

        # Regular resources.
        package.add_resources(
            'res/xml/test.xml',
        )
        package.add_resources(
            'res/layout/test.xml',
        )

        resources = {
            'res/xml/test.xml': 'res/xml/test.xml',
            'res/layout/test.xml': 'res/layout/test.xml',
        }
        self.assertEquals(package.resources, resources)
        self.assertFalse(package.external_resources)
        self.assertFalse(package.preprocessed_resources)

        # External resources.
        package.add_external_resource(
            src='mobile/android/base/branding/unofficial/content/icon.png',
            dst='res/drawable-mdpi/icon.png',
        )

        external_resources = {
            'res/drawable-mdpi/icon.png': 'mobile/android/base/branding/unofficial/content/icon.png',
        }
        self.assertEquals(package.resources, resources)
        self.assertEquals(package.external_resources, external_resources)
        self.assertFalse(package.preprocessed_resources)

        # Preprocessed resources.
        package.add_preprocessed_resources(
            'res/xml/sync_syncadapter.xml',
            'res/layout/test.xml',
        )

        preprocessed_resources = {
            'res/xml/sync_syncadapter.xml': 'res/xml/sync_syncadapter.xml.in',
            'res/layout/test.xml': 'res/layout/test.xml.in',
        }
        self.assertEquals(package.resources, resources)
        self.assertEquals(package.external_resources, external_resources)
        self.assertEquals(package.preprocessed_resources, preprocessed_resources)

if __name__ == '__main__':
    main()
