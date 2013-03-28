# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

r"""Data structures representing Android packages described by
Mozilla's source tree.
"""

from data import (
    TreeMetadata,
    SandboxDerived,
)


class AndroidPackageData(object):
    """
    A dumb container describing an Android Package.

    Encapsulates:

    * regular resources
    * external resources
    * preprocessed resources

    External resources are those outside of the source directory
    describing the package -- usually, these are branding resources.
    """
    __slots__ = (
        'resources',
        'preprocessed_resources',
        'external_resources',
        '_input_base',
        '_output_base',
    )

    def __init__(self, input_base='res/', output_base='res/'):
        """
        Sane Android packages copy resources from `$(SRCDIR)/res` to
        $(OBJDIR)/res`.  Fennec copies resources from
        `$(SRCDIR)/resources` to `$(OBJDIR)/res`.

        * `input_base`: copy resources from `$(SRCDIR)/input_base`
        * `output_base`: copy resources to `$(OBJDIR)/output_base`
        """
        self._input_base = input_base
        self._output_base = output_base
        self.resources = {}
        self.preprocessed_resources = {}
        self.external_resources = {}

    def add_resource(self, src, dst):
        self.resources[dst] = src

    def add_resources(self, *resources):
        for dst in resources:
            # dst like 'res/layout/foo.xml', src like 'resources/layout/foo.xml'
            src = dst.replace(self._output_base, self._input_base)
            self.resources[dst] = src

    def add_external_resource(self, src, dst):
        # dst like 'res/drawable-mdpi/logo.png', src like 'mobile/android/branding/unofficial/content/logo.png'
        self.external_resources[dst] = src

    def _add_preprocessed_resource(self, src, dst):
        self.preprocessed_resources[dst] = src

    def add_preprocessed_resources(self, *resources):
        for dst in resources:
            # dst like 'res/layout/foo.xml', src like 'resources/layout/foo.xml.in'
            src = dst.replace(self._output_base, self._input_base) + '.in'
            self.preprocessed_resources[dst] = src

    def all_output_filenames(self):
        outset = set()
        outset |= set(self.resources.keys())
        outset |= set(self.external_resources.keys())
        outset |= set(self.preprocessed_resources.keys())
        return outset

class AndroidPackage(SandboxDerived):
    """Describe an Android package.

    A thin wrapper around an `AndroidPackageData` instance.
    """
    __slots__ = ('package',)

    def __init__(self, sandbox, package):
        SandboxDerived.__init__(self, sandbox)

        assert isinstance(package, AndroidPackageData)
        self.package = package
