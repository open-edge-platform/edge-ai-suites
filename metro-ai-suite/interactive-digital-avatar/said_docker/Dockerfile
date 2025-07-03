ARG OS_VER=22.04
ARG OS_IMAGE=ubuntu

FROM ${OS_IMAGE}:${OS_VER}
# FROM intel/oneapi-basekit:2024.2.0-devel-ubuntu22.04
USER root
WORKDIR /app
COPY said_flask_ov.py .
COPY said_ov_run.sh .

# gpu
RUN apt update && apt install -y gnupg wget 
RUN wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg
RUN echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy client" | \
    tee /etc/apt/sources.list.d/intel-gpu-jammy.list
RUN apt update
RUN apt install -y \
    intel-opencl-icd intel-level-zero-gpu level-zero intel-level-zero-gpu-raytracing \
    intel-media-va-driver-non-free libmfx1 libmfxgen1 libvpl2 \
    libegl-mesa0 libegl1-mesa libegl1-mesa-dev libgbm1 libgl1-mesa-dev libgl1-mesa-dri \
    libglapi-mesa libgles2-mesa-dev libglx-mesa0 libigdgmm12 libxatracker2 mesa-va-drivers \
    mesa-vdpau-drivers mesa-vulkan-drivers va-driver-all vainfo hwinfo clinfo 

# mini-forge
RUN apt-get update && apt-get install -y wget bzip2
RUN wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
RUN bash Miniforge3-Linux-x86_64.sh -b
ENV PATH=/root/miniforge3/bin:$PATH
RUN conda create -n said_ov python=3.11
# SHELL ["conda", "run", "-n", "said_ov", "/bin/bash", "-c"]
RUN /root/miniforge3/envs/said_ov/bin/python -m pip install openvino-dev[tensorflow2,onnx] flask

COPY SAiD.patch .

# git
RUN apt-get update && \
    apt-get install -y git
RUN git clone https://github.com/yunik1004/SAiD.git
RUN cd SAiD && \
    git checkout bb7b18018358d3156569d8051f386943744a5ea0 && \ 
    patch -p1 < ../SAiD.patch && \
    /root/miniforge3/envs/said_ov/bin/python -m pip install -e .

# Fix model download issue
RUN /root/miniforge3/envs/said_ov/bin/python -m pip install huggingface_hub==0.25.0

RUN mkdir ov_models

EXPOSE 5000
ENTRYPOINT ["/bin/bash", "/app/said_ov_run.sh"]