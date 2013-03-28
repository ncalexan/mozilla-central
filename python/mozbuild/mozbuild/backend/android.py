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
      * install internal resources
      * copy external resources
      * preprocess appropriate resources
      * write ANDROID_PACKAGE_RESOURCES for R.java to depend on
      * add to GARBAGE
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

    def _group_by_directory(self, resources):
        # group destinations by directory
        grouped = defaultdict(dict)
        for dst, src in resources:
            dstdir = os.path.dirname(dst)
            grouped[dstdir][dst] = src
        return grouped

    def _write_list(self, backend_file, key, items):
        for item in sorted(items):
            backend_file.write('%s += %s\n' % (key, item))

    def _write_internal_resources(self, backend_file):
        grouped = self._group_by_directory(self.package.resources.items())

        for dstdir in sorted(grouped.keys()):
            key = 'INSTALL_' + dstdir.replace('/', '-')
            self._write_list(backend_file, '%s_FILES' % key, grouped[dstdir].values())
            backend_file.write('%s_DEST := %s\n' % (key, dstdir))
            backend_file.write('INSTALL_TARGETS += %s\n' % key)

    def _write_external_resources(self, backend_file):
        for dst, src in sorted(self.package.external_resources.items()):
            backend_file.write('%s: $(topsrcdir)/%s\n' % (dst, src))
            backend_file.write('\t$(NSINSTALL) -D $(dir $@)\n')
            backend_file.write('\tcp "$^" "$@"\n')

    def _write_preprocessed_resources(self, backend_file):
        grouped = self._group_by_directory(self.package.preprocessed_resources.items())

        for dstdir in sorted(grouped.keys()):
            key = dstdir.replace('/', '-')
            self._write_list(backend_file, key, grouped[dstdir].values())
            backend_file.write('%s_PATH := %s\n' % (key, dstdir))
            backend_file.write('PP_TARGETS += %s\n' % key)

    def _write_resource_list(self, backend_file):
        self._write_list(backend_file,
                         'ANDROID_PACKAGE_RESOURCES',
                         sorted(self.package.all_output_filenames()))

    def _write_garbage(self, backend_file):
        fnset = set()
        fnset |= set(self.package.preprocessed_resources.keys())
        fnset |= set(self.package.external_resources.keys())
        for dst in sorted(fnset):
            backend_file.write('GARBAGE += %s\n' % dst)

    def write(self, backend_file):
        # Temporary hack to have a sensible default rule.
        backend_file.write('all::\n\n')

        self._write_internal_resources(backend_file)
        self._write_external_resources(backend_file)
        self._write_preprocessed_resources(backend_file)
        self._write_resource_list(backend_file)
        self._write_garbage(backend_file)
        backend_file.write('\n')
