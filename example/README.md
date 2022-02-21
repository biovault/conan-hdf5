
- [Using the HDF5 Package](#using-the-hdf5-package)
  - [Install package with __conan__](#install-package-with-conan)
  - [Install from package.tgz](#install-from-packagetgz)

# Using the HDF5 Package

The HDF5 package itself is build using __conan__ to manage versions and dependencies. However you have the choice of using the prebuilt HDF5 package either with or without __conan__. (Note  the hdf5example.cpp in the test_package will also build with either of these two recipes)



## Install package with __conan__

1. Add the lkeb-artifactory:

a) Install __conan__ (>= 1.43)
b) Add lkeb-artifactory (you wiil need to append the cert.pem file to the <user>/.conan/cacert.pem ):

```
conan remote add lkeb-artifactory https://lkeb-artifactory.lumc.nl/artifactory/api/conan/conan-local
```


c) create a __conan__ profile (in this case called `action_build`) with the settings for your compiler (see the [conan documentation](https://docs.conan.io/en/latest/reference/commands/misc/profile.html)). 

For example this is a profile for an MSVC 2017 build:

```
[settings]
os=Windows
os_build=Windows
arch=x86_64
arch_build=x86_64
compiler=Visual Studio
compiler.version=15
build_type=Release
```

d) a simple conan file is needed to specify the requirements (as show in this example)

```
[requires]
hdf5/1.10.8@lkeb/stable
zlib/1.2.11

[generators]
cmake

[options]
hdf5:cxx=True
hdf5:parallel=False
hdf5:shared=True
```

e) Make a __build__ subdirectory, `cd build` and install the hdf5 package with conan using the `action_build` profile:

```
conan install .. -pr action_build
```

Conan will pull the required version of hdf5 into the local cache and create a conanbuildinfo.cmake file. 

f) Use the __CMakeLists.txt__ given here. The hdf5 package has it's own  

## Install from package.tgz

a) Navigate to the [artifactory HDF5 package](https://lkeb-artifactory.lumc.nl/ui/repos/tree/General/conan-local%2Flkeb%2Fhdf5) choose the version and open theetree to the package level.  (Not each package has a unique checksum.) 

b) Open the checksummed package and examine the conaninfo.txt file (use the __Properties__ window) for the one that matches your build configuration

c) Download and unpack the conan_package.tgz. The scmake subdirectory can be used as the `hdf5_ROOT` in the CMakeLists.txt file.