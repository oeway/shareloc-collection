import requests

import yaml
import json
import os
from tqdm import tqdm
from shareloc_utils.batch_download import download_url, resolve_url, convert_potree, convert_smlm
import boto3
import shutil

S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_BUCKET = "public"
S3_DATA_DIR = "pointclouds"
S3_KEY = os.environ.get("S3_KEY")
S3_SECRET = os.environ.get("S3_SECRET")

S3_URL = f"{S3_ENDPOINT}/{S3_BUCKET}/{S3_DATA_DIR}"

def generate_potree(rdf, dataset_dir, file_patterns, extension=".potree.zip", delimiter=","):
    attachments = rdf["attachments"]
    rdf_url = rdf["rdf_source"]
    for sample in attachments["samples"]:
        os.makedirs(os.path.join(dataset_dir, rdf["doi"], sample["name"]), exist_ok=True)
        for file in sample.get("files", []):
            file_path = os.path.join(dataset_dir, rdf["doi"], sample["name"], file["name"])
            if file_path.endswith(".smlm"):
                # TODO: check if the file is already exists in the s3
                zip_name = os.path.join(rdf["doi"], sample["name"], file["name"].replace(".smlm", ".potree.zip"))
                target_url = S3_URL + "/" + zip_name
                print(f"Checking {target_url}...")
                r = requests.head(target_url)
                if r.status_code == 200:
                    print("File already exists in the s3: " + zip_name)
                    continue 
                s3_client = boto3.client('s3', endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET)
                object_name = S3_DATA_DIR + "/" + zip_name
                
                # download the file
                download_url(
                    resolve_url(rdf_url, sample["name"] + "/" + file["name"]),
                    file_path,
                )
                print("Converting " + file_path + "...")
                convert_potree(file_path, True)
                
                print("Uploading " + file_path + " to s3...")
                s3_client.upload_file(file_path.replace(".smlm", ".potree.zip"), S3_BUCKET, object_name)

                # Remove the folder
                shutil.rmtree(os.path.join(dataset_dir, rdf["doi"])) 
                

def generate_collection():
    rdfs = []
    with open("collection.yaml", "rb") as f:
        collection = yaml.safe_load(f.read())
    items = collection["collection"]
    for item in tqdm(items):
        rdf_source = item["rdf_source"]
        r = requests.get(rdf_source)
        if not r.status_code == 200:
            print(f"Could not get item {item['id']}: {r.status_code}: {r.reason}")
            break
        rdf = yaml.safe_load(
            r.text
            .replace("!<tag:yaml.org,2002:js/undefined>", ""),
        )
        rdf.update(item)
        rdfs.append(rdf)
        generate_potree(rdf, "datasets", ["*.smlm"])
        break
    
    collection["collection"] = rdfs
    os.makedirs("dist", exist_ok=True)
    json.dump(collection, open("dist/collection.json", "w"), indent=2)
      
generate_collection()  