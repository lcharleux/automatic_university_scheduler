# UTILITIES
import os


def create_directory(directory: str) -> None:
    """
    Create a directory if it does not exist.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)


def create_directories(directories: list) -> None:
    """
    Create multiple directories if they do not exist.
    """
    for directory in directories:
        create_directory(directory)
