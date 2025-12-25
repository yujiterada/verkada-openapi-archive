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

    # Save the modified JSON
    with open(output_path + '.json', 'w') as f:
        json.dump(data, f, indent=2)

    with open(output_path + '_compressed.json', 'w') as f:
        json.dump(data, f)

    print(f"Successfully reordered paths. Output saved to: {output_path}")

# Usage
reorder_openapi_paths('openapi.json', 'openapi_transformed')
