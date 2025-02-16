#!/usr/bin/env python

# Passing an environment variable containing unicode literals to a subprocess
# on Windows and Python2 raises a TypeError. Since there is no unicode
# string in this script, we don't import unicode_literals to avoid the issue.
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from distutils import sysconfig
from shutil import rmtree
from tempfile import mkdtemp
import errno
import multiprocessing
import os
import os.path as p
import platform
import re
import shlex
import subprocess
import sys
import tarfile
import shutil
import hashlib
import tempfile

PY_MAJOR, PY_MINOR = sys.version_info[ 0 : 2 ]
if not ( ( PY_MAJOR == 2 and PY_MINOR == 7 ) or
         ( PY_MAJOR == 3 and PY_MINOR >= 4 ) or
         PY_MAJOR > 3 ):
  sys.exit( 'ycmd requires Python 2.7 or >= 3.4; '
            'your version of Python is ' + sys.version )

DIR_OF_THIS_SCRIPT = p.dirname( p.abspath( __file__ ) )
DIR_OF_THIRD_PARTY = p.join( DIR_OF_THIS_SCRIPT, 'third_party' )

for folder in os.listdir( DIR_OF_THIRD_PARTY ):
  abs_folder_path = p.join( DIR_OF_THIRD_PARTY, folder )
  if p.isdir( abs_folder_path ) and not os.listdir( abs_folder_path ):
    sys.exit(
      'ERROR: some folders in {0} are empty; you probably forgot to run:\n'
      '\tgit submodule update --init --recursive\n'.format(
        DIR_OF_THIRD_PARTY )
    )

sys.path.insert( 1, p.abspath( p.join( DIR_OF_THIRD_PARTY, 'argparse' ) ) )
sys.path.insert( 1, p.abspath( p.join( DIR_OF_THIRD_PARTY, 'requests' ) ) )

import argparse
import requests

NO_DYNAMIC_PYTHON_ERROR = (
  'ERROR: found static Python library ({library}) but a dynamic one is '
  'required. You must use a Python compiled with the {flag} flag. '
  'If using pyenv, you need to run the command:\n'
  '  export PYTHON_CONFIGURE_OPTS="{flag}"\n'
  'before installing a Python version.' )
NO_PYTHON_LIBRARY_ERROR = 'ERROR: unable to find an appropriate Python library.'

# Regular expressions used to find static and dynamic Python libraries.
# Notes:
#  - Python 3 library name may have an 'm' suffix on Unix platforms, for
#    instance libpython3.4m.so;
#  - the linker name (the soname without the version) does not always
#    exist so we look for the versioned names too;
#  - on Windows, the .lib extension is used instead of the .dll one. See
#    https://en.wikipedia.org/wiki/Dynamic-link_library#Import_libraries
STATIC_PYTHON_LIBRARY_REGEX = '^libpython{major}\.{minor}m?\.a$'
DYNAMIC_PYTHON_LIBRARY_REGEX = """
  ^(?:
  # Linux, BSD
  libpython{major}\.{minor}m?\.so(\.\d+)*|
  # OS X
  libpython{major}\.{minor}m?\.dylib|
  # Windows
  python{major}{minor}\.lib|
  # Cygwin
  libpython{major}\.{minor}\.dll\.a
  )$
"""

JDTLS_MILESTONE = '0.14.0'
JDTLS_BUILD_STAMP = '201802282111'
JDTLS_SHA256 = (
  'ce27fa4af601d11c3914253d51218667003b51468672d0ae369039ec8a111a3b'
)


def OnMac():
  return platform.system() == 'Darwin'


def OnWindows():
  return platform.system() == 'Windows'


def OnCiService():
  return 'CI' in os.environ


def FindExecutableOrDie( executable, message ):
  path = FindExecutable( executable )

  if not path:
    sys.exit( "ERROR: Unable to find executable '{0}'. {1}".format(
      executable,
      message ) )

  return path


