from medcat.cli.system_utils import prompt_statement
import sys
import fire
import os
import json
import logging
import medcat

env_var_field_mapping = {
                         "username": "MEDCAT_GIT_USERNAME",
                         "git_auth_token" : "MEDCAT_GIT_AUTH_TOKEN",
                         "git_repo_url" : "MEDCAT_GIT_REPO_URL",
                         "git_organisation_name" : "MEDCAT_ORGANISATION_NAME"
                        }

def config():
    config_data = {}
    
    for k,v in env_var_field_mapping.items():
        while True:
            input_val = input("Please input your " + k + " (" + v + ") : ")
            if input_val.strip() != "" or k == "git_organisation_name":
                if k == "git_organisation_name":
                    config_data[v] = get_git_user_project(config_data[env_var_field_mapping["git_repo_url"]]).split("/")[0]
                    logging.info(" " + env_var_field_mapping[k] + " not set, inferring ORGANISATION name from the git repo : " + "\033[1m" +  config_data[env_var_field_mapping["git_repo_url"]] + "\033[0m" +
                                 " \n the organisation name will be : " + config_data[v])
                    if prompt_statement("Is this correct ?"):
                        break
                else:
                    config_data[v] = input_val.strip()
                    break

    generate_medcat_config_file(config_data)

def get_auth_environment_vars():
    """
        :returns: a dict with the github username, auth token, repo url and organisation name
    """
    auth_vars = { 
                 "username" : os.getenv(env_var_field_mapping["username"], ""), 
                 "git_auth_token": os.getenv(env_var_field_mapping["git_auth_token"], ""), 
                 "git_repo_url":  os.getenv(env_var_field_mapping["git_repo_url"], ""), 
                 "git_organisation_name" : os.getenv(env_var_field_mapping["git_organisation_name"], "")
                }
    try:
        env_medcat_config_file = get_medcat_config_settings()

        for k,v in auth_vars.items():
            if v.strip() == "" and env_var_field_mapping[k] in env_medcat_config_file.keys() and env_medcat_config_file[env_var_field_mapping[k]] != "":
                auth_vars[k] = env_medcat_config_file[env_var_field_mapping[k]]
            elif v.strip() == "" and k == "git_organisation_name":
                auth_vars[k] = get_git_user_project(env_medcat_config_file[env_var_field_mapping[k]]).split("/")[0]
            else:
                logging.error("Please set your configuration settings by using the 'python3 -m medcat config' command or by exporting the global variable in your current session 'export " + env_var_field_mapping[k] + "=your_value' !")
                raise ValueError("CONFIG NOT SET for :  " + k + "  , from environment var : " + env_var_field_mapping[k])

    except Exception as exception:
        logging.error(repr(exception))
        sys.exit()

    return auth_vars

def generate_medcat_config_file(config_settings={}, config_dirname="config", config_file="env_version_control.json"):
    config_path = os.path.join(os.path.dirname(medcat.__file__), config_dirname)
    try:
        if os.path.isdir(config_path) is False:
            os.makedirs(config_path)  
    except Exception as exception:
        logging.error("Could not create MedCAT config folder " + str(config_path))
        logging.error(repr(exception))

    with open(os.path.join(config_path, config_file), "w") as f:
        json.dump(config_settings, f)
        logging.info("Config file saved in : " + str(os.path.join(config_path, config_file)))

def get_medcat_config_settings(config_dirname="config", config_file="env_version_control.json"):
    config_file_contents = {}
    config_file_full_path = os.path.join(os.path.dirname(medcat.__file__), config_dirname, config_file)
    if os.path.isfile(config_file_full_path):
        with open(config_file_full_path, "r") as f:
            config_file_contents = json.load(f)
    return config_file_contents    

def get_git_user_project(url=""):
    """
        :return: user/repo_name from git url, e.g: https://github.com/user/repo_name -> user/repo_name
    """
    if url.strip() == "":
        env_git_repo_url = get_auth_environment_vars()["git_repo_url"]
    else:
        env_git_repo_url = url
    user_repo_and_project = '/'.join(env_git_repo_url.split('.git')[0].split('/')[-2:])
    return user_repo_and_project

def get_git_default_headers():
    env_git_auth_token = get_auth_environment_vars()["git_auth_token"]
    headers = {"Accept" : "application/vnd.github.v3+json", "Authorization": "token " + env_git_auth_token} 
    return headers

def get_git_download_headers():
    headers = get_git_default_headers()
    headers["Accept"] =  "application/octet-stream"
    return headers

def get_git_upload_headers():
    headers = get_git_default_headers()
    headers = {**headers, "Content-Type": "application/octet-stream"}
    return headers 

def get_git_api_request_url():
    return "https://api.github.com/repos/" + get_git_user_project() + "/"

def get_git_api_upload_url():
    return "https://uploads.github.com/repos/" + get_git_user_project() + "/"


if __name__ == '__main__':
  fire.Fire(config)