#ifndef __DTYPE_HPP__
#define __DTYPE_HPP__

// #include <sycl/sycl.hpp>

namespace bevfusion {
namespace types {
    struct Int3 {
        int x, y, z;
        Int3() : x(0), y(0), z(0) {}
        Int3(int x_, int y_, int z_) : x(x_), y(y_), z(z_) {}
    };

    struct Int2 {
    int x, y;

    Int2() = default;
    Int2(int x, int y = 0) : x(x), y(y) {}
    };

    struct Float2 {
    float x, y;

    Float2() = default;
    Float2(float x, float y = 0) : x(x), y(y) {}
    };

    struct Float3 {
    float x, y, z;

    Float3() = default;
    Float3(float x, float y = 0, float z = 0) : x(x), y(y), z(z) {}
    };

    struct Float4 {
    float x, y, z, w;

    Float4() = default;
    Float4(float x, float y = 0, float z = 0, float w = 0) : x(x), y(y), z(z), w(w) {}
    };

    // // It is only used to specify the type only, while hoping to avoid header file contamination.
    // typedef struct dpct_type_162407 {
    // unsigned short __x;
    // } half;
}
}

#endif // __DTYPE_HPP__