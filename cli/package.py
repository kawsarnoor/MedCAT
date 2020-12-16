import fire
import requests
import dvc.api
import sys
import os
import subprocess
import markdown
import logging
from git import Repo

headers = {'Authorization': 'token <insert_token_for_private_repo>'} # for private repo's we want to specify the access token to the github repo
git_repo_base_url = "https://api.github.com/repos/vladd-bit/tagtest"


# TO DO:
#  - include SHA-1 has to base model tag."
#  - link up dvc files with release versions

def upload_model(model_name, version, parent_model_name):
    try:
        os.chdir(os.getcwd())

        current_dir = os.getcwd()
        print("Current dir: ", current_dir)
        print("Git status:")
        subprocess.call(["git", "status"], cwd=current_dir)
        print("DVC status:")
        subprocess.call(["python3", "-m", "dvc","status"], cwd=current_dir)

        repo = Repo(current_dir)
        repo.config_reader()             
   
        # assert repo.is_dirty()

        model_card = ""
        with open("modelcard.md") as f:
            model_card = f.read()
        
        print("Untracked files:", repo.untracked_files)
        
        print("Active branch:", repo.active_branch)
        
        print(repo.git.describe())

        # TO DO, include SHA-1 has to base model tag."
    
        new_tag = repo.create_tag(str(model_name) + "-" + str(version), ref=repo.active_branch, message=" Model parent reference: " + parent_model_name + ' \n ')

        repo.remotes.origin.push(new_tag)
        subprocess.call(["python3", "-m", "dvc","commit"], cwd=current_dir)
        subprocess.call(["python3", "-m", "dvc","push"], cwd=current_dir)

    except Exception as exception:
        print("ERROR, could not push new model version")
        print("ERROR description : ", exception, file=sys.stderr)

    except AssertionError as error:
        logging.exception(error)

def package(model_name, version, parent_model_name):
    upload_model(model_name, version, parent_model_name)

if __name__ == '__main__':
  fire.Fire(package)
