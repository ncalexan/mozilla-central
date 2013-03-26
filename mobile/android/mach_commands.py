# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function

import errno
import logging
import os
import shutil
import sys

from Preprocessor import Preprocessor

from mozbuild.base import (
    MachCommandBase,
    MozbuildObject,
)

from mozbuild.backend.configenvironment import (
    ConfigEnvironment,
)

from mozbuild.frontend.reader import (
    MozbuildSandbox,
)

from mach.decorators import (
    CommandArgument,
    CommandProvider,
    Command,
)

from mozpack.path import (
    rebase,
    relpath,
)

from mozbuild.util import (
    ensureParentDir,
    FileAvoidWrite,
)

LOG_TAG = 'create_eclipse_projects'

class ProjectCreator(MozbuildObject):
    '''Create Eclipse projects for Firefox for Android.'''

    def __init__(self, topsrcdir, settings, log_manager, topobjdir=None,
                 workspace_directory=None,
                 project_name=None,
                 template_directory=None):
        MozbuildObject.__init__(self, topsrcdir, settings, log_manager,
                                topobjdir=topobjdir)

        self.log(logging.WARN, LOG_TAG, {'topsrcdir': self.topsrcdir,
                                         'topobjdir': self.topobjdir, },
                 'Using {topsrcdir} for source and {topobjdir} for objects.')

        self.workspace_directory = os.path.abspath(os.path.expanduser(workspace_directory))
        self.project_name = project_name
        self._template_directory = template_directory

        self._environment = None
        self._mozbuild_sandbox = None
        self._madedirs = []

        self.defines = self._get_defines()
        self._add_special_defines()

        self._init_preprocessor(self.defines)

    @property
    def template_directory(self):
        if self._template_directory is None:
            self._template_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eclipse")
        return self._template_directory

    @property
    def project_directory(self):
        return os.path.join(self.workspace_directory, self.project_name)

    @property
    def environment(self):
        if self._environment is None:
            config_status = os.path.join(self.topobjdir, 'config.status')
            self._environment = ConfigEnvironment.from_config_status(config_status)
        return self._environment

    @property
    def mozbuild_sandbox(self):
        if self._mozbuild_sandbox is None:
            path = os.path.join(self.topsrcdir, 'mobile/android/base/moz.build')
            self._mozbuild_sandbox = MozbuildSandbox(self.environment, path)
            self._mozbuild_sandbox.exec_file(path, True)
        return self._mozbuild_sandbox

    def _init_preprocessor(self, defines):
        self.pp = Preprocessor()
        self.pp.setLineEndings("lf")
        self.pp.setMarker("#")
        self.pp.do_filter("substitution")
        self.pp.context.update(defines)

    def _ensureParentDir(self, filename):
        dirname = os.path.dirname(filename)
        if dirname and not dirname in self._madedirs and not os.path.exists(dirname):
            os.makedirs(dirname)
            self._madedirs.append(dirname)

    def _preprocess(self, input_filename, output_filename, makedirs=True):
        '''
        Preprocess `input_filename` into `output_filename`, substituting
        definitions from `defines`.

        Directories needed to write output file will be created if
        `makedirs` is truthy.
        '''
        # make sure we can actually write to output directory
        if makedirs:
            self._ensureParentDir(output_filename)

        # Avoid writing unchanged files.  This trades memory (since
        # output is buffered) to save disk access (refreshes and
        # recompiles in Eclipse).
        with FileAvoidWrite(output_filename) as fo:
            self.pp.out = fo
            with open(input_filename, "rt") as fi:
                self.pp.do_include(fi)

    def _find(self, src, base, *names):
        lines = []
        def _lh(line):
            lines.append(line)

        args = ["find", base]

        names = list(names)
        while names:
            args.extend(["-name", names.pop()])
            if names:
                args.append("-o")

        if src:
            self._run_command_in_srcdir(args=args, line_handler=_lh)
        else:
            self._run_command_in_objdir(args=args, line_handler=_lh)

        return lines

    def _order_symlinks(self, d):
        r'''

        Take a list of (src, dst) associations and order it so that
        the destination links are close together on the file system.
        '''
        def _key(assoc):
            src, dst = assoc
            return dst

        ordered = []
        for (src, dst) in d:
            src = os.path.abspath(src)
            dst = os.path.abspath(dst)

            ordered.append((src, dst))
        ordered.sort(key=_key)

        return ordered

    def _shorten(self, link):
        r'''

        If link starts with `topobjdir`, `topsrcdir`, or
        `project_directory`, return a shorter textual representation.

        '''
        if link.startswith(self.topobjdir):
            _, end = link.split(self.topobjdir)
            if end.startswith('/'):
                end = end[1:]
            return os.path.join("OBJDIR", end)
        if link.startswith(self.topsrcdir):
            _, end = link.split(self.topsrcdir)
            if end.startswith('/'):
                end = end[1:]
            return os.path.join("SRCDIR", end)
        if link.startswith(self.project_directory):
            _, end = link.split(self.project_directory)
            if end.startswith('/'):
                end = end[1:]
            return os.path.join(self.project_name, end)
        return link

    def _update_or_create_symlink(self, src, dst):
        r'''

        Make `dst` point to `src` but don't always re-create links,
        since that is slow.

        '''
        try:
            existing = os.readlink(dst)
            if os.path.abspath(existing) != src:
                # dst exists, is a link, and is wrong
                os.remove(dst)
                os.symlink(src, dst)
                message = 'Replaced link from {dst} to {src}.'
            else:
                message = 'Keeping existing link from {dst} to {src}.'
        except OSError as e:
            if e.errno == errno.EINVAL:
                # dst exists but is not a link
                raise Exception("Not replacing non-link '%s'" % dst)
            elif e.errno == errno.ENOENT:
                # dst does not exist
                os.symlink(src, dst)
                message = 'Creating link from {dst} to {src}.'
            else:
                raise e

        # for logging only.
        shortsrc = self._shorten(src)
        shortdst = self._shorten(dst)

        self.log(logging.WARN, LOG_TAG,
                 {'src': shortsrc, 'dst': shortdst},
                 message)


    def _create_symlinks(self, assocs):
        r'''

        Take a list of (src, dst) associations and create symlinks
        from dst -> src.

        Removes any existing files and ensures that directory trees
        are in place to allow destination links to be created.

        Logs process.
        '''
        ordered = self._order_symlinks(assocs)

        total = len(ordered)
        count = 0
        for (src, dst) in ordered:
            self._ensureParentDir(dst)

            self._update_or_create_symlink(src, dst)

            count += 1
            if (count % 100 == 0):
                self.log(logging.WARN, LOG_TAG, {'count': count, 'total': total},
                         'Created {count} of {total} symlinks.')

    def _jar_links(self):
        d = {}
        p = os.path.join(self.project_directory, "jars")
        for fn in self._find(False, "mobile/android/base", "*.jar"):
            src = os.path.join(self.topobjdir, fn)
            dst = os.path.join(p, os.path.basename(fn))
            d[src] = dst

        return d

    def _robocop_links(self):
        d = {}
        p = os.path.join(self.project_directory, "jars")
        for fn in self._find(True, "build/mobile/robocop", "*.jar"):
            src = os.path.join(self.topsrcdir, fn)
            dst = os.path.join(p, os.path.basename(fn))
            d[src] = dst

        src = os.path.join(self.topobjdir, "build/mobile/robocop/classes")
        dst = os.path.join(self.project_directory, "classes", "robocop")
        d[src] = dst

        return d

    def _android_compatibility_links(self):
        d = {}
        src = self.defines['ANDROID_COMPAT_LIB']
        dst = os.path.join(self.project_directory, "jars", os.path.basename(src))
        d[src] = dst

        return d

    def _get_package(self, fileobj):
        for line in fileobj.readlines():
            line = line.strip()
            if line.startswith('package'):
                break
        else:
            raise Exception("Could not find package declaration in " + fileobj.name)

        package = line.split("package ")[1].split(";")[0].strip()

        # Oh god.
        package = package.replace('@ANDROID_PACKAGE_NAME@', self.defines['ANDROID_PACKAGE_NAME'])

        return package

    def _source_files(self):
        d = {}
        p = os.path.join(self.project_directory, "src")
        for fn in self._find(True, "mobile/android/base", "*.java"):
            bn = os.path.basename(fn)
            if bn in ['ANRReporter.java']:
                continue
            src = os.path.join(self.topsrcdir, fn)

            # The destination depends on the source file's *declared*
            # package, not the package determined by the source file's
            # filesystem location.
            package_dir = self._get_package(open(src)).replace('.', '/')

            dst = os.path.join(p, package_dir, bn)
            d[src] = dst

        return d

    def _resource_files(self):
        d = {}
        for fn in self._find(True, "mobile/android/base/resources", "*.xml", "*.png"):
            src = os.path.join(self.topsrcdir, fn)
            dst = os.path.join(self.project_directory, "res",
                               relpath(fn, "mobile/android/base/resources"))
            d[src] = dst

        return d

    def _files_from_manifest(self, mn, dst_dir):
        d = {}
        if not os.path.exists(mn):
            return d

        for fn in open(mn, 'rt').readlines():
            fn = fn.strip()
            src = os.path.join(self.topsrcdir, fn)
            dst = os.path.join(dst_dir, os.path.basename(fn))
            d[src] = dst

        return d

    # TODO: get this from Makefile.in.
    def _branding_files(self):
        d = {}
        for (mn, res_folder) in [
            ("android-resources.mn",       "drawable-mdpi"),
            ("android-resources-hdpi.mn",  "drawable-hdpi"),
            ("android-resources-xhdpi.mn", "drawable-xhdpi"),
            ]:
            dst_dir = os.path.join(self.project_directory, "res", res_folder)

            mn = os.path.join(self.topsrcdir,
                              self.defines['MOZ_BRANDING_DIRECTORY'],
                              mn)

            d.update(self._files_from_manifest(mn, dst_dir))

        return d

    # TODO: get this from Makefile.in.
    def _icon_files(self):
        d = {}
        p = os.path.join(self.topsrcdir,
                         self.defines['MOZ_BRANDING_DIRECTORY'],
                         "content")

        for (icon, res_folder) in [
            ("fennec_48x48.png",   "drawable-mdpi"),
            ("fennec_72x72.png",   "drawable-hdpi"),
            ("fennec_96x96.png",   "drawable-xhdpi"),
            ("fennec_144x144.png", "drawable-xxhdpi"),
            ]:
            dst_dir = os.path.join(self.project_directory, "res", res_folder)

            src = os.path.join(p, icon)
            dst = os.path.join(dst_dir, "icon.png")
            d[src] = dst

        return d

    def _preprocessed_xml_files(self):
        d = {}
        for fn in self.mozbuild_sandbox['ANDROID_PREPROCESSED_RESOURCE_XML_FILES']:
            src = os.path.join(self.topobjdir, "mobile/android/base", fn)
            dst = os.path.join(self.project_directory, fn)
            d[src] = dst
        return d

    def _get_defines(self):
        # Long term, prefer to white-list defines to avoid
        # cargo-culting everything.
        # defines = {}
        # defines_list = ['MOZ_BUILD_APP',
        #                 'MOZ_APP_VERSION',
        #                 'MOZ_UPDATE_CHANNEL',
        #                 'ANDROID_COMPAT_LIB',
        #                 'ANDROID_CPU_ARCH',
        #                 'ANDROID_PACKAGE_NAME']
        # for define in defines_list:
        #     defines[define] = environment.substs[define]

        # Need to strip empty values out of config. This could upset
        # #ifdefs but we'll work that out in time.
        defines = {}
        for (key, val) in self.environment.substs.items():
            if val:
                defines[key] = val
        return defines

    def _add_special_defines(self):
        '''Defines that make *me* feel /special/.

        Updates `self.defines` in-place -- sorry.

        We should transition these to config.status defines ASAP.
        '''
        self.defines['_REPLACE_PACKAGE_DIR'] = self.defines['ANDROID_PACKAGE_NAME'].replace('.', '/')
        self.defines['_REPLACE_APP_NAME'] = self.project_name
        self.defines['_PACKAGE_NAME_'] = self.defines['ANDROID_PACKAGE_NAME']
        self.defines['_REPLACE_OBJ_PROJECT_PATH'] = os.path.join(self.topobjdir, "mobile/android/base")
        self.defines['_REPLACE_OBJ_PATH'] = self.topobjdir
        self.defines['_REPLACE_PROJECT_NAME'] = self.project_name
        self.defines['_REPLACE_MOZ_SRC_DIR'] = self.topsrcdir
        self.defines['_REPLACE_PACKAGE_NAME'] = self.defines['ANDROID_PACKAGE_NAME']

        self.defines['MOZ_CHILD_PROCESS_NAME'] = 'lib/libplugin-container.so'
        self.defines['MOZ_MIN_CPU_VERSION'] = '0'
        self.defines['MOZ_BUILD_TIMESTAMP'] = '0'
        self.defines['MOZ_APP_BUILDID'] = open(os.path.join(self.topobjdir, "config", "buildid"), 'rt').readline().strip()
        self.defines['MOZ_ANDROID_SHARED_ACCOUNT_TYPE'] = self.defines['ANDROID_PACKAGE_NAME'] + "_sync"
        self.defines['MOZ_APP_ABI'] = self.defines['TARGET_XPCOM_ABI']
        self.defines['MANGLED_ANDROID_PACKAGE_NAME'] = self.defines['ANDROID_PACKAGE_NAME'].replace('fennec', 'f3nn3c')
        self.defines['OBJDIR'] = os.path.join(self.topobjdir, "mobile", "android", "base")

    def _java_in_preprocess_files(self):
        d = {}
        for fn in self._find(True, "mobile/android/base", "*.java.in"):
            bn = os.path.basename(fn)
            if bn in ['CrashReporter.java.in']:
                continue

            src = os.path.join(self.topsrcdir, fn)
            package_dir = self._get_package(open(src)).replace('.', '/')

            dst = os.path.join(self.project_directory, "src", package_dir, bn)
            dst, _ = dst.split(".in")

            d[fn] = dst
        return d

    def _links(self):
        symlinks = {}
        for f in [
            self._jar_links,
            self._robocop_links,
            self._android_compatibility_links,
            self._source_files,
            self._resource_files,
            self._branding_files,
            self._icon_files,
            self._preprocessed_xml_files,
            ]:
            symlinks.update(f())
        return symlinks.items()

    def _create_links(self):
        javains = self._java_in_preprocess_files()
        self._preprocess_files(javains)

        symlinks = self._links()
        self.log(logging.WARN, LOG_TAG, {'symlinks': len(symlinks)},
                 'Creating {symlinks} symlinks.')
        self._create_symlinks(symlinks)

    def _preprocess_files(self, assocs):
        self.log(logging.WARN, LOG_TAG, {'count': len(assocs)},
                 'Preprocessing {count} files.')
        for src in assocs:
            dst = assocs[src]
            self._preprocess(src, dst)

    def _project_links(self):
        symlinks = []

        # Needed to avoid "Failed to parse AndroidManifest: aborting!"
        # during Launch.
        src = os.path.join(self.topobjdir, "mobile", "android", "base", "AndroidManifest.xml")
        dst = os.path.join(self.project_directory, "AndroidManifest.xml")
        symlinks.append((src, dst))

        # special case strings.xml
        src = os.path.join(self.topobjdir, "mobile", "android", "base", "res", "values", "strings.xml")
        dst = os.path.join(self.project_directory, "res", "values", "strings.xml")
        symlinks.append((src, dst))

        return symlinks

    def _create_project_links(self):
        symlinks = self._project_links()
        self.log(logging.WARN, LOG_TAG, {'symlinks': len(symlinks)},
                 'Creating {symlinks} project symlinks.')
        self._create_symlinks(symlinks)

    def _create_project_files(self):
        self._create_project_links()

        # eclipse/KEY -> workspace/VALUE
        fns = {
            "dotclasspath": ".classpath",
            "dotproject": ".project",
            "project.properties": "project.properties",
            }
        for fn in fns:
            self._preprocess(os.path.join(self.template_directory, fn),
                             os.path.join(self.project_directory, fns[fn]))

        # Special case 'App.launch'.  The path '.externalToolBuilders'
        # is standard and hard to change, so let's leave it.
        for fn in self._find(True, self.template_directory, "*.launch"):
            bn = os.path.basename(fn)
            if bn in ["App.launch"]:
                continue

            dst = os.path.join(self.project_directory, ".externalToolBuilders", bn)
            self._preprocess(fn, dst)

        self._preprocess(os.path.join(self.template_directory, "App.launch"),
                         os.path.join(self.project_directory, ".settings", "App.launch"))

        self._preprocess(os.path.join(self.template_directory, "org.eclipse.jdt.core.prefs"),
                         os.path.join(self.project_directory, ".settings", "org.eclipse.jdt.core.prefs"))

        self._preprocess(os.path.join(self.template_directory, "org.mozilla.ide.eclipse.fennec.prefs"),
                         os.path.join(self.project_directory, ".settings", "org.mozilla.ide.eclipse.fennec.prefs"))

        self._preprocess(os.path.join(self.template_directory, "save-actions.pl"),
                         os.path.join(self.project_directory, "scripts", "save-actions.pl"))

    '''Create Eclipse projects for Firefox for Android.'''
    def create_projects(self,
                        create_links=True,
                        create_project_files=True,
                        **kwargs):
        self._ensureParentDir(self.project_directory)

        if create_links:
            self._create_links()

        if create_project_files:
            self._create_project_files()

@CommandProvider
class MachCommands(MachCommandBase):
    @Command('eclipsify', help='Create Eclipse projects for Fennec.')
    @CommandArgument('--workspace', '-w',
                     help='Eclipse workspace directory.')
    @CommandArgument('--project', '-p', default='FennecTest',
                     help='Eclipse project name.')
    @CommandArgument('--no-links', '-L', default=False,
                     action='store_true',
                     help='do not refresh symlinks.')
    @CommandArgument('--no-project-files', '-P', default=False,
                     action='store_true',
                     help='do not create project files.')
    def eclipsify(self, **params):
        workspace = params.pop('workspace', None)
        if not workspace:
            raise Exception('Eclipse workspace directory must be provided.')
        project = params.pop('project')
        create_links = not params.pop('no_links')
        create_project_files = not params.pop('no_project_files')

        helper = ProjectCreator(self.topsrcdir, self.settings, self.log_manager,
                                topobjdir=os.path.abspath(self.topobjdir),
                                workspace_directory=workspace,
                                project_name=project)

        helper.create_projects(create_links=create_links,
                               create_project_files=create_project_files,
                               **params)
