import os
import json
import datetime

def generate_fake_meta(file_dir):
    if not os.path.isdir(file_dir):
        raise ValueError(f"The provided path '{file_dir}' is not a valid directory.")
    
    timestamp = datetime.date(2025, 1, 1)
    timestamp = int(timestamp.strftime("%Y%m%d"))  # 20250101

    cnt = 1
    month = 1

    meta_dir = os.path.join(file_dir, "meta")
    os.makedirs(meta_dir, exist_ok=True)

    for root, _, files in os.walk(file_dir): 
        if root.split("/")[-1] == "meta":
            continue
        for file_name in files:                
            file_path = os.path.join(root, file_name)
            # Skip directories, only process files
            if os.path.isfile(file_path):
                # Generate the JSON file name
                base_name, _ = os.path.splitext(file_name)
                json_file_path = os.path.join(meta_dir, f"{base_name}.json")
                fake_label = f"camera_{cnt}"
                timestamp = datetime.date(2025, month, cnt % 30 + 1)  # Increment day, reset to 1 if exceeds 30
                fake_timestamp = int(timestamp.strftime("%Y%m%d"))
                fake_meta = {
                    "camera": fake_label,  
                    "timestamp": fake_timestamp  
                }

                cnt += 1
                if cnt > month*30:
                    month += 1

                # Write the JSON content to the file
                with open(json_file_path, "w") as json_file:
                    json.dump(fake_meta, json_file, indent=4)


def remove_fake_meta_files(file_dir):
    meta_dir = os.path.join(file_dir, "meta")
    if os.path.exists(meta_dir):
        for file_name in os.listdir(meta_dir):
            file_path = os.path.join(meta_dir, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Removed metadata file: {file_path}")
        os.rmdir(meta_dir)
        print(f"Removed directory: {meta_dir}")


def copy_dataset(file_dir, dst_dir):
    if not os.path.isdir(file_dir):
        raise ValueError(f"The provided path '{file_dir}' is not a valid directory.")
    
    os.makedirs(dst_dir, exist_ok=True)

    for file_name in sorted(os.listdir(file_dir)):
        file_path = os.path.join(file_dir, file_name)
        if os.path.isfile(file_path):
            dst_file_path = os.path.join(dst_dir, file_name)
            with open(file_path, 'rb') as src_file:
                with open(dst_file_path, 'wb') as dst_file:
                    dst_file.write(src_file.read())
    print(f"Copied dataset to {dst_dir}")