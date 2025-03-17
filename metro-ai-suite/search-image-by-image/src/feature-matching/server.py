"""
FastAPI server for search
"""

import base64
import io
import json
import logging
import os
from typing import Annotated

import httpx  # For sending HTTP requests
import numpy as np
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from marshmallow import ValidationError
from PIL import Image
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema

from encoder import Base64ImageProcessor
from milvus_utils import (
    CollectionExists,
    create_collection,
    get_milvus_client,
    get_search_results,
)
from schemas import ObjectDetectionSchema

load_dotenv()

# Milvus Settings
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
MILVUS_ENDPOINT = os.getenv("MILVUS_ENDPOINT")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")

# Model Settings
MODEL_DIM = os.getenv("MODEL_DIM")

# MQTT Settings
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

# Detection Settings
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.4))

# Create Milvus Client
milvus_client = get_milvus_client(uri=MILVUS_ENDPOINT, token=MILVUS_TOKEN)

# Create MQTT Client
mqtt_client = mqtt.Client()

# Create Milvus Collection
try:
    create_collection(
        milvus_client=milvus_client,
        collection_name=COLLECTION_NAME,
        dim=int(MODEL_DIM),
        drop_old=False,
    )
except CollectionExists:
    print(f"Collection {COLLECTION_NAME} already exists. Will not create a new one.")


# Function to decode base64 tensor blobs
def process_tensor_blobs(tensor_blobs):
    """
    Processes a list of Base64-encoded tensor blobs and returns a list of embeddings in list format.

    Args:
        tensor_blobs (list): List of Base64-encoded strings representing tensor blobs.

    Returns:
        list: A list of embeddings, each represented as a list of floats.
    """
    if not isinstance(tensor_blobs, list):
        print("Error: 'tensor_blobs' is not a list")
        return []

    embeddings = []
    for item in tensor_blobs:
        try:
            # Decode Base64 string
            decoded = base64.b64decode(item)

            # Convert binary to numpy array (assumes float32 embeddings; update dtype if needed)
            embedding = np.frombuffer(
                decoded, dtype=np.float32
            )  # Replace `float32` with actual data type
            embeddings.append(embedding)
        except Exception as e:
            print(f"Error processing item: {e}")

    if len(embeddings) > 0:
        # Convert embeddings to a list of lists (Milvus format)
        return [embedding.tolist() for embedding in embeddings]

    return []


# Define the on_connect callback
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)


# Define the on_message callback
def on_message(client, userdata, message):
    payload = json.loads(message.payload.decode())
    try:
        to_insert = []
        timestamp = payload["metadata"]["time"]
        metadata = payload.get("metadata", {})
        objects = metadata.get("objects", [])
        data = ObjectDetectionSchema().load(metadata)

        for detected_object in objects:
            detection = detected_object.get("detection", {})
            label_name = detection.get("label", "").lower().replace(" ", "_")
            confidence = detection.get("confidence", 0)
            data = payload["tensor_blobs"]
            frame = payload["blob"]

            # Decode the frame
            image_bytes = base64.b64decode(frame)
            image = Image.open(io.BytesIO(image_bytes))

            if confidence > CONFIDENCE_THRESHOLD:
                # Process tensor blobs and get embeddings_list
                embeddings_list = process_tensor_blobs(data)
                frame_path = f"static/{payload['metadata']['time']}_{label_name}.jpg"
                image.save(frame_path)
                to_insert.append(
                    {
                        "vector": embeddings_list[0],
                        "filename": frame_path,
                        "label": label_name,
                        "timestamp": timestamp,
                    }
                )
                if len(data) > 0:
                    milvus_client.insert(
                        collection_name=COLLECTION_NAME,
                        data=to_insert,
                    )
    except ValidationError as err:
        print(f"Error deserializing payload: {err.messages}")


# Assign the callbacks
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to the MQTT broker
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Start the MQTT client loop in a separate thread
mqtt_client.loop_start()

# Create static folder if it doesn't exist
os.makedirs("static", exist_ok=True)

app = FastAPI()

# Initialize the Base64ImageProcessor with the desired size
processor = Base64ImageProcessor(size=(224, 224))


