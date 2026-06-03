#!/bin/bash
echo '============================================'
echo '   COMPREHENSIVE WSL ROS ENVIRONMENT AUDIT'
echo '============================================'

echo ''
echo '=== 3. Navigation Stack ==='
dpkg -l | grep -E 'ros-melodic-(navigation|move-base|amcl|gmapping|dwa|global-planner|map-server|cartographer)' | awk '{print $2, $3}'
echo "(count: $(dpkg -l | grep -cE 'ros-melodic-(navigation|move-base|amcl|gmapping|dwa|global-planner|map-server|cartographer)') packages)"

echo ''
echo '=== 4. Perception / Vision ==='
dpkg -l | grep -E 'ros-melodic-(usb-cam|cv-bridge|image|vision|ar-track|find-object)' | awk '{print $2, $3}'
echo "(count: $(dpkg -l | grep -cE 'ros-melodic-(usb-cam|cv-bridge|image|vision|ar-track|find-object)') packages)"

echo ''
echo '=== 5. SLAM ==='
dpkg -l | grep -E 'ros-melodic-(hector|gmapping|cartographer)' | awk '{print $2, $3}'
echo "(count: $(dpkg -l | grep -cE 'ros-melodic-(hector|gmapping|cartographer)') packages)"

echo ''
echo '=== 6. Voice / Audio ==='
dpkg -l | grep -E 'ros-melodic-(audio|sound|speech|voice)' | awk '{print $2, $3}'
echo "(count: $(dpkg -l | grep -cE 'ros-melodic-(audio|sound|speech|voice)') packages)"
echo '--- Python audio ---'
python2 -c 'import pyaudio; print("pyaudio OK")' 2>&1 || echo 'pyaudio MISSING'

echo ''
echo '=== 7. RQT / GUI Tools ==='
dpkg -l | grep 'ros-melodic-rqt' | awk '{print $2, $3}'
echo "(count: $(dpkg -l | grep -c 'ros-melodic-rqt') packages)"

echo ''
echo '=== 8a. Our Workspace - Packages ==='
source /opt/ros/melodic/setup.bash
source /home/lx_hm/abot_ws/devel/setup.bash
echo '--- Our packages ---'
rospack list 2>&1 | grep -E 'mission_manager|common|robot_slam|abot_|user_demo'

echo ''
echo '=== 8b. Workspace Build Status ==='
ls -la /home/lx_hm/abot_ws/devel/lib/ 2>&1 | head -20
echo '--- Build artifacts ---'
find /home/lx_hm/abot_ws/devel -name "*.pyc" -o -name "*.so" -o -name "*.cfg" 2>/dev/null | head -20

echo ''
echo '=== 8c. Package Dependencies ==='
source /opt/ros/melodic/setup.bash
source /home/lx_hm/abot_ws/devel/setup.bash
echo '--- mission_manager deps ---'
rospack depends mission_manager 2>&1 || echo 'rosdep not initialized'
echo '--- common deps ---'
rospack depends common 2>&1 || echo 'rosdep not initialized'

echo ''
echo '=== 9. Missing Dependencies (rosdep) ==='
source /opt/ros/melodic/setup.bash
source /home/lx_hm/abot_ws/devel/setup.bash
rosdep check --from-paths /home/lx_hm/abot_ws/src --ignore-src 2>&1 | head -40

echo ''
echo '=== 10. Python 2 Packages ==='
python2 -c 'import rospy; print("rospy OK")' 2>&1
python2 -c 'import yaml; print("yaml OK")' 2>&1
python2 -c 'import cv2; print("cv2 OK")' 2>&1
python2 -c 'import numpy; print("numpy OK")' 2>&1
python2 -c 'import tf; print("tf OK")' 2>&1
python2 -c 'import actionlib; print("actionlib OK")' 2>&1
python2 -c 'import json; print("json OK")' 2>&1
python2 -c 'import threading; print("threading OK")' 2>&1

echo ''
echo '=== 11. Additional: pip packages ==='
pip2 list 2>&1 | grep -iE 'rospy|catkin|rosdep|rosinstall|wstool|vcstool|defusedxml|netifaces'

echo ''
echo '=== 12. Additional: /opt/ros/melodic health ==='
ls /opt/ros/melodic/setup.bash && echo '/opt/ros/melodic OK'
dpkg -l | grep -c 'ros-melodic-' && echo ' total ROS melodic packages installed'

echo ''
echo '=== 13. Additional: workspace src structure ==='
ls -la /home/lx_hm/abot_ws/src/ 2>&1

echo ''
echo '=== AUDIT COMPLETE ==='
