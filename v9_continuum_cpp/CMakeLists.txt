cmake_minimum_required(VERSION 3.15)
project(V9ContinuumCpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(include)

# 1. Main Bot Executable
add_executable(v9_bot src/main.cpp)

# 2. Test Runner & Backtest Suite Executable
add_executable(v9_tests tests/test_runner.cpp)

if(MSVC)
    target_compile_options(v9_bot PRIVATE /W4 /O2)
    target_compile_options(v9_tests PRIVATE /W4 /O2)
else()
    target_compile_options(v9_bot PRIVATE -Wall -Wextra -O3)
    target_compile_options(v9_tests PRIVATE -Wall -Wextra -O3)
endif()
