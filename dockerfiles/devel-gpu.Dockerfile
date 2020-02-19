# To build, do:
# $ docker build --pull -t laigd/myenv -f <this file> ./
#
# See http://dev.im-bot.com/docker-select-caching/ on how to rebuild with
# selected cache. Basically we need to do:

# - Add this and below command will run without cache `ARG CACHEBUST=1`
# - When you need to rebuild with selected cache, run it with --build-arg option
#   `$ docker build -t your-image --build-arg CACHEBUST=$(date +%s) .`

ARG UBUNTU_VERSION=16.04
ARG CUDA_MAJOR_VERSION=10
ARG CUDA_MINOR_VERSION=1

FROM nvidia/cuda:${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION}-base-ubuntu${UBUNTU_VERSION} as base

# We need to re-declare the ARGs after a FROM instruction, see
# https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact
ARG UBUNTU_VERSION
ARG CUDA_MAJOR_VERSION
ARG CUDA_MINOR_VERSION

# See https://developer.download.nvidia.com/compute/machine-learning/repos/ubuntu1604/x86_64/ for the available cudnn and tensorrt versions.
ARG CUDNN_MAJOR_VERSION=7
ARG CUDNN_VERSION_SUFFIX=5.0.56
ARG CUBLAS_MAJOR_VERSION=10
ARG CUBLAS_VERSION_SUFFIX=1.0.105
ARG TENSORRT_MAJOR_VERSION=6
ARG TENSORRT_VERSION_SUFFIX=0.1

# CUDA dependencies
# TensorRT will be installed in /usr/lib/x86_64-linux-gnu
RUN apt-get update && apt-get install -y --no-install-recommends \
        apt-utils \
        build-essential \
        \
        cuda-command-line-tools-${CUDA_MAJOR_VERSION}-${CUDA_MINOR_VERSION} \
        cuda-cudart-dev-${CUDA_MAJOR_VERSION}-${CUDA_MINOR_VERSION} \
        cuda-cufft-dev-${CUDA_MAJOR_VERSION}-${CUDA_MINOR_VERSION} \
        cuda-curand-dev-${CUDA_MAJOR_VERSION}-${CUDA_MINOR_VERSION} \
        cuda-cusolver-dev-${CUDA_MAJOR_VERSION}-${CUDA_MINOR_VERSION} \
        cuda-cusparse-dev-${CUDA_MAJOR_VERSION}-${CUDA_MINOR_VERSION} \
        \
        libcudnn${CUDNN_MAJOR_VERSION}=${CUDNN_MAJOR_VERSION}.${CUDNN_VERSION_SUFFIX}-1+cuda${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION} \
        libcudnn${CUDNN_MAJOR_VERSION}-dev=${CUDNN_MAJOR_VERSION}.${CUDNN_VERSION_SUFFIX}-1+cuda${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION} \
        \
        libcublas${CUBLAS_MAJOR_VERSION}=${CUBLAS_MAJOR_VERSION}.${CUBLAS_VERSION_SUFFIX} \
        libcublas-dev=${CUBLAS_MAJOR_VERSION}.${CUBLAS_VERSION_SUFFIX} \
        \
        libnvinfer${TENSORRT_MAJOR_VERSION}=${TENSORRT_MAJOR_VERSION}.${TENSORRT_VERSION_SUFFIX}-1+cuda${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION} \
        libnvinfer-dev=${TENSORRT_MAJOR_VERSION}.${TENSORRT_VERSION_SUFFIX}-1+cuda${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION} \
        \
        libcurl3-dev \
        libfreetype6-dev \
        libhdf5-serial-dev \
        libpng12-dev \
        libzmq3-dev \
        pkg-config \
        rsync \
        software-properties-common \
        unzip zip zlib1g-dev wget curl git tmux vim iputils-ping \
        libcupti-dev libtool automake \
    && find /usr/local/cuda-${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION}/lib64/ -type f -name 'lib*_static.a' -not -name 'libcudart_static.a' -delete \
    && rm /usr/lib/x86_64-linux-gnu/libcudnn_static_v${CUDNN_MAJOR_VERSION}.a

# Configure the build for our CUDA configuration.
ENV CI_BUILD_PYTHON python
ENV LD_LIBRARY_PATH=/usr/local/cuda/extras/CUPTI/lib64:$LD_LIBRARY_PATH
ENV TF_NEED_CUDA=1
ENV TF_NEED_TENSORRT 1
ENV TF_CUDA_COMPUTE_CAPABILITIES=7.0
ENV TF_CUDA_VERSION=${CUDA_MAJOR_VERSION}.${CUDA_MINOR_VERSION}
ENV TF_CUDNN_VERSION=${CUDNN_MAJOR_VERSION}

ARG PYTHON=python3
ARG PIP=pip3

# See http://bugs.python.org/issue19846
ENV LANG C.UTF-8

RUN apt-get update && apt-get install -y \
        ${PYTHON} \
        ${PYTHON}-pip \
        ${PYTHON}-dev \
        ${PYTHON}-numpy \
        ${PYTHON}-wheel \
        ${PYTHON}-virtualenv \
        ${PYTHON}-tk

RUN ${PIP} --no-cache-dir install --upgrade \
        pip \
        setuptools

# Some TF tools expect a "python" binary
RUN ln -s $(which ${PYTHON}) /usr/local/bin/python

RUN apt-get update && apt-get install -y openjdk-8-jdk swig

RUN ${PIP} --no-cache-dir install \
        Pillow \
        requests \
        h5py \
        keras_applications \
        keras_preprocessing \
        matplotlib \
        mock \
        numpy \
        scipy \
        sklearn \
        pandas

# Install bazel
ARG BAZEL_VERSION=0.22.0
RUN mkdir /bazel \
    && wget -O /bazel/installer.sh "https://github.com/bazelbuild/bazel/releases/download/${BAZEL_VERSION}/bazel-${BAZEL_VERSION}-installer-linux-x86_64.sh" \
    && wget -O /bazel/LICENSE.txt "https://raw.githubusercontent.com/bazelbuild/bazel/master/LICENSE" \
    && chmod +x /bazel/installer.sh \
    && /bazel/installer.sh \
    && rm -f /bazel/installer.sh

# Install gcc-6
# RUN apt-get update && \
#       add-apt-repository ppa:ubuntu-toolchain-r/test -y && \
#       apt-get update && \
#       apt-get install gcc-6 g++-6 -y && \
#       update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-6 60 --slave /usr/bin/g++ g++ /usr/bin/g++-6 && \
#       gcc -v
