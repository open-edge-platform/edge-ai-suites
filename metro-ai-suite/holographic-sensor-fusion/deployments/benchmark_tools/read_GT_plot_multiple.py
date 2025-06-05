import numpy as np
import pickle
import cv2
import os
import csv
import argparse

# Read the ground truth pickle files and plot the radar detections on the corresponding images
def read_GT_plot(gt_dir, img_dir, output_dir, csv_file_path):
    
    ## Write the header
    with open(csv_file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Frame Num","radar_rois", "Class Lables"])

    # List all pickle files in the ground truth directory and sort them
    gt_files = [f for f in os.listdir(gt_dir) if f.endswith('.pickle')]
    gt_files.sort()  # Sort the files alphabetically

    # Iterate over each file
    for gt_file in gt_files:
        gt_path = os.path.join(gt_dir, gt_file)
        
        # Load the radar data from the pickle file
        with open(gt_path, 'rb') as f:
            radar_data = pickle.load(f)
        
        # Construct the corresponding image file path
        img_file = gt_file.replace('.pickle', '.jpg')
        img_path = os.path.join(img_dir, img_file)
        
        frame_num = os.path.splitext(img_file)[0]
        
        # Read the corresponding image
        original_img = cv2.imread(img_path)
        
        # create birdview
        bird_view = np.full((height, width, 3), 0, dtype=np.uint8)

        # draw grids
        grid_size = 32
        for x in range(0, bird_view.shape[1], grid_size):
            cv2.line(bird_view, (x, 0), (x, bird_view.shape[0]), (100, 100, 100), 1)
        for y in range(0, bird_view.shape[0], grid_size):
            cv2.line(bird_view, (0, y), (bird_view.shape[1], y), (100, 100, 100), 1)

        # draw origin point, red color
        origin = (origin_row, origin_col) #(256, 256)
        
        cv2.circle(bird_view, origin, 5, (0, 0, 255), -1) 
        frame_detections = []
        class_labels =[]

        ## gt save bounding boxes: up left, down right, center

        for i in range(len(radar_data['cart_boxes'])):
            cart_box = radar_data['cart_boxes'][i]
            
            #y_c, x_c, h, w = box
            y_c = cart_box[0]
            x_c = cart_box[1]
            h = cart_box[2]
            w = cart_box[3]
            y1, y2, x1, x2 = int(y_c-h/2), int(y_c+h/2), int(x_c-w/2), int(x_c+w/2)
            top_left = (x1, y1)
            bottom_right = (x2, y2)
            x1_radar = (x1-origin_row) *resolution
            x2_radar = (x2-origin_row)*resolution
            y1_radar = (origin_col-y1)*resolution
            y2_radar = (origin_col-y2)*resolution
            x_c_radar = (x_c-origin_row)*resolution
            y_c_radar = (origin_col-y_c)*resolution
            print("boxes left: ",(x1,y1), "boxes right: ", (x2,y2))
            print("radar boxes left: ",(x1_radar,y1_radar), "radar boxes right: ", (x2_radar,y2_radar))
            cv2.rectangle(bird_view, top_left, bottom_right, (255, 0, 0), 2)  # blue rectangle
            # Overlay radar coordinates on the image
            radar_coords_text1 = f"({x1_radar:.2f}, {y1_radar:.2f})"
            radar_coords_text2 = f"({x2_radar:.2f}, {y2_radar:.2f})"

            radar_coords_center = f"({x_c_radar:.2f}, {y_c_radar:.2f})"
            # coordinates of radar center
            cv2.putText(bird_view, radar_coords_center, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            
            # Overlay class label on the image
            class_label = radar_data['classes'][i]
            class_text = f"{class_label}"
            cv2.putText(bird_view, class_text, (x1, y1 - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Add axis labels
            # The x-axis is up, the y-axis is to the right
            cv2.putText(bird_view, 'X', (280, 256), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(bird_view, 'Y', (256, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            # Draw coordinate axes with arrows
            # origin = (256, 256)
            cv2.circle(bird_view, origin, 5, (0, 0, 255), -1)  # Red dot for origin
            cv2.arrowedLine(bird_view, origin, (280, 256), (0, 255, 0), 2)  # X-axis
            cv2.arrowedLine(bird_view, origin, (256, 230), (0, 255, 0), 2)  # Y-axis
            radar_roi =[x1_radar, y1_radar, x2_radar,y2_radar, float(x_c_radar), float(y_c_radar)]
            frame_detections.append(radar_roi)
            class_labels.append(class_label)
        
        # Write radar gt data to CSV(up left, down right)            
        with open(csv_file_path, 'a', newline='') as file:
            writer = csv.writer(file)
            # writer.writerow([frame_num, str(frame_detections), str(class_labels)])
            writer.writerow([frame_num, frame_detections, class_labels])
    
        # Concatenate the original image and the bird's eye view
        total_width = original_img.shape[1] + bird_view.shape[1]
        max_height = max(original_img.shape[0], bird_view.shape[0])
        resize_height = 256
        resize_width = int(ori_img_width*resize_height/ori_img_height)

        print('resize_height: ', resize_height)
        print('resize_width: ', resize_width)

        original_img = cv2.resize(original_img, (resize_width, resize_height))

        new_img =cv2.hconcat([original_img, bird_view])
        
        # Save the concatenated image
        output_img_path = os.path.join(output_dir, img_file)
        cv2.imwrite(output_img_path, new_img)

        # imshow
        cv2.imshow('GT Results Image', new_img)
        cv2.waitKey(5)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read raddet gt and plot")
    parser.add_argument("--folder_path", required=True, type=str, help="Path to the gt foler.")
    
    args = parser.parse_args()
    folder_path = args.folder_path

    ### params
    ## birdview shape
    resolution = 100/512
    width = 512
    height = 256

    ## original image shape
    ori_img_width = 640
    ori_img_height = 480

    ## origin coordinates
    x_min = 0.0
    x_min_pixel = x_min/resolution
    origin_row = int(height + x_min_pixel)
    origin_col = int(width/2)
    print("origin_row: ", origin_row)
    print("origin_col: ", origin_col)

    # Define the directories containing the ground truth and images
    gt_dir = os.path.join(folder_path, "gt")
    img_dir = os.path.join(folder_path, "left")
    output_dir = os.path.join(folder_path, "gt_images") # new directory for saving gt images

    # Create the output directory if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # CSV file setup
    csv_file_path = os.path.join(folder_path, 'radar_gt.csv')

    read_GT_plot(gt_dir, img_dir, output_dir, csv_file_path)
    


