import fire
import requests
import sys
import os
import json
import subprocess
import logging
import site
import shutil
import git
from git import Repo
from functools import reduce
from requests.api import head
from .download import get_all_available_model_tags
from .system_utils import *
from .modeltagdata import ModelTagData


def select_model_packaging_folder(request_url, headers, model_name):

    if model_name != "":
        available_model_tags = get_all_available_model_tags(request_url, headers)
        found_matching_tags = [tag_name for tag_name in available_model_tags if model_name in tag_name] 

        found_model_folders = []
        root, subdirs, files = next(os.walk(get_local_model_storage_path()))

        for subdir in subdirs:
            if subdir in available_model_tags:
                found_model_folders.append(subdir)

        found_matching_folders = [dir_name for dir_name in found_model_folders if model_name in dir_name] 

        version_choice = ""
        # to add the automatic option once model loading has the extra provenance fields
        if found_matching_folders:
            print("Found the following model folders matching the name given:", found_matching_folders)
            version_choice = input("Please input what folder to use for packaging : ")

        elif not found_matching_folders and found_matching_tags:
            print("No models detected on the machine, however, there are available releases matching the tag name: ", found_matching_tags)
            version_choice = input("Please input the model_name-version:")
            subprocess.run([sys.executable, "-m", "medcat", "download", str(version_choice)],
                           cwd=get_local_model_storage_path())
        
        elif not found_matching_folders and available_model_tags:
            print("No models detected on the machine, however, there are other releases available for download: ", available_model_tags)
            version_choice = input("Please input the model_name-version:")
            subprocess.run([sys.executable, "-m", "medcat", "download", str(version_choice)],
                           cwd=get_local_model_storage_path())

        elif prompt_statement("Is this a new model release ?"):  # if model.provenance_model != "" && no tags with model name exist:
            if prompt_statement("Should the model_name : " + "\033[1m" + model_name + "\033[0m"  + " be used ? the version will be 1.0 by default, another name can be provided by answering NO."):
                version_choice = model_name
            else:
                version_choice = input("give the model release a name, the version will be 1.0 by default:")
            #if prompt_statement("Are you certain that " + '\033[1m' +  version_choice + '\033[0m'  + " is correct ? this process is irreversible, please double-check."):
            shutil.rmtree(os.path.join(get_local_model_storage_path(), version_choice), ignore_errors=True)

        elif not version_choice or not available_model_tags:
            logging.error("Model name not provided or no model tags found for download, exitting")
            sys.exit()
      
        return os.path.join(get_local_model_storage_path(), version_choice)

    elif os.path.isdir(os.path.join(get_local_model_storage_path(), model_name)):
        return os.path.join(get_local_model_storage_path(), model_name)

def create_new_base_repository(repo_folder_path, git_repo_url, remote_name="origin", branch="master"):
    """
        Creates a base repository for a NEW base model release. 
        The base repo always points to the HEAD commit of the git history, not to a tag/release commit.
    """

    try:
        subprocess.run(["git", "init"], cwd=repo_folder_path)
        subprocess.run(["git", "remote", "add", remote_name, git_repo_url], cwd=repo_folder_path)
        subprocess.run(["git", "pull", remote_name, branch], cwd=repo_folder_path)
    except Exception as exception:
        logging.error("Error creating base model repostiroy: " + repr(exception))
        sys.exit()


def copy_model_files_to_folder(source_folder, dest_folder):

    root, subdirs, files = next(os.walk(source_folder))

    for file_name in files:
        if file_name in get_permitted_push_file_list():
            print("Copying file : " + file_name, " to ", dest_folder)
            shutil.copy2(source_folder + "/" + file_name, dest_folder)
        else:
            print("Discarding " + file_name + " as it is not in the permitted model file naming convention...")


