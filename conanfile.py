import os
import re

from fnmatch import fnmatch
from conans import ConanFile, tools
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain
from conans.errors import ConanException
import subprocess
from pathlib import Path
import shutil


class HDF5Conan(ConanFile):
    name = "hdf5"
    version = "1.10.8"
    description = "HDF5 C and C++ libraries"
    url = "http://github.com/biovault/conan-hdf5"
    license = "MIT"
    # generators = "cmake"
    generators = "CMakeDeps"
    settings = "os", "compiler", "build_type", "arch"
    requires = "zlib/1.2.11"
    revision_mode = "scm"
    exports = [
        "LICENSE.md",
        "CMakeLists.txt",
    #    "FindVTK.cmake",
    #    "vtknetcdf_snprintf.diff",
    #    "vtktiff_mangle.diff",
    ]
    source_subfolder = "hdf5"
    options = {
        "shared": [True, False],
        "cxx": [True, False],
        "parallel": [True, False]
    }
    default_options = (
        "shared=True",
        "cxx=True",
        "parallel=False"
    )

    short_paths = True

    version_split = version.split(".")
    short_version = "%s.%s" % (version_split[0], version_split[1])
    windows_source_folder = f"CMake-hdf5-{version}"
    windows_archive_name = f"{windows_source_folder}.zip"

    def source(self):
        major_minor_version = ".".join(self.version.split(".")[:2])
        if tools.os_info.is_windows:
            tools.download(
                f"https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-{major_minor_version}/hdf5-{self.version}/src/CMake-hdf5-{self.version}.zip",
                self.windows_archive_name
            )
            tools.unzip(self.windows_archive_name)
            os.unlink(self.windows_archive_name)
            os.rename(self.windows_source_folder, self.source_subfolder)
        else:
            tools.get(f"https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-{major_minor_version}/hdf5-{self.version}/src/CMake-hdf5-{self.version}.tar.gz")
            os.rename(self.windows_source_folder, self.source_subfolder)

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

        tc = CMakeToolchain(self, generator=generator)
        tc.variables["BUILD_TESTING"] = "OFF"
        tc.variables["BUILD_EXAMPLES"] = "OFF"
        tc.variables["BUILD_SHARED_LIBS"] = "TRUE" if self.options.shared else "FALSE"

        # HDF5 options
        if (self.options.cxx):
            tc.variables["HDF5_BUILD_CPP_LIB"] = "ON"

        if (self.options.parallel):
            tc.variables["HDF5_ENABLE_PARALLEL"] = "ON"

        tc.variables["HDF5_BUILD_EXAMPLES"] = "OFF"
        tc.variables["HDF5_BUILD_UTILS"] = "OFF"
        tc.variables["HDF5_BUILD_TOOLS"] = "OFF"
        tc.variables["HDF5_BUILD_HL_LIB"] = "OFF"
        tc.variables["HDF5_BUILDHL_TOOLS"] = "OFF"

        if (
            self.settings.build_type == "Debug"
            and self.settings.compiler == "Visual Studio"
        ):
            tc.variables["CMAKE_DEBUG_POSTFIX"] = "_d"

        if self.settings.os == "Macos":
            self.env["DYLD_LIBRARY_PATH"] = os.path.join(self.build_folder, "lib")
            self.output.info("cmake build: %s" % self.build_folder)

        tc.variables["CMAKE_TOOLCHAIN_FILE"] = "conan_toolchain.cmake"
        tc.variables["CMAKE_INSTALL_PREFIX"] = str(
            Path(self.build_folder, "install")
        ).replace("\\", "/")

        if self.settings.os == "Linux":
            tc.variables["CMAKE_CONFIGURATION_TYPES"] = "Debug;Release"

        return tc

    def generate(self):
        print("In generate")
        tc = self._get_tc()
        tc.generate()
        deps = CMakeDeps(self)
        deps.generate()

    def _configure_cmake(self):
        cmake = CMake(self)
        build_path = Path(self.source_subfolder) / f"hdf5-{self.version}"
        print(f"source path {str(build_path)}")
        cmake.configure( build_script_folder=str(build_path) )  # build_script_folder=str(PureWindowsPath(self.source_subfolder))
        return cmake

    def _do_build(self, cmake, build_type):
        # if self.settings.os == "Macos":
        # run_environment does not work here because it appends path just from
        # requirements, not from this package itself
        # https://docs.conan.io/en/latest/reference/build_helpers/run_environment.html#runenvironment
        #    lib_path = os.path.join(self.build_folder, "lib")
        #    self.run(
        #        f"DYLD_LIBRARY_PATH={lib_path} cmake --build build {cmake.build_config} -j"
        #    )
        cmake.build(build_type=build_type)
        cmake.install(build_type=build_type)

    def build(self):

        # Until we know exactly which  dlls are needed just build release
        cmake_debug = self._configure_cmake()
        self._do_build(cmake_debug, "Debug")

        cmake_release = self._configure_cmake()
        self._do_build(cmake_release, "Release")

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

    def _pkg_bin(self, build_type):
        src_dir = f"{self.build_folder}/lib/{build_type}"
        dst_lib = f"lib/{build_type}"
        dst_bin = f"bin/{build_type}"
        self.copy("*.lib", src=src_dir, dst=dst_lib, keep_path=False)
        self.copy("*.dll", src=src_dir, dst=dst_bin, keep_path=False)
        self.copy("*.so", src=src_dir, dst=dst_lib, keep_path=False)
        self.copy("*.dylib", src=src_dir, dst=dst_lib, keep_path=False)
        self.copy("*.a", src=src_dir, dst=dst_lib, keep_path=False)
        if ((build_type == "Debug") or (build_type == "RelWithDebInfo")) and (
            self.settings.compiler == "Visual Studio"
        ):
            self.copy("*.pdb", src=src_dir, dst=dst_lib, keep_path=False)




    def package(self):
        package_dir = os.path.join(self.build_folder, "package")
        print("Packaging install dir: ", package_dir)
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
            pdb_dest = Path(package_dir, 'pdb')
            pdb_dest.mkdir()
            pdb_files = Path(self.build_folder).glob('bin/Debug/*.pdb')
            for pfile in pdb_files:
                shutil.copy(pfile, pdb_dest)

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
        # Merge the Debug and Release into a single directory
        #self._merge_install_dirs(['Debug', 'Release'], 'DebRel', Path(package_dir), delete=True)
        self.copy(pattern="*", src=package_dir)

