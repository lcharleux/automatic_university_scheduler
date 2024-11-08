# UTILITIES
import os
import yaml


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


def read_from_yaml(path):
    """
    Reads a YAML file and returns its contents as a Python dictionary.

    Parameters:
    path (str): The path to the YAML file.

    Returns:
    dict: The contents of the YAML file as a Python dictionary.
    """
    with open(path) as f:
        data = yaml.safe_load(f)
    return data


def dump_to_yaml(data, path):
    """
    Dumps a Python dictionary to a YAML file.

    Parameters:
    data (dict): The data to be dumped to the YAML file.
    path (str): The path to the YAML file.
    """
    with open(path, "w") as f:
        yaml.dump(data, f)


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    OFF = "\033[0m"


class Messages:
    SUCCESS = f"{Colors.GREEN}SUCCESS{Colors.OFF}"
    WARNING = f"{Colors.YELLOW}WARNING{Colors.OFF}"
    ERROR = f"{Colors.RED}ERROR{Colors.OFF}"
    INFO = f"{Colors.BLUE}INFO{Colors.OFF}"
    CYCLE = f"{Colors.MAGENTA}CYCLE{Colors.OFF}"
    SOURCE = f"{Colors.CYAN}SOURCE{Colors.OFF}"
    SINK = f"{Colors.CYAN}SINK{Colors.OFF}"
    FAIL = f"{Colors.RED}FAIL{Colors.OFF}"


def create_instance(session, cls, commit=False, **kwargs):
    """
    Create an instance of a SQLAlchemy model.
    """
    instance = cls(**kwargs)
    session.add(instance)
    if commit:
        session.commit()
    return instance
