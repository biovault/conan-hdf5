import os
import re

from fnmatch import fnmatch
from conans import ConanFile, tools
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain
from conans.errors import ConanException
import subprocess
from pathlib import Path
import shutil
import argparse
import json

# derived from https://github.com/conan-io/conan-center-index/blob/master/recipes/hdf5/all/conanfile.py


class HDF5Conan(ConanFile):
    name = "hdf5"
    version = "1.12.1"
    description = "HDF5 C and C++ libraries"
    url = "http://github.com/biovault/conan-hdf5"
    license = "MIT"
    # generators = "cmake"
    generators = "CMakeDeps"
    settings = "os", "compiler", "build_type", "arch"
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
    windows_source_folder = f"CMake-hdf5-{version}"
    windows_archive_name = f"{windows_source_folder}.zip"

    def source(self):
        major_minor_version = ".".join(self.version.split(".")[:2])
        if tools.os_info.is_windows:
            tools.download(
                f"https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-{major_minor_version}/hdf5-{self.version}/src/CMake-hdf5-{self.version}.zip",
                self.windows_archive_name,
            )
            tools.unzip(self.windows_archive_name)
            os.unlink(self.windows_archive_name)
            os.rename(self.windows_source_folder, self.source_subfolder)
        else:
            tools.get(
                f"https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-{major_minor_version}/hdf5-{self.version}/src/CMake-hdf5-{self.version}.tar.gz"
            )
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

    def requirements(self):
        if self.options.with_zlib:
            self.requires("zlib/1.2.13")
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

        tc = CMakeToolchain(self, generator=generator)
        tc.variables["BUILD_TESTING"] = "OFF"
        tc.variables["BUILD_EXAMPLES"] = "OFF"
        tc.variables["BUILD_SHARED_LIBS"] = "TRUE" if self.options.shared else "FALSE"

        # HDF5 options
        tc.variables["HDF5_BUILD_CPP_LIB"] = "ON" if self.options.cxx else "OFF"
        tc.variables["HDF5_ENABLE_PARALLEL"] = "ON" if self.options.parallel else "OFF"

        tc.variables["HDF5_BUILD_HL_LIB"] = "ON" if self.options.build_hl else "OFF"
        tc.variables["HDF5_BUILDHL_TOOLS"] = "ON" if self.options.build_hl else "OFF"

        tc.variables["HDF5_ENABLE_SZIP_SUPPORT"] = (
            "ON" if self.options.szip_support else "OFF"
        )

        # Using an external zlib
        if self.options.with_zlib:
            tc.variables["HDF5_ENABLE_Z_LIB_SUPPORT"] = "ON"
        #    tc.variables["HDF5_ALLOW_EXTERNAL_SUPPORT"] = "GIT"
        #    tc.variables["ZLIB_URL"] = "https://github.com/madler/zlib"
        #    tc.variables["ZLIB_BRANCH"] = "tags/v1.2.13"

        tc.variables["HDF5_BUILD_EXAMPLES"] = "OFF"
        tc.variables["HDF5_BUILD_UTILS"] = "OFF"
        tc.variables["HDF5_BUILD_TOOLS"] = "OFF"

        if (
            self.settings.build_type == "Debug"
            and self.settings.compiler == "Visual Studio"
        ):
            tc.variables["CMAKE_DEBUG_POSTFIX"] = "_d"

        if self.settings.os == "Macos":
            self.env["DYLD_LIBRARY_PATH"] = os.path.join(self.build_folder, "lib")
            self.output.info("cmake build: %s" % self.build_folder)

        tc.variables["CMAKE_TOOLCHAIN_FILE"] = "conan_toolchain.cmake"
        tc.variables["CMAKE_INSTALL_PREFIX"] = os.path.join(
            self.build_folder, "install"
        )

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
        cmake.configure(
            build_script_folder=str(build_path)
        )  # build_script_folder=str(PureWindowsPath(self.source_subfolder))
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

        print(f"zlib rootpath: {Path(self.deps_cpp_info['zlib'].rootpath).as_posix()}")

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

    # def _pkg_bin(self, build_type):
    #     src_dir = f"{self.build_folder}/lib/{build_type}"
    #     dst_lib = f"lib/{build_type}"
    #     dst_bin = f"bin/{build_type}"
    #     self.copy("*.lib", src=src_dir, dst=dst_lib, keep_path=False)
    #     self.copy("*.dll", src=src_dir, dst=dst_bin, keep_path=False)
    #     self.copy("*.so", src=src_dir, dst=dst_lib, keep_path=False)
    #     self.copy("*.dylib", src=src_dir, dst=dst_lib, keep_path=False)
    #     self.copy("*.a", src=src_dir, dst=dst_lib, keep_path=False)
    #     if ((build_type == "Debug") or (build_type == "RelWithDebInfo")) and (
    #         self.settings.compiler == "Visual Studio"
    #     ):
    #         self.copy("*.pdb", src=src_dir, dst=dst_lib, keep_path=False)

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
            pdb_dest = Path(package_dir, "pdb")
            pdb_dest.mkdir()
            pdb_files = Path(self.build_folder).glob("bin/Debug/*.pdb")
            for pfile in pdb_files:
                shutil.copy(pfile, pdb_dest)

        if self.options.with_zlib:
            print("packaging zlib")
            zlib_libs = Path(self.deps_cpp_info["zlib"].rootpath, "lib").glob("*.*")
            lib_dest = Path(package_dir, "lib")
            lib_dest.mkdir(parents=True)
            for lib in zlib_libs:
                suffixed_file = self._inject_stem_suffix(lib, "d")
                print(f"packaging zlib from {lib} to {lib_dest} {suffixed_file}")
                shutil.copy(lib, Path(lib_dest, suffixed_file))

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

        # package the requirements along with hdf5 if they are found
        if (
            Path("libpath_dict.json").exists()
            and Path("libpath_debug_dict.json").exists()
        ):
            with open("libpath_dict.json", "r") as f:
                libpath_dict = json.load(f)
            with open("libpath_debug_dict.json", "r") as f:
                libpath_debug_dict = json.load(f)

            if self.options.with_zlib:
                print("packaging zlib")
                lib_dest = Path(libpath_dict["zlib"], "lib")
                lib_dest.mkdir(parents=True)
                for lib in zlib_libs:
                    print(f"packaging zlib from {lib} to {lib_dest}")
                    shutil.copy(lib, lib_dest)

        self.copy(pattern="*", src=package_dir)


