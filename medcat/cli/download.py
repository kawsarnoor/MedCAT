import fire
import requests
import site
import os
import sys
import subprocess

## Use python decorator to do the response checking

def get_matching_version(version, request_url, headers):

    request_url = request_url + 'releases/tags/' + version
    response = requests.get(request_url, headers=headers)

    result = {'request_success': False, 'credentials_correct': True ,'response_message': '', 'tag_asset_id': ''}
   
    if response.status_code == 200:
        result['request_success'] = True
        for asset in response.json()['assets']:
            if asset['name'] == str(version + ".bundle"):   
                result['tag_asset_id'] = str(asset['id'])
    if response.status_code == 404:
        result['response_message'] = response.json()['message']
    if response.status_code == 401:
        result['response_message'] = response.json()['message']
        result['credentials_correct'] = False

    return result

# need to take care of USER_SITE and /usr/lib path (non-permissible to user) site.getsitepackages()[0]
def download_asset(version, request_url, asset_id, headers):
    download_headers = headers
    download_headers["Accept"] = "application/octet-stream"

    downloaded_tag_bundle_file = requests.get(request_url, headers=download_headers)
    if downloaded_tag_bundle_file.status_code == 200:
        asset_folder_location = site.USER_SITE + "/" + version
        with open(asset_folder_location + ".bundle", 'wb') as f:
            f.write(downloaded_tag_bundle_file.content)
            print("Downloaded model to : ", asset_folder_location + ".bundle")
        return True
    else:
        print("Could not download asset file : ", downloaded_tag_bundle_file.status_code, " ", downloaded_tag_bundle_file.text)

    return False

def unpack_asset(version):
    try:
        asset_folder_location = site.USER_SITE + "/" + version
        subprocess.run(["git","clone", asset_folder_location + ".bundle"], cwd=site.USER_SITE)  
        while True:
            try:
                subprocess.run([sys.executable, "-m", "dvc", "pull"], cwd=asset_folder_location)
                break
            except:
                pass
    except Exception as exception:
        print("Error unpacking model file asset : ", exception, file=sys.stderr)

def download(version, git_auth_token=""):

    git_auth_token = "731c26c74cc5fab2f16d843c97c8154df80caa59"
    # Headers
    headers = {"Accept" : "application/vnd.github.v3+json", "Authorization": "token " + git_auth_token} # for private repo's we want to specify the access token to the github repo2
    model_repo_url =  "vladd-bit/tagtest/" #'kawsarnoor/MedCatModels/'
    request_url = 'https://api.github.com/repos/' + model_repo_url 

    # Try to get exact match:
    result = get_matching_version(version, request_url, headers)

    if result["request_success"]:
        print("Found release ", version, ". Downloading...")
        if result["tag_asset_id"]:
          download_asset(version, request_url + "releases/assets/" + result["tag_asset_id"], result["tag_asset_id"], headers)
          unpack_asset(version)
        else:
            print("Tag asset id not found, please retry...")
    else:
        list_tags_req = requests.get(url=request_url + "tags", headers=headers)
        model_tag_names = []
        if list_tags_req.status_code == 200:
            for tag in list_tags_req.json():
                if version in tag["name"]:
                    model_tag_names.append(tag["name"])
        
            if model_tag_names:
                print("Found the folowing tags with the similar name :")
                print(model_tag_names)
                while True:
                    model_choice = input("Please input the model version you would like to download: \n")
                    if model_choice in model_tag_names:
                        result = get_matching_version(model_choice, request_url, headers)
                        print("Found release ", model_choice, ". Downloading...")
                        download_asset(model_choice, request_url + "releases/assets/" + result["tag_asset_id"], result["tag_asset_id"], headers)
                        unpack_asset(model_choice)
                        break
            else:
                print("No tags found with the given name.")
        else:
            print(list_tags_req.status_code, " " , list_tags_req.text)
                

    
    """
    # Try to get exact match:
    result = getMatchingVersion(version, request_url, headers)

    if result['request_success']:
        # Load model into package
        return 'Tag found'
    if result['credentials_correct']:
        # Load closest package
        getClosestMatchingVersion(version, request_url, headers)
        return 'installing medcat model....'
    else:
        return result['response_message']
    
    return version
    """
if __name__ == '__main__':
  fire.Fire(download)
