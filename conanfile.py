import os
import re

from fnmatch import fnmatch
from conans import ConanFile, tools
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain
from conan.tools import files
from conans.errors import ConanException
import subprocess
from pathlib import Path
import shutil
import argparse
import json
import platform

# derived from https://github.com/conan-io/conan-center-index/blob/master/recipes/hdf5/all/conanfile.py


class HDF5Conan(ConanFile):
    name = "hdf5"
    version = "1.14.2"
    patch_suffix = ""
    description = "HDF5 C and C++ libraries"
    url = "http://github.com/biovault/conan-hdf5"
    license = "MIT"
    # generators = "cmake"
    generators = "CMakeDeps"
    settings = "os", "compiler", "build_type", "arch"
    revision_mode = "scm"
    exports = (
        "LICENSE.md",
        "CMakeLists.txt",
        "*.json",
    )  # When packaging the dependencies paths are in json files
    source_subfolder = "hdf5"
    options = {
        "shared": [True, False],
        "cxx": [True, False],
        "parallel": [True, False],
        "with_zlib": [True, False],
        "szip_support": [True, False],
        "build_hl": [True, False],
    }
    default_options = (
        "shared=False",
        "cxx=True",
        "parallel=False",
        "with_zlib=True",
        "szip_support=False",
        "build_hl=False",
    )

    short_paths = True

    version_split = version.split(".")
    short_version = "%s.%s" % (version_split[0], version_split[1])
    windows_source_folder = f"hdf5-{version}{patch_suffix}"
    linux_source_folder = f"CMake-hdf5-{version}{patch_suffix}"
    windows_archive_name = f"{windows_source_folder}.zip"

    def source(self):
        major_minor_version = ".".join(self.version.split(".")[:2])
        if tools.os_info.is_windows:
            tools.download(
                f"https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-{major_minor_version}/hdf5-{self.version}/src/CMake-hdf5-{self.version}{self.patch_suffix}.zip",
                self.windows_archive_name,
            )
            tools.unzip(self.windows_archive_name, strip_root=True) # Remove the root dir in this version 1.4.2
            os.unlink(self.windows_archive_name)
            os.rename(self.windows_source_folder, self.source_subfolder)
        else:
            tools.get(
                f"https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-{major_minor_version}/hdf5-{self.version}/src/CMake-hdf5-{self.version}{self.patch_suffix}.tar.gz"
            )
            os.rename(self.linux_source_folder, self.source_subfolder)

    def export_sources(self):
        print(f"In export_sources {Path.cwd()}")
        self.copy("*.cmake", src=Path(Path.cwd(), 'cmake'))

    def export(self):
        # This requires that libpath JSON files have created by running
        # python conanfile.py <build_profile> <host_profile>
        # (see __main__ below)
        # if not (
        #     Path("libpath_dict.json").exists()
        #     and Path("libpath_debug_dict.json").exists()
        # ):
        #     print("****ERROR*** Missing library dict.json files.")
        #     print(
        #         "Check that: python conanfile.py <build_profile> <host_profile> \n",
        #         "was first run successfully in this directory",
        #     )
        #     exit(1)
        # print(f"export folder {self.export_folder}")
        # for jf in Path(".").glob("libpath*.json"):
        #     print(f"JSON {jf}")
        pass

    def _system_package_architecture(self):
        if tools.os_info.with_apt:
            if self.settings.arch == "x86":
                return ":i386"
            elif self.settings.arch == "x86_64":
                return ":amd64"

        if tools.os_info.with_yum:
            if self.settings.arch == "x86":
                return ".i686"
            elif self.settings.arch == "x86_64":
                return ".x86_64"
        return ""

    def configure(self):
        if self.options.cxx and self.options.parallel:
            msg = "The cxx and parallel options are not compatible"
            raise ConanException(msg)

    def config_options(self):
        if self.settings.compiler == "Visual Studio":
            del self.options.fPIC

    def requirements(self):
        #if self.options.with_zlib:
        #    self.requires("zlib/1.2.13")
        if self.options.szip_support:
            self.requires("szip/2.1.1")
        if self.options.parallel:
            self.requires("openmpi/4.1.0")

    # Required to define build_folder for generate when using install with --build=never
    def layout(self):
        self.folders.build = "build"
        self.folders.generators = self.folders.build

    def _get_tc(self):
        """Generate the CMake configuration using
        multi-config generators on all platforms, as follows:

        Windows - defaults to Visual Studio
        Macos - XCode
        Linux - Ninja Multi-Config

        CMake needs to be at least 3.17 for Ninja Multi-Config

        Returns:
            CMakeToolchain: a configured toolchain object
        """
        generator = None
        if self.settings.os == "Macos":
            generator = "Xcode"

        if self.settings.os == "Linux":
            generator = "Ninja Multi-Config"
            #generator = "Unix Makefiles"

        tc = CMakeToolchain(self, generator=generator)
        tc.variables[
            "HDF5_EXTERNALLY_CONFIGURED"
        ] = "OFF"  # ensure CMake config generation
        tc.variables["BUILD_TESTING"] = "OFF"
        tc.variables["BUILD_EXAMPLES"] = "OFF"
        tc.variables["BUILD_SHARED_LIBS"] = "ON" if self.options.shared else "OFF"

        # HDF5 options
        tc.variables["HDF5_BUILD_CPP_LIB"] = "ON" if self.options.cxx else "OFF"
        tc.variables["HDF5_BUILD_FORTRAN"] = "OFF"
        tc.variables["HDF5_ENABLE_PARALLEL"] = "ON" if self.options.parallel else "OFF"

        tc.variables["HDF5_BUILD_HL_LIB"] = "ON" if self.options.build_hl else "OFF"
        tc.variables["HDF5_BUILDHL_TOOLS"] = "ON" if self.options.build_hl else "OFF"

        tc.variables["HDF5_ENABLE_SZIP_SUPPORT"] = (
            "ON" if self.options.szip_support else "OFF"
        )
        tc.variables["TGZPATH"] = "${CMAKE_SOURCE_DIR}/../"
        tc.variables["HDF5_ENABLE_DEBUG_APIS"] = "OFF"
        tc.variables["HDF_PACKAGE_NAMESPACE"] = "hdf5::"
        
        # Using an external zlib
        if self.options.with_zlib:
            
            # Build strategies are defined in hdf5/release_docs/INSTALL_Cmake.txt
            # This setup is strategy D. (Download tar.gz sources)
            # Using this because it also delivers the zlib CMAKE export files
            tc.variables["HDF5_ENABLE_Z_LIB_SUPPORT"] = "ON"
            tc.variables["BUILD_ZLIB_WITH_FETCHCONTENT"] = "ON"
            tc.variables["ZLIB_TGZ_ORIGPATH"] = "https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz"
            # This setup is strategy B. (Use source packages from an GIT server)
            #tc.variables["HDF5_ALLOW_EXTERNAL_SUPPORT"] = "GIT"
            #tc.variables["BUILD_ZLIB_WITH_FETCHCONTENT"] = "OFF"
            #tc.variables["ZLIB_GIT_URL"] = "https://github.com/madler/zlib"
            #tc.variables["ZLIB_GIT_BRANCH"] = "v1.3.1"
            tc.variables["ZLIB_EXTERNALLY_CONFIGURED"] = "OFF"
            tc.variables["ZLIB_EXPORTED_TARGETS"] = "ON"
            tc.variables["ZLIB_USE_EXTERNAL"] = "ON"
            tc.variables["ZLIB_PACKAGE_NAME"] = "zlib"
             

        tc.variables["HDF5_BUILD_EXAMPLES"] = "OFF"
        tc.variables["HDF5_BUILD_UTILS"] = "OFF"
        tc.variables["HDF5_BUILD_TOOLS"] = "OFF"
        tc.variables["HDF5_ENABLE_EMBEDDED_LIBINFO"] = "OFF"
        tc.variables["HDF5_ENABLE_HSIZET"] = "OFF"
        tc.variables["HDF5_PACKAGE_EXTLIBS"] = "ON"
        # tc.variables["PREFIX"] = "hdf5"
        # tc.variables["HDF5_PREFIX"] = "hdf5"

        #if self.settings.compiler == "Visual Studio":
        tc.variables["CMAKE_DEBUG_POSTFIX"] = "_d"
        tc.variables[
            "CMAKE_MSVC_RUNTIME_LIBRARY"
        ] = "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL"

        # Make sure all paths are Posix to avoid escape character issues
        if self.settings.os == "Macos":
            self.env["DYLD_LIBRARY_PATH"] = str(
                Path(self.build_folder, "lib").as_posix()
            )
            self.output.info("cmake build: %s" % self.build_folder)

        tc.variables["CMAKE_TOOLCHAIN_FILE"] = "conan_toolchain.cmake"
        tc.variables["CMAKE_INSTALL_PREFIX"] = str(
            Path(self.build_folder, "install").as_posix()
        )

        tc.variables["CMAKE_CONFIGURATION_TYPES"] = "Debug;Release"

        if self.settings.os == "Windows":
            tc.variables["CMAKE_CXX_FLAGS"] = tc.variables.get("CMAKE_CXX_FLAGS", "") + "/DWIN32 /EHsc /MP /permissive- /Zc:__cplusplus"
            tc.variables["CMAKE_EXE_LINKER_FLAGS"] = tc.variables.get("CMAKE_EXE_LINKER_FLAGS", "") + "/NODEFAULTLIB:LIBCMT"
            tc.variables["CMAKE_CXX_FLAGS_DEBUG"] = tc.variables.get("CMAKE_CXX_FLAGS_DEBUG", "") + "/MDd"
            tc.variables["CMAKE_CXX_FLAGS_RELEASE"] = tc.variables.get("CMAKE_CXX_FLAGS_RELEASE", "") + "/MD"

        return tc

    def generate(self):
        print("In generate")
        tc = self._get_tc()
        tc.generate()
        deps = CMakeDeps(self)
        # print(f"Dependency libs {self.deps_cpp_info.libs}")
        # for item in deps.content.items():
        #     print(f"Generator files {item}")
        # if self.settings.os != "Linux" or self.settings.build_type == "Release":
        #     deps.configuration = "Release"
        #     deps.generate()
        # if self.settings.os != "Linux" or self.settings.build_type == "Debug":
        #     deps.configuration = "Debug"
        #     deps.generate()
        deps.generate()

    def _configure_cmake(self, cli_args=None):
        cmake = CMake(self)
        build_path = (
            Path(self.source_subfolder) if self.settings.os == "Windows" else Path(self.source_subfolder) / f"hdf5-{self.version}{self.patch_suffix}"
        )
        print(
            f"source path (relative to {cmake._conanfile.source_folder}) {str(build_path)}"
        )
        cmake.configure(
            build_script_folder=str(build_path), cli_args=cli_args
        )  # build_script_folder=str(PureWindowsPath(self.source_subfolder))
        return cmake

    def _do_build(self, cmake, build_type, cli_args=None):
        # if self.settings.os == "Macos":
        # run_environment does not work here because it appends path just from
        # requirements, not from this package itself
        # https://docs.conan.io/en/latest/reference/build_helpers/run_environment.html#runenvironment
        #    lib_path = os.path.join(self.build_folder, "lib")
        #    self.run(
        #        f"DYLD_LIBRARY_PATH={lib_path} cmake --build build {cmake.build_config} -j"
        #    )
        cmake.build(build_type=build_type, cli_args=cli_args)
        # cmake.install(build_type=build_type)

    def build(self):

        #if self.settings.build_type == "Debug":
        print("Start Debug build")
        cmake = self._configure_cmake() # To debug pass ["--log-level=VERBOSE", "--trace-expand"]
        self._do_build(cmake, "Debug", ["--verbose"])
        print("End Debug build")

        # Until we know exactly which  dlls are needed just build release
        #if self.settings.build_type == "Release":
        print("Start Release build")
        
        if self.settings.os == "Linux":
            self._do_build(cmake, "Release", ["--verbose"])
        else:
            cmake_debug = self._configure_cmake()
            self._do_build(cmake_debug, "Release", ["--verbose"])
        print("End Release build")



    def cmake_fix_macos_sdk_path(self, file_path):
        # Read in the file
        with open(file_path, "r") as file:
            file_data = file.read()

        if file_data:
            # Replace the target string
            file_data = re.sub(
                # Match sdk path
                r";/Applications/Xcode\.app/Contents/Developer/Platforms/MacOSX\.platform/Developer/SDKs/MacOSX\d\d\.\d\d\.sdk/usr/include",
                "",
                file_data,
                re.M,
            )

            # Write the file out again
            with open(file_path, "w") as file:
                file.write(file_data)

    # Package has no build type marking
    def package_id(self):
        del self.info.settings.build_type
        if self.settings.compiler == "Visual Studio":
            del self.info.settings.compiler.runtime

    def _inject_stem_suffix(self, path, suffix):
        """_summary_

        Parameters
        ----------
        path : Path
            file name (potentially with path)
        suffix : str
            suffix string to inject before .extension

        Returns
        -------
        Path
            Just the file name (no preceeding path) with the suffix injected
        """
        new_path = Path(path.stem + suffix + path.suffix)
        return new_path

    def package(self):
        # Merge the Debug and Release into a single directory
        # except for Linux where separate Debug and Release packages are
        # created due to Ninja issues
        # System:
        # 1) create a package directory
        # 2) install debug  and release to that dir
        # 3) Add the zlib dependency
        # 4) complete the packaging
        package_dir = os.path.join(Path(self.build_folder).parents[0], "package")
        Path(package_dir).mkdir()
        print("Packaging install dir: ", package_dir)
        #if self.settings.os != "Linux" or self.settings.build_type == "Debug":
        print("Package Debug")
        subprocess.run(
            [
                "cmake",
                "--install",
                self.build_folder,
                "--config",
                "Debug",
                "--prefix",
                package_dir,
            ]
        )
        if tools.os_info.is_windows:
            # pdb need to be adjacent to lib
            pdb_dest = Path(package_dir, "lib")
            # pdb_dest.mkdir()
            pdb_files = Path(self.build_folder).glob("bin/Debug/*.pdb")
            for pfile in pdb_files:
                shutil.copy(pfile, pdb_dest)

        # if self.settings.os != "Linux" or self.settings.build_type == "Release":
        print("Package Release")
        subprocess.run(
            [
                "cmake",
                "--install",
                self.build_folder,
                "--config",
                "Release",
                "--prefix",
                package_dir,
            ]
        )

        self.copy(pattern="*", src=package_dir)
