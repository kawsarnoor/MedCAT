import fire
import sys
import os
import subprocess
import markdown
import logging
from git import Repo

headers = {'Authorization': 'token <insert_token_for_private_repo>'} # for private repo's we want to specify the access token to the github repo
git_repo_base_url = "https://api.github.com/repos/kawsarnoor/MedCatModels/"

# TO DO:
#  - include SHA-1 has to base model tag."
#  - link up dvc files with release versions

def upload_model(model_name, parent_model_name="", version="auto"):
    try:
        python_executable = sys.executable
        os.chdir(os.getcwd())
        current_dir = os.getcwd()

        print("Current dir: ", current_dir)
        print("Git status:")
        subprocess.call(["git", "status"], cwd=current_dir)
        print("============================================================")
        print("DVC status:")
        subprocess.call([python_executable, "-m", "dvc","status"], cwd=current_dir)
        print("============================================================")

        repo = Repo(current_dir, search_parent_directories=True)
        repo.config_reader()             
   
        # assert repo.is_dirty()

        model_card = ""
        with open("modelcard.md") as f:
            model_card = f.read()
        
        print("Active branch:", repo.active_branch)

        if repo.untracked_files:
            print("There are files which are untracked.")
            print("Untracked files:", repo.untracked_files)

            if prompt_statement("Do you wish to add them manually or to add all ? Yes = manual, No = add all"):
                for file_name in repo.untracked_files:
                    if prompt_statement("Add : " + file_name + " to the DVC repo ?"):      
                        subprocess.call([python_executable, "-m", "dvc","add", file_name], cwd=current_dir)
                        repo.git.add(file_name + ".dvc")
            else: 
                for file_name in repo.untracked_files:
                    subprocess.call([python_executable, "-m", "dvc","add", file_name], cwd=current_dir)
                repo.git.add(all=True)
            
            for root, dirs, files in os.walk(current_dir):
                if ".gitignore" in files:
                    repo.git.add(os.path.join(root, ".gitignore"))
            

        repo.index.commit((str(model_name) + "_" + str(version)))

        model_name, parent_model_name, version = generate_model_name(repo, model_name, parent_model_name, version)  

        print("Model name :  " + model_name, "         version : " + str(version), "       parent : " + parent_model_name)      
        
        new_tag = repo.create_tag(str(model_name) + "_" + str(version), ref=repo.head.object.hexsha, message=" Model parent reference: " + parent_model_name + ' \n ')
        repo.remotes.origin.push(new_tag)
            
        subprocess.call([python_executable, "-m", "dvc", "commit"], cwd=current_dir)
        subprocess.call([python_executable, "-m", "dvc", "push"], cwd=current_dir)

    except Exception as exception:
        print("ERROR, could not push new model version")
        print("ERROR description: ", exception, file=sys.stderr)

    except AssertionError as error:
        logging.exception(error)

def generate_model_name(repo, model_name, parent_model_name="", version="auto"):
    tags = repo.tags

    if tags:
        current_tag = repo.git.describe()
        print("Git current tag description:", current_tag)

    if parent_model_name == "":
            parent_model_name = "N/A"

    return model_name, parent_model_name, version


def package(model_name, version, parent_model_name):
    upload_model(model_name, parent_model_name,  version)

def prompt_statement(prompt_text, answer="yes"):
    valid_answers = {"yes" : True, "no" : False, "y" : True, "n" : False}
    exit_answer =["exit", "cancel"]

    while True:
        print(prompt_text + " Yes/No (Y/N)")
        choice = input().lower()
         
        if choice in valid_answers.keys():
            return valid_answers[choice]
        else:
            if choice in exit_answer:
                sys.exit()
            print("Invalid answer")

if __name__ == '__main__':
  fire.Fire(package)
