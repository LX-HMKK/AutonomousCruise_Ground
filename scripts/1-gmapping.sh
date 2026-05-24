#!/bin/bash
### gmapping with abot ###

export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

gnome-terminal -- bash -c 'roscore; exec bash' &
sleep 1

gnome-terminal -- bash -c '
  source /opt/ros/melodic/setup.bash
  source /home/abot/abot_ws/devel/setup.bash
  sleep 3
  roslaunch abot_bringup robot_with_imu.launch
  exec bash' &
sleep 1

gnome-terminal -- bash -c '
  source /opt/ros/melodic/setup.bash
  source /home/abot/abot_ws/devel/setup.bash
  sleep 8
  roslaunch robot_slam gmapping.launch
  exec bash' &
sleep 1

gnome-terminal -- bash -c '
  source /opt/ros/melodic/setup.bash
  source /home/abot/abot_ws/devel/setup.bash
  sleep 10
  roslaunch robot_slam view_mapping.launch
  exec bash' &
sleep 1

gnome-terminal -- bash -c '
  source /opt/ros/melodic/setup.bash
  source /home/abot/abot_ws/devel/setup.bash
  sleep 12
  rosrun teleop_twist_keyboard teleop_twist_keyboard.py
  exec bash' &

echo 'All 5 terminals launched.'
