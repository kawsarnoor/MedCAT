import git
import os
import sys
import logging
import medcat

def prompt_statement(prompt_text, answer="yes"):
    valid_answers = {"yes": True, "no": False, "y": True, "n": False}
    exit_answer = ["exit", "cancel", "abort"]
    
    while True:
        print(prompt_text)
        print(" \t (Yes/No or Y/N), type exit/cancel/abort, or press CTRL+C to ABORT, all choices are case insensitive!")
        choice = input().lower()

        if choice in valid_answers.keys():
            return valid_answers[choice]
        else:
            print("Invalid answer, please try again...")
            if choice in exit_answer:
                sys.exit()

def get_downloaded_local_model_folder(model_name):
    try:
        full_model_path = os.path.join(get_local_model_storage_path(), model_name)
        if os.path.isdir(full_model_path):
            if is_dir_git_repository(full_model_path):
                return full_model_path
        return ""
    except Exception as exception:
        logging.error("Could not find model folder " + model_name + ".")
        

def get_local_model_storage_path(storage_path=os.path.dirname(medcat.__file__), models_dir="models"):
    
    medcat_model_installation_dir_path = os.path.join(storage_path, models_dir)

    if not os.path.exists(medcat_model_installation_dir_path):
        try:
            os.mkdir(medcat_model_installation_dir_path)
            return medcat_model_installation_dir_path
        except OSError as os_exception:
            logging.error("Could not create MedCAT model storage folder: " + medcat_model_installation_dir_path)
            logging.error(repr(os_exception))

    elif os.access(medcat_model_installation_dir_path, os.R_OK | os.X_OK | os.W_OK):
        return medcat_model_installation_dir_path

    return ""

def is_dir_git_repository(path):
    try:
        _ = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError as exception:
        logging.error("Folder:" + path + " is not a git repository. Description:" + repr(exception))
        return False

def get_permitted_push_file_list():
    return ["cdb.dat", "vocab.dat"]