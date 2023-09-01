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
    windows_source_folder = f"CMake-hdf5-{version}{patch_suffix}"
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
            os.rename(self.windows_source_folder, self.source_subfolder)

    def export(self):
        # This requires that libpath JSON files have created by running
        # python conanfile.py <build_profile> <host_profile>
        # (see __main__ below)
        if not (
            Path("libpath_dict.json").exists()
            and Path("libpath_debug_dict.json").exists()
        ):
            print("****ERROR*** Missing library dict.json files.")
            print(
                "Check that: python conanfile.py <build_profile> <host_profile> \n",
                "was first run successfully in this directory",
            )
            exit(1)
        print(f"export folder {self.export_folder}")
        for jf in Path(".").glob("libpath*.json"):
            print(f"JSON {jf}")

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
            # generator = "Unix Makefiles"

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
        tc.variables["HDF5_ENABLE_DEBUG_APIS"] = "OFF"
        # Using an external zlib
        if self.options.with_zlib:
            tc.variables["HDF5_ENABLE_Z_LIB_SUPPORT"] = "ON"
        #    tc.variables["HDF5_ALLOW_EXTERNAL_SUPPORT"] = "GIT"
        #    tc.variables["ZLIB_URL"] = "https://github.com/madler/zlib"
        #    tc.variables["ZLIB_BRANCH"] = "tags/v1.2.13"

        tc.variables["HDF5_BUILD_EXAMPLES"] = "OFF"
        tc.variables["HDF5_BUILD_UTILS"] = "OFF"
        tc.variables["HDF5_BUILD_TOOLS"] = "OFF"
        tc.variables["HDF5_ENABLE_EMBEDDED_LIBINFO"] = "OFF"
        tc.variables["HDF5_ENABLE_HSIZET"] = "OFF"
        # tc.variables["PREFIX"] = "hdf5"
        # tc.variables["HDF5_PREFIX"] = "hdf5"

        if self.settings.compiler == "Visual Studio":
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

        return tc

    def generate(self):
        print("In generate")
        tc = self._get_tc()
        tc.generate()
        deps = CMakeDeps(self)
        # print(f"Dependency libs {self.deps_cpp_info.libs}")
        # for item in deps.content.items():
        #     print(f"Generator files {item}")
        if self.settings.os != "Linux" or self.settings.build_type == "Release":
            deps.configuration = "Release"
            deps.generate()
        if self.settings.os != "Linux" or self.settings.build_type == "Debug":
            deps.configuration = "Debug"
            deps.generate()

    def _configure_cmake(self):
        cmake = CMake(self)
        build_path = (
            Path(self.source_subfolder) / f"hdf5-{self.version}{self.patch_suffix}"
        )
        print(
            f"source path (relative to {cmake._conanfile.source_folder}) {str(build_path)}"
        )
        cmake.configure(
            build_script_folder=str(build_path)
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
        print(f"zlib rootpath: {Path(self.deps_cpp_info['zlib'].rootpath).as_posix()}")

        # Until we know exactly which  dlls are needed just build release
        if self.settings.build_type == "Debug":
            cmake_debug = self._configure_cmake()
            self._do_build(cmake_debug, "Debug", ["--verbose"])

        if self.settings.build_type == "Release":
            cmake_release = self._configure_cmake()
            self._do_build(cmake_release, "Release", ["--verbose"])

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
        if self.settings.os != "Linux":
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
        if self.settings.os != "Linux" or self.settings.build_type == "Debug":
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

        if self.settings.os != "Linux" or self.settings.build_type == "Release":
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


        # add dependencies to the packing dir before copying to package
        libpath_folder = Path(__file__).parent.resolve()
        print(f"check export folder {str(libpath_folder)} for libpaths")
        # package the requirements if they are found
        if (
            Path(libpath_folder, "libpath_dict.json").exists()
            or Path(libpath_folder, "libpath_debug_dict.json").exists()
        ):
            if Path(libpath_folder, "libpath_dict.json").exists():
                with open(Path(libpath_folder, "libpath_dict.json"), "r") as f:
                    libpath_dict = json.load(f)
                    print(f"{libpath_dict}")
            if Path(libpath_folder, "libpath_debug_dict.json").exists():
                with open(Path(libpath_folder, "libpath_debug_dict.json"), "r") as f:
                    libpath_debug_dict = json.load(f)
                    print(f"{libpath_debug_dict}")

            # Merge debug and release zlibs as follows
            # 1 Append d to debug lib files
            # 2 Copy all directories to <hdps packaging>/deps/zlib https://docs.python.org/3/library/shutil.html#shutil.copytree
            # 3 Define a ZLIB_ROOT variable as <hdps packaging>/deps/zlib (allows find_package(ZLIB))
            if self.options.with_zlib:
                print(f"packaging release zlib to {package_dir}")
                shutil.copytree(Path(libpath_dict["zlib"]), Path(package_dir, "zlib"))

                print("packaging debug zlib binaries")
                zlib_libs = Path(libpath_debug_dict["zlib"], "lib").glob("*.*")
                lib_dest = Path(package_dir, "zlib", "lib")
                for lib in zlib_libs:
                    print(f"packaging zlib from {lib} to {lib_dest}")
                    # The original zlib libraries do not have a different name for debug.
                    # So inject a suffix zlib.lib -> zlibd.lib to make a distinction.
                    # The suffix is chosen for compatibility with cmake;s find_package(ZLIB)
                    suffixed_file = self._inject_stem_suffix(lib, "d")
                    shutil.copy(lib, Path(lib_dest, suffixed_file))

                # Add ZLIB_ROOT to package
                # define content for hdf5-targets-zlib.cmake
                zlib_cmake_path = Path(
                    package_dir, "cmake", "hdf5-targets-zlib.cmake"
                )
                contentstr = """set(HDF5_ZLIB_ROOT,  "${_IMPORT_PREFIX}/zlib")
                """
                files.save(self, Path(zlib_cmake_path), contentstr)

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

    # Install Release dependencies
    baseInstall = [
        "conan",
        "install",
        ".",
        f"-pr:b={args.build_profile_name}",
        f"-pr:h={args.host_profile_name}",
        "--build=never",
    ]
    installCmd = baseInstall + [
        "-s:h",
        "build_type=Release",
    ]
    subprocess.run(
        installCmd + (["-s:h", "compiler.runtime=MD"] if os.name == "nt" else [])
    )

    # Install Debug dependencies
    debugInstallCmd = baseInstall + [
        "-s:h",
        "build_type=Debug",
    ]
    subprocess.run(
        debugInstallCmd + (["-s:h", "compiler.runtime=MDd"] if os.name == "nt" else [])
    )

    # 3) For all requirements get the install path
    # create a release and debug dict containing this information
    infoCmd = [
        "conan",
        "info",
        "--paths",
        "--only",
        "package_folder",
        ".",
        f"-pr:b={args.build_profile_name}",
        f"-pr:h={args.host_profile_name}",
    ]

    # 3.1) dict for Release dependencies
    res = subprocess.run(
        infoCmd
        + ["-s:h", "build_type=Release"]
        + (["-s:h", "compiler.runtime=MD"] if os.name == "nt" else []),
        capture_output=True,
        text=True,
    )
    # Reduce the conan info output list to array of requirement and package paths
    # Dropping the last 2 entries (which are the package to be build)
    req_path_array = [
        x.strip().replace("package_folder:", "").strip() for x in res.stdout.split("\n")
    ][0:-2]
    deps_keys = [x.split("/")[0] for x in req_path_array[0::2]]
    libpath_dict = dict(zip(deps_keys, req_path_array[1::2]))

    # 3.2) dict for Debug dependencies
    res = subprocess.run(
        infoCmd
        + ["-s:h", "build_type=Debug"]
        + (["-s:h", "compiler.runtime=MDd"] if os.name == "nt" else []),
        capture_output=True,
        text=True,
    )
    req_path_array = [
        x.strip().replace("package_folder:", "").strip() for x in res.stdout.split("\n")
    ][0:-2]
    deps_keys = [x.split("/")[0] for x in req_path_array[0::2]]
    libpath_debug_dict = dict(zip(deps_keys, req_path_array[1::2]))

    # 4) Display the results (for debugging) and save in json format to allow
    # easy retrieval in the packaging step
    print(libpath_dict)
    print(libpath_debug_dict)
    with open("libpath_dict.json", "w") as f:
        json.dump(libpath_dict, f)
    with open("libpath_debug_dict.json", "w") as f:
        json.dump(libpath_debug_dict, f)
