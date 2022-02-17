// Eample taken from http://web.mit.edu/fwtools_v3.1.0/www/Intro/IntroExamples.html

#include "hdf5.h"
#include "H5Cpp.h"
#include <iostream>
#include <vector>

using namespace H5;

int test_with_c_interface(const char* file_name, const char* dataset_name)
{
	std::cout << "C Interface test..." << std::endl;
    // open the file and read two datasets
    auto hf5_file = H5Fopen(file_name, H5F_ACC_RDONLY, H5P_DEFAULT);
    auto dataset1 = H5Dopen(hf5_file, dataset_name, H5P_DEFAULT);

    // did it read what was created? Check the dimensions.
    hsize_t dims[2];
    hid_t dspace1 = H5Dget_space(dataset1);
    H5Sget_simple_extent_dims(dspace1, dims, nullptr);
    std::cout << dims[0] << ":" << dims[1] << std::endl;
    H5Sclose(dspace1);
    H5Dclose(dataset1);
	H5Fclose(hf5_file);
    if (dims[0] == 9000  && dims[1] == 128) {
        std::cout << "C Interface Success!" << std::endl;
        return(0);
    }
    std::cout << "C Interface Fail!" << std::endl;
    return(1);
}

int test_with_cpp_interface(const char* file_name, const char* dataset_name)
{
	std::cout << "CPP Interface test..." << std::endl;
    H5File file(file_name, H5F_ACC_RDWR);
	DataSet dataset = file.openDataSet(dataset_name);
    DataSpace dataspace = dataset.getSpace();
    hsize_t dims[2]{0, 0};
    if (dataspace.getSimpleExtentNdims() != 2) {
		std::cout << "Unexpected number of dimensions" << std::endl;
        return(1);
    }
    dataspace.getSimpleExtentDims(&dims[0], NULL);
	std::cout << dims[0] << ":" << dims[1] << std::endl;
    if (dims[0] == 9000  && dims[1] == 128) {
        std::cout << "CPP Interface Success!" << std::endl;
        return(0);
    }
    std::cout << "CPP Interface Fail!" << std::endl;
    return(1);
}

int main(int argc, char** argv)
{
    auto file_name = argv[1];
    auto dataset_name = argv[2];

	int result = test_with_c_interface(file_name, dataset_name);
    result += test_with_cpp_interface(file_name, dataset_name);

    exit(result);
}