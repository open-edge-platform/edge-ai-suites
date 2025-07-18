import os
import shutil
import numpy as np
import argparse

parser = argparse.ArgumentParser(description="")
parser.add_argument(
    "--dataset_folder",
    required=True,
    type=str,
    help="dataset folder.",
)
parser.add_argument(
    "--save_folder",
    required=True,
    type=str,
    help="save folder.",
)

args = parser.parse_args()


sub_folders = ["bgr", "radar"]


def select_raddet_data(source_folder, target_folder, sub_folders):
    os.makedirs(target_folder, exist_ok=True)
    for sub_folder in sub_folders:
        source_sub_folder = os.path.join(source_folder, sub_folder)
        target_sub_folder = os.path.join(target_folder, sub_folder)

        os.makedirs(target_sub_folder, exist_ok=True)
        for file_name in os.listdir(source_sub_folder):
            if file_name.endswith(".bin"):
                base_name = os.path.splitext(file_name)[0]
                try:
                    file_number = int(base_name)
                    if 559 <= file_number <= 724:
                        source_path = os.path.join(source_sub_folder, file_name)
                        target_path = os.path.join(target_sub_folder, file_name)
                        shutil.copy2(source_path, target_path)
                        print(f"Copied: {file_name} to {target_sub_folder}")
                except ValueError:
                    continue


if __name__ == "__main__":
    select_raddet_data(args.dataset_folder, args.save_folder, sub_folders)
