#!/usr/local/bin/python

import json
import httpx
import asyncio
import os
import boto3
from botocore.exceptions import ClientError


def list_buckets():
    s3_resource = boto3.resource("s3")
    for bucket in s3_resource.buckets.all():
        print(f"\t{bucket.name}")

def list_files_in_a_bucket(bucket_name):
    s3_resource = boto3.resource("s3")
    bucket = s3_resource.Bucket(bucket_name)
    for obj in bucket.objects.all():
        print(f"\t{obj.key}")


def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name, ExtraArgs={'ACL':'public-read','ContentType': 'application/json'})
    except ClientError as e:
        print('ERROR', e)
        return False
    return True


def download_file_from_bucket(object_name, bucket, result_file_name):

    # Download the file
    s3_client = boto3.client('s3')
    try:
        with open(result_file_name, 'wb') as f:
            response = s3_client.download_fileobj(bucket, object_name, f)
    except ClientError as e:
        print('ERROR', e)
        return False
    return True





async def import_xml():
    url = 'http://localhost:8000/api/import-xml'
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data='')
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            print(f"error sending request: {e}")

async def get_static_conference():
    url = "http://localhost:8000/api/conference/static"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
        response.raise_for_status()
        
        res = response.json()
        with open('sfscon2024.json','wt') as f:
            f.write(json.dumps(res))

        send_to_s3('sfscon2024.json')
        
                
def send_to_s3(fname):
    # list_buckets()
    list_files_in_a_bucket('sfscon-backend-failover')

    upload_file(fname, 'sfscon-backend-failover')
    
    list_files_in_a_bucket('sfscon-backend-failover')
    download_file_from_bucket(fname, 'sfscon-backend-failover', 'downloaded.sfs2024.json')
        
        
async def main():

    res = await import_xml()
    if res and 'changes' in res and res['changes']:
        await get_static_conference()
            
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
