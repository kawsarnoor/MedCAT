from medcat.cli.config import get_auth_environment_vars, get_git_api_request_url, get_git_default_headers, get_git_upload_headers, get_git_user_project
import fire
import requests
import sys
import os
import json
import subprocess
import logging
import shutil
import dvc
from git import Repo
from .download import get_all_available_model_tags
from .system_utils import *
from .modeltagdata import ModelTagData

def verify_model_package(request_url, headers, full_model_tag_name):

    available_model_tags = get_all_available_model_tags(request_url, headers)
    found_matching_tags = [tag_name for tag_name in available_model_tags if full_model_tag_name in tag_name] 

    found_model_folders = []
    root, subdirs, files = next(os.walk(get_local_model_storage_path()))

    for subdir in subdirs:
        if subdir in available_model_tags:
            found_model_folders.append(subdir)

    found_matching_folders = [dir_name for dir_name in found_model_folders if full_model_tag_name in dir_name] 

    if not found_matching_folders and found_matching_tags:
        print("NO model named " + "\033[1m" + full_model_tag_name + "\033[0m" + " found on this machine, please download it...")
        #subprocess.run([sys.executable, "-m", "medcat", "download", str(full_model_tag_name), git_auth_token],
        #                cwd=get_local_model_storage_path())
        return True

    return False

def select_model_package_and_name(model_name, previous_model_tag_data=False, predicted_version="1.0"):
    """
        Allows the user to select the model's name according to previous model history.
        :return: model name and bool if its a new release 
    """
    if previous_model_tag_data is not False:
        print("The model you want to package is based on the following model:" + "\033[1m" + previous_model_tag_data.model_name + "-" + previous_model_tag_data.version + "\033[0m" + ".")
        if model_name == "":
            model_name = previous_model_tag_data.model_name

    is_new_release = False

    if model_name != "":
        print("Please use only alphabet characters (a-Z, A-Z), no numbers and no symbols accepted besides underscore '_' . Invalid characters will be removed.")
        while True:
            if previous_model_tag_data != False and model_name == previous_model_tag_data.model_name:
                if prompt_statement("\n Do you want to update the tag number of an existing model ? (improvement of model)  e.g : " + "\033[1m" + model_name + "-" + previous_model_tag_data.version + "\033[0m" + " -> " 
                + "\033[1m" + model_name + "-" + predicted_version + "\033[0m" ) is False:
                    if prompt_statement("Do you want to create a specialist model tag? e.g : " + "\033[1m" + model_name + "-" + previous_model_tag_data.version + "\033[0m" + " -> " + "\033[1m" + "<new_model_name>-1.0" + "\033[0m" ):
                        model_name = input("Give the model tag a name, the version will be 1.0 by default:")
                        is_new_release = True
                        break
                else:
                    break

            elif previous_model_tag_data != False and model_name != previous_model_tag_data.model_name:
                if prompt_statement("Do you want to create a specialist model tag? e.g : " + "\033[1m" + previous_model_tag_data.model_name + "-" + previous_model_tag_data.version + "\033[0m" + " -> "+ "\033[1m" + model_name + "-1.0" + "\033[0m" ):
                    print("Using "  + "\033[1m" + model_name  + "\033[0m" + " as the new model name.")
                else:
                    model_name = input("Give the model tag a name, the version will be 1.0 by default:")
                is_new_release = True
                break
            else:
                is_new_release = True
                if prompt_statement("This is a new model release (version will be set to 1.0 by default), are you satisified with the name ? given name : " + "\033[1m" + model_name + "\033[0m" + " . The tag will be :" + "\033[1m" + model_name + "-1.0" +  "\033[0m"  ):
                    print("Using "  + "\033[1m" + model_name  + "\033[0m" + " as the new model name.")
                else:
                    model_name = input("Give the model tag a name, the version will be 1.0 by default:")
                    break

        if not is_input_valid(model_name):
            print("Invalid characters detected in the model name, the new model name will be:" + sanitize_input(model_name))
            if not prompt_statement("Proceed ? (answering NO will return you to the model name selection process)"):
                select_model_package_and_name(sanitize_input(model_name))

        if model_name != "":
            return model_name, is_new_release
        
    logging.error("No model name has been provided, and the models detected in the current folder have no model tag data history...")
    logging.error("Please re-run the command and provide a name for the model as a parameter: python3 -m medcat package [model_name]")
    logging.error("Exiting...")
    sys.exit()