@app.post("/search/")
async def search(
    images: Annotated[list[UploadFile], File(description="Upload an image")]
):
    # Step 0: Check if a search_image pipeline is already running
    pipeline_id = None
    try:
        async with httpx.AsyncClient() as client:
            # Fetch pipelines status
            response = await client.get("http://sibi-evam:8080/pipelines/status")
            response.raise_for_status()
            pipelines = response.json()
            
            # Check if a search_image pipeline is already running
            for pipeline in pipelines:

                # Ignore the pipelines that are not running
                if pipeline["state"] != "RUNNING":
                    continue

                _pipeline_response = await client.get(f"http://sibi-evam:8080/pipelines/{pipeline['id']}")
                _pipeline_response.raise_for_status()
                _pipeline_response_json = _pipeline_response.json()

                # If the pipeline is search_image, save the pipeline_id and break
                if _pipeline_response_json["request"]["pipeline"]["version"] == "search_image":
                    pipeline_id = pipeline['id']
                    break

    except httpx.RequestError as e:
        # Ignore the error and continue
        logging.error(f"An error occurred while making the status request: {str(e)}")

    # Step 1: When the search_image pipeline is not running, start the pipeline with sync mode as true
    if not pipeline_id:
        pipeline_endpoint = "http://sibi-evam:8080/pipelines/user_defined_pipelines/search_image"
        body = {"sync": True}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(pipeline_endpoint, json=body)
                response.raise_for_status()  # Raise HTTP error for non-2xx responses

                pipeline_id = (
                    response.text.strip()
                )  # Use `.strip()` to remove any extra whitespace

        except httpx.RequestError as e:
            return {
                "error": f"An error occurred while making the pipeline request: {str(e)}"
            }

    # Step 2: Process the uploaded images
    # Process the uploaded images
    results = []
    for image in images:
        # Read the uploaded image
        _bytes = await image.read()

        # Convert bytes to a PIL image
        img = Image.open(io.BytesIO(_bytes))

        # Process the image using the Base64ImageProcessor
        base64_image = processor.process_image_to_base64(img)

        # Append the Base64 string to the results
        results.append({"base64_image": base64_image})
    # Extract the Base64 string
    base64_image = results[0]["base64_image"]  # Access the value of "base64_image"

    # Step 3: Send data to the second pipeline
    # Ensure pipeline_id has no extra quotes
    pipeline_id = pipeline_id.strip('"').strip()  # Remove surrounding quotes, if any
    second_pipeline_endpoint = (
        f"http://sibi-evam:8080/pipelines/user_defined_pipelines/search_image/{pipeline_id}"
    )

    second_pipeline_body = {
        "source": {"data": base64_image, "type": "base64_image"},
        "include_feature_vector": True,
        "publish_frame": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            second_response = await client.post(
                second_pipeline_endpoint, json=second_pipeline_body
            )
            second_response.raise_for_status()  # Raise HTTP error for non-2xx responses

            second_pipeline_result = second_response.json()  # Parse the response
            # Parse the JSON string
            second_pipeline_result_parsed = json.loads(second_pipeline_result)
            tensor_blobs = second_pipeline_result_parsed["tensor_blobs"]

    except httpx.RequestError as e:
        return {
            "error": f"An error occurred while making the second pipeline request: {str(e)}"
        }
    embeddings_list = process_tensor_blobs(tensor_blobs)
    try:
        results = get_search_results(
            milvus_client=milvus_client,
            collection_name=COLLECTION_NAME,
            query_vector=embeddings_list[0],
            output_fields=["filename", "label", "timestamp"],
        )
        return results
    except Exception as e:
        logging.error(f"Search failed: {str(e)}")
        return {"error": "Search failed"}


@app.get("/static/{filename}")
async def get_image(filename: str):
    file_path = f"static/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        return JSONResponse(status_code=404, content={"message": "File not found"})


@app.post("/clear/")
async def clear():
    print("Clearing collection")
    create_collection(
        milvus_client=milvus_client,
        collection_name=COLLECTION_NAME,
        dim=int(MODEL_DIM),
        drop_old=True,
    )

    for file in os.listdir("static"):
        os.remove(os.path.join("static", file))

    return JSONResponse(status_code=200, content={"message": "Success"})
