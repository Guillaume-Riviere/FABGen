# linux image with golang, python and lua
FROM ubuntu:latest

# install golang
RUN apt-get update && apt-get install -y golang
# install apt-get -y install golang-golang-x-tools
RUN apt-get install -y golang-golang-x-tools
# install python
RUN apt-get install -y python3
# install pip
RUN apt-get install -y python3-pip

# pip install pypeg2
RUN pip3 install pypeg2
# install lua
RUN apt-get install -y lua5.2
# install cmake
RUN apt-get install -y cmake

# install git
RUN apt-get install -y git
# https://github.com/algosup/2022-2023-project-3-harfang3d-binding-Project-8-group.git
#RUN git clone https://github.com/algosup/2022-2023-project-3-harfang3d-binding-Project-6-group.git

COPY . ./app/

# CMD ["/bin/bash"]