# On Windows, distutils.spawn.find_executable only works for .exe files
# but .bat and .cmd files are also executables, so we use our own
# implementation.
def FindExecutable( executable ):
  # Executable extensions used on Windows
  WIN_EXECUTABLE_EXTS = [ '.exe', '.bat', '.cmd' ]

  paths = os.environ[ 'PATH' ].split( os.pathsep )
  base, extension = os.path.splitext( executable )

  if OnWindows() and extension.lower() not in WIN_EXECUTABLE_EXTS:
    extensions = WIN_EXECUTABLE_EXTS
  else:
    extensions = ['']

  for extension in extensions:
    executable_name = executable + extension
    if not os.path.isfile( executable_name ):
      for path in paths:
        executable_path = os.path.join(path, executable_name )
        if os.path.isfile( executable_path ):
          return executable_path
    else:
      return executable_name
  return None


def PathToFirstExistingExecutable( executable_name_list ):
  for executable_name in executable_name_list:
    path = FindExecutable( executable_name )
    if path:
      return path
  return None


def NumCores():
  ycm_cores = os.environ.get( 'YCM_CORES' )
  if ycm_cores:
    return int( ycm_cores )
  try:
    return multiprocessing.cpu_count()
  except NotImplementedError:
    return 1


def CheckCall( args, **kwargs ):
  quiet = kwargs.get( 'quiet', False )
  kwargs.pop( 'quiet', None )
  status_message = kwargs.get( 'status_message', None )
  kwargs.pop( 'status_message', None )

  if quiet:
    _CheckCallQuiet( args, status_message, **kwargs )
  else:
    _CheckCall( args, **kwargs )


def _CheckCallQuiet( args, status_message, **kwargs ):
  if not status_message:
    status_message = 'Running {0}'.format( args[ 0 ] )

  # __future_ not appear to support flush= on print_function
  sys.stdout.write( status_message + '...' )
  sys.stdout.flush()

  with tempfile.NamedTemporaryFile() as temp_file:
    _CheckCall( args, stdout=temp_file, stderr=subprocess.STDOUT, **kwargs )

  print( "OK" )


def _CheckCall( args, **kwargs ):
  exit_message = kwargs.get( 'exit_message', None )
  kwargs.pop( 'exit_message', None )
  stdout = kwargs.get( 'stdout', None )

  try:
    subprocess.check_call( args, **kwargs )
  except subprocess.CalledProcessError as error:
    if stdout is not None:
      stdout.seek( 0 )
      print( stdout.read().decode( 'utf-8' ) )
      print( "FAILED" )

    if exit_message:
      sys.exit( exit_message )
    sys.exit( error.returncode )


def GetGlobalPythonPrefix():
  # In a virtualenv, sys.real_prefix points to the parent Python prefix.
  if hasattr( sys, 'real_prefix' ):
    return sys.real_prefix
  # In a pyvenv (only available on Python 3), sys.base_prefix points to the
  # parent Python prefix. Outside a pyvenv, it is equal to sys.prefix.
  if PY_MAJOR >= 3:
    return sys.base_prefix
  return sys.prefix


def GetPossiblePythonLibraryDirectories():
  prefix = GetGlobalPythonPrefix()

  if OnWindows():
    return [ p.join( prefix, 'libs' ) ]
  # On pyenv and some distributions, there is no Python dynamic library in the
  # directory returned by the LIBPL variable. Such library can be found in the
  # "lib" or "lib64" folder of the base Python installation.
  return [
    sysconfig.get_config_var( 'LIBPL' ),
    p.join( prefix, 'lib64' ),
    p.join( prefix, 'lib' )
  ]


