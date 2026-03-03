cmake_minimum_required(VERSION 3.12)

set(PROJECT_NAME vrisc16)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

include(pico_sdk_import.cmake)
project(${PROJECT_NAME} C CXX ASM)

pico_sdk_init()

add_subdirectory(src)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(PY_SCRIPTS
    scripts/vrasm.py
    scripts/vrctl.py
)

set(VRISC16_VENV_DIR "${CMAKE_INSTALL_PREFIX}/share/${PROJECT_NAME}/venv")
set(VRISC16_REQ_FILE "${CMAKE_SOURCE_DIR}/requirements.txt")

install(CODE
"
  message(\"[${PROJECT_NAME}] Creating Python venv in ${VRISC16_VENV_DIR}\")
  execute_process(COMMAND \"${Python3_EXECUTABLE}\" -m venv \"${VRISC16_VENV_DIR}\")
  execute_process(COMMAND \"${VRISC16_VENV_DIR}/bin/pip\" install -U pip wheel)
  execute_process(COMMAND \"${VRISC16_VENV_DIR}/bin/pip\" install -r \"${VRISC16_REQ_FILE}\")
"
)

install(CODE
"
  file(MAKE_DIRECTORY \"${CMAKE_INSTALL_PREFIX}/bin\")
  file(WRITE \"${CMAKE_INSTALL_PREFIX}/bin/vrasm\" \"#!/usr/bin/env bash\nexec \\\"${VRISC16_VENV_DIR}/bin/python\\\" \\\"${CMAKE_INSTALL_PREFIX}/share/${PROJECT_NAME}/scripts/vrasm.py\\\" \\\"\\$@\\\"\n\")
  execute_process(COMMAND chmod +x \"${CMAKE_INSTALL_PREFIX}/bin/vrasm\")

  file(WRITE \"${CMAKE_INSTALL_PREFIX}/bin/vrctl\" \"#!/usr/bin/env bash\nexec \\\"${VRISC16_VENV_DIR}/bin/python\\\" \\\"${CMAKE_INSTALL_PREFIX}/share/${PROJECT_NAME}/scripts/vrctl.py\\\" \\\"\\$@\\\"\n\")
  execute_process(COMMAND chmod +x \"${CMAKE_INSTALL_PREFIX}/bin/vrctl\")
"
)

install(DIRECTORY scripts/
        DESTINATION share/${PROJECT_NAME}/scripts
        FILE_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)