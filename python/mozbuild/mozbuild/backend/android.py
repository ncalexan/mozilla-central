# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import unicode_literals

from collections import defaultdict

import os

class AndroidPackageMakefileFragment(object):
    r'''A Makefile fragment encapsulating the rules for building an
    Android APK file.

    For resources, these rules:

      * ensure resource directories exist
      * install regular resources
      * copy external resources
      * preprocess appropriate resources
      * write ANDROID_PACKAGE_RESOURCES for R.java to depend on
      * add to GARBAGE and GARBAGE_DIRS
    '''
    def __init__(self, package):
        self.package = package

    def _directories(self, files):
        dirset = set()
        for dst in files:
            dstdir = os.path.dirname(dst)
            dirset.add(dstdir)
        return dirset

    def _all_output_directories(self):
        return self._directories(self.package.all_output_filenames())

    def _write_resource_directories(self, backend_file):
        for dstdir in sorted(self._all_output_directories()):
            backend_file.write('ANDROID_PACKAGE_DIRS += %s\n' % dstdir)

    def _write_resource_installs(self, backend_file):
        # group destinations by directory
        dirs = defaultdict(dict)

        for dst, src in self.package.resources.items():
            dstdir = os.path.dirname(dst)
            dirs[dstdir][dst] = src

        for dstdir in sorted(dirs.keys()):
            for dst, src in sorted(dirs[dstdir].items()):
                backend_file.write('%s: $(srcdir)/%s\n' % (dst, src))
                backend_file.write('\t$(NSINSTALL) $^ %s\n' % dstdir)
            backend_file.write('\n')

    def _write_external_resource_copies(self, backend_file):
        for dst, src in sorted(self.package.external_resources.items()):
            backend_file.write('%s: $(topsrcdir)/%s\n' % (dst, src))
            backend_file.write('\tcp $^ $@\n')
        backend_file.write('\n')

    def _write_preprocessed_resources(self, backend_file):
        for dst, src in sorted(self.package.preprocessed_resources.items()):
            backend_file.write('%s: $(srcdir)/%s\n' % (dst, src))
            backend_file.write('\t$(PYTHON) $(topsrcdir)/config/Preprocessor.py $(AUTOMATION_PPARGS) $(DEFINES) $(ACDEFINES) $< > $@\n')
        backend_file.write('\n')

    def _write_android_package_resources(self, backend_file):
        # directories...
        backend_file.write('ANDROID_PACKAGE_RESOURCES += $(call mkdir_deps,$(ANDROID_PACKAGE_DIRS))\n')

        # ... and filenames.
        for dst in sorted(self.package.all_output_filenames()):
            backend_file.write('ANDROID_PACKAGE_RESOURCES += %s\n' % dst)
        backend_file.write('\n')

    def _write_garbage(self, backend_file):
        # directories...
        backend_file.write('GARBAGE_DIRS += $(ANDROID_PACKAGE_DIRS)\n')
        backend_file.write('GARBAGE_DIRS += res\n')

        # ... and preprocessed/copied filenames.
        fnset = set()
        fnset.update(self.package.preprocessed_resources.keys())
        fnset.update(self.package.external_resources.keys())
        for dst in sorted(fnset):
            backend_file.write('GARBAGE += %s\n' % dst)
        backend_file.write('\n')

    def write(self, backend_file):
        # Temporary hack to have a sensible default rule.
        backend_file.write('all::\n\n\n')

        self._write_resource_installs(backend_file)
        self._write_external_resource_copies(backend_file)
        self._write_preprocessed_resources(backend_file)
        self._write_resource_directories(backend_file)
        self._write_android_package_resources(backend_file)
        self._write_garbage(backend_file)
