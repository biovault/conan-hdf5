cmake_minimum_required (VERSION 3.12)
project (PackageTest C CXX)


# Note: The HDF5 share directory contains the CMake package
# this need to be in the CMAKE_PREFIX_PATH
# in order to locate the cmake package files
#
# Alternatively pass an HDF5_ROOT and use a HINTS or PATH
# option in the find_package thus
# find_package (HDF5 REQUIRED COMPONENTS CXX static PATHS "${HDF5_ROOT}/share")
find_package (HDF5 REQUIRED COMPONENTS CXX static)  # Using the static cpp library 

set (example hdf5example)

add_executable (${example} ${example}.cpp)
message("HDF5 VARIABLES FOR CXX 1: ${HDF5_INCLUDE_DIR} 2: ${HDF5_CXX_STATIC_LIBRARY}")
target_include_directories(${example} PRIVATE ${HDF5_INCLUDE_DIR})
target_link_libraries (${example} PRIVATE ${HDF5_CXX_STATIC_LIBRARY})