def inject_tag_data_to_model_files(model_folder_path, model_name, parent_model_name, version, commit_hash, git_repo_url, parent_model_tag):
    for file_name in get_permitted_push_file_list(): 
        if ".dat" in file_name and os.path.isfile(os.path.join(model_folder_path, file_name)):
            loaded_model_file = load_model_from_file(model_folder_path, file_name)
            if hasattr(loaded_model_file, "vc_model_tag_data"):
                loaded_model_file.vc_model_tag_data = ModelTagData(model_name, parent_model_name, version,
                                                                   commit_hash, git_repo_url, parent_model_tag)
                logging.info("Updating model object : " + model_name +"-"+ version + " " + file_name + " with tag data...")
                loaded_model_file.save_model(output_save_path=model_folder_path)
                logging.info("Complete..")

def detect_model_name_from_files(model_folder_path="."):
    for file_name in get_permitted_push_file_list(): 
        if ".dat" in file_name and os.path.isfile(os.path.join(model_folder_path, file_name)):
            loaded_model_file = load_model_from_file(model_folder=model_folder_path, file_name=file_name, bypass_model_path=True)
            if hasattr(loaded_model_file, "vc_model_tag_data"):
                return loaded_model_file.vc_model_tag_data
    return False

def upload_model(model_name, parent_model_name, version):
 
    upload_headers = get_git_upload_headers()
    headers = get_git_default_headers()
    
    git_repo_url = get_auth_environment_vars()["git_repo_url"]
    git_api_repo_base_url = "https://api.github.com/repos/" + get_git_user_project()
    uploads_git_repo_base_url = "https://uploads.github.com/repos/" + get_git_user_project()
      
    # folder where we are now (where we called the package command)
    current_folder = os.getcwd()

    # get information about the model files we currently want to package
    previous_tag_model_data = detect_model_name_from_files()

    # this is the predicted version number, will change to 1.0 if its a new release
    version = generate_model_version(model_name, version, previous_tag_model_data) 

    # determine the final model name
    model_name, is_new_release = select_model_package_and_name(model_name, previous_tag_model_data, predicted_version=version)

    # version reset if it's a new release
    if is_new_release:
        version = "1.0"

    # need to add user/ institution name 
    tag_name = model_name + "-" + version

    # create folder for new model release
    # folder where the original model files are: /lib/python/site-packages/medcat-{version}/models/...
    new_model_package_folder = os.path.join(get_local_model_storage_path(), tag_name)
    
    if get_downloaded_local_model_folder(tag_name):
        #if prompt_statement(tag_name + " folder is already present on computer, do you wish to delete it ?"):
        shutil.rmtree(new_model_package_folder, ignore_errors=True)

    create_model_folder(tag_name)

    # check to see if there is a tag with the same name, (this is only useful in case the dvc push fails, )
    #result = get_matching_version(tag_name, request_url, headers)

    #if result["request_success"]:
    #    create_new_base_repository(new_model_package_folder, git_repo_url, checkout_full_tag_name=tag_name)

    #if get_downloaded_local_model_folder(tag_name):
    #    if prompt_statement(tag_name + " folder is already present on computer, do you wish to delete it ?"):
    #        shutil.rmtree(new_model_package_folder, ignore_errors=True)

    if previous_tag_model_data != False:
        tmp_old_full_model_tag_name = previous_tag_model_data.model_name + "-" + str(previous_tag_model_data.version)
        print("Creating new folder for the release... checking out from tag: " + tmp_old_full_model_tag_name )
        create_new_base_repository(new_model_package_folder, git_repo_url, checkout_full_tag_name=tmp_old_full_model_tag_name)
    else:
        create_new_base_repository(new_model_package_folder, git_repo_url)
    
    bundle_file_path = ""
    active_remote = ""
    
    try:
        print("Current directory:", current_folder)
        print("Current GIT working dir: ", new_model_package_folder)
        print("===================================================================")
        print("Git status:")
        subprocess.run(["git", "status"], cwd=new_model_package_folder)
        print("===================================================================")
        print("DVC status:")
        subprocess.run([sys.executable, "-m", "dvc","status"], cwd=new_model_package_folder)
        print("===================================================================")
        
        repo = Repo(new_model_package_folder, search_parent_directories=False)
        
        # fetch all tags
        subprocess.run(["git", "fetch", "--tags", "--force"], cwd=new_model_package_folder)
        
        active_branch = repo.active_branch
        
        copy_model_files_to_folder(current_folder, new_model_package_folder)
        
        ## TODO
        ### check if this is now a parent:
        parent_model_tag = ""
        if previous_tag_model_data != False:
            if model_name != previous_tag_model_data.model_name:
                parent_model_name = previous_tag_model_data.model_name
                parent_model_tag = previous_tag_model_data.model_name + "-" + previous_tag_model_data.version
            else:
                parent_model_name = previous_tag_model_data.parent_model_name
            
        if parent_model_name != "":
            release_name = str(model_name) + "-" + str(parent_model_name) + "-" + str(version)
        else:
            release_name = str(model_name) + "-" + str(version)

        # attempt to generate new model_name and inject it into the model file data
        # IMPORTANT: the commit points to the parent model or the last commit of the repository (non-tag) commit
        
        # Update dvc repo files (if any) before checking for untracked files ( we need to regenerate dvc file hashes if there were changes)
        # We need to check the files before injecting new tag/release data into them, otherwise they will always be flagged as changed..
        subprocess.run([sys.executable, "-m", "dvc", "commit"], cwd=new_model_package_folder, text=True)

        changed_files = [ item.a_path for item in repo.index.diff(None) ]

        # if there have been changes on the file hashes since the previous commit, then, we can inject the new release data into the model files
        if changed_files:
            # TODO get storage location of files
            inject_tag_data_to_model_files(new_model_package_folder, model_name, parent_model_name, version, str(repo.head.commit), git_repo_url, parent_model_tag)
            subprocess.run([sys.executable, "-m", "dvc", "commit", "--force"], cwd=new_model_package_folder, text=True)
            #process = subprocess.Popen([sys.executable, "-m", "dvc", "commit"], cwd=new_model_package_folder,  bufsize=0, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            #for line in iter(process.stdout.readline, ""):
            #    process.stdin.write("y\n")
            #subprocess.run([sys.executable, "-m", "dvc", "commit"], cwd=new_model_package_folder, input=b"y")
        
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
                                subprocess.run([sys.executable, "-m", "dvc","add", file_name], cwd=new_model_package_folder)
                                repo.git.add(file_name + ".dvc")
                            elif ".dvc" in file_name and file_name not in repo.ignored(file_name):
                                repo.git.add(file_name)
                            else:
                                print("Cannot add file, it is either a file ignored in .gitignore or a DVC handled file.")
                else: 
                    for file_name in untracked_files:
                        if ".dvc" not in file_name and file_name not in repo.ignored(file_name):
                            subprocess.run([sys.executable, "-m", "dvc","add", file_name], cwd=new_model_package_folder)
                    repo.git.add(all=True)

            for root, dirs, files in os.walk(new_model_package_folder):
                if ".gitignore" in files:
                    repo.git.add(os.path.join(root, ".gitignore"))

            for file_name in changed_files:
                repo.git.add(file_name)
            
        staged_files = len(repo.index.diff("HEAD"))

        print("Staged files:", staged_files)

        if staged_files:

            if prompt_statement("Do you want to create the tag: " + tag_name + " and release " + release_name + "?" ):
                
                repo.index.commit(tag_name)
                new_tag = repo.create_tag(path=tag_name, ref=repo.head.commit.hexsha)

                repo.remotes.origin.push(new_tag)

                model_card_info_string, model_card_info_json = generate_model_card_info(git_repo_url, 
                                                                                        model_name, 
                                                                                        parent_model_name, 
                                                                                        new_model_package_folder, 
                                                                                        version, 
                                                                                        tag_name, 
                                                                                        parent_model_tag)

                tag_data = {
                    "tag_name" :  tag_name, # user_repo_and_project.split('/')[1] + "-" + tag_name
                    "name" : release_name,
                    "draft" : False,
                    "prerelease" : False,
                    "target_commitish" : repo.head.commit.hexsha,
                    "body" : model_card_info_string
                }

                create_tag_request = requests.post(url=git_api_repo_base_url + "/releases", data=json.dumps(tag_data), headers=headers)

                if create_tag_request.status_code == 201:
                    print("Success, created release : " + release_name + ", with tag : " + tag_name + " .")

                    subprocess.run(["git", "bundle", "create", str(tag_name) + ".bundle", "--all"], cwd=new_model_package_folder)
                    bundle_file_path = new_model_package_folder + "/" + str(tag_name) + ".bundle"

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
                
                subprocess.call([sys.executable, "-m", "dvc", "push"], cwd=new_model_package_folder)
                  
            else:
                raise Exception("Could not push new model version")
        else:
            print("No changes to be submitted. Checking model files with storage server for potential update pushing....")
            subprocess.run([sys.executable, "-m", "dvc", "push"], cwd=new_model_package_folder)
        
    except Exception as exception:
        """
            Resets the head commit to default previous one, it should happen in case of any error.
            If the tag has been already pushed then it will be deleted from the git repo.
        """
        logging.error("description: " + repr(exception))
        logging.warning("Push process cancelled... reverting state...")
       
        #subprocess.run(["git", "reset", "HEAD~"], cwd=new_model_package_folder)
        if tag_name != "": 
            logging.warning("Deleting tag " + tag_name + " because the push operation has failed and changes were reverted.")
            #subprocess.run(["git", "push", "origin", "--delete", tag_name ], cwd=new_model_package_folder)
            subprocess.run(["git", "tag", "--delete", tag_name ], cwd=new_model_package_folder)
       
    finally:
        if bundle_file_path != "":
            os.remove(bundle_file_path)
    