def FindPythonLibraries():
  include_dir = sysconfig.get_python_inc()
  library_dirs = GetPossiblePythonLibraryDirectories()

  # Since ycmd is compiled as a dynamic library, we can't link it to a Python
  # static library. If we try, the following error will occur on Mac:
  #
  #   Fatal Python error: PyThreadState_Get: no current thread
  #
  # while the error happens during linking on Linux and looks something like:
  #
  #   relocation R_X86_64_32 against `a local symbol' can not be used when
  #   making a shared object; recompile with -fPIC
  #
  # On Windows, the Python library is always a dynamic one (an import library to
  # be exact). To obtain a dynamic library on other platforms, Python must be
  # compiled with the --enable-shared flag on Linux or the --enable-framework
  # flag on Mac.
  #
  # So we proceed like this:
  #  - look for a dynamic library and return its path;
  #  - if a static library is found instead, raise an error with instructions
  #    on how to build Python as a dynamic library.
  #  - if no libraries are found, raise a generic error.
  dynamic_name = re.compile( DYNAMIC_PYTHON_LIBRARY_REGEX.format(
    major = PY_MAJOR, minor = PY_MINOR ), re.X )
  static_name = re.compile( STATIC_PYTHON_LIBRARY_REGEX.format(
    major = PY_MAJOR, minor = PY_MINOR ), re.X )
  static_libraries = []

  for library_dir in library_dirs:
    if not p.exists( library_dir ):
      continue

    # Files are sorted so that we found the non-versioned Python library before
    # the versioned one.
    for filename in sorted( os.listdir( library_dir ) ):
      if dynamic_name.match( filename ):
        return p.join( library_dir, filename ), include_dir

      if static_name.match( filename ):
        static_libraries.append( p.join( library_dir, filename ) )

  if static_libraries and not OnWindows():
    dynamic_flag = ( '--enable-framework' if OnMac() else
                     '--enable-shared' )
    sys.exit( NO_DYNAMIC_PYTHON_ERROR.format( library = static_libraries[ 0 ],
                                              flag = dynamic_flag ) )

  sys.exit( NO_PYTHON_LIBRARY_ERROR )


def CustomPythonCmakeArgs( args ):
  # The CMake 'FindPythonLibs' Module does not work properly.
  # So we are forced to do its job for it.
  if not args.quiet:
    print( 'Searching Python {major}.{minor} libraries...'.format(
      major = PY_MAJOR, minor = PY_MINOR ) )

  python_library, python_include = FindPythonLibraries()

  if not args.quiet:
    print( 'Found Python library: {0}'.format( python_library ) )
    print( 'Found Python headers folder: {0}'.format( python_include ) )

  return [
    '-DPYTHON_LIBRARY={0}'.format( python_library ),
    '-DPYTHON_INCLUDE_DIR={0}'.format( python_include )
  ]


def GetGenerator( args ):
  if OnWindows():
    return 'Visual Studio {version}{arch}'.format(
        version = args.msvc,
        arch = ' Win64' if platform.architecture()[ 0 ] == '64bit' else '' )
  if PathToFirstExistingExecutable( ['ninja'] ):
    return 'Ninja'
  return 'Unix Makefiles'


