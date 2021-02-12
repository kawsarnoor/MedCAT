import shutil
import subprocess
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
        model_name = ""
        
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

def get_auth_environment_vars():
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

def create_model_folder(full_model_tag_name):
    try:
        os.makedirs(os.path.join(get_local_model_storage_path(),full_model_tag_name))
    except Exception as exception:
        logging.info("Could not create model folder " + full_model_tag_name + ".")
        logging.info("" + repr(exception))

def get_downloaded_local_model_folder(full_model_tag_name):
    """
        Check if folder for model exists and it is a GIT repository.
        Returns empty if either of conditions fail.
    """
    try:
        full_model_path = os.path.join(get_local_model_storage_path(), full_model_tag_name)
        if os.path.isdir(full_model_path):
            if is_dir_git_repository(full_model_path):
                return full_model_path
        return False
    except Exception as exception:
        logging.error("Could not find model folder " + full_model_tag_name + ".")

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
    
def copy_model_files_to_folder(source_folder, dest_folder):

    root, subdirs, files = next(os.walk(source_folder))

    for file_name in files:
        if file_name in get_permitted_push_file_list():
            logging.info("Copying file : " + file_name + " to " + dest_folder)
            shutil.copy2(os.path.join(source_folder, file_name), dest_folder)
        else:
            logging.info("Discarding " + file_name + " as it is not in the permitted model file pushing convention...")

def create_new_base_repository(repo_folder_path, git_repo_url, remote_name="origin", branch="master", checkout_full_tag_name=""):
    """
        Creates a base repository for a NEW base model release. 
        The base repo always points to the HEAD commit of the git history, not to a tag/release commit.

        :checkout_full_tag_name : should be used in the case of creating/updating from already existing model release/tag 
    """

    try:
        subprocess.run(["git", "init"], cwd=repo_folder_path)
        subprocess.run(["git", "remote", "add", remote_name, git_repo_url], cwd=repo_folder_path)
       
        if checkout_full_tag_name != "":
             subprocess.run(["git", "fetch", "--tags", "--force"], cwd=repo_folder_path)
             subprocess.run(["git", "checkout", "tags/" + checkout_full_tag_name, "-b" , branch], cwd=repo_folder_path)

        subprocess.run(["git", "pull", remote_name, branch], cwd=repo_folder_path)


    except Exception as exception:
        logging.error("Error creating base model repository: " + repr(exception))
        sys.exit()

def is_dir_git_repository(path):
    try:
        repo = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError as exception:
        logging.error("Folder:" + path + " is not a git repository. Description:" + repr(exception))
        return False

def sanitize_input():
    pass

def get_file_ext_to_ignore():
    return ["*.dat"]

def get_permitted_push_file_list():
    return ["cdb.dat", "vocab.dat", "modelcard.md", "modelcard.json"]