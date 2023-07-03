cmake_minimum_required (VERSION 3.12)
project (PackageTest C CXX)

macro(print_all_variables)
    message(STATUS "print_all_variables------------------------------------------{")
    get_cmake_property(_variableNames VARIABLES)
    foreach (_variableName ${_variableNames})
        message(STATUS "${_variableName}=${${_variableName}}")
    endforeach()
    message(STATUS "print_all_variables------------------------------------------}")
endmacro()



# Note: The HDF5 share directory contains the CMake package
# this need to be in the CMAKE_PREFIX_PATH
# in order to locate the cmake package files
#
# Alternatively pass an HDF5_ROOT and use a HINTS or PATH
# option in the find_package thus
# find_package (HDF5 REQUIRED COMPONENTS CXX static PATHS "${HDF5_ROOT}/share")
set(HDF5_USE_STATIC_LIBRARIES TRUE)
find_package(HDF5 COMPONENTS CXX C static REQUIRED)  # Using the static cpp library 
message(status "HDF5 FOUND: ${HDF5_FOUND}")
# our HDF5 bundles zlib in a subdirectory and provides a hint as to the root path
set(ZLIB_ROOT ${HDF5_ZLIB_ROOT})
find_package (ZLIB REQUIRED)

print_all_variables()

set (example hdf5example)
add_executable (${example} ${example}.cpp)
set_property(TARGET ${example} PROPERTY CXX_STANDARD 11)
message("HDF5 VARIABLES FOR CXX 1: ${HDF5_INCLUDE_DIR} 2: ${HDF5_CXX_LIBRARIES} 3: ${ZLIB_LIBRARIES}")
target_include_directories(${example} PRIVATE ${hdf5_INCLUDE_DIR})
target_link_libraries (${example} PRIVATE ${C_STATIC_LIBRARY} ${HDF5_CXX_STATIC_LIBRARY} ${ZLIB_LIBRARIES})