def ParseArguments():
  parser = argparse.ArgumentParser()
  parser.add_argument( '--clang-completer', action = 'store_true',
                       help = 'Enable C-family semantic completion engine.' )
  parser.add_argument( '--cs-completer', action = 'store_true',
                       help = 'Enable C# semantic completion engine.' )
  parser.add_argument( '--go-completer', action = 'store_true',
                       help = 'Enable Go semantic completion engine.' )
  parser.add_argument( '--rust-completer', action = 'store_true',
                       help = 'Enable Rust semantic completion engine.' )
  parser.add_argument( '--js-completer', action = 'store_true',
                       help = 'Enable JavaScript semantic completion engine.' ),
  parser.add_argument( '--java-completer', action = 'store_true',
                       help = 'Enable Java semantic completion engine.' ),
  parser.add_argument( '--system-boost', action = 'store_true',
                       help = 'Use the system boost instead of bundled one. '
                       'NOT RECOMMENDED OR SUPPORTED!' )
  parser.add_argument( '--system-libclang', action = 'store_true',
                       help = 'Use system libclang instead of downloading one '
                       'from llvm.org. NOT RECOMMENDED OR SUPPORTED!' )
  parser.add_argument( '--msvc', type = int, choices = [ 12, 14, 15 ],
                       default = 15, help = 'Choose the Microsoft Visual '
                       'Studio version (default: %(default)s).' )
  parser.add_argument( '--all',
                       action = 'store_true',
                       help   = 'Enable all supported completers',
                       dest   = 'all_completers' )
  parser.add_argument( '--enable-coverage',
                       action = 'store_true',
                       help   = 'For developers: Enable gcov coverage for the '
                                'c++ module' )
  parser.add_argument( '--enable-debug',
                       action = 'store_true',
                       help   = 'For developers: build ycm_core library with '
                                'debug symbols' )
  parser.add_argument( '--build-dir',
                       help   = 'For developers: perform the build in the '
                                'specified directory, and do not delete the '
                                'build output. This is useful for incremental '
                                'builds, and required for coverage data' )
  parser.add_argument( '--quiet',
                       action = 'store_true',
                       help = 'Quiet installation mode. Just print overall '
                              'progress and errors' )
  parser.add_argument( '--skip-build',
                       action = 'store_true',
                       help = "Don't build ycm_core lib, just install deps" )


  # These options are deprecated.
  parser.add_argument( '--omnisharp-completer', action = 'store_true',
                       help = argparse.SUPPRESS )
  parser.add_argument( '--gocode-completer', action = 'store_true',
                       help = argparse.SUPPRESS )
  parser.add_argument( '--racer-completer', action = 'store_true',
                       help = argparse.SUPPRESS )
  parser.add_argument( '--tern-completer', action = 'store_true',
                       help = argparse.SUPPRESS ),

  args = parser.parse_args()

  if args.enable_coverage:
    # We always want a debug build when running with coverage enabled
    args.enable_debug = True

  if ( args.system_libclang and
       not args.clang_completer and
       not args.all_completers ):
    sys.exit( 'ERROR: you can\'t pass --system-libclang without also passing '
              '--clang-completer or --all as well.' )
  return args


def GetCmakeArgs( parsed_args ):
  cmake_args = []
  if parsed_args.clang_completer or parsed_args.all_completers:
    cmake_args.append( '-DUSE_CLANG_COMPLETER=ON' )

  if parsed_args.system_libclang:
    cmake_args.append( '-DUSE_SYSTEM_LIBCLANG=ON' )

  if parsed_args.system_boost:
    cmake_args.append( '-DUSE_SYSTEM_BOOST=ON' )

  if parsed_args.enable_debug:
    cmake_args.append( '-DCMAKE_BUILD_TYPE=Debug' )
    cmake_args.append( '-DUSE_DEV_FLAGS=ON' )

  # coverage is not supported for c++ on MSVC
  if not OnWindows() and parsed_args.enable_coverage:
    cmake_args.append( '-DCMAKE_CXX_FLAGS=-coverage' )

  use_python2 = 'ON' if PY_MAJOR == 2 else 'OFF'
  cmake_args.append( '-DUSE_PYTHON2=' + use_python2 )

  extra_cmake_args = os.environ.get( 'EXTRA_CMAKE_ARGS', '' )
  # We use shlex split to properly parse quoted CMake arguments.
  cmake_args.extend( shlex.split( extra_cmake_args ) )
  return cmake_args


