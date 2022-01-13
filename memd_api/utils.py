import os


def load_env(name, default=None):
    if name in os.environ:
        return os.environ[name]
    file_env = name + '_FILE'
    if os.environ.get(file_env):
        path = os.environ[file_env]
        if os.path.isfile(path):
            with open(path, 'r') as fh:
                return fh.read()
    if default is not None:
        return default
    raise ValueError(f'Environment Variable {name} is not defined and is required.')
