from jsonschema import validate, exceptions
import yaml
import sys
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime
from pathlib import Path

if __name__ == '__main__':
    config = None
    config_schema = None
    verify_ssl = False
    output_name = 'tokens.yaml'

    print("---------------------------------------")
    print("------cloud.iO provisioning script-----")
    print("---------------------------------------")

    # Read and validate config file
    with open("config.yaml", "r") as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print("Cannot read config file")
            print(exc)
            sys.exit(1)

    with open("config_schema.yaml", "r") as stream:
        try:
            config_schema = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print("Cannot read config schema file")
            print(exc)
            sys.exit(1)

    try:
        validate(config, config_schema)
    except exceptions.ValidationError as exc:
        print("The config file format is not valid")
        print(exc)
        sys.exit(1)
    except exceptions.SchemaError as exc:
        print("The config_schema file format is not valid")
        print(exc)
        sys.exit(1)

    # Create the endpoint
    friendly_name = ""
    while friendly_name == "":
        friendly_name = str(input("Enter a friendlyName: "))

    create_url = config['host'] + "/api/v1/endpoints"
    create_params = {'friendlyName': friendly_name}
    auth = HTTPBasicAuth(username=config['username'], password=config['password'])

    r = requests.post(create_url, params=create_params, auth=auth, verify=verify_ssl)

    if r.status_code != 200 and r.status_code != 204:
        print("Error while creating endpoint")
        r.raise_for_status()
        sys.exit(1)

    endpoint_data = r.json()
    print("Endpoint created with uuid " + endpoint_data['uuid'])

    # Modify the endpoint information
    endpoint_data['metaData'] = config['metadata']
    endpoint_data['banned'] = config['banned']
    endpoint_data['groupMemberships'] = config['endpointGroups']

    modify_url = create_url + "/" + endpoint_data['uuid']
    modify_headers = {'Content-Type': 'application/json'}

    r = requests.put(modify_url, data=json.dumps(endpoint_data), auth=auth, headers=modify_headers, verify=verify_ssl)

    if r.status_code != 200 and r.status_code != 204:
        print("Error while modifying endpoints data")
        r.raise_for_status()
        sys.exit(1)

    print("Endpoint data modified")

    # Generate the token
    token_url = modify_url + "/provisionToken"
    token_headers = modify_headers

    # TODO: fix this tricky line
    config['customProperties']['ch.hevs.cloudio.endpoint.ssl.clientCert'] = config['customProperties']['ch.hevs.cloudio.endpoint.ssl.clientCert'] + endpoint_data['uuid'] + '.p12'

    r = requests.post(token_url, data=json.dumps({'customProperties': config['customProperties']}), auth=auth, headers=token_headers, verify=verify_ssl)

    if r.status_code != 200 and r.status_code != 204:
        print("Error while generating token")
        r.raise_for_status()
        sys.exit(1)

    token = str(r.text)
    print("Token created: " + token)

    token_item = {'uuid': endpoint_data['uuid'], 'friendlyName': friendly_name,
                  'generationTime': str(datetime.now()), 'token': token}

    current_out = None

    # create the output file if not exist
    output_path = Path(output_name)
    output_path.touch(exist_ok=True)

    with open(output_name, "r") as stream:
        try:
            current_out = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print("Cannot read tokens output file")
            print(exc)
            sys.exit(1)

    if current_out is None:
        current_out = {'tokens': []}

    current_out['tokens'].append(token_item)

    with open(output_name, 'w') as yamlfile:
        try:
            yaml.safe_dump(current_out, yamlfile)
        except yaml.YAMLError as exc:
            print("Cannot write tokens output file")
            print(exc)
            sys.exit(1)

    print('Token added to ' + output_name)