def RunYcmdTests( args, build_dir ):
  tests_dir = p.join( build_dir, 'ycm', 'tests' )
  os.chdir( tests_dir )
  new_env = os.environ.copy()

  if OnWindows():
    # We prepend the folder of the ycm_core_tests executable to the PATH
    # instead of overwriting it so that the executable is able to find the
    # Python library.
    new_env[ 'PATH' ] = DIR_OF_THIS_SCRIPT + ';' + new_env[ 'PATH' ]
  else:
    new_env[ 'LD_LIBRARY_PATH' ] = DIR_OF_THIS_SCRIPT

  CheckCall( p.join( tests_dir, 'ycm_core_tests' ),
             env = new_env,
             quiet = args.quiet,
             status_message = 'Running ycmd tests' )


def RunYcmdBenchmarks( build_dir ):
  benchmarks_dir = p.join( build_dir, 'ycm', 'benchmarks' )
  new_env = os.environ.copy()

  if OnWindows():
    # We prepend the folder of the ycm_core_tests executable to the PATH
    # instead of overwriting it so that the executable is able to find the
    # Python library.
    new_env[ 'PATH' ] = DIR_OF_THIS_SCRIPT + ';' + new_env[ 'PATH' ]
  else:
    new_env[ 'LD_LIBRARY_PATH' ] = DIR_OF_THIS_SCRIPT

  # Note we don't pass the quiet flag here because the output of the benchmark
  # is the only useful info.
  CheckCall( p.join( benchmarks_dir, 'ycm_core_benchmarks' ), env = new_env )


# On Windows, if the ycmd library is in use while building it, a LNK1104
# fatal error will occur during linking. Exit the script early with an
# error message if this is the case.
def ExitIfYcmdLibInUseOnWindows():
  if not OnWindows():
    return

  ycmd_library = p.join( DIR_OF_THIS_SCRIPT, 'ycm_core.pyd' )

  if not p.exists( ycmd_library ):
    return

  try:
    open( p.join( ycmd_library ), 'a' ).close()
  except IOError as error:
    if error.errno == errno.EACCES:
      sys.exit( 'ERROR: ycmd library is currently in use. '
                'Stop all ycmd instances before compilation.' )


def BuildYcmdLib( args ):
  cmake = FindExecutableOrDie( 'cmake', 'cmake is required to build ycmd' )

  if args.build_dir:
    build_dir = os.path.abspath( args.build_dir )
    if not os.path.exists( build_dir ):
      os.makedirs( build_dir )
  else:
    build_dir = mkdtemp( prefix = 'ycm_build_' )

  try:
    full_cmake_args = [ '-G', GetGenerator( args ) ]
    full_cmake_args.extend( CustomPythonCmakeArgs( args ) )
    full_cmake_args.extend( GetCmakeArgs( args ) )
    full_cmake_args.append( p.join( DIR_OF_THIS_SCRIPT, 'cpp' ) )

    os.chdir( build_dir )

    exit_message = (
      'ERROR: the build failed.\n\n'
      'NOTE: it is *highly* unlikely that this is a bug but rather\n'
      'that this is a problem with the configuration of your system\n'
      'or a missing dependency. Please carefully read CONTRIBUTING.md\n'
      'and if you\'re sure that it is a bug, please raise an issue on the\n'
      'issue tracker, including the entire output of this script\n'
      'and the invocation line used to run it.' )

    CheckCall( [ cmake ] + full_cmake_args,
               exit_message = exit_message,
               quiet = args.quiet,
               status_message = 'Generating ycmd build configuration' )

    build_targets = [ 'ycm_core' ]
    if 'YCM_TESTRUN' in os.environ:
      build_targets.append( 'ycm_core_tests' )
    if 'YCM_BENCHMARK' in os.environ:
      build_targets.append( 'ycm_core_benchmarks' )

    if OnWindows():
      config = 'Debug' if args.enable_debug else 'Release'
      build_config = [ '--config', config ]
    else:
      build_config = [ '--', '-j', str( NumCores() ) ]

    for target in build_targets:
      build_command = ( [ 'cmake', '--build', '.', '--target', target ] +
                        build_config )
      CheckCall( build_command,
                 exit_message = exit_message,
                 quiet = args.quiet,
                 status_message = 'Compiling ycmd target: {0}'.format(
                   target ) )

    if 'YCM_TESTRUN' in os.environ:
      RunYcmdTests( args, build_dir )
    if 'YCM_BENCHMARK' in os.environ:
      RunYcmdBenchmarks( build_dir )
  finally:
    os.chdir( DIR_OF_THIS_SCRIPT )

    if args.build_dir:
      print( 'The build files are in: ' + build_dir )
    else:
      rmtree( build_dir, ignore_errors = OnCiService() )


