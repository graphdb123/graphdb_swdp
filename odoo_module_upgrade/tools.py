
import subprocess
import re
import pathlib

from .config import _AVAILABLE_MIGRATION_STEPS
from .log import logger


def _get_available_init_version_names():
    return [x["init_version_name"] for x in _AVAILABLE_MIGRATION_STEPS]


def _get_available_target_version_names():
    return [x["target_version_name"] for x in _AVAILABLE_MIGRATION_STEPS]


def _get_latest_version_name():
    return _AVAILABLE_MIGRATION_STEPS[-1]["target_version_name"]


def _get_latest_version_code():
    return _AVAILABLE_MIGRATION_STEPS[-1]["target_version_code"]


def _execute_shell(shell_command, path=False, raise_error=True):
    if path:
        shell_command = "cd '%s' && %s" % (str(path.resolve()), shell_command)
    logger.debug("Execute Shell:\n%s" % (shell_command))
    if raise_error:
        return subprocess.check_output(shell_command, shell=True)
    else:
        return subprocess.run(shell_command, shell=True)


# def _read_content(file_path):
#     f = open(file_path, "r")
#     text = f.read()
#     f.close()
#     return text

def _read_content(file_path):
    """ Method 1: Try UTF-8 first, then fallback to other encodings """
    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                text = f.read()
            logger.debug(f"Successfully read file {file_path} with encoding: {encoding}")
            return text
        except UnicodeDecodeError as e:
            logger.debug(f"Failed to read {file_path} with encoding {encoding}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error reading {file_path} with encoding {encoding}: {e}")
            continue
    
    """ If all encodings fail, try reading with error handling """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        logger.warning(f"Read file {file_path} with UTF-8 and replaced invalid characters")
        return text
    except Exception as e:
        raise Exception(f"Unable to read file {file_path} with any encoding: {e}")


# def _write_content(file_path, content):
#     f = open(file_path, "w")
#     f.write(content)
#     f.close()

def _write_content(file_path, content):
    """Write content to file using UTF-8 encoding to handle Unicode characters"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.debug(f"Successfully wrote file {file_path} with UTF-8 encoding")
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        raise


def _replace_in_file(file_path, replaces, log_message=False):
    current_text = _read_content(file_path)
    new_text = current_text

    for old_term, new_term in replaces.items():
        new_text = re.sub(old_term, new_term or "", new_text)

    # Write file if changed
    if new_text != current_text:
        if not log_message:
            log_message = "Changing content of file: %s" % file_path.name
        logger.info(log_message)
        _write_content(file_path, new_text)
    return new_text


def get_files(module_path, extensions):
    """
    Returns a list of files with the specified extensions within the module_path.
    """
    file_paths = []
    module_dir = pathlib.Path(module_path)

    if not module_dir.is_dir():
        raise Exception(f"'{module_path}' is not a valid directory.")

    for ext in extensions:
        file_paths.extend(module_dir.rglob(f"*{ext}"))

    return file_paths