def upload_model(model_name, parent_model_name, version, git_auth_token):
    headers = {"Accept": "application/vnd.github.v3+json", "Authorization": "token " + git_auth_token}
    upload_headers = {**headers, "Content-Type": "application/octet-stream"}

    user_repo = "kawsarnoor/MedCatModels"

    git_repo_url = "https://github.com/" + user_repo + ".git"
    request_url = 'https://api.github.com/repos/' + user_repo + "/"

    # folder where we are now
    original_folder = os.getcwd()

    # folder where the model files are: /lib/python/site-packages/medcat-{version}/models/...
    current_dir = get_local_model_storage_path(get_local_model_storage_path(), models_dir=select_model_packaging_folder(request_url, headers, model_name))
    

    if current_dir != "" and not is_dir_git_repository(current_dir):
        create_new_base_repository(current_dir, git_repo_url)
    
    # copy files to model folder repo (inside site-packages)
    copy_model_files_to_folder(original_folder, current_dir)

    tag_name = ""
    bundle_file_path = ""
    active_remote = "origin"
    
    try:
        print("Current working dir: ", current_dir)
        print("===================================================================")
        print("Git status:")
        subprocess.call(["git", "status"], cwd=current_dir)
        print("===================================================================")
        print("DVC status:")
        subprocess.call([sys.executable, "-m", "dvc","status"], cwd=current_dir)
        print("===================================================================")

        repo = Repo(current_dir, search_parent_directories=True)

        git_api_repo_base_url = "https://api.github.com/repos/" + '/'.join(repo.remotes.origin.url.split('.git')[0].split('/')[-2:])
        uploads_git_repo_base_url = "https://uploads.github.com/repos/" + '/'.join(repo.remotes.origin.url.split('.git')[0].split('/')[-2:])

        # fetch all tags
        subprocess.call(["git", "fetch", "--tags", "--force"], cwd=current_dir)   
        
        # Update dvc repo files (if any) before checking for untracked files ( we need to regenerate dvc file hashes if there were changes)
        subprocess.run([sys.executable, "-m", "dvc", "commit"], cwd=current_dir) # capture_output=False, text=True, input="y\n")

        active_branch = repo.active_branch

        if repo.head.is_detached:
            print("Detached HEAD, creating branch from tag name") 
            # repo.branches['master'].checkout() 
            # git swtch -c BRANCH

        changed_files = [ item.a_path for item in repo.index.diff(None) ]
        untracked_files = repo.untracked_files
  
        if untracked_files or changed_files:
            print("There are files which are untracked.")
            print("Untracked files:", untracked_files)
            print("Unstaged files:", changed_files)

            if untracked_files:
                if prompt_statement("Do you wish to add them manually or to add all ? Yes = manual, No = add all"):
                    for file_name in untracked_files:
                        if prompt_statement("Add : " + file_name + " to the DVC repo ?"):      
                            if ".dvc" not in file_name and file_name not in repo.ignored(file_name):
                                subprocess.call([sys.executable, "-m", "dvc","add", file_name], cwd=current_dir)
                                repo.git.add(file_name + ".dvc")
                            elif ".dvc" in file_name and file_name not in repo.ignored(file_name):
                                repo.git.add(file_name)
                            else:
                                print("Cannot add file, it is either a file ignored in .gitignore or a DVC handled file.")
                else: 
                    for file_name in untracked_files:
                        if ".dvc" not in file_name and file_name not in repo.ignored(file_name):
                            subprocess.call([sys.executable, "-m", "dvc","add", file_name], cwd=current_dir)
                    repo.git.add(all=True)

            for root, dirs, files in os.walk(current_dir):
                if ".gitignore" in files:
                    repo.git.add(os.path.join(root, ".gitignore"))

            for file_name in changed_files:
                repo.git.add(file_name)
            
        staged_files = len(repo.index.diff("HEAD"))

        print("Staged files:", staged_files)

        if staged_files:
            model_name, parent_model_name, version = generate_model_name(repo, model_name, parent_model_name, version) 

            #TO DO : inject_model_tag_data into individual model files ?
            
            if parent_model_name != "":
                tag_name = str(model_name) + "-" + str(parent_model_name) + "-" + str(version)
            else:
                tag_name = str(model_name) + "-" + str(version)

            release_name = str(model_name) + "-" + str(version)    

            if prompt_statement("Do you want to create the tag: " + tag_name + " and release " + release_name + "?" ):
                repo.index.commit(release_name)
                new_tag = repo.create_tag(path=tag_name, ref=repo.head.commit.hexsha)
                repo.remotes.origin.push(new_tag)

                tag_data = {
                    "tag_name" : tag_name,
                    "name" : release_name,
                    "draft" : False,
                    "prerelease" : False,
                    "target_commitish" : repo.head.commit.hexsha,
                    "body" : generate_model_card_info(model_name, current_dir, parent_model_name, version, tag_name)
                }

                create_tag_request = requests.post(url=git_api_repo_base_url + "/releases", data=json.dumps(tag_data), headers=headers)

                if create_tag_request.status_code == 201:
                    print("Success, created release : " + release_name + ", with tag : " + tag_name + " .")

                    subprocess.call(["git", "bundle", "create", str(tag_name) + ".bundle", "--all"], cwd=current_dir)
                    bundle_file_path = current_dir + "/" + str(tag_name) + ".bundle"
                        
                    #if "nt" in os.name:
                    #    subprocess.call(["tar.exe", "-af", str(tag_name) + ".zip", bundle_file_path ], cwd=current_dir)
                    #else:
                    #    subprocess.call(["zip", "-9 -y -q", str(tag_name) + ".zip", bundle_file_path ], cwd=current_dir)
                    #subprocess.call(["tar", "-zf", str(tag_name) + ".tar.gz", bundle_file_path ], cwd=current_dir)

                    req_release_data = requests.get(url=git_api_repo_base_url + "/releases/tags/" + str(tag_name), headers=headers)

                    if req_release_data.status_code == 200:

                        file_asset_url = uploads_git_repo_base_url +  "/releases/" + str(req_release_data.json()["id"]) + "/assets?name=" + str(tag_name) + ".bundle"
                        delete_asset_url = git_api_repo_base_url + "/releases/assets/"

                        for asset in req_release_data.json()["assets"]:
                            req_delete_release_asset = requests.delete(url=delete_asset_url + str(asset["id"]), headers=headers)
                            if req_delete_release_asset.status_code >= 400:
                                print("Response: ", str(req_delete_release_asset.status_code), " Failed to delete asset: ", str(asset["name"]), "  id: ", str(asset["id"]))
                                print("Reason:", req_delete_release_asset.text)

                        with open(bundle_file_path, "rb") as file:
                            data = file.read()
                            req_upload_release_asset = requests.post(url=file_asset_url, data=data, headers=upload_headers)
                            
                            if req_upload_release_asset.status_code == 201:
                                print("Asset : ", file_asset_url, "uploaded successfully" )
                            else:
                                print("Response: ", str(req_upload_release_asset.status_code), " Failed to upload asset: ", bundle_file_path)
                                print("Reason:", req_upload_release_asset.text)

                elif create_tag_request.status_code == 200:
                        print("Success, created release : " + release_name + ", with tag : " + tag_name + " .")
                else:
                    raise Exception("Failed to create release : " + release_name + ", with tag : " + tag_name + " . \n" + "Reason:" + create_tag_request.text)

                while True:
                    try:
                        subprocess.call([sys.executable, "-m", "dvc", "push"], cwd=current_dir)
                        break
                    except:
                        pass
            else:
                raise Exception("Process cancelled... reverting state...")
        else:
            print("No changes to be submitted. Checking model files with storage server for potential update pushing....")
            subprocess.call([sys.executable, "-m", "dvc", "push"], cwd=current_dir)
        
    except Exception as exception:
        """
            Resets the head commit to default previous one, it should happen in case of any error.
            If the tag has been already pushed then it will be deleted from the git repo.
        """
        print("Process cancelled... reverting state...")
      
        subprocess.call(["git", "reset", "HEAD~"], cwd=current_dir)
        if tag_name != "": 
            print("Deleting tag ", tag_name)
            subprocess.call(["git", "push", "origin", "--delete", tag_name ], cwd=current_dir)
            subprocess.call(["git", "tag", "--delete", tag_name ], cwd=current_dir)

        logging.error("could not push new model version")
        logging.error("description: " + repr(exception))

        #if current_dir != "":
        #    shutil.rmtree(current_dir, ignore_errors=True)
    
    finally:
        # delete the bundle file
        if bundle_file_path != "":
            os.remove(bundle_file_path)

  

