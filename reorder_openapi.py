import json

def reorder_openapi_paths(file_path, output_path):
    # Load the JSON data
    with open(file_path, 'r') as f:
        data = json.load(f)

    if 'paths' in data:
        original_paths = data['paths']
        new_paths = {}

        # 1. Check if /token exists and add it first
        if '/token' in original_paths:
            new_paths['/token'] = original_paths['/token']

        # 2. Add all other paths in their original order
        for path, details in original_paths.items():
            if path != '/token':
                new_paths[path] = details

        # Replace the old paths object with the reordered one
        data['paths'] = new_paths

    # Modify securitySchemes
    if 'components' in data and 'securitySchemes' in data['components']:
        schemes = data['components']['securitySchemes']
        if 'GetToken' in schemes:
            # 1. change ApiKey.description to GetToken.description
            # GetToken is the same as ApiKey
            if 'ApiKey' in schemes and 'description' in schemes['GetToken']:
                schemes['ApiKey']['description'] = schemes['GetToken']['description']

            # 2. remove GetToken
            del schemes['GetToken']

            # 3. change GetToken to ApiKey in ALL endpoints
            # Doublechecking
            if 'paths' in data:
                for path, operations in data['paths'].items():
                    for method, details in operations.items():
                        if isinstance(details, dict):
                            if 'security' in details:
                                for scheme in details['security']:
                                    if 'GetToken' in scheme:
                                        print("!!! GetToken in {} {} !!!".format(method, path))
                                        scheme['ApiKey'] = scheme.pop('GetToken')

                            # 4. Add ApiToken to all endpoints so global config is not used
                            else:
                                details['security'] = [{"ApiToken": []}]

                            # 5. Change DenyList tag to Deny List
                            if 'tags' in details:
                                details['tags'] = ['Deny List' if tag == 'DenyList' else tag for tag in details['tags']]

    # Save the modified JSON
    with open(output_path + '.json', 'w') as f:
        json.dump(data, f, indent=2)

    with open(output_path + '_compressed.json', 'w') as f:
        json.dump(data, f)

    print(f"Successfully reordered paths. Output saved to: {output_path}")

# Usage
reorder_openapi_paths('openapi.json', 'openapi_transformed')
