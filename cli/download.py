import fire
import requests

## Use python decorator to do the response checking

def getMatchingVersion(version, request_url, headers):

    request_url = request_url + '/tags/' + version
    response = requests.get(request_url)
    result = {'request_success': False, 'credentials_correct': True ,'response_message': ''}

    if response.status_code == 200:
        result['request_success'] = True
    if response.status_code == 404:
        result['response_message'] = response.json()['message']
    if response.status_code == 401:
        result['response_message'] = response.json()['message']
        result['credentials_correct'] = False

    return result

def getClosestMatchingVersion(version, request_url, headers):

    # Following git tag naming convention we would expect to have <model_name>-<version_number>
    request_url = request_url
    response = requests.get(request_url)
    result = {'request_success': False}
    model_name = version.split('-')[0] # name validation needed

    if response.status_code == 200:
        tag_names = [(idx, float(r['tag_name'].split('-')[1])) for idx, r in enumerate(response.json()) if (model_name in r['tag_name']) ]
        print(tag_names)
        max_tag = max(tag_names, key=lambda t: t[1])
        result['request_success'] = True    

    return 'close'

def download(version):

    # Headers
    headers = {'Authorization': 'token <insert_token_for_private_repo>'} # for private repo's we want to specify the access token to the github repo
    model_repo_url = 'kawsarnoor/MedCatModels/'
    request_url = 'https://api.github.com/repos/' + model_repo_url + 'releases'

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

if __name__ == '__main__':
  fire.Fire(download)
