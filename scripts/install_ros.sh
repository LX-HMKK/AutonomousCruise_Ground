sudo sh -c '. /etc/lsb-release && echo "deb http://mirrors.ustc.edu.cn/ros/ubuntu/ `lsb_release -cs` main" > /etc/apt/sources.list.d/ros-latest.list'
sudo apt-key adv --keyserver 'hkp://keyserver.ubuntu.com:80' --recv-key C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654
sudo apt update
sudo apt install ros-melodic-desktop-full
echo "source /opt/ros/melodic/setup.bash" >> ~/.bashrc
source ~/.bashrc
sudo apt install ros-melodic-gmapping ros-melodic-cartographer ros-melodic-rplidar-ros ros-melodic-amcl ros-melodic-map-server ros-melodic-navigation ros-melodic-ar-track-alvar ros-melodic-teleop-twist-keyboard  ros-melodic-imu-filter-madgwick  ros-melodic-robot-pose-ekf  ros-melodic-usb-cam ros-melodic-move-base ros-melodic-move-base-msgs  ros-melodic-ar-track-alvar  ros-melodic-uvc-camera   ros-melodic-opencv-apps   
sudo apt install python-pip
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple opencv-contrib-python
sudo apt install mplayer libasound2-dev python-rosdep





