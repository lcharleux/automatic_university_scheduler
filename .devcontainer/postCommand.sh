#!/bin/bash
echo "Start Devcontainer post-command process !"

cd ../automatic_university_scheduler/
echo "Installing pre-commit"
/opt/conda/envs/ortools/bin/pre-commit install
/opt/conda/envs/ortools/bin/pre-commit install-hooks
echo "Devcontainer post-command process done !"
