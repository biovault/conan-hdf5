import os
import h5py
import numpy as np
from conans import ConanFile, tools
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps
from pathlib import Path


class Hdf5TestConan(ConanFile):
    name = "Hdf5PackageTest"
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps"
    requires = "hdf5/1.10.8" 
    exports = "CMakeLists.txt", "hdf5example.cpp"

    def generate(self):
        print("Generating toolchain")
        tc = CMakeToolchain(self)
        # Use the HDF5 cmake package in the share directory
        tc.variables["CMAKE_PREFIX_PATH"] = Path(
            self.deps_cpp_info["hdf5"].rootpath, 'share'
        ).as_posix()
        tc.generate()
        deps = CMakeDeps(self)
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self.settings):
            # Create a test hdf5 file to test containing
            # two datasets caled "dataset" and "query"
            with h5py.File("dataset.hdf5", "w") as f:
                np_d = np.random.randint(0, 128, size=(9000, 128), dtype=np.uint8)
                np_d = np_d.astype(np.float64)
                np_q = np.random.randint(0, 128, size=(1000, 128), dtype=np.uint8)
                np_q = np_q.astype(np.float64)
                f.create_dataset("test_dataset1", data=np_d)
                f.create_dataset("test_dataset2", data=np_q)
            print("Running hdf5 example...")

            if self.settings.os == "Windows":
                self.run(str(Path(Path.cwd(), "Release", "hdf5example.exe")) + " dataset.hdf5 test_dataset1" )
            else:
                self.run(str(Path(Path.cwd(), "hdf5example")) + " dataset.hdf5 test_dataset1" )
