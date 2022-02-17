// Eample taken from http://web.mit.edu/fwtools_v3.1.0/www/Intro/IntroExamples.html

#include "hdf5.h"


int main(int argc, char** argv)
{
    auto file = argv[1];
    auto dataset1_name = argv[2];
    auto dataset2_name = argv[3];

    // open the file and read two datasets
    auto hf5_file = H5Fopen(file, H5F_ACC_RDONLY, H5P_DEFAULT);
    auto dataset1 = H5Dopen1(hf5_file, dataset1_name);
    auto dataset2 = H5Dopen1(hf5_file, dataset2_name);
    return 0;
}