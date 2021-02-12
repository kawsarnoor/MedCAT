import fire
from medcat.cli.system_utils import get_auth_environemnt_vars
from medcat.cli.download import get_all_available_model_tags

def listmodels():

    env_git_auth_token = get_auth_environemnt_vars()["git_auth_token"]
    env_git_repo_url = get_auth_environemnt_vars()["git_repo_url"]

    headers = {"Accept" : "application/vnd.github.v3+json", "Authorization": "token " + env_git_auth_token}

    user_repo_and_project = '/'.join(env_git_repo_url.split('.git')[0].split('/')[-2:])

    request_url = 'https://api.github.com/repos/' + user_repo_and_project + "/"
    print("Checking " + env_git_repo_url + " for releases...")
    print("The following model tags are available from download : " + str(get_all_available_model_tags(request_url, headers)))

if __name__ == '__main__':
    fire.Fire(listmodels)