def generate_model_card_info(git_repo_url, model_name, parent_model_name, model_folder_path, version="", tag_name="", parent_model_tag_name=""):
    """
       input:
       -----
           - model card information

       output:
       ------
          - model_card string (to be used to display github releases page
          - model_card_json object (json format for model card to be uploaded as asset to associated model release
    """

    model_card_json = {}
    model_card = ""

    model_card_json['model_name'] = model_name
    model_card_json['tag_name'] = tag_name
    model_card_json['version'] = version


    if parent_model_name == "":
        model_card_json['parent_model_name'] = "N/A"
        model_card_json['parent_model_tag_url'] = ""

    else:
        model_card_json['parent_model_tag_url'] = git_repo_url[:-4] + "/releases/tag/" + parent_model_tag_name if str(git_repo_url).endswith(".git") else ""
        model_card_json['parent_model_tag_url'] = "<a href="+ parent_model_tag_url + ">" + parent_model_tag_name + "</a>"
 


    model_card_path = os.path.join(model_folder_path, "modelcard.md")

    if os.path.isfile(model_card_path):
        with open(model_card_path) as f:
            model_card = f.read()
        model_card = model_card.replace("<model_name>-<parent_model_name>-<model_version>", model_card_json['tag_name'])
        model_card = model_card.replace("<model_name>", model_card_json['model_name'])
        model_card = model_card.replace("<parent_model_name>", model_card_json['parent_model_name'])
        model_card = model_card.replace("<parent_model_tag>", model_card_json['parent_model_tag_url'])
        model_card = model_card.replace("<model_version>", model_card_json['version'])
    else:
        logging.error("Could not find model card file that holds a brief summary of the model data & specs.")

    return model_card, model_card_json



