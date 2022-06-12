FROM continuumio/miniconda3

# VARIABLES
ARG PATH="/root/miniconda3/bin:${PATH}"
ARG ENVNAME="ortools"

SHELL ["/bin/bash", "--login", "-c"]
ENV PATH="/root/miniconda3/bin:${PATH}"
RUN apt-get update \
    && apt-get install -y wget \
    git \
     && rm -rf /var/lib/apt/lists/*
RUN conda create --name $ENVNAME
RUN echo "conda activate $ENVNAME" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]
# Conda installs 
RUN conda install -y -c conda-forge ortools-python ipython \
    pandas xlrd xlwt pytables \
    pre-commit black 

# NVTOP : NOT WORKING PROPERLY YET
# RUN apt update \
#     && apt install -y nvtop htop nodejs npm
# RUN npm install -g -y gtop

SHELL ["/bin/bash", "--login", "-c"]
