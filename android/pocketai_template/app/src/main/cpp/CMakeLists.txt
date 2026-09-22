cmake_minimum_required(VERSION 3.22.1)

project(pocket_ai)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(LLAMA_BUILD_COMMON OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_APP OFF CACHE BOOL "" FORCE)
set(LLAMA_OPENSSL OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)

add_subdirectory(../../../../../third_party/llama.cpp llama.cpp-build EXCLUDE_FROM_ALL)

add_library(pocket_ai SHARED ai_bridge.cpp)

find_library(log_lib log)

target_include_directories(pocket_ai PRIVATE
    ../../../../../third_party/llama.cpp/include
)

target_link_libraries(pocket_ai
    PRIVATE
    llama
    ${log_lib}
)
