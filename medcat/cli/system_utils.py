import git
import os
import sys
import pickle
import logging
import medcat
from .modeltagdata import ModelTagData

def load_model_from_file(full_model_tag_name="", file_name="", model_folder=".", bypass_model_path=False):
    """
        Looks into the models directory in your /site-packages/medcat-{version}/model_name/ installation.
        - bypass_model_path = will look into specified folder
    """
    full_file_path = os.path.join(model_folder, file_name)

    if bypass_model_path is False:
        full_file_path = os.path.join(get_downloaded_local_model_folder(full_model_tag_name), file_name)

    data = False
    with open(full_file_path, 'rb') as f:
        data = pickle.load(f)

        version = ""
        model_name=""
        
        if full_model_tag_name != "":
            model_name, version = get_str_model_version(full_model_tag_name)

        try:
            if isinstance(data, dict) and "vc_model_tag_data" not in data.keys():
                data["vc_model_tag_data"] = ModelTagData(model_name, version=version)
            elif not hasattr(data, "vc_model_tag_data"):
                data.vc_model_tag_data = ModelTagData(model_name, version=version)
            elif not data.vc_model_tag_data.model_name:
                data.vc_model_tag_data.model_name = model_name
                data.vc_model_tag.data_version = version
                
        except Exception as exception:
            logging.error("could not add vc_model_tag_data attribute to model data file")
            logging.error(repr(exception))

    return data

def get_str_model_version(model_full_tag_name, delimiter='-'):
    split_name_and_version = model_full_tag_name.split(delimiter)
    model_name = split_name_and_version[0]
    version = "1.0"
    if len(split_name_and_version) > 1:
        version = split_name_and_version[1]
    return model_name, version

def get_auth_environemnt_vars():
    """
        returns a dict with the github username and git access token
    """
    env_var_field_mapping = {"username": "MEDCAT_GIT_USERNAME",
     "git_auth_token" : "MEDCAT_GIT_AUTH_TOKEN",
      "git_repo_url" : "MEDCAT_GIT_REPO_URL"}

    auth_vars = { "username" : os.getenv(env_var_field_mapping["username"], ""), 
                  "git_auth_token": os.getenv(env_var_field_mapping["git_auth_token"], ""),
                  "git_repo_url":  os.getenv(env_var_field_mapping["git_repo_url"], "") }
    
    for k,v in auth_vars.items():
        if not v.strip():
            raise ValueError("CONFIG NOT SET for :  " + k + "  , from environment var : " + env_var_field_mapping[k])

    return auth_vars

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
        repo = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError as exception:
        logging.error("Folder:" + path + " is not a git repository. Description:" + repr(exception))
        return False

def get_permitted_push_file_list():
    return ["cdb.dat", "vocab.dat", "modelcard.md", "modelcard.json"]