def EnableCsCompleter( args ):
  build_command = PathToFirstExistingExecutable(
    [ 'msbuild', 'msbuild.exe', 'xbuild' ] )
  if not build_command:
    sys.exit( 'ERROR: msbuild or xbuild is required to build Omnisharp.' )

  os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'OmniSharpServer' ) )
  CheckCall( [ build_command, '/property:Configuration=Release',
                              '/property:Platform=Any CPU',
                              '/property:TargetFrameworkVersion=v4.5' ],
             quiet = args.quiet,
             status_message = 'Building OmniSharp for C# completion' )


def EnableGoCompleter( args ):
  go = FindExecutableOrDie( 'go', 'go is required to build gocode.' )

  os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'gocode' ) )
  CheckCall( [ go, 'build' ],
             quiet = args.quiet,
             status_message = 'Building gocode for go completion' )
  os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'godef' ) )
  CheckCall( [ go, 'build', 'godef.go' ],
             quiet = args.quiet,
             status_message = 'Building godef for go definition' )


def EnableRustCompleter( args ):
  """
  Build racerd. This requires a reasonably new version of rustc/cargo.
  """
  cargo = FindExecutableOrDie( 'cargo',
                               'cargo is required for the Rust completer.' )

  os.chdir( p.join( DIR_OF_THIRD_PARTY, 'racerd' ) )
  command_line = [ cargo, 'build' ]
  # We don't use the --release flag on CI services because it makes building
  # racerd 2.5x slower and we don't care about the speed of the produced racerd.
  if not OnCiService():
    command_line.append( '--release' )
  CheckCall( command_line,
             quiet = args.quiet,
             status_message = 'Building racerd for Rust completion' )


def EnableJavaScriptCompleter( args ):
  # On Debian-based distributions, node is by default installed as nodejs.
  node = PathToFirstExistingExecutable( [ 'nodejs', 'node' ] )
  if not node:
    sys.exit( 'ERROR: node is required to set up Tern.' )
  npm = FindExecutableOrDie( 'npm', 'ERROR: npm is required to set up Tern.' )

  # We install Tern into a runtime directory. This allows us to control
  # precisely the version (and/or git commit) that is used by ycmd.  We use a
  # separate runtime directory rather than a submodule checkout directory
  # because we want to allow users to install third party plugins to
  # node_modules of the Tern runtime.  We also want to be able to install our
  # own plugins to improve the user experience for all users.
  #
  # This is not possible if we use a git submodule for Tern and simply run 'npm
  # install' within the submodule source directory, as subsequent 'npm install
  # tern-my-plugin' will (heinously) install another (arbitrary) version of Tern
  # within the Tern source tree (e.g. third_party/tern/node_modules/tern. The
  # reason for this is that the plugin that gets installed has "tern" as a
  # dependency, and npm isn't smart enough to know that you're installing
  # *within* the Tern distribution. Or it isn't intended to work that way.
  #
  # So instead, we have a package.json within our "Tern runtime" directory
  # (third_party/tern_runtime) that defines the packages that we require,
  # including Tern and any plugins which we require as standard.
  os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'tern_runtime' ) )
  CheckCall( [ npm, 'install', '--production' ],
             quiet = args.quiet,
             status_message = 'Setting up Tern for JavaScript completion' )


