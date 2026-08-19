# syntax=docker/dockerfile:1
ARG AUTOWARE_BASE_IMAGE=autoware/autoware:1.14.0-melodic@sha256:883aa8df23a0dd2fe6914ad159ce9c25d76a2b7a63e5eb90dba5dc33f29ecae4
FROM ${AUTOWARE_BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER root

ARG VISUALIZATION_REPOSITORY
ARG VISUALIZATION_REF=sim/vehicle-visualization
ARG VISUALIZATION_SHA=""

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    test -n "${VISUALIZATION_REPOSITORY}"; \
    test -n "${VISUALIZATION_SHA}"; \
    rm -rf /home/autoware/Autoware/src/autoware/visualization; \
    git clone --branch "${VISUALIZATION_REF}" --single-branch \
      "${VISUALIZATION_REPOSITORY}" \
      /home/autoware/Autoware/src/autoware/visualization; \
    git -C /home/autoware/Autoware/src/autoware/visualization \
      checkout --detach "${VISUALIZATION_SHA}"; \
    python3 /home/autoware/Autoware/src/autoware/visualization/scripts/check_package_coherence.py; \
    chown -R autoware:autoware /home/autoware/Autoware/src/autoware/visualization

USER autoware
RUN source /opt/ros/melodic/setup.bash \
 && source /home/autoware/Autoware/install/local_setup.bash \
 && cd /home/autoware/Autoware \
 && colcon build \
      --cmake-clean-cache \
      --packages-select \
        decision_maker_panel \
        detected_objects_visualizer \
        fastvirtualscan \
        gazebo_world_description \
        glviewer \
        integrated_viewer \
        points2image \
        rosinterface \
        sim_vehicle_description \
        autoware_rviz_plugins \
        vehicle_description \
        vehicle_model \
      --cmake-args -DCMAKE_BUILD_TYPE=Release

LABEL org.opencontainers.image.source="${VISUALIZATION_REPOSITORY}" \
      org.opencontainers.image.revision="${VISUALIZATION_SHA}"
