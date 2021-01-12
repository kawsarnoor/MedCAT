import fire
import requests
import sys
import os
import json
import subprocess
from subprocess import Popen,PIPE
from git import Repo

def upload_model(model_name, parent_model_name, version):
    
    headers = {"Accept" : "application/vnd.github.v3+json", "Authorization": "token <token>"}

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
        repo_config = repo.config_reader()
        git_repo_base_url = "https://api.github.com/repos/" + '/'.join(repo.remotes.origin.url.split('.git')[0].split('/')[-2:])

        # Update dvc repo files (if any) before checking for untracked files ( we need to regenerate dvc file hashes if there were changes)
        subprocess.run([python_executable, "-m", "dvc", "commit"], cwd=current_dir) # capture_output=False, text=True, input="y\n")
        subprocess.call(["git", "fetch", "--tags"], cwd=current_dir)   

        if repo.head.is_detached:
            print("Detached HEAD, creating branch from tag name") 
            #current_tag_name = next((tag for tag in repo.tags if tag.commit == repo.head.commit), None)
            #repo.branches['master'].checkout() 
        else:
            print("Active branch:", repo.active_branch)
       
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

        if staged_files:
            model_name, parent_model_name, version = generate_model_name(repo, model_name, parent_model_name, version)  
            
            if parent_model_name != "":
                tag_name = str(model_name) + "-" + str(parent_model_name) + "-" + str(version)
            else:
                tag_name = str(model_name) + "-" + str(version)

            release_name = str(model_name) + "-" + str(version)    

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
            elif create_tag_request.status_code == 400:
                print(create_tag_request.json())

        subprocess.call([python_executable, "-m", "dvc", "push"], cwd=current_dir)
        
    except Exception as exception:
        print("ERROR, could not push new model version")
        print("ERROR description: ", exception, file=sys.stderr)
    

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

def generate_model_name(repo, model_name, parent_model_name="", version="auto"):
    tags = repo.tags

    if tags:
        current_tag = repo.git.describe("--tags")
        print("Git current tag description:", current_tag)

        found_tags = [str(tag) for tag in tags if model_name in str(tag.path)]
        found_tags = [dict(zip(["model_name", "parent_model_name", "version"], ftag.split('-', 2))) if len(ftag.split('-', 2)) == 3
                      else dict(zip(["model_name", "version"], ftag.split('-',2))) for ftag in found_tags]

        if found_tags:
            for ftag in found_tags:
                ftag["version"] = str(ftag["version"]).split('.')
                ftag["version"] = int(''.join(map(str, ftag["version"])))

            latest_version_tag = max(found_tags, key=lambda tag: tag["version"])

            if version == "auto":
                version = '.'.join(map(str, str(int(latest_version_tag["version"] + 1)))) 
            else:
                int_version = int(''.join(map(str, str(version).split('.'))))
                if int_version <= latest_version_tag["version"]:
                    raise ValueError("Version number specified: " + str(version) + " lower than latest version number " + '.'.join(map(str, str(latest_version_tag["version"]))))
    
    elif version == "auto":
        version = "1.0"

    return model_name, parent_model_name, version

def package(model_name,  parent_model_name="", version="auto"):
    upload_model(model_name, parent_model_name,  version)

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
