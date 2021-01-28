import fire
import requests
import sys
import os
import json
import subprocess
from subprocess import Popen,PIPE
from git import Repo
from functools import reduce
from requests.api import head
from dataclasses import dataclass
import site
from .download import download_asset, get_matching_version
import shutil

@dataclass
class ModelTagData:
    model_name: str 
    parent_model_name: str
    version: str
    commit_hash: str

def check_installed_models(request_url, headers, model_name, git_auth_token):

    list_tags_req = requests.get(url=request_url + "tags", headers=headers)
    found_model_folders = []

    if model_name != "":
        model_tag_names = []

        if list_tags_req.status_code == 200:
            for tag in list_tags_req.json():
                model_tag_names.append(tag["name"])
        
        root, subdirs, files =  next(os.walk(site.USER_SITE))

        for subdir in subdirs:
            if os.path.isdir(site.USER_SITE + "/" + subdir):
                if subdir in model_tag_names:
                    found_model_folders.append(subdir)

        if found_model_folders:
            print("Found the following model folders:", found_model_folders)
            folder_choice = input("Please input what folder to use for packaging ? \n")
        #else:
        #    if prompt_statement("No existing model folders found, would you like to download the model?"):
        #        version_choice = input("Please input the model version name: \n")
                
            return site.USER_SITE + "/" + folder_choice
    elif os.path.isdir(site.USER_SITE + "/" + model_name):
        return site.USER_SITE + "/" + model_name

    return site.USER_SITE + "/" + model_name

def copy_model_files_to_folder(source_folder, dest_folder):
    files_permitted = ["cdb.dat", "vocab.dat"]
    
    root, subdirs, files =  next(os.walk(source_folder))

    for file_name in files:
        if file_name in files_permitted:
            print("Copying file : " + file_name, "to ", dest_folder )
            shutil.copy2(source_folder + "/" + file_name, dest_folder)

