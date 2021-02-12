import fire
import requests
import shutil
import os
import sys
import subprocess
import logging
from .system_utils import *


def get_matching_version(full_model_tag_name, request_url, headers):

    request_url = request_url + 'releases/tags/' + full_model_tag_name
    response = requests.get(request_url, headers=headers)

    asset_extension = ".bundle"
    result = {'request_success': False, 'credentials_correct': True ,'response_message': '', 'tag_asset_id': ''}
   
    if response.status_code == 200:
        result['request_success'] = True
        for asset in response.json()['assets']:
            if asset['name'] == str(full_model_tag_name + asset_extension):   
                result['tag_asset_id'] = str(asset['id'])
    if response.status_code == 404:
        result['response_message'] = response.json()['message']
    if response.status_code == 401:
        result['response_message'] = response.json()['message']
        result['credentials_correct'] = False

    return result

def download_asset(full_model_tag_name, request_url, asset_id, headers):

    download_headers = headers
    download_headers["Accept"] = "application/octet-stream"

    downloaded_tag_bundle_file = requests.get(request_url + "releases/assets/" + asset_id, headers=download_headers)

    asset_extension = ".bundle"

    if downloaded_tag_bundle_file.status_code == 200:
        model_asset_file_and_folder_location = get_local_model_storage_path()

        if model_asset_file_and_folder_location != "":
            model_asset_location = os.path.join(model_asset_file_and_folder_location, full_model_tag_name)
            with open(model_asset_location + asset_extension, 'wb') as f:
               f.write(downloaded_tag_bundle_file.content)
               print("Downloaded model package file to : ", model_asset_location + asset_extension)

            return True
    else:
        logging.error("Could not download model package file : " + str(downloaded_tag_bundle_file.status_code) + ", " + downloaded_tag_bundle_file.text)

    return False

def get_all_available_model_tags(request_url, headers):

    list_tags_req = requests.get(url=request_url + "tags", headers=headers)
    model_tag_names = []

    if list_tags_req.status_code == 200:
        for tag in list_tags_req.json():
            model_tag_names.append(tag["name"])
    else:
        logging.error("Failed to fetch list of all releases available: " + str(list_tags_req.status_code) + " " + list_tags_req.text)

    return model_tag_names

def unpack_asset(full_model_tag_name, git_repo_url, remote_name="origin", branch="master"):

    asset_extension = ".bundle"
    try:
        model_storage_path = get_local_model_storage_path()
        if model_storage_path != "":
            model_asset_dir_location = os.path.join(model_storage_path, full_model_tag_name)
            model_asset_bundle_file = model_asset_dir_location + asset_extension

            if os.path.exists(model_asset_dir_location) and os.path.isdir(model_asset_dir_location):
                print("Found previous installation of model:" + full_model_tag_name, " in path:", model_asset_dir_location, ", deleting folder ...")
                if prompt_statement("Should this installation be deleted and reinstalled ?"):
                    shutil.rmtree(model_asset_dir_location, ignore_errors=True)
                    subprocess.run(["git", "clone", model_asset_bundle_file], cwd=model_storage_path)  
            else:
                subprocess.run(["git", "clone", model_asset_bundle_file], cwd=model_storage_path)  

            if is_dir_git_repository(model_asset_dir_location):
                subprocess.run(["git", "remote", "remove", remote_name], cwd=model_asset_dir_location)
                subprocess.run(["git", "remote", "add", remote_name, git_repo_url], cwd=model_asset_dir_location)

            if os.path.isfile(model_asset_bundle_file):
                os.remove(model_asset_bundle_file)

            subprocess.run([sys.executable, "-m", "dvc", "pull"], cwd=model_asset_dir_location, check=True)
            
    except Exception as exception:
        logging.error("Error unpacking model file asset : " + repr(exception))

def download(full_model_tag_name):

    env_git_auth_token = get_auth_environment_vars()["git_auth_token"]
    env_git_repo_url = get_auth_environment_vars()["git_repo_url"]
    
    headers = {"Accept" : "application/vnd.github.v3+json", "Authorization": "token " + env_git_auth_token}
    
    git_repo_url = env_git_repo_url

    user_repo_and_project = '/'.join(git_repo_url.split('.git')[0].split('/')[-2:])

    request_url = 'https://api.github.com/repos/' + user_repo_and_project + "/"

    # Try to get exact match:
    result = get_matching_version(full_model_tag_name, request_url, headers)

    if result["request_success"]:
        print("Found release ", full_model_tag_name, ". Downloading...")
        if result["tag_asset_id"]:
          download_asset(full_model_tag_name, request_url, asset_id=result["tag_asset_id"], headers=headers)
          unpack_asset(full_model_tag_name, git_repo_url)
        else:
            print("Release tag " + full_model_tag_name + " asset id not found, please retry...")
    else:
        available_model_release_tag_names = get_all_available_model_tags(request_url=request_url, headers=headers)
       
        if available_model_release_tag_names:
            matching_tag_names = []
            for tag_name in available_model_release_tag_names:
                if full_model_tag_name in tag_name:
                    matching_tag_names.append(tag_name)
        
            if matching_tag_names:
                print("Found the following tags with a similar name:")
                print(matching_tag_names)
                while True:
                    model_choice = input("Please input the model version you would like to download: \n")
                    if model_choice in matching_tag_names:
                        result = get_matching_version(model_choice, request_url, headers)
                        print("Found release ", model_choice, ". Downloading...")
                        download_asset(model_choice, request_url, asset_id=result["tag_asset_id"], headers=headers)
                        unpack_asset(model_choice, git_repo_url)
                        break
            else:
                print("No release tags found with the given name or containing a similar name, however, the following releases are available:")
                print(available_model_release_tag_names)
                while True:
                    model_choice = input("Please input the model version you would like to download: \n")
                    if model_choice in available_model_release_tag_names:
                        result = get_matching_version(model_choice, request_url, headers)
                        print("Found release ", model_choice, ". Downloading...")
                        download_asset(model_choice, request_url, asset_id=result["tag_asset_id"], headers=headers)
                        unpack_asset(model_choice, git_repo_url)
                        break
        else:
            print("No model release tags found on repository: " + request_url)
            print("Make sure you have configured MedCAT repository settings via the configure command.")
            sys.exit()
                
if __name__ == '__main__':
  fire.Fire(download)