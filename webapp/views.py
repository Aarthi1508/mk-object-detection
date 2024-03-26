from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .forms import ImageUploadForm
from .models import UploadedImage
import boto3
from botocore.exceptions import NoCredentialsError
from django.shortcuts import render, redirect
from .forms import ImageUploadForm
from .models import UploadedImage
import os 
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import uuid
import json
from pymongo import MongoClient
import pymongo
from PIL import Image, ImageDraw
import io
from datetime import datetime

# Load environment variables from .env
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent

# Replace 'your_access_key', 'your_secret_key', 'your_bucket_name', and 'your_s3_region'
aws_access_key = os.getenv('AWS_ACCESS_KEY')
aws_secret_key = os.getenv('AWS_SECRET_KEY')
aws_bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
aws_s3_region = os.getenv('AWS_S3_REGION')

aws_s3_upload_folder = os.getenv('AWS_S3_UPLOADED_IMAGES_FOLDER')
aws_s3_detected_folder = os.getenv('AWS_S3_DETECTED_IMAGES_FOLDER')
# Create an S3 client
s3 = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key, region_name=aws_s3_region)

rekognition = boto3.client('rekognition', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key, region_name=aws_s3_region)

mongo_client = MongoClient(os.getenv('MONGODB_CLIENT_URL'))
db = mongo_client[os.getenv('MONGODB_DATABASE')]
collection = db[os.getenv('MONGODB_COLLECTION')]


def generate_16_digit_id():
    # Generate a UUID (Universally Unique Identifier)
    unique_id = uuid.uuid4()

    # Convert UUID to a hexadecimal string and take the first 16 characters
    hex_id = str(unique_id.hex)[:16]

    return hex_id

img_id = generate_16_digit_id()

def image_upload(request):
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('image_list')
    else:
        form = ImageUploadForm()
    return render(request, 'image_upload.html', {'form': form})


@csrf_exempt
def upload_to_s3(request):
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the form data to the database
            instance = form.save()

            # Upload the image to S3
            upload_result = upload_to_s3_synchronously(instance.image)

            if upload_result:
                # return JsonResponse({'status': 'success'})
                return redirect('uploaded_page')  # 'uploaded_page' is the name of the URL pattern for the uploaded page
            
            else:
                return JsonResponse({'status': 'error'})
        else:
            # Form is not valid, return JsonResponse with error message or specific details
            print("Invalid form data")
            return JsonResponse({'status': 'error', 'error_message': 'Invalid form data'})
    else:
        # Not a POST request, return JsonResponse indicating the error
        return JsonResponse({'status': 'error', 'error_message': 'Invalid request method'})


def upload_to_s3_synchronously(image_file):
    try:
        result_dict = {}
        result_dict['image_id'] = img_id
        
        # Define the directory path
        save_dir = "webapp/detection_results"

        # Check if the directory exists, if not, create it
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
                
        with open(save_dir+"/"+str(img_id)+".json", "w") as file:
            json.dump(result_dict, file)
            
        
        upload_folder_prefix = os.getenv('AWS_S3_UPLOADED_IMAGES_FOLDER')
        s3.upload_fileobj(image_file, aws_bucket_name, upload_folder_prefix+'/'+str(img_id)+'.jpeg')

        print("Upload Successful")
        
        
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False
    
def uploaded_page(request):
    # Retrieve the most recently uploaded image
    uploaded_image = UploadedImage.objects.last()

    # Pass the uploaded image data to the template
    print("uploaded image url is ", uploaded_image.image.url)
    return render(request, 'uploaded_page.html', {'uploaded_image': uploaded_image})


def get_latest_object_in_folder():
    # Initialize the S3 client

   

    # List all objects in the bucket with the given prefix (folder)
    response = s3.list_objects_v2(Bucket=aws_bucket_name, Prefix = aws_s3_upload_folder)
   

    # Extract the objects within the folder
    objects_in_folder = response['Contents']

    # Extract the most recent object (assuming they are sorted by last modified time)
    latest_object = max(objects_in_folder, key=lambda obj: obj['LastModified'])

    # Get the key (filename) of the latest object
    latest_key = latest_object['Key']

    return latest_key

def get_latest_object_url_in_folder():

    # List all objects in the bucket with the given prefix (folder)
    response = s3.list_objects_v2(Bucket=aws_bucket_name, Prefix=aws_s3_detected_folder)

    # Extract the objects within the folder
    objects_in_folder = response['Contents']

    # Extract the most recent object (assuming they are sorted by last modified time)
    latest_object = max(objects_in_folder, key=lambda obj: obj['LastModified'])

    # Get the key (filename) of the latest object
    latest_key = latest_object['Key']

    # Generate a URL for the latest object
    s3_url = s3.generate_presigned_url('get_object', Params={'Bucket': aws_bucket_name, 'Key': latest_key})

    return s3_url

def download_image_from_s3(bucket, key):
    file_byte_string = s3.get_object(Bucket=bucket, Key=key)['Body'].read()
    img = Image.open(io.BytesIO(file_byte_string))
    return img

def upload_image_to_s3(img, bucket, key):
    # In-memory file
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr = img_byte_arr.getvalue()

    s3.put_object(Bucket=bucket, Key=key, Body=img_byte_arr)

def add_bounding_boxes_to_image(image, detection_results):
    draw = ImageDraw.Draw(image)
    # Loop through each detection in the results
    for detection in detection_results['Labels']:
        for instance in detection['Instances']:
            box = instance['BoundingBox']
            left = image.width * box['Left']
            top = image.height * box['Top']
            width = image.width * box['Width']
            height = image.height * box['Height']

            draw.rectangle([left, top, left+width, top+height], outline='red', width=3)
    return image

# Modify the detect_objects_in_image function to return the full response for processing
def detect_objects_in_image(image_key):
    response = rekognition.detect_labels(Image={'S3Object': {'Bucket': aws_bucket_name, 'Name': image_key}})
    return response

def reformat_detection_results(detection_results):
    reformatted_results = []
    for label in detection_results['Labels']:
        class_name = label['Name']
        instances = [instance for instance in label.get('Instances', []) if 'BoundingBox' in instance]
        count = len(instances)
        details = []
        for i, instance in enumerate(instances):
            box = instance['BoundingBox']
            bbox_coordinates = [
                box['Left'] * 100,  # Assuming percentage conversion if needed
                box['Top'] * 100,
                (box['Left'] + box['Width']) * 100,
                (box['Top'] + box['Height']) * 100
            ]
            details.append({
                "occurrence": i + 1,
                "bbox_coordinates": bbox_coordinates,
                "confidence_level": instance['Confidence']
            })
        if details:  # Only add to results if there are instances with bounding boxes
            reformatted_results.append({
                "class": class_name,
                "count": count,
                "details": details
            })
    return reformatted_results


def save_detection_results_and_image_info_to_mongodb(image_key, detection_results, processed_image_key):
    reformatted_results = reformat_detection_results(detection_results)
    document = {
        "image_id": img_id,  # Placeholder, replace with actual ID if available
        "timestamp": datetime.now(),
        "detection_results": reformatted_results,
    }
    collection.insert_one(document)
    print("Detection results and processed image info saved to MongoDB with timestamp.")


def detect_object(request):
    # Assuming get_latest_object_url_in_folder and related functions are defined
    print("detect object is called")
    try:
        latest_image_key = get_latest_object_in_folder()
        if latest_image_key:
            print(f"Latest image key: {latest_image_key}")
            # Download the latest image
            image = download_image_from_s3(aws_bucket_name, latest_image_key)
            # Detect objects in the latest image
            detection_result = detect_objects_in_image(latest_image_key)
            # Add bounding boxes to the image
            image_with_boxes = add_bounding_boxes_to_image(image, detection_result)
            # Construct new key for the processed image
            processed_image_key = aws_s3_upload_folder + latest_image_key.split('/')[-1]
            # Upload the modified image back to S3 in a different folder
            upload_image_to_s3(image_with_boxes, aws_bucket_name, processed_image_key)
            # Save detection results and processed image info to MongoDB
            save_detection_results_and_image_info_to_mongodb(latest_image_key, detection_result, processed_image_key)

            return JsonResponse({'status': 'success', 'message': 'Object detection completed!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'No images found in the specified folder.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
def get_latest_record_from_mongodb(fields=None):
    mongodb_client = os.getenv('MONGODB_CLIENT_URL')
    mongodb_database = os.getenv('MONGODB_DATABASE')
    mongodb_collection = os.getenv('MONGODB_COLLECTION')

    client = pymongo.MongoClient(mongodb_client)
    db = client[mongodb_database]
    collection = db[mongodb_collection]

    # Specify the fields to retrieve
    fields = ["image_id", "timestamp", "detection_results"]

    # Include '_id' in the projection and set its value to 0 to exclude it
    projection = {field: 1 for field in fields}
    projection['_id'] = 0

    # Find the document with the highest timestamp
    latest_record = collection.find_one({}, projection=projection, sort=[("timestamp", pymongo.DESCENDING)])

    print("latest record", latest_record)

    return latest_record

def detected_image_page(request):
    image_url = get_latest_object_url_in_folder()
    latest_mongo_db_record = get_latest_record_from_mongodb()

    return render(request, 'detected_image_page.html', {
        'latest_image_url': image_url,
        'latest_mongo_db_record': latest_mongo_db_record
    })

def image_details_popup(request):
    latest_mongo_db_record = get_latest_record_from_mongodb()
    return render(request, 'popup_content.html', {'latest_mongo_db_record': latest_mongo_db_record})