def upload_model(model_name, parent_model_name, version, git_auth_token):
    
    headers = {"Accept" : "application/vnd.github.v3+json", "Authorization": "token " + git_auth_token}
    upload_headers = {**headers , "Content-Type" : "application/octet-stream"}

    model_repo_url =  "vladd-bit/tagtest/" #'kawsarnoor/MedCatModels/'
    request_url = 'https://api.github.com/repos/' + model_repo_url 

    # folder where we are now
    original_folder = os.getcwd()

    print(original_folder)

    # SITE-PACKAGES MODEL FOLDER LOCATION
    os.chdir(check_installed_models(request_url, headers, model_name, git_auth_token))
    current_dir = os.getcwd()

    # copy files to model folder repo (inside site-packages)
    copy_model_files_to_folder(original_folder, current_dir)

    tag_name = ""
    bundle_file_path = ""
    active_remote = "origin"

    print(current_dir)
    
    try:
        python_executable = sys.executable
      
        print("Current dir: ", current_dir)
        print("Git status:")
        subprocess.call(["git", "status"], cwd=current_dir)
        print("===================================================================")
        print("DVC status:")
        subprocess.call([python_executable, "-m", "dvc","status"], cwd=current_dir)
        print("===================================================================")

        repo = Repo(current_dir, search_parent_directories=True)
        
        #repo_config = repo.config_reader()

        git_repo_base_url = "https://api.github.com/repos/" + '/'.join(repo.remotes.origin.url.split('.git')[0].split('/')[-2:])
 
        # fetch all tags
        subprocess.call(["git", "fetch", "--tags", "--force"], cwd=current_dir)   
        
        # Update dvc repo files (if any) before checking for untracked files ( we need to regenerate dvc file hashes if there were changes)
        subprocess.run([python_executable, "-m", "dvc", "commit"], cwd=current_dir) # capture_output=False, text=True, input="y\n")

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
                                subprocess.call([python_executable, "-m", "dvc","add", file_name], cwd=current_dir)
                                repo.git.add(file_name + ".dvc")
                            elif ".dvc" in file_name and file_name not in repo.ignored(file_name):
                                repo.git.add(file_name)
                            else:
                                print("Cannot add file, it is either a file ignored in .gitignore or a DVC handled file.")
                else: 
                    for file_name in untracked_files:
                        if ".dvc" not in file_name and file_name not in repo.ignored(file_name):
                            subprocess.call([python_executable, "-m", "dvc","add", file_name], cwd=current_dir)
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
                    "body" : generate_model_card_info(model_name, parent_model_name, version, tag_name)
                }

                create_tag_request = requests.post(url=git_repo_base_url + "/releases", data=json.dumps(tag_data), headers=headers)
                
                if create_tag_request.status_code == 201:
                    print("Success, created release : " + release_name + ", with tag : " + tag_name + " .")

                    subprocess.call(["git", "bundle", "create", str(tag_name) + ".bundle", "--all"], cwd=current_dir)
                    bundle_file_path = "./" + str(tag_name) + ".bundle"
                        
                    #if "nt" in os.name:
                    #    subprocess.call(["tar.exe", "-af", str(tag_name) + ".zip", bundle_file_path ], cwd=current_dir)
                    #else:
                    #    subprocess.call(["zip", "-9 -y -q", str(tag_name) + ".zip", bundle_file_path ], cwd=current_dir)
                    #subprocess.call(["tar", "-zf", str(tag_name) + ".tar.gz", bundle_file_path ], cwd=current_dir)

                    req_release_data = requests.get(url=git_repo_base_url + "/releases/tags/" + str(tag_name), headers=headers)

                    if req_release_data.status_code == 200:

                        uploads_git_repo_base_url = "https://uploads.github.com/repos/" + '/'.join(repo.remotes.origin.url.split('.git')[0].split('/')[-2:])
                    
                        file_asset_url = uploads_git_repo_base_url +  "/releases/" + str(req_release_data.json()["id"]) + "/assets?name=" + str(tag_name)
                        delete_asset_url = git_repo_base_url + "/releases/assets/"

                        for asset in req_release_data.json()["assets"]:
                            req_delete_release_asset = requests.delete(url=delete_asset_url + str(asset["id"]), headers=headers)
                            if req_delete_release_asset.status_code >= 400:
                                print("Response: ", req_delete_release_asset.status_code, " Failed to delete asset: ", str(asset["name"]), "  id: ", str(asset["id"]))
                                print("Reason:", req_delete_release_asset.text)

                        with open( "./" + str(tag_name) +".bundle", "rb") as file:
                            data = file.read()
                            req_upload_release_asset = requests.post(url=file_asset_url+ ".bundle", data=data, headers=upload_headers)
                            
                            if req_upload_release_asset.status_code == 201:
                                print("Asset : ", file_asset_url, "uploaded successfully" )
                            else:
                                print("Response: ", req_upload_release_asset.status_code, " Failed to upload asset: ", bundle_file_path)
                                print("Reason:", req_upload_release_asset.text)

                elif create_tag_request.status_code == 200:
                        print("Success, created release : " + release_name + ", with tag : " + tag_name + " .")
                else:
                    raise Exception("Failed to create release : " + release_name + ", with tag : " + tag_name + " . \n" + "Reason:" + create_tag_request.text)

                while True:
                    try:
                        subprocess.call([python_executable, "-m", "dvc", "push"], cwd=current_dir)
                        break
                    except:
                        pass
            else:
                raise Exception("Process cancelled... reverting state...")
        else:
            print("No changes to be submitted. Checking model files with storage server for potential update pushing....")
            subprocess.call([python_executable, "-m", "dvc", "push"], cwd=current_dir)
        
    except Exception as exception:
        print("Process cancelled... reverting state...")
      
        subprocess.call(["git", "reset", "HEAD~"], cwd=current_dir)
        if tag_name != "": 
            print("Deleting tag ", tag_name)
            subprocess.call(["git", "push", "origin", "--delete", tag_name ], cwd=current_dir)
            subprocess.call(["git", "tag", "--delete", tag_name ], cwd=current_dir)
            
        #subprocess.call(["git", "reset", "--hard"], cwd=current_dir)

        print("ERROR, could not push new model version")
        print("ERROR description: ", exception, file=sys.stderr)
    
    finally:
        if bundle_file_path != "":
            os.remove(bundle_file_path)
    

