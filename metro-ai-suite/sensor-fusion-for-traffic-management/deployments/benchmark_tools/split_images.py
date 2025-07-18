from PIL import Image
import os
import argparse

def split_image(image_path, left_folder, right_folder):
    img = Image.open(image_path)

    if img.size != (1280, 480):
        print(f"Image {image_path} is not of size 1280x480. Skipping.")
        return
    
    # crop image
    left_img = img.crop((0, 0, 640, 480))
    right_img = img.crop((640, 0, 1280, 480))
    
    # prepare img path
    base_name = os.path.basename(image_path)
    left_img_path = os.path.join(left_folder, base_name)
    right_img_path = os.path.join(right_folder, base_name)
    
    left_img.save(left_img_path)
    right_img.save(right_img_path)
    
    print(f"Processed {image_path}:")
    print(f"  Left part saved to {left_img_path}")
    print(f"  Right part saved to {right_img_path}")

def process_folder(folder_path, left_folder, right_folder):
    os.makedirs(left_folder, exist_ok=True)
    os.makedirs(right_folder, exist_ok=True)
    
    for filename in os.listdir(folder_path):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            image_path = os.path.join(folder_path, filename)
            split_image(image_path, left_folder, right_folder)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split stereo images into left and right parts.")
    parser.add_argument("--folder_path", required=True, type=str, help="Path to the folder with stereo images.")
    
    args = parser.parse_args()
    folder_path = args.folder_path
    
    # concat folder path
    stereo_image_folder_path = os.path.join(folder_path, "stereo_image")

    left_folder = os.path.join(folder_path, "left")
    right_folder = os.path.join(folder_path, "right")
    process_folder(stereo_image_folder_path, left_folder, right_folder)