def EnableJavaCompleter( switches ):
  def Print( *args, **kwargs ):
    if not switches.quiet:
      print( *args, **kwargs )

  if switches.quiet:
    sys.stdout.write( 'Installing jdt.ls for Java support...' )
    sys.stdout.flush()

  TARGET = p.join( DIR_OF_THIRD_PARTY, 'eclipse.jdt.ls', 'target', )
  REPOSITORY = p.join( TARGET, 'repository' )
  CACHE = p.join( TARGET, 'cache' )

  JDTLS_SERVER_URL_FORMAT = ( 'http://download.eclipse.org/jdtls/milestones/'
                              '{jdtls_milestone}/{jdtls_package_name}' )
  JDTLS_PACKAGE_NAME_FORMAT = ( 'jdt-language-server-{jdtls_milestone}-'
                                '{jdtls_build_stamp}.tar.gz' )

  package_name = JDTLS_PACKAGE_NAME_FORMAT.format(
      jdtls_milestone = JDTLS_MILESTONE,
      jdtls_build_stamp = JDTLS_BUILD_STAMP )
  url = JDTLS_SERVER_URL_FORMAT.format(
      jdtls_milestone = JDTLS_MILESTONE,
      jdtls_build_stamp = JDTLS_BUILD_STAMP,
      jdtls_package_name = package_name )
  file_name = p.join( CACHE, package_name )

  if p.exists( REPOSITORY ):
    shutil.rmtree( REPOSITORY )

  os.makedirs( REPOSITORY )

  if not p.exists( CACHE ):
    os.makedirs( CACHE )
  elif p.exists( file_name ):
    with open( file_name, 'rb' ) as existing_file:
      existing_sha256 = hashlib.sha256( existing_file.read() ).hexdigest()
    if existing_sha256 != JDTLS_SHA256:
      Print( 'Cached tar file does not match checksum. Removing...' )
      os.remove( file_name )


  if p.exists( file_name ):
    Print( 'Using cached jdt.ls: {0}'.format( file_name ) )
  else:
    Print( "Downloading jdt.ls from {0}...".format( url ) )
    request = requests.get( url, stream = True )
    with open( file_name, 'wb' ) as package_file:
      package_file.write( request.content )
    request.close()

  Print( "Extracting jdt.ls to {0}...".format( REPOSITORY ) )
  with tarfile.open( file_name ) as package_tar:
    def is_within_directory(directory, target):
        
        abs_directory = os.path.abspath(directory)
        abs_target = os.path.abspath(target)
    
        prefix = os.path.commonprefix([abs_directory, abs_target])
        
        return prefix == abs_directory
    
    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
    
        for member in tar.getmembers():
            member_path = os.path.join(path, member.name)
            if not is_within_directory(path, member_path):
                raise Exception("Attempted Path Traversal in Tar File")
    
        tar.extractall(path, members, numeric_owner=numeric_owner) 
        
    
    safe_extract(package_tar, REPOSITORY)

  Print( "Done installing jdt.ls" )

  if switches.quiet:
    print( 'OK' )


def WritePythonUsedDuringBuild():
  path = p.join( DIR_OF_THIS_SCRIPT, 'PYTHON_USED_DURING_BUILDING' )
  with open( path, 'w' ) as f:
    f.write( sys.executable )


def Main():
  args = ParseArguments()
  if not args.skip_build:
    ExitIfYcmdLibInUseOnWindows()
    BuildYcmdLib( args )
    WritePythonUsedDuringBuild()
  if args.cs_completer or args.omnisharp_completer or args.all_completers:
    EnableCsCompleter( args )
  if args.go_completer or args.gocode_completer or args.all_completers:
    EnableGoCompleter( args )
  if args.js_completer or args.tern_completer or args.all_completers:
    EnableJavaScriptCompleter( args )
  if args.rust_completer or args.racer_completer or args.all_completers:
    EnableRustCompleter( args )
  if args.java_completer or args.all_completers:
    EnableJavaCompleter( args )


if __name__ == '__main__':
  Main()