def generate_model_version(model_name, version, previous_model_tag_data=False):
    try:
        tags = get_all_available_model_tags()

        if tags:
            similar_tag_names = [tag for tag in tags if model_name in str(tag)]

            similar_tags = []

            #for tag_name in similar_tag_names:
            #    tag_split = tag_name.split('-', 2)
            #    
            #    if len(tag_split > 2):
            #        similar_tags.append(ModelTagData(model_name=tag_split[1], version=tag_split[-1]))
            #    else:
            #        similar_tags.append(ModelTagData(model_name=tag_split[0], version=tag_split[-1]))
            #    if similar_tags[-1].model_name != model_name:
            #        del similar_tags[-1]
           
        # if the model has a history, and the provided model name is empty then we assume its an update/improvement of the same model
        if version=="auto" and previous_model_tag_data != False and (model_name == previous_model_tag_data.model_name or model_name == ""):
            version = '.'.join(map(str, str(int(''.join(map(str, str(previous_model_tag_data.version).split('.')))) + 1)))

        # if its still auto then it means it is a new release
        if version == "auto":
            version = "1.0"

    except Exception as exception:
        version = "1.0"
        logging.error("Error when generating model tag/release name: " + repr(exception))

    return version

def package(full_model_tag_name="", version="auto"):
    #subprocess.run(["git", "config", "--global", "credential.helper", "cache"])
    upload_model(full_model_tag_name, parent_model_name="", version=version)

if __name__ == '__main__':
    fire.Fire(package)
