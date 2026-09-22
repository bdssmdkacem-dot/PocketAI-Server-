cmake_minimum_required(VERSION 3.22.1)

project(pocket_ai)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(pocket_ai SHARED ai_bridge.cpp)

find_library(log_lib log)
target_link_libraries(pocket_ai log_lib)
