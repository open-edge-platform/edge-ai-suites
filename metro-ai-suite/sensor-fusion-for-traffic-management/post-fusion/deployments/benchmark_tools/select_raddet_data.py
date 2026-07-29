import os
import shutil
import argparse

def select_raddet_data(source_folder, target_folder, sub_folders):
    os.makedirs(target_folder, exist_ok=True)
    for sub_folder in sub_folders:
        source_sub_folder = os.path.join(source_folder, sub_folder)
        target_sub_folder = os.path.join(target_folder, sub_folder)
        
        os.makedirs(target_sub_folder, exist_ok=True)
        if os.path.exists(source_sub_folder):
            for item in os.listdir(source_sub_folder):  
                item_path = os.path.join(source_sub_folder, item)
                if os.path.isdir(item_path):
                    for file_name in os.listdir(item_path):
                        if file_name.endswith('.jpg') or file_name.endswith('.pickle') or file_name.endswith('.npy'):
                            base_name = os.path.splitext(file_name)[0]
                            try:
                                file_number = int(base_name)
                                if 559 <= file_number <= 724:
                                    source_path = os.path.join(item_path, file_name)
                                    target_path = os.path.join(target_sub_folder, file_name)
                                    shutil.copy2(source_path, target_path)
                                    print(f'Copied: {file_name} to {target_sub_folder}')
                            except ValueError:
                                continue
        else:
            print(f"Source sub-folder {source_sub_folder} does not exist.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select and copy specific files based on their numeric names.")
    parser.add_argument("--dataset_folder", required=True, type=str, help="Path to the dataset folder.")
    parser.add_argument("--save_folder", required=True, type=str, help="Path to the save folder.")
    args = parser.parse_args()

    sub_folders = ['gt', 'RAD', 'stereo_image']
    select_raddet_data(args.dataset_folder, args.save_folder, sub_folders)
    