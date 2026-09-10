cmake_minimum_required(VERSION 3.24)
project(cycles_dlss5_bridge LANGUAGES CXX)

if(NOT WIN32)
  message(FATAL_ERROR "The DLSS 5 bridge is Windows-only")
endif()

add_library(dlss5nr_bridge SHARED src/dlss5nr_bridge.cpp)
target_include_directories(dlss5nr_bridge PRIVATE include)
target_compile_features(dlss5nr_bridge PRIVATE cxx_std_17)
target_link_libraries(dlss5nr_bridge PRIVATE d3d12 dxgi ole32)

add_library(nvngx_caller_shim SHARED src/caller_shim.cpp)
target_compile_features(nvngx_caller_shim PRIVATE cxx_std_17)
set_target_properties(nvngx_caller_shim PROPERTIES OUTPUT_NAME "nvngx.dll_blender")

include(CTest)
if(BUILD_TESTING)
  add_executable(stock_color_test tests/stock_color_test.cpp)
  target_include_directories(stock_color_test PRIVATE include)
  target_compile_features(stock_color_test PRIVATE cxx_std_17)
  # Assertions must remain active in Release builds.
  target_compile_options(stock_color_test PRIVATE /UNDEBUG)
  add_test(NAME stock_color COMMAND stock_color_test)
endif()