def generate_model_card_info(model_name, parent_model_name="", version="", tag_name=""):

    model_card = ""
    
    if parent_model_name == "":
        parent_model_name = "N/A"

    parent_model_tag = ""
    
    if os.path.isfile("modelcard.md"): 
        with open("modelcard.md") as f:
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

            found_model_tags = [ModelTagData(str(ftag).split('-', 2)[0], str(ftag).split('-', 2)[1], str(ftag).split('-', 2)[2], str(ftag.commit) )
                                if len(str(ftag).split('-', 2)) == 3 
                                else ModelTagData(str(ftag).split('-', 2)[0], "", str(ftag).split('-', 2)[1], str(ftag.commit))
                                for ftag in found_model_tags]

            current_model_tag =  ModelTagData(str(current_tag).split('-', 2)[0], str(current_tag).split('-', 2)[1], 
                                              str(current_tag).split('-', 2)[2],
                                              str(current_tag.commit))  \
                                              if len(str(current_tag).split('-', 2)) == 3  \
                                              else \
                                              ModelTagData(str(current_tag).split('-', 2)[0], "", str(current_tag).split('-', 2)[1], str(current_tag.commit)) \
                                              if current_tag is not None else None

            #found_parent_model_tags = [ found_model_tag 
            #        for found_model_tag in found_model_tags 
            #        if not found_model_tag.parent_model_name
            #    ]
                   
            if current_model_tag is not None and model_name != current_model_tag.model_name:
                print(" ### WARNING ! ### Current given model_name differs from the repo TAG model name : ", model_name, " vs " , current_model_tag.model_name )

            if found_model_tags:
                if current_model_tag is not None :
                    if current_model_tag.model_name == model_name:
                        #parent_tags_with_curr_model = [tag for tag in found_parent_model_tags 
                        #                               if current_model_tag.parent_model_name == tag.parent_model_name and current_model_tag.commit_hash == tag.commit_hash]
                        #print(parent_tags_with_curr_model)
                        if version == "auto":
                            version = '.'.join(map(str, str(int(''.join(map(str, str(current_model_tag.version).split('.'))))  + 1)))  
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

            elif current_model_tag is not None :
                if current_model_tag.model_name != model_name:
                    # if we find that the model names are different, we assume they have the same parent,
                    # if the previous model has no parent, then it will become the parent of this model
                    if not current_model_tag.parent_model_name:
                        parent_model_name = current_model_tag.parent_model_name
                    else:
                        parent_model_name = current_model_tag.model_name

                    version = "1.0"
                elif version == "auto":
                    version = '.'.join(map(str, str(int(''.join(map(str, str(current_model_tag.version).split('.'))))  + 1)))  
            else:
                version = "1.0"
        
        elif version == "auto":
            version = "1.0"

    except Exception as exception:
        version = "1.0"
        print("ERROR ", exception, file=sys.stderr)   

    return model_name, parent_model_name, version

def package(model_name, parent_model_name="", version="auto", git_auth_token=""):
    
    git_auth_token = "731c26c74cc5fab2f16d843c97c8154df80caa59"

    if git_auth_token.strip() == "":
        raise ValueError("No git token given, please provide your git token.")

    upload_model(model_name, parent_model_name, version, git_auth_token)

def prompt_statement(prompt_text, answer="yes"):
    valid_answers = {"yes" : True, "no" : False, "y" : True, "n" : False}
    exit_answer = ["exit", "cancel"]

    while True:
        print(prompt_text + " Yes/No (Y/N), type exit or cancel to abort")
        choice = input().lower()
         
        if choice in valid_answers.keys():
            return valid_answers[choice]
        else:
            if choice in exit_answer:
                sys.exit()
            print("Invalid answer")

if __name__ == '__main__':
  fire.Fire(package)