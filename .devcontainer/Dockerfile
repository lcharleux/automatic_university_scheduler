ARG BASE_IMAGE=continuumio/miniconda3
FROM ${BASE_IMAGE}

# disable terminal interaction for apt
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C

# Get user parameters from runner
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG ENVNAME="ortools"

# Set user parameters as environment variables
ENV USERNAME=${USERNAME}
ENV USER_GID=${USER_GID}
ENV USER_UID=${USER_UID}





# Create the '$USER' user
# RUN groupmod --gid ${USER_GID} -n ${USERNAME} root && \
#         usermod -l ${USERNAME} -u ${USER_UID} -o -m -d /home/${USERNAME} triton-server && \
#         mkdir -p /home/${USERNAME} && \
#         sudo chown ${USERNAME}:${USERNAME} /home/${USERNAME} && \
#         echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} && \
#         chmod 0440 /etc/sudoers.d/${USERNAME} && \
#         adduser ${USERNAME} video && adduser ${USERNAME} sudo

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    #
    # [Optional] Add sudo support. Omit if you don't need to install software after connecting.
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME



# Fundamentals
RUN sudo apt-get update && sudo apt-get install -y \
        bash-completion locales \
        && sudo rm -rf /var/lib/apt/lists/*

RUN locale-gen en_US.UTF-8
RUN sudo localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

# Log as $USER and create a .bashrc file for config
USER ${USERNAME}
# Add possibility to write in /opt
RUN sudo chown -R $USER_UID:$USER_GID /opt/conda/

RUN touch ~/.bashrc
RUN sudo mkdir /opt/conda/pkgs
RUN sudo touch /opt/conda/pkgs/urls.txt

# Install miniconda
ENV CONDA_DIR ~/.conda
# Put conda in path so we can use conda activate
ENV PATH=$CONDA_DIR/bin:$PATH

RUN conda create --name $ENVNAME
RUN echo "conda activate $ENVNAME" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]
# Create conda environment named myenv
# RUN . ~/.bashrc && \
#         conda init bash && \
#         conda create -n $ENVNAME

# Set auto activation of env when launching bash
#RUN echo "conda activate $ENVNAME" > ~/.bashrc

# Add conda env to PATH
ENV PATH ~/.conda/envs/$ENVNAME/bin:$PATH

# Copy scripts
# RUN sudo mkdir -p /usr/local/bin/scripts
# COPY scripts/*entrypoint.sh /usr/local/bin/scripts/
# RUN sudo chmod +x /usr/local/bin/scripts/*.sh
# RUN sudo rm -r /workspace

RUN   conda install -y -c conda-forge ortools-python ipython \
      pandas xlrd xlwt pytables \
      pre-commit black



# Set default workspace according user input
# ARG HOME_FOLDER
# WORKDIR ${HOME_FOLDER}
