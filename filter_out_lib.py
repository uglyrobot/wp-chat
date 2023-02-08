# load the json file, and strip any objects from the bits list that have xxx in the the url field
# save the new list to a new json file

import json

with open('libraries/wpdevcode-docs-crawl.json') as f:
    data = json.load(f)
    
new_data = {
	"version": 1,
	"embedding_model": "openai.com:text-embedding-ada-002",
	"bits": []
}

for item in data['bits']:
    if '/reference/files/' not in item['info']['url']:
        new_data['bits'].append(item)
        
with open('libraries/wpdevcode-docs-crawl-NEW.json', 'w') as f:
    json.dump(new_data, f)
    