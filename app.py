from flask import Flask, render_template, request, jsonify
from flask_cors import CORS  # Import CORS
from openai import OpenAI, BadRequestError
import requests
from pymongo import MongoClient
from datetime import datetime
import pdfplumber
import time
import io
import pdfplumber
import requests
from io import BytesIO
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
import json
import re
import ast
import requests
import uuid
import boto3
from difflib import SequenceMatcher
from openai import OpenAI
from pymongo import MongoClient
import mimetypes
import os
#pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
openai_key = os.getenv('OPENAI_API_KEY')
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

MONGODB_URI = "mongodb+srv://Vaibhav:vaibhavattherate25@userdata.joyki.mongodb.net/?retryWrites=true&w=majority&appName=UserData"
bucket_name = "firstbucket222003"  
region_name = "eu-north-1"  # Example: "us-east-1
def create_prompt( pdf_url,extracted_text=" "):
    # Structure the prompt for GPT-4
    prompt = """
    You are an expert in analyzing medical reports. Given the following medical report, your task is to extract the key information and test results in a structured format.

Please follow this output structure:

{
    "mob_no": "Extract the patient's mobile number, if present.",
    "name": "Extract the patient's name, if present.",
    "Age": "Extract the patient's age, if present.",
    "Gender": "Extract the patient's gender, if present.",
    "info": {
        "dd/mm/yyyy"("Extract the report date in the format dd/mm/yyyy, or write 'Not provided' if the date is not available."): 
         {
            "Test Name 1"(mentioned In the report): {
                "Parameter 1": "Extract the value of this parameter if present.",
                "Parameter 2": "Extract the value of this parameter if present.",
                ...
            },
            "Test Name 2"(mentioned In the report): {
                "Parameter 1": "Extract the value of this parameter if present.",
                ...
            }
        }
    }

Instructions:
1. Identify and extract any tests present in the report (e.g., Lipid Profile, CBC, Thyroid Function Test, etc.).
2. For each test, extract its specific parameters and values. If a test has no parameters or values, skip it.
3. Ensure the format is strictly followed, do not return in json format.
4. Extract the values with its units.
5. If any data (like mobile number or date) is missing from the report, explicitly write "Not provided."

"""




    # The 'extra' variable definition was incorrectly indented. It should be inside the function body.
    extra = f"""Here is the document text:
    {extracted_text}""" 
    if (extracted_text == " "):
        return prompt
    return prompt + extra # Corrected indentation
def stream_pdf_to_s3_with_credentials(pdf_url, bucket_name, s3_file_name, aws_access_key_id, aws_secret_access_key, region_name):
    """Streams a PDF from a URL and uploads it directly to S3 with explicit credentials."""
    
    try:
        # Set up S3 client with AWS credentials passed in function
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )

        # Stream the PDF content
        response = requests.get(pdf_url, stream=True)

        if response.status_code == 200:
            # Upload the streamed content to S3 without setting the ACL
            content_type, _ = mimetypes.guess_type(pdf_url)

            if content_type is None:
                # If the mimetype can't be guessed, default to binary/octet-stream
                content_type = 'binary/octet-stream'
            s3_client.upload_fileobj(
                response.raw, 
                bucket_name, 
                s3_file_name, 
                ExtraArgs={
                    'ContentType': content_type  # Set Content-Type to PDF
                }
            )
            print(f"PDF uploaded successfully to S3 bucket {bucket_name}")
            
            # Generate the S3 file URL
            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_file_name}"
            return s3_url
        else:
            print(f"Failed to download PDF from {pdf_url}")
            return None
    except Exception as e:
        print(f"Failed to upload PDF to S3: {e}")
        return None
def extract_text_from_image_pdf_tesseract(url):
    # Step 1: Stream the PDF from the URL
    response = requests.get(url)
    pdf_bytes = BytesIO(response.content)
    tesseract_langs = 'eng+hin'
    # Step 2: Convert PDF pages to images
    images = convert_from_bytes(pdf_bytes.read(), dpi=300)

    # Step 3: Extract text from each image using Tesseract OCR
    text = ""
    for i, image in enumerate(images):
        # Use Tesseract OCR to extract text in both English and Hindi
        page_text = pytesseract.image_to_string(image, lang=tesseract_langs)
        text += f"Page {i + 1}:\n{page_text}\n\n"

    return text
def check_link_type(url):
    # Get the file extension
    file_extension = url.split('.')[-1].lower()
    
    # Check for image file extensions
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

    if file_extension in image_extensions:
        return "Image"
    elif file_extension == 'pdf':
        return "PDF"
    else:
        return "Unknown file type"
def extract_text_from_pdf_url(url):
    response = requests.get(url)
    response.raise_for_status()  # Ensure we got a valid response

    # Create a BytesIO object from the response content
    pdf_stream = BytesIO(response.content)

    # Use pdfplumber to open the PDF file from the BytesIO object
    with pdfplumber.open(pdf_stream) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text
def extract_text(url):
    text=extract_text_from_pdf_url(url)
    check=len(text.split())
    if(check< 30):
      text = extract_text_from_image_pdf_tesseract(url)
    # Step 1: Stream the PDF from the URL
   # print(text)
    return text
def pdf_list(pdf_files):
# List to store extracted text from each PDF
  pdf_texts = []

  for pdf_path in pdf_files:
      text=extract_text(pdf_path)  # Extract text from each page
      tt=create_prompt(pdf_path,text)
      pdf_texts.append(tt)  
  return pdf_texts

def extract_info_image(image_url, prompt):
    attempts = 0
    max_attempts = 3

    while attempts < max_attempts:
        try:
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                },
                            },
                        ],
                    }
                ],
                temperature=0.1,
                top_p=1,          # Consider all possible tokens for precise output
                    #frequency_penalty=0,  # No penalty for repetition
                presence_penalty=0
            )

            return response.choices[0].message.content.strip()

        except BadRequestError as e:
            
      
                #print(f"Attempt {attempts + 1} failed: {error_message}")
                attempts += 1
                print(attempts)
                time.sleep(10)  # Wait for 2 seconds before retrying
              # If it's not an "Invalid image" error, re-raise the exception

    # If the maximum number of attempts is reached
    return "Error: Unable to process the image after 3 attempts."

# List of prompts
def create_jsonfile(pdf_texts):
  prompts =pdf_texts

# JSONL file to save the forma  tted data
  file_path = "requests.jsonl"

# Open the file for writing
  with open(file_path, "w") as file:
    # Iterate through each prompt and format it into the JSON structure
      for i, prompt in enumerate(prompts, start=1):
        # Create the JSON structure for each prompt
          json_data = {
              "custom_id": f"request-{i}",
              "method": "POST",
              "url": "/v1/chat/completions",
              "body": {
                  "model": "gpt-4o-mini",
                  "messages": [
                      {"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}
                  ],
                  "max_tokens": 1000
              }
          }
        
        # Write each JSON object as a line in the .jsonl file
          file.write(json.dumps(json_data) + "\n")

  print("Data saved to requests.jsonl in JSONL format.")

def final_Dictonary(final_response):
  text = final_response.text
  dict_strings = re.split(r'(?<=})\n(?={"id": "batch_req)', text)
  dict_list = [json.loads(entry) for entry in dict_strings]
  final_dict=[]
  for i in range(len(dict_list)):
    final_dict.append(json.loads(dict_list[i]['response']['body']["choices"][0]["message"]['content']))
  return final_dict


def stringmatch(string1, string2):
    # Create a SequenceMatcher object
    similarity_ratio = SequenceMatcher(None, string1, string2).ratio()
    
    # Check if similarity is at least 80%
    if similarity_ratio >= 0.8:
        return True
    else:
        return False
def find_similar_users(name_to_match):
    # Connect to MongoDB
    client = MongoClient(MONGODB_URI)  # Adjust if needed
    db = client["mydb"]
    user_collection = db["users"]

    # Find users where 'name' field exists
    users = user_collection.find({"full_name": {"$exists": True}})


    # List to store matching results
    matching_users = []

    # Check each user for name similarity
    for user in users:
        name = user.get("full_name")  # Retrieve the name from user document
        if stringmatch(name, name_to_match):
            return True
    return False
def add_report_url_to_single_date(data, report):
    # Assuming the date key is known (in this case "10/01/2023")
    report_url=report[0]
    type=report[1]
    for date in data['info']:
        data['info'][date]['report_url'] = [report_url]
        data['info'][date]['status'] =type
    return data
def send_message(contact_number, message):
    """Calls the API to send a message to the respective contact number."""
    url = "https://app.squareflow.in/api/sendtextmessage.php"
    params = {
        "LicenseNumber": "36650586182",
        "APIKey": "nlhPT6vAGsdUScxFOBJ4i0WgR",
        "Contact": f"{contact_number}",
        "Message": message
    }
    response = requests.get(url, params=params)
    
    # Return the API response (for debugging or logging purposes)
    return response.status_code, response.text
def send_force_message(contact_number,pdf_url):
    """Calls the API to send a media message with a button to the respective contact number."""
    url = "https://app.squareflow.in/api/sendmediamessage.php"
    message =f"""The *name* in this report *does not match* your name in the My MediBoard database.

Report:{pdf_url}

If you still wish *to upload this report* to your MediBoard, please *click the button below*."""
    button_text = "Force upload"

    params = {
        "LicenseNumber": "36650586182",
        "APIKey": "nlhPT6vAGsdUScxFOBJ4i0WgR",
        "Contact": contact_number,  
        "Message": message,         # The message text
        "Type": "button",           # Fixed type as 'button' for this API
        "HeaderType": "text",       # Assuming the header type is 'text'
        "Button": button_text       # The button text
    }
    
    response = requests.get(url, params=params)
    
    # Return the API response (for debugging or logging purposes)
    return response.status_code, response.text
def mongodbdata(d,mob_no,pdf_url,type):
  time.sleep(120)
  client = MongoClient(MONGODB_URI)
  db = client["mydb"]
  collection = db["patientinfo"]
  # original_string =d["mob_no"]
  # no_space_string = original_string.replace(" ", "")
  # mob_no = no_space_string
  name = d["name"]

  new_data = d['info']
  url=""
  for date in d['info']:
    url=d['info'][date]['report_url'] 
  
  if type=='normal':
        if find_similar_users(name):
                print("Similar user found. Updating data.")
                existing_user = collection.find_one({"mob_no": mob_no})

                date_key = list(new_data.keys())[0]
                date_data = new_data[date_key]

                
                if existing_user:
                    report_date = list(new_data.keys())[0]

# Extract all tests under that date
                    tests = new_data[report_date]

                    # Loop through and append each new test
                    if "report_url" in tests:
                        # Extract the report URLs
                        new_urls = tests.pop("report_url")  # Remove 'report_url' from tests and save the URLs separately

                        # Append the new URLs to the existing report_url array
                        collection.update_one(
                            {"mob_no": mob_no},  # Assuming each document has a unique identifier like a mobile number
                            {
                                "$push": {
                                    f"info.{report_date}.report_url": {"$each": new_urls}  # Append new URLs
                                }
                            },
                            upsert=True  # Create the document if it doesn't exist
                        )
                    for test_name, test_data in tests.items():
                        # Update or append the test results for the given date dynamically
                        collection.update_one(
                            {"mob_no": mob_no},  # Assuming each document has a unique _id for the patient
                            {
                                "$set": {
                                    f"info.{report_date}.{test_name}": test_data
                                }
                            },
                            upsert=True  # Create the document if it doesn't exist
                        )

                    # collection.update_one(
                    #     {"mob_no": mob_no},
                    #     {"$set": {f"info.{date_key}": date_data}}
                    # )
                    print("Date-wise data appended successfully for existing user.")
                else:

                    new_user_document = {
                        "mob_no": mob_no,
                        "name": name,
                        "Age": d['Age'],
                        "Gender": d['Gender'],
                        "info": new_data 
                    }
                    collection.insert_one(new_user_document)
                    print("New user created and data added successfully.")
                
                
        else:
            message='this report can not be excess'
            print(message)
            status_code, response_text = send_force_message(mob_no,url[0])
            print(f"API called: Status code {status_code}, Response: {response_text}")
            print("No similar user found. Creating new user.NOt able to append the data.")
  else:
      existing_user = collection.find_one({"mob_no": mob_no})

      date_key = list(new_data.keys())[0]
      date_data = new_data[date_key]
      if existing_user:
                    report_date = list(new_data.keys())[0]

# Extract all tests under that date
                    tests = new_data[report_date]
                    if "report_url" in tests:
    # Extract the report URLs
                        new_urls = tests.pop("report_url")  # Remove 'report_url' from tests and save the URLs separately

                        # Append the new URLs to the existing report_url array
                        collection.update_one(
                            {"mob_no": mob_no},  # Assuming each document has a unique identifier like a mobile number
                            {
                                "$push": {
                                    f"info.{report_date}.report_url": {"$each": new_urls}  # Append new URLs
                                }
                            },
                            upsert=True  # Create the document if it doesn't exist
                        )
                    # Loop through and append each new test
                    for test_name, test_data in tests.items():
                        # Update or append the test results for the given date dynamically
                        collection.update_one(
                            {"mob_no": mob_no},  # Assuming each document has a unique _id for the patient
                            {
                                "$set": {
                                    f"info.{report_date}.{test_name}": test_data
                                }
                            },
                            upsert=True  # Create the document if it doesn't exist
                        )
                    # collection.update_one(
                    #     {"mob_no": mob_no},
                    #     {"$set": {f"info.{date_key}": date_data}}
                    # )
                    print("Date-wise data appended successfully for force user.")
      else:

                    new_user_document = {
                        "mob_no": mob_no,
                        "name": name,
                        "Age": d['Age'],
                        "Gender": d['Gender'],
                        "info": new_data 
                    }
                    collection.insert_one(new_user_document)
                    print("New force user created and data added successfully.")
                
                
                

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/infoextract', methods=['POST'])
def infoextract():
    print("Request received")
    data = request.get_json()
    pdf_urls = data['pdf_urls']
    mob_num = data['mob_num']
    type=data['type']
    pdf_amazon=[]
    image_amazon=[]
    print(pdf_urls)
    print(mob_num)
    print(type)
    if type[0]=='normal':
        for j, pdf in enumerate(pdf_urls):
            if check_link_type(pdf) == "PDF":
                #random_number = random.randint(10000000, 99999999)  # Generates a random 8-digit number
                s3_file_name = f"{uuid.uuid4()}.pdf" 
                #pdf_amazon.append(stream_pdf_to_s3_with_credentials(pdf, bucket_name, s3_file_name, aws_access_key_id, aws_secret_access_key, region_name))
                link= stream_pdf_to_s3_with_credentials(pdf, bucket_name, s3_file_name, aws_access_key_id, aws_secret_access_key, region_name)
                print(link)
    
                client = OpenAI(api_key=openai_key)
                pdf_texts=pdf_list([pdf])
                for i,  pdf in enumerate(pdf_texts):
                    completion = client.chat.completions.create( 
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": pdf}
                    ],
                    temperature=0.1,
                    top_p=1,          # Consider all possible tokens for precise output
                    #frequency_penalty=0,  # No penalty for repetition
                    presence_penalty=0,
                    )
                    extracted_text=completion.choices[0].message.content.strip()
                    print(extracted_text)
                    data=json.loads(extracted_text)
                    d=add_report_url_to_single_date(data, [link,type[0]])
                    
                    print(d)
                    mongodbdata(d,mob_num[j],link,type[0])
            else:
                #random_number = random.randint(10000000, 99999999)  # Generates a random 8-digit number
                s3_file_name = f"{uuid.uuid4()}.jpg"
                link = stream_pdf_to_s3_with_credentials(pdf, bucket_name, s3_file_name, aws_access_key_id, aws_secret_access_key, region_name)
                prompt=create_prompt(pdf)
                extracted_text=extract_info_image(pdf, prompt)
                print(extracted_text)
                data=json.loads(extracted_text)
                d=add_report_url_to_single_date(data, [link,type[0]])
                    
                print(d)
                mongodbdata(d,mob_num[j],link,type[0])



    else:
        for j ,pdf_url in enumerate(pdf_urls):
            if check_link_type(pdf_url) == "PDF":
    
                client = OpenAI(api_key=openai_key)
                pdf_texts=pdf_list([pdf_url])
                for i,  pdf in enumerate(pdf_texts):
                    completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": pdf}
                    ],
                    temperature=0.1,
                    top_p=1,          # Consider all possible tokens for precise output
                    #frequency_penalty=0,  # No penalty for repetition
                    presence_penalty=0,
                    )
                    extracted_text=completion.choices[0].message.content.strip()
                    print(extracted_text)
                    data=json.loads(extracted_text)
                    d=add_report_url_to_single_date(data, [pdf_url,type[0]])
                    
                    print(d)
                    mongodbdata(d,mob_num[j],pdf_url,type[0])
            else:
                
                prompt=create_prompt(pdf_url)
                extracted_text=extract_info_image(pdf_url, prompt)
                print(extracted_text)
                data=json.loads(extracted_text)
                d=add_report_url_to_single_date(data, [pdf_url,type[0]])
                    
                print(d)
                mongodbdata(d,mob_num[j],pdf_url,type[0])
            
        # print(pdf_urls)
        # client = OpenAI(api_key=openai_key)
        # pdf_texts=pdf_list(pdf_urls)
        # for i,  pdf in enumerate(pdf_texts):
        #     completion = client.chat.completions.create(
        #     model="gpt-4o-mini",
        #     messages=[
        #         {"role": "user", "content": pdf}
        #     ]
        #     )
        #     extracted_text=completion.choices[0].message.content.strip()
        #     print(extracted_text)
        #     data=json.loads(extracted_text)
        #     d=add_report_url_to_single_date(data, [pdf_urls[i],type[0]])
            
        #     print(d)
        #     mongodbdata(d,mob_num[i],pdf_urls[i],type[0]) 
    # create_jsonfile(pdf_texts)

    # client = OpenAI(api_key=openai_key)
    # batch_input_file = client.files.create(
    # file=open("requests.jsonl", "rb"),
    # purpose="batch"
    # )
    # batch_input_file_id = batch_input_file.id
    
    # client = OpenAI(api_key=openai_key)
    # info=client.batches.create(
    #     input_file_id=batch_input_file_id,
    #     endpoint="/v1/chat/completions",
    #     completion_window="24h",
    #     metadata={
    #         "description": "nightly eval job"
    #     }
    #     )

    # file_id=''
    # while True:
    #     # Retrieve the batch
    #     h = client.batches.retrieve(info.id)
        
    #     # Check if output_file_id is None
    #     if h.output_file_id is not None:
    #         file_id=h.output_file_id
    #         print("Output file ID found:", h.output_file_id)
    #         break  # Exit the loop if the output_file_id is available
    #     else:
    #         print("Output file ID not available, checking again in 3 minutes...")
     
    
    #     time.sleep(180)

    # file_response = client.files.content(file_id) 
    # final=final_Dictonary(file_response)

    # for i, d in enumerate(final): #Iterate using enumerate to get both index and value
    #     mongodbdata(d, mob_num[i])
    return "done"
if __name__ == '__main__':
    app.run(debug=True)