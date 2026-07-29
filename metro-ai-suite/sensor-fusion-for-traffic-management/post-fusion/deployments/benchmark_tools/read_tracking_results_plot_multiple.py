import numpy as np
import cv2
import os
import csv
import argparse


def toImageCoordinate(radar_point):
    radar_x, radar_y =radar_point
    image_x = int(origin_row - radar_x/resolution)
    image_y = int(origin_col - radar_y/resolution)
    return image_x, image_y

def read_tracking_plot(img_dir, output_dir, csv_file_path):

    # Open the CSV file for reading
    with open(csv_file_path, mode='r') as file:
        # Create a CSV reader object
        csv_reader = csv.reader(file)
        
        # Skip the header if there is one
        next(csv_reader)
        
        # Iterate over each row in the CSV file
        for row in csv_reader:
            # Process each row here
            # For example, print the row
            print(row)
            frameId = row[0]
            radarRois = row[1]
            radarSizes = row[2]
            radarStates = row[3]
            radarID = row[4]
            # frameId =int(frameId)+103
            frameId =int(frameId) + 559
            frameId = f"{frameId:06}"
            img_file = frameId + '.jpg'
            img_path = os.path.join(img_dir, img_file)
            # Read the corresponding image
            original_img = cv2.imread(img_path)
            
            # draw birdview
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
            
            parts = radarRois.split()
            radarSize = radarSizes.split()
            
            if len(parts) % 4 == 0:
                num_groups = len(parts) // 4
                frame_detections = []  # save radar detection results
                for i in range(num_groups):
                    # radar_x, radar_y actually is the center coordinates of the radar box
                    radar_x, radar_y, vx, vy = map(float, parts[i*4:(i+1)*4])
                    w, h = map(float, radarSize[i*2:(i+1)*2])

                    # align with garnet park demo
                    radar_y = -radar_y # for plot
                    xSize =4.2
                    ySize =1.7
                    # radar_x1 = radar_x
                    # radar_y1 = radar_y
                    
                    # radar_x2 = radar_x + xSize
                    # radar_y2 = radar_y + ySize
                    ### radar_x, radar_y is the center point
                    ## x points to up, y points to right
                    radar_x1 = radar_x + xSize/2
                    radar_y1 = radar_y - ySize/2

                    radar_x2 = radar_x - xSize/2
                    radar_y2 = radar_y + ySize/2
                    detection ={
                        'group':i+1,
                        'radar_x1': radar_x1,
                        'radar_y1': radar_y1,
                        'radar_x2': radar_x2,
                        'radar_y2': radar_y2
                    }

                    frame_detections.append(detection) 
                    
                    # print(f"Group {i+1}: radar_x: {radar_x}, radar_y: {radar_y}, vx: {vx}, vy: {vy}")
                    print("boxes left: ",(radar_x1,radar_y1), "boxes right: ", (radar_x2,radar_y2))

                    # top_left = (radar_x1, radar_y1)
                    # bottom_right = (radar_x2, radar_y2)
                    
                    top_left = (radar_y1, radar_x1)
                    bottom_right = (radar_y2, radar_x2)
                    center = (radar_y, radar_x)

                    if radar_x!=0.0 and radar_y!=0.0:
                    
                        image_left_x, image_left_y = toImageCoordinate(top_left)
                        image_right_x, image_right_y =toImageCoordinate(bottom_right)
                        cv2.rectangle(bird_view, (image_left_x, image_left_y), (image_right_x, image_right_y), (255, 0, 0), 2)  # 蓝色矩形
                        radar_y1 = -radar_y1
                        radar_y2 = -radar_y2

                        radar_y = -radar_y # for display the real data
                        
                        # Overlay radar coordinates on the image
                        # coordinates of top left
                        radar_coords_text1 = f"({radar_y1:.2f}, {radar_x1:.2f})"   ##align with gt to see difference
                        radar_coords_text2 = f"({radar_y2:.2f}, {radar_x2:.2f})"
                        # cv2.putText(bird_view, radar_coords_text1, (image_left_x, image_left_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                        
                        # coordinates of radar center
                        radar_coords_center = f"({radar_y:.2f}, {radar_x:.2f})"
                        cv2.putText(bird_view, radar_coords_center, (image_left_x, image_left_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            ## Add axis labels
            # The x-axis is up, the y-axis is to the right
            cv2.putText(bird_view, 'Y', (280, 256), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(bird_view, 'X', (256, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            # Draw coordinate axes with arrows

            cv2.circle(bird_view, origin, 5, (0, 0, 255), -1)  # Red dot for origin
            cv2.arrowedLine(bird_view, origin, (280, 256), (0, 255, 0), 2)  # X-axis
            cv2.arrowedLine(bird_view, origin, (256, 230), (0, 255, 0), 2)  # Y-axis
            
            # Concatenate the original image and the bird's eye view
            total_width = original_img.shape[1] + bird_view.shape[1]
            max_height = max(original_img.shape[0], bird_view.shape[0])
            resize_height =height
            resize_width = int(ori_img_width*resize_height/ori_img_height)

            print('resize_height: ',resize_height)
            print('resize_width: ',resize_width)

            original_img = cv2.resize(original_img, (resize_width, resize_height))

            new_img =cv2.hconcat([original_img, bird_view])
            
            # Save the concatenated image
            output_img_path = os.path.join(output_dir, img_file)
            cv2.imwrite(output_img_path, new_img)

            # imshow
            cv2.imshow('Tracking Results Image', new_img)
            cv2.waitKey(5)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read radar tracking results and plot")
    parser.add_argument("--folder_path", required=True, type=str, help="Path to the foler including imgs and tracking csv results file.")
    
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
    img_dir = os.path.join(folder_path, "left")
    output_dir = os.path.join(folder_path, "tracking_images") # new directory for saving gt images

    # Create the output directory if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # CSV file setup
    csv_file_path = os.path.join(folder_path, 'radarResults.csv')

    read_tracking_plot(img_dir, output_dir, csv_file_path)
