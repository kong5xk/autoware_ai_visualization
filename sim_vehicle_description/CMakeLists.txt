cmake_minimum_required(VERSION 2.8.3)
project(sim_vehicle_description)

find_package(catkin REQUIRED)

catkin_package()

foreach(dir config launch mesh urdf)
  install(DIRECTORY ${dir}/
    DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/${dir}
  )
endforeach()