def generate_model_card_info(model_name, model_folder_path, parent_model_name="", version="", tag_name=""):
    model_card = ""

    if parent_model_name == "":
        parent_model_name = "N/A"

    parent_model_tag = ""

    model_card_path = os.path.join(model_folder_path, "modelcard.md")

    if os.path.isfile(model_card_path):
        with open(model_card_path) as f:
            model_card = f.read()
        model_card = model_card.replace("<model_name>-<parent_model_name>-<model_version>", tag_name)
        model_card = model_card.replace("<model_name>", model_name)
        model_card = model_card.replace("<parent_model_name>", parent_model_name)
        model_card = model_card.replace("<parent_model_tag>", parent_model_tag)
        model_card = model_card.replace("<model_version>", version)
    else:
        print("Could not find model card file that holds a brief summary of the model data & specs.")

    return model_card


def generate_model_name(repo, model_name, parent_model_name, version):
    try:
        tags = repo.tags

        if tags:
            current_tag = next((tag for tag in tags if tag.commit == repo.head.commit), None)

            found_model_tags = [tag for tag in tags if model_name in str(tag.path)]

            found_model_tags = [
                ModelTagData(str(ftag).split('-', 2)[0], str(ftag).split('-', 2)[1], str(ftag).split('-', 2)[2],
                             str(ftag.commit))
                if len(str(ftag).split('-', 2)) == 3
                else ModelTagData(str(ftag).split('-', 2)[0], "", str(ftag).split('-', 2)[1], str(ftag.commit))
                for ftag in found_model_tags]

            split_current_model_tag_name = str(current_tag).split('-', 2)
            current_model_tag = ModelTagData(model_name=split_current_model_tag_name[0],
                                             parent_mode_name=split_current_model_tag_name[1],
                                             version=split_current_model_tag_name[2],
                                             commit_hash=str(current_tag.commit)) \
                                if len(split_current_model_tag_name) == 3 \
                                else \
                                ModelTagData(model_name=split_current_model_tag_name[0], parent_model_name="",
                                             version=split_current_model_tag_name[1],
                                             commit_hash=str(current_tag.commit)) \
                                    if current_tag is not None else None

            # found_parent_model_tags = [ found_model_tag
            #        for found_model_tag in found_model_tags 
            #        if not found_model_tag.parent_model_name
            #    ]

            if current_model_tag is not None and model_name != current_model_tag.model_name:
                print(" ### WARNING ! ### Current given model_name differs from the repo TAG model name : ", model_name,
                      " vs ", current_model_tag.model_name)

            if found_model_tags:
                if current_model_tag is not None:
                    if current_model_tag.model_name == model_name:
                        # parent_tags_with_curr_model = [tag for tag in found_parent_model_tags
                        #                               if current_model_tag.parent_model_name == tag.parent_model_name and current_model_tag.commit_hash == tag.commit_hash]
                        # print(parent_tags_with_curr_model)
                        if version == "auto":
                            version = '.'.join(
                                map(str, str(int(''.join(map(str, str(current_model_tag.version).split('.')))) + 1)))
                            # need to trace parent_model_version....
                        if current_model_tag.parent_model_name != "":
                            parent_model_name = current_model_tag.parent_model_name
                            version = "1.0"
                    elif current_model_tag.model_name != model_name:
                        # if we find that the model names are different, we assume they have the same parent,
                        # if the previous model has no parent, then it will become the parent of this model
                        if current_model_tag.parent_model_name != "":
                            parent_model_name = current_model_tag.parent_model_name
                        else:
                            parent_model_name = current_model_tag.model_name
                        version = "1.0"

            elif current_model_tag is not None:
                if current_model_tag.model_name != model_name:
                    # if we find that the model names are different, we assume they have the same parent,
                    # if the previous model has no parent, then it will become the parent of this model
                    if not current_model_tag.parent_model_name:
                        parent_model_name = current_model_tag.parent_model_name
                    else:
                        parent_model_name = current_model_tag.model_name

                    version = "1.0"
                elif version == "auto":
                    version = '.'.join(
                        map(str, str(int(''.join(map(str, str(current_model_tag.version).split('.')))) + 1)))
            else:
                version = "1.0"

        elif version == "auto":
            version = "1.0"

    except Exception as exception:
        version = "1.0"
        logging.error("Error when generating model tag/release name: " + repr(exception))

    return model_name, parent_model_name, version


def package(model_name, git_auth_token, parent_model_name="", version="auto"):

    # TODO : implement credential cache
    # git config credential.helper 'cache --timeout=300'

    #subprocess.run(["git", "config", "credential.helper", "'cache --timeout=400'"])

    if git_auth_token.strip() == "":
        raise ValueError("No git token given, please provide your git token.")

    upload_model(model_name, parent_model_name=parent_model_name, version=version, git_auth_token=git_auth_token)


if __name__ == '__main__':
    fire.Fire(package)
