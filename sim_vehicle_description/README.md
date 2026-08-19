# sim_vehicle_description

Vehicle-specific RViz resources for the simulation fork. This package is kept
separate from the upstream `vehicle_description` package so upstream updates do
not overwrite simulation choices.

## Launch

```bash
roslaunch sim_vehicle_description simulation.launch
```

The launch file loads `config/vehicle_info.yaml` below `/vehicle_info` and
publishes the URDF transforms used by RViz. Its arguments make the package
usable with a replacement mesh without editing launch XML:

```bash
roslaunch sim_vehicle_description simulation.launch \
  mesh_file:=package://sim_vehicle_description/mesh/my_vehicle.dae \
  mesh_xyz:="0 0 0" mesh_rpy:="0 0 0"
```

When replacing the default mesh, commit the mesh and update
`config/vehicle_info.yaml` in the same change. The default `sim_vehicle.dae` is
copied from the Autoware.AI 1.14.0 baseline and retains its original license.