if __name__ == "__main__":
    """
    1) Install all requirements for this package - Release + Debug
    2) Get list of requirements
    3) For each requirement get the install path - create a release and debug dict
    4) Write files
    """
    # 1) Install all dependencies - Release + Debug
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "build_profile_name", type=str, help="Name of the conan profile used for build"
    )
    parser.add_argument(
        "host_profile_name", type=str, help="Name of the conan profile used for host"
    )
    args = parser.parse_args()

    # Install Release
    installCmd = [
        "conan",
        "install",
        ".",
        f"-pr:b={args.build_profile_name}",
        f"-pr:h={args.host_profile_name}",
        "--build=never",
    ]
    subprocess.run(installCmd)

    # Install Debug
    debugInstallCmd = installCmd + [
        "-s:h",
        "build_type=Debug",
    ]
    if os.name == "nt":
        debugInstallCmd = debugInstallCmd + ["-s:h", "compiler.runtime=MDd"]
    subprocess.run(debugInstallCmd)

    # 2) Get list of requirements
    res = subprocess.run(
        ["conan", "info", ".", "--build-order=ALL"], capture_output=True, text=True
    )

    reqs = res.stdout.strip("[]\n").split(",")

    # 3) For each requirement get the install path - create a release and debug dict
    libpath_dict = {}
    libpath_debug_dict = {}
    for req in reqs:
        infoCmd = [
            "conan",
            "info",
            "--paths",
            "--package-filter",
            f"{req}",
            "--only",
            "package_folder",
            ".",
            f"-pr:b={args.build_profile_name}",
            f"-pr:h={args.host_profile_name}",
        ]
        res = subprocess.run(
            infoCmd,
            capture_output=True,
            text=True,
        )
        lib_path = res.stdout.replace("package_folder:", "").split()
        libpath_dict[req.split("/")[0]] = str(Path(lib_path[1]).as_posix())

        debugInfoCmd = infoCmd + ["-s:h", "build_type=Debug"]

        if os.name == "nt":
            debugInfoCmd = debugInfoCmd + ["-s:h", "compiler.runtime=MDd"]

        res = subprocess.run(
            debugInfoCmd,
            capture_output=True,
            text=True,
        )
        lib_path = res.stdout.replace("package_folder:", "").split()
        libpath_debug_dict[req.split("/")[0]] = str(Path(lib_path[1]).as_posix())

    print(libpath_dict)
    print(libpath_debug_dict)
    with open("libpath_dict.json", "w") as f:
        json.dump(libpath_dict, f)
    with open("libpath_debug_dict.json", "w") as f:
        json.dump(libpath_debug_dict